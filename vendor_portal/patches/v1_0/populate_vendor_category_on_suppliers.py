# For all existing Suppliers that have a supplier_group but no vendor_category: Map common supplier_groups to vendor_categories (e.g., Raw Material → Raw Materials, Services → IT Services). Log unmapped suppliers.


import frappe
 
 
def execute():
    """
    Map existing Suppliers to Vendor Categories based on their supplier_group.
    Logs unmapped suppliers for manual review.
    """
    # Mapping of supplier_group → vendor_category 
    group_to_category = {
        "Raw Material":    "Raw Materials",
        "Services":        "IT Services",
        "Packaging":       "Packaging",
        "Logistics":       "Logistics",
        "Office":          "Office Supplies",
        "All Supplier Groups": None,  # Skip
    }
 
    suppliers = frappe.get_all(
        "Supplier",
        filters={"custom_vendor_category": ["in", ["", None]]},
        fields=["name", "supplier_name", "supplier_group"]
    )
 
    mapped   = 0
    unmapped = []
 
    for supplier in suppliers:
        category = group_to_category.get(supplier.supplier_group)
        if category and frappe.db.exists("Vendor Category", category):
            frappe.db.set_value("Supplier", supplier.name, "custom_vendor_category", category)
            mapped += 1
        else:
            unmapped.append(f"{supplier.name} ({supplier.supplier_group})")
 
    frappe.db.commit()
 
    if unmapped:
        frappe.log_error(
            "The following suppliers could not be mapped to a Vendor Category:\n"
            + "\n".join(unmapped),
            "populate_vendor_category_on_suppliers — Unmapped Suppliers"
        )
 
    print(f"populate_vendor_category_on_suppliers: {mapped} mapped, {len(unmapped)} unmapped.")