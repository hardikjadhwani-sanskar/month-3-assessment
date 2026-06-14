
# If any Supplier records have comments containing rating keywords ("good", "bad", "late delivery", etc.), create corresponding Vendor Rating Log entries with estimated scores. This demonstrates intelligent data migration.



import frappe
from frappe.utils import today
 
 
# Keyword → estimated score mapping
KEYWORD_SCORE_MAP = {
    "excellent":     5,
    "great":         5,
    "good":          4,
    "reliable":      4,
    "average":       3,
    "ok":            3,
    "poor":          2,
    "bad":           2,
    "late delivery": 2,
    "delayed":       2,
    "blacklisted":   1,
    "terrible":      1,
}
 
 
def execute():
    """
    Look at Comment records on Supplier documents.
    If they contain rating keywords, create Vendor Rating Log entries.
    """
    comments = frappe.db.sql("""
        SELECT name, reference_name AS supplier, content
        FROM `tabComment`
        WHERE reference_doctype = 'Supplier'
          AND comment_type = 'Comment'
          AND content IS NOT NULL
    """, as_dict=True)
 
    created = 0
 
    for comment in comments:
        content_lower = comment.content.lower()
        matched_score = None
 
        for keyword, score in KEYWORD_SCORE_MAP.items():
            if keyword in content_lower:
                matched_score = score
                break
 
        if matched_score is None:
            continue
 
        # Avoid duplicates
        if frappe.db.exists("Vendor Rating Log", {
            "supplier":    comment.supplier,
            "remarks":     f"Migrated from comment: {comment.name}"
        }):
            continue
 
        try:
            frappe.get_doc({
                "doctype":     "Vendor Rating Log",
                "supplier":    comment.supplier,
                "rating_type": "Communication",
                "score":       matched_score,
                "remarks":     f"Migrated from comment: {comment.name}",
                "rating_date": today(),
                "rated_by":    "Administrator",
            }).insert(ignore_permissions=True, ignore_links=True)
            created += 1
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"migrate_supplier_notes failed for comment {comment.name}"
            )
 
    frappe.db.commit()
    print(f"migrate_supplier_notes_to_rating_logs: Created {created} rating log(s).")
 

