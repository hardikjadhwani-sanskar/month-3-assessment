# Recalculate vendor_rating and total_rating_count for all Suppliers based on actual Vendor Rating Log entries using the weighted formula.

import frappe
from frappe.utils import flt
 
 
def execute():
    """
    Recalculate vendor_rating and total_rating_count for all Suppliers
    based on actual Vendor Rating Log entries using the weighted formula.
    """
    settings = frappe.get_single("Vendor Portal Settings")
    weights = {
        "Delivery":      flt(settings.rating_weight_delivery),
        "Quality":       flt(settings.rating_weight_quality),
        "Pricing":       flt(settings.rating_weight_pricing),
        "Communication": flt(settings.rating_weight_communication),
    }
 
    suppliers = frappe.get_all(
        "Vendor Rating Log",
        fields=["supplier"],
        distinct=True
    )
 
    for row in suppliers:
        supplier = row.supplier
        try:
            breakdown = frappe.db.sql("""
                SELECT rating_type, AVG(score) AS avg_score
                FROM `tabVendor Rating Log`
                WHERE supplier = %s
                GROUP BY rating_type
            """, supplier, as_dict=True)
 
            total_weight = 0
            weighted_sum = 0
            for b in breakdown:
                w = weights.get(b.rating_type, 0)
                weighted_sum += b.avg_score * w
                total_weight += w
 
            avg         = round(weighted_sum / total_weight, 2) if total_weight else 0
            total_count = frappe.db.count("Vendor Rating Log", {"supplier": supplier})
 
            frappe.db.set_value("Supplier", supplier, {
                "custom_vendor_rating":       avg,
                "custom_total_rating_count":  total_count,
            })
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"recalculate_vendor_ratings failed for {supplier}"
            )
 
    frappe.db.commit()
    print(f"recalculate_vendor_ratings: Processed {len(suppliers)} suppliers.")
