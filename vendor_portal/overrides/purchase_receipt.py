
import frappe
from frappe.utils import date_diff, getdate


def validate(doc, method):

    
    if not doc.is_new():

        doc.flags.has_short_delivery = False

        short_items = []

        for item in doc.items:
            if not item.purchase_order or not item.purchase_order_item:
                continue

            qty_ordered = frappe.db.get_value(
                "Purchase Order Item",
                item.purchase_order_item,
                "qty"
            )

            if not qty_ordered:
                continue

            accepted_qty = item.received_qty or 0
            threshold = qty_ordered * 0.90

            if accepted_qty < threshold:
                doc.flags.has_short_delivery = True
                short_items.append(
                    f"{item.item_code}: ordered {qty_ordered}, "
                    f"received {accepted_qty}"
                )

        if short_items : 
            doc.flags.short_item_list = short_items  # pass to next hook via flags


            comment_to_be_added = f"Short delivery detected — {', '.join(short_items)}"
            latest_comment = frappe.db.get_all(
                "Comment",
                filters={
                    "reference_doctype": "Purchase Receipt",
                    "reference_name": doc.name,
                    "comment_type": "Comment"
                },
                fields=["content"],
                order_by="creation desc",
                limit=1
            )

            # Avoid duplicate comments on every save
            if not latest_comment or latest_comment[0].content != comment_to_be_added:
                doc.add_comment(
                    "Comment",
                    f"Short delivery detected — {', '.join(short_items)}"
                )
        
            frappe.msgprint(
                f"Warning: Short delivery on: {', '.join(short_items)}",
                indicator="orange",
                alert=True
            )


def on_submit(doc, method):
    """

    Score matrix:
      5 = on time  + full qty
      4 = on time  + short delivery
      3 = late     + full qty
      2 = late     + short delivery
    """
    is_late = _is_late(doc)

    is_short = _check_short_delivery(doc)
   

    # Score matrix
    if not is_late and not is_short:
        score = 5
    elif not is_late and is_short:
        score = 4
    elif is_late and not is_short:
        score = 3
    else:
        score = 2  # late + short

    vendor_rating_log = frappe.get_doc({
        "doctype": "Vendor Rating Log",
        "supplier": doc.supplier,
        "purchase_receipt": doc.name,
        "rating_type": "Delivery",
        "score": score,
        "posting_date": doc.posting_date,
        "is_late": is_late,
        "has_short_delivery": is_short,
    })

    vendor_rating_log.insert(
    )

    frappe.logger().info(
        f"Vendor Rating Log created for PR {doc.name} | "
        f"Supplier: {doc.supplier} | Score: {score} | "
        f"Late: {is_late} | Short: {is_short}"
    )


# ─── Private helpers ──────────────────────────────────────────────

def _is_late(doc):
    """
    Returns True if posting_date > expected_delivery_date from linked PO
    by more than 2 days.
    Uses the first PO linked in items (assumes one PO per receipt).
    """
    po_name = _get_linked_po(doc)
    if not po_name:
        return False

    expected_date = frappe.db.get_value(
        "Purchase Order",
        po_name,
        "schedule_date"  # assuming schedule_date is the expected delivery date; adjust if different
    )

    if not expected_date:
        return False

    days_diff = date_diff(doc.posting_date, expected_date)
    return days_diff > 2


def _get_linked_po(doc):
    """
    Returns the first Purchase Order name linked to this receipt's items.
    """
    for item in doc.items:
        if item.purchase_order:
            return item.purchase_order
    return None


def _check_short_delivery(doc):
  
    for item in doc.items:
        if not item.purchase_order_item:
            continue
        qty_ordered = frappe.db.get_value(
            "Purchase Order Item",
            item.purchase_order_item,
            "qty"
        )
        if item.received_qty < qty_ordered:
            return True
    return False