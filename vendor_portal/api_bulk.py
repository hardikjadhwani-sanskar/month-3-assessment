# • Bulk Vendor Import: API that accepts a CSV of vendor details and creates Vendor Onboarding records in bulk using frappe.enqueue.

import frappe
from frappe import _
from frappe.utils import today, add_days

@frappe.whitelist()
def bulk_import_vendors(csv_content):
    """
    Accepts CSV content as a string, parses it, and creates Vendor Onboarding records in bulk.
    Expected CSV columns: supplier_name, company_name, email, phone, vendor_category,
    address_line_1, city , state.
    """
    import csv
    from io import StringIO

    reader = csv.DictReader(StringIO(csv_content))
    required_fields = {"supplier_name", "company_name", "email", "phone", "vendor_category", "address_line_1", "city", "state"}
    created_count = 0
    errors = []

    for idx, row in enumerate(reader, start=1):
        if not required_fields.issubset(row.keys()):
            errors.append(f"Row {idx}: Missing required fields.")
            continue

        try:
            onboarding = frappe.get_doc({
                "doctype": "Vendor Onboarding",
                "supplier_name": row["supplier_name"],
                "company_name": row["company_name"],
                "email": row["email"],
                "phone": row["phone"],
                "vendor_category": row["vendor_category"],
                "address_line_1": row["address_line_1"],
                "city": row["city"],
                "state": row["state"],
                "onboarding_status": "Draft",
            })
            onboarding.insert(ignore_permissions=True)
            created_count += 1
        except Exception as e:
            errors.append(f"Row {idx}: {str(e)}")

    return {
        "created_count": created_count,
        "errors": errors
    }
    


