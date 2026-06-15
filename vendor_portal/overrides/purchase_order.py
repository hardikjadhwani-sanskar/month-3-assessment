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
        super().validate()  # Call the original validate method first

        supplier_name = self.supplier
        supplier_doc = frappe.get_doc("Supplier", supplier_name)

        # Check if supplier is blacklisted
        if supplier_doc.custom_is_blacklisted:
            reason = supplier_doc.custom_blacklist_reason or "No reason provided"
            frappe.throw(f"Cannot create Purchase Order for blacklisted supplier {supplier_name}. Reason: {reason}",
                         frappe.ValidationError)

        # Check vendor rating against category threshold
        vendor_category = supplier_doc.custom_vendor_category
        if vendor_category:
            category_doc = frappe.get_doc("Vendor Category", vendor_category)
            minimum_rating_threshold = category_doc.minimum_rating_threshold
            if supplier_doc.custom_vendor_rating < minimum_rating_threshold:
                frappe.throw(f"Supplier {supplier_name} rating ({supplier_doc.custom_vendor_rating}) is below the minimum threshold ({minimum_rating_threshold}) for {vendor_category}.",
                             frappe.ValidationError)

        # Log validation info
        frappe.logger().info(f"PO {self.name} validated for supplier {supplier_name}.")

    
    # • on_submit (call super().on_submit() first): Auto-create a Vendor Rating Log entry with 
    # rating_type = Pricing, score calculated as: if grand_total is within 10% of the avg PO value for 
    # this supplier → score 4, if cheaper → score 5, if more expensive → score 3. This demonstrates auto-rating on submission.
    


    def on_submit(self):
        super().on_submit()  # Call the original on_submit method first

        # Calculate rating score based on grand_total and average PO value for this supplier
        supplier_name = self.supplier
        result = frappe.get_all(
                "Purchase Order",
                filters={
                    "supplier": supplier_name,
                    "docstatus": 1
                },
                fields=[
                    {"AVG": "grand_total", "as": "avg_po_value"}
                ]
        )

        avg_po_value = result[0].avg_po_value if result else 0
        
        if avg_po_value:
            if abs(self.grand_total - avg_po_value) <= 0.1 * avg_po_value: # if within 10%
                score = 4
            elif self.grand_total < avg_po_value: # if cheaper 
                score = 5
            else:
                score = 3

            # Create Vendor Rating Log entry
            rating_log = frappe.get_doc({
                "doctype": "Vendor Rating Log",
                "supplier": supplier_name,
                "rating_type": "Pricing",
                "score": score,
                "purchase_order": self.name
            })
            rating_log.insert() # Insert the log entry into the database

    # • on_cancel (call super().on_cancel() first): Delete any Vendor Rating Log entries linked to this PO.
    def on_cancel(self):
        super().on_cancel()  # Call the original on_cancel method first

        # Delete any Vendor Rating Log entries linked to this PO
        frappe.db.delete("Vendor Rating Log", {"purchase_order": self.name})