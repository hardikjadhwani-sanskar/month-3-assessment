
import frappe
import re


def get_context(context):
    context.no_cache = 1
    context.title = "Vendor Registration"


@frappe.whitelist(allow_guest=True)
def submit_vendor_registration(**kwargs):
    # \"\"\"
    # Public API — no login required.
    # Creates a Vendor Onboarding record in Draft state.
    # \"\"\"
    required = ["supplier_name", "company_name", "email", "phone",
                "vendor_category", "address_line_1", "city", "state"]

    for field in required:
        if not kwargs.get(field):
            frappe.throw(frappe._(f"{field.replace('_',' ').title()} is required."))

    # Basic GST validation if provided
    gst = kwargs.get("gst_number", "")
    if gst:
        pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
        if not re.match(pattern, gst):
            frappe.throw(frappe._("Invalid GST number format."))

    doc = frappe.get_doc({
        "doctype":            "Vendor Onboarding",
        "supplier_name":      kwargs.get("supplier_name"),
        "company_name":       kwargs.get("company_name"),
        "email":              kwargs.get("email"),
        "phone":              kwargs.get("phone"),
        "gst_number":         kwargs.get("gst_number"),
        "pan_number":         kwargs.get("pan_number"),
        "vendor_category":    kwargs.get("vendor_category"),
        "bank_name":          kwargs.get("bank_name"),
        "bank_account_number": kwargs.get("bank_account_number"),
        "ifsc_code":          kwargs.get("ifsc_code"),
        "address_line_1":     kwargs.get("address_line_1"),
        "city":               kwargs.get("city"),
        "state":              kwargs.get("state"),
        "pincode":            kwargs.get("pincode"),
        "contact_person":     kwargs.get("contact_person"),
        "onboarding_status":  "Draft",
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"name": doc.name, "status": "Draft"}
