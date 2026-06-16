# CustomPurchaseOrder(PurchaseOrder):
# • validate (call super().validate() first): Block PO creation if Supplier is blacklisted (is_blacklisted = 1). 
# Throw: "Cannot create Purchase Order for blacklisted supplier {supplier_name}. Reason: {blacklist_reason}". 
# Block PO if Supplier’s vendor_rating < vendor_category.minimum_rating_threshold. 
# Throw: "Supplier {supplier_name} rating ({rating}) is below the minimum threshold ({threshold}) for {category}.". 
# Add a custom log entry: frappe.logger().info("PO {name} validated for supplier {supplier}").



import frappe
from erpnext.buying.doctype.purchase_order.purchase_order import PurchaseOrder

class CustomPurchaseOrder(PurchaseOrder):
    def validate(self):
        super().validate()
        supplier_doc = frappe.get_doc("Supplier", self.supplier)

        # Check blacklist
        if supplier_doc.custom_is_blacklisted:
            reason = supplier_doc.custom_blacklist_reason or "No reason provided"
            frappe.throw(
                f"Cannot create Purchase Order for blacklisted supplier "
                f"{self.supplier}. Reason: {reason}",
                frappe.ValidationError
            )

        # Check rating threshold — only when supplier has actual ratings
        vendor_category = supplier_doc.custom_vendor_category
        rating_count    = supplier_doc.custom_total_rating_count or 0

        if vendor_category and rating_count > 0:  # ✅ skip check for new suppliers
            category_doc          = frappe.get_doc("Vendor Category", vendor_category)
            minimum_threshold     = category_doc.minimum_rating_threshold or 0
            vendor_rating         = supplier_doc.custom_vendor_rating or 0

            if minimum_threshold and vendor_rating < minimum_threshold:
                frappe.throw(
                    f"Supplier {self.supplier} rating ({vendor_rating}) is below "
                    f"the minimum threshold ({minimum_threshold}) for {vendor_category}.",
                    frappe.ValidationError
                )

        frappe.logger().info(f"PO {self.name} validated for supplier {self.supplier}.")

    
    # • on_submit (call super().on_submit() first): Auto-create a Vendor Rating Log entry with 
    # rating_type = Pricing, score calculated as: if grand_total is within 10% of the avg PO value for 
    # this supplier → score 4, if cheaper → score 5, if more expensive → score 3. This demonstrates auto-rating on submission.
    


    def on_submit(self):
        super().on_submit()

        settings = frappe.get_single("Vendor Portal Settings")
        if not settings.auto_rating_enabled:
            return

        # Use raw SQL for AVG 
        result = frappe.db.sql("""
            SELECT AVG(grand_total) AS avg_po_value
            FROM `tabPurchase Order`
            WHERE supplier = %s
            AND docstatus = 1
            AND name != %s
        """, (self.supplier, self.name), as_dict=True)

        avg_po_value = result[0].avg_po_value if result and result[0].avg_po_value else None

        if avg_po_value:
            if abs(self.grand_total - avg_po_value) <= 0.1 * avg_po_value:
                score = 4
            elif self.grand_total < avg_po_value:
                score = 5
            else:
                score = 3
        else:
            score = 4  # No prior POs — neutral default

        frappe.get_doc({
            "doctype":        "Vendor Rating Log",
            "supplier":       self.supplier,
            "rating_type":    "Pricing",
            "score":          score,
            "purchase_order": self.name,
        }).insert(ignore_permissions=True, ignore_links=True)

    # • on_cancel (call super().on_cancel() first): Delete any Vendor Rating Log entries linked to this PO.
    def on_cancel(self):
        super().on_cancel()  # Call the original on_cancel method first

        # Delete any Vendor Rating Log entries linked to this PO
        frappe.db.delete("Vendor Rating Log", {"purchase_order": self.name})