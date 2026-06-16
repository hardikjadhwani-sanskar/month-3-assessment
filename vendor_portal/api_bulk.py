import csv
from io import StringIO

import frappe
from frappe import _


@frappe.whitelist()
def bulk_import_vendors(csv_content):
    """
    Queue a background job to import vendors from CSV.

    Expected CSV columns:
    supplier_name, company_name, email, phone,
    vendor_category, address_line_1, city, state
    """

    if not csv_content:
        frappe.throw(_("CSV content is required."))

    frappe.enqueue(
        "vendor_portal.api_bulk.process_vendor_import",
        csv_content=csv_content,
        queue="long",
        timeout=600,
    )

    return {
        "success": True,
        "message": _("Vendor import has been queued.")
    }

@frappe.whitelist()
def process_vendor_import(csv_content):
    """
    Background job that processes vendor CSV data
    and creates Vendor Onboarding records.
    """

    reader = csv.DictReader(StringIO(csv_content))

    required_fields = {
        "supplier_name",
        "company_name",
        "email",
        "phone",
        "vendor_category",
        "address_line_1",
        "city",
        "state",
    }

    created_count = 0
    errors = []

    for idx, row in enumerate(reader, start=2):  # start=2 because row 1 is header

        try:
            # Validate required columns exist
            missing_columns = required_fields - set(row.keys())
            if missing_columns:
                raise ValueError(
                    f"Missing CSV column(s): {', '.join(sorted(missing_columns))}"
                )

            # Validate required values
            for field in required_fields:
                if not row.get(field):
                    raise ValueError(f"{field} is required")

            # Optional duplicate check
            existing = frappe.db.exists(
                "Vendor Onboarding",
                {
                    "supplier_name": row["supplier_name"],
                    "company_name": row["company_name"],
                },
            )

            if existing:
                raise ValueError(
                    f"Vendor '{row['supplier_name']}' already exists"
                )

            onboarding = frappe.get_doc({
                "doctype": "Vendor Onboarding",
                "supplier_name": row["supplier_name"].strip(),
                "company_name": row["company_name"].strip(),
                "email": row["email"].strip(),
                "phone": row["phone"].strip(),
                "vendor_category": row["vendor_category"].strip(),
                "address_line_1": row["address_line_1"].strip(),
                "city": row["city"].strip(),
                "state": row["state"].strip(),
                "onboarding_status": "Draft",
            })

            onboarding.insert(ignore_permissions=True)

            created_count += 1

        except Exception as e:
            errors.append(
                f"Row {idx}: {str(e)}"
            )

    frappe.db.commit()

    frappe.logger().info(
        {
            "created_count": created_count,
            "errors": errors,
        }
    )

    return {
        "created_count": created_count,
        "errors": errors,
    }