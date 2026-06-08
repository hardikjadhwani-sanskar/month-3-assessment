# vendor_portal/api.py
"""
Whitelisted API endpoints for Vendor Portal.
All functions use parameterized SQL — never string concatenation.
All wrapped in try-except with frappe.log_error for production safety.
"""

import frappe
from frappe.utils import today, flt


@frappe.whitelist()
def get_vendor_dashboard(supplier):
    """
    Returns comprehensive vendor stats for a supplier.
    Used by Supplier form dashboard section.
    """
    try:
        # Total POs and value
        po_data = frappe.db.sql("""
            SELECT
                COUNT(name)        AS total_pos,
                SUM(grand_total)   AS total_po_value
            FROM `tabPurchase Order`
            WHERE supplier = %s AND docstatus = 1
        """, supplier, as_dict=True)[0]

        # Receipts
        receipt_data = frappe.db.sql("""
            SELECT
                COUNT(name) AS total_receipts,
                SUM(CASE WHEN status != 'Completed' THEN 1 ELSE 0 END) AS pending_receipts
            FROM `tabPurchase Receipt`
            WHERE supplier = %s AND docstatus = 1
        """, supplier, as_dict=True)[0]

        # Invoices
        invoice_data = frappe.db.sql("""
            SELECT
                SUM(grand_total)      AS total_invoiced,
                SUM(outstanding_amount) AS outstanding_amount
            FROM `tabPurchase Invoice`
            WHERE supplier = %s AND docstatus = 1
        """, supplier, as_dict=True)[0]

        # Rating breakdown by type
        rating_breakdown = frappe.db.sql("""
            SELECT
                rating_type,
                AVG(score) AS avg_score,
                COUNT(*)   AS count
            FROM `tabVendor Rating Log`
            WHERE supplier = %s
            GROUP BY rating_type
        """, supplier, as_dict=True)

        # Overall avg rating
        avg_data = frappe.db.sql("""
            SELECT AVG(score) AS avg_rating, COUNT(*) AS total_ratings
            FROM `tabVendor Rating Log`
            WHERE supplier = %s
        """, supplier, as_dict=True)[0]

        # Recent 10 ratings
        recent_ratings = frappe.get_list(
            "Vendor Rating Log",
            filters={"supplier": supplier},
            fields=["creation", "rating_type", "score", "remarks", "rated_by"],
            order_by="creation desc",
            limit=10
        )

        return {
            "total_pos":          po_data.total_pos or 0,
            "total_po_value":     flt(po_data.total_po_value, 2),
            "total_receipts":     receipt_data.total_receipts or 0,
            "pending_receipts":   receipt_data.pending_receipts or 0,
            "total_invoiced":     flt(invoice_data.total_invoiced, 2),
            "outstanding_amount": flt(invoice_data.outstanding_amount, 2),
            "avg_rating":         flt(avg_data.avg_rating, 2),
            "total_ratings":      avg_data.total_ratings or 0,
            "rating_breakdown":   rating_breakdown,
            "recent_ratings":     recent_ratings,
        }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "get_vendor_dashboard Error")
        frappe.throw(frappe._("Error fetching vendor dashboard data."))


@frappe.whitelist()
def submit_vendor_rating(supplier, rating_type, score, remarks,
                         purchase_order=None, purchase_receipt=None):
    """
    Create a Vendor Rating Log entry and recalculate supplier's weighted average rating.
    Weights come from Vendor Portal Settings.
    """
    try:
        score = flt(score)
        if not (1 <= score <= 5):
            frappe.throw(frappe._("Score must be between 1 and 5."))

        log = frappe.get_doc({
            "doctype":          "Vendor Rating Log",
            "supplier":         supplier,
            "rating_type":      rating_type,
            "score":            score,
            "remarks":          remarks,
            "purchase_order":   purchase_order,
            "purchase_receipt": purchase_receipt,
            "rated_by":         frappe.session.user
            
        })
        log.insert(ignore_permissions=True, ignore_links=True)

        # Recalculate weighted avg
        _recalculate_supplier_rating(supplier)

        return {"name": log.name, "score": score}

    except frappe.ValidationError:
        raise
    except Exception:
        frappe.log_error(frappe.get_traceback(), "submit_vendor_rating Error")
        frappe.throw(frappe._("Error submitting vendor rating."))


@frappe.whitelist()
def get_vendor_rating_history(supplier):
    """Fetch all Vendor Rating Log entries for a supplier, newest first."""
    try:
        return frappe.get_list(
            "Vendor Rating Log",
            filters={"supplier": supplier},
            fields=["name", "creation", "rating_type", "score", "remarks", "rated_by"],
            order_by="creation desc",
            limit=50
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "get_vendor_rating_history Error")
        frappe.throw(frappe._("Error fetching rating history."))


@frappe.whitelist()
def create_vendor_rating_log(supplier, rating_type, score, remarks,
                              purchase_order=None, purchase_receipt=None):
    
    return submit_vendor_rating(
        supplier, rating_type, score, remarks, purchase_order, purchase_receipt
    )


@frappe.whitelist()
def get_supplier_comparison(item_code, qty=1):
    """
    Returns a list of suppliers who have supplied this item, with ratings and pricing.
    Helps purchase team compare vendors for an item.
    """
    try:
        qty = flt(qty)
        data = frappe.db.sql("""
            SELECT
                poi.supplier                                AS supplier,
                s.supplier_name                             AS supplier_name,
                s.custom_vendor_rating                      AS vendor_rating,
                s.custom_vendor_category                    AS vendor_category,
                s.custom_total_rating_count                 AS total_rating_count,
                MAX(poi.rate)                               AS last_rate,
                AVG(poi.rate)                               AS avg_rate,
                SUM(poi.qty)                                AS total_supplied_qty,
                AVG(CASE WHEN vrl.rating_type = 'Delivery'
                         THEN vrl.score END)                AS delivery_score
            FROM `tabPurchase Order Item` poi
            JOIN `tabPurchase Order` po
                ON po.name = poi.parent AND po.docstatus = 1
            JOIN `tabSupplier` s
                ON s.name = po.supplier
            LEFT JOIN `tabVendor Rating Log` vrl
                ON vrl.supplier = po.supplier
            WHERE poi.item_code = %s
            GROUP BY poi.supplier
            ORDER BY s.custom_vendor_rating DESC
        """, item_code, as_dict=True)

        return data
    except Exception:
        frappe.log_error(frappe.get_traceback(), "get_supplier_comparison Error")
        frappe.throw(frappe._("Error fetching supplier comparison."))


@frappe.whitelist()
def get_onboarding_status_summary():
    """Returns summary counts for the Vendor Onboarding dashboard widget."""
    try:
        counts = frappe.db.sql("""
            SELECT
                onboarding_status,
                COUNT(*) AS count
            FROM `tabVendor Onboarding`
            GROUP BY onboarding_status
        """, as_dict=True)

        # simplify summary to a dict for easy access
        summary = {row.onboarding_status: row.count for row in counts} # e.g. {"Under Review": 5, "Approved": 10, "Rejected": 2}

        recent = frappe.get_list(
            "Vendor Onboarding",
            fields=["name", "supplier_name", "onboarding_status", "creation"],
            order_by="creation desc",
            limit=10
        )

        return {
            "total_pending":     summary.get("Under Review", 0),
            "total_approved":    summary.get("Approved", 0),
            "total_rejected":    summary.get("Rejected", 0),
            "total_draft":       summary.get("Draft", 0),
            "recent_submissions": recent,
        }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "get_onboarding_status_summary Error")
        frappe.throw(frappe._("Error fetching onboarding summary."))


# ─── Internal helper ──────────────────────────────────────────────────────────

def _recalculate_supplier_rating(supplier):
    """
    Recalculate supplier's vendor_rating as a weighted average.
    Weights are fetched from Vendor Portal Settings.
    """
    settings = frappe.get_single("Vendor Portal Settings")
    weights = {
        "Delivery":      flt(settings.rating_weight_delivery, 1),
        "Quality":       flt(settings.rating_weight_quality, 1),
        "Pricing":       flt(settings.rating_weight_pricing, 1),
        "Communication": flt(settings.rating_weight_communication, 1),
    }

    breakdown = frappe.db.sql("""
        SELECT rating_type, AVG(score) AS avg_score
        FROM `tabVendor Rating Log`
        WHERE supplier = %s
        GROUP BY rating_type
    """, supplier, as_dict=True)

    total_weight = 0
    weighted_sum = 0
    for row in breakdown:
        w = weights.get(row.rating_type, 0)
        weighted_sum += row.avg_score * w
        total_weight += w

    avg = round(weighted_sum / total_weight, 2) if total_weight else 0

    total_count = frappe.db.count("Vendor Rating Log", {"supplier": supplier})

    frappe.db.set_value("Supplier", supplier, {
        "custom_vendor_rating":       avg,
        "custom_total_rating_count":  total_count,
    })
    frappe.db.commit()