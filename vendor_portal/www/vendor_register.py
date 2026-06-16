import frappe
import re


def get_context(context):
    context.no_cache = 1
    context.title = "Vendor Registration"


@frappe.whitelist(allow_guest=True)
def submit_vendor_registration(**kwargs):
    required = ["supplier_name", "company_name", "email", "phone",
                "vendor_category", "address_line_1", "city", "state"]
    for field in required:
        if not kwargs.get(field):
            frappe.throw(frappe._(f"{field.replace('_', ' ').title()} is required."))

    # Basic GST validation if provided
    gst = kwargs.get("gst_number")
    if gst:
        pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
        if not re.match(pattern, gst):
            frappe.throw(frappe._("Invalid GST number format."))

    doc = frappe.get_doc({
        "doctype":             "Vendor Onboarding",
        "supplier_name":       kwargs.get("supplier_name"),
        "company_name":        kwargs.get("company_name"),
        "email":               kwargs.get("email"),
        "phone":               kwargs.get("phone"),
        "gst_number":          kwargs.get("gst_number"),
        "pan_number":          kwargs.get("pan_number"),
        "vendor_category":     kwargs.get("vendor_category"),
        "bank_name":           kwargs.get("bank_name"),
        "bank_account_number": kwargs.get("bank_account_number"),
        "ifsc_code":           kwargs.get("ifsc_code"),
        "address_line_1":      kwargs.get("address_line_1"),
        "city":                kwargs.get("city"),
        "state":               kwargs.get("state"),
        "pincode":             kwargs.get("pincode"),
        "contact_person":      kwargs.get("contact_person"),
        "onboarding_status":   "Draft",
    })
    


    # ── Documents section ───────────────────────────────────────────────
    # Maps each expected file input's `name` attribute from the HTML form
    # to the document_type label stored in the child table.
    document_field_map = {
        "gst_certificate": "GST Certificate",
        "pan_card":        "PAN Card",
    }

    _attach_uploaded_documents(doc, document_field_map)
    doc.insert(ignore_permissions=True)

    frappe.db.commit()
    return {"name": doc.name, "status": "Draft"}


def _attach_uploaded_documents(doc, document_field_map):
    """
    Reads uploaded files from frappe.request.files (populated by the
    multipart/form-data POST from the registration form), saves each as
    a File record attached to the Vendor Onboarding doc, and appends a
    row to the doc's `documents` child table.

    document_field_map: dict of {html_input_name: document_type_label}
    """
    uploaded_files = frappe.request.files if frappe.request else {}

    for field_name, document_type in document_field_map.items():
        file_obj = uploaded_files.get(field_name)
        if not file_obj or not file_obj.filename:
            # Field wasn't submitted — required-ness should be enforced
            # via the HTML `required` attribute and/or validated below.
            continue

        file_doc = frappe.get_doc({
            "doctype":         "File",
            "file_name":       file_obj.filename,
            "attached_to_doctype": "Vendor Onboarding",
            "content":         file_obj.stream.read(),
            "is_private":      1,
        })
        file_doc.insert(ignore_permissions=True)

        doc.append("documents", {
            "document_type": document_type,
            "document_file": file_doc.file_url,
        })

