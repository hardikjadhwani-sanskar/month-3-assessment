
import frappe


def get_context(context):
    context.no_cache = 1
    context.title = "Check Application Status"


@frappe.whitelist(allow_guest=True)
def get_status(query):
    # \"\"\"Look up onboarding by name or email.\"\"\"
    if not query:
        return None

    # Try by name first
    if frappe.db.exists("Vendor Onboarding", query):
        return frappe.db.get_value(
            "Vendor Onboarding", query,
            ["name", "supplier_name", "vendor_category", "onboarding_status",
             "rejection_reason", "linked_supplier", "creation"],
            as_dict=True
        )

    # Try by email
    result = frappe.db.get_value(
        "Vendor Onboarding",
        {"email": query},
        ["name", "supplier_name", "vendor_category", "onboarding_status",
         "rejection_reason", "linked_supplier", "creation"],
        as_dict=True
    )
    return result