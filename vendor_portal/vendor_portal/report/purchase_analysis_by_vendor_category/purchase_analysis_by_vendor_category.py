# vendor_portal/report/purchase_analysis_by_vendor_category/purchase_analysis_by_vendor_category.py

# Columns: Vendor Category, Total Suppliers, Active Suppliers, Total PO Value, Avg PO Value, Total Items Purchased, Avg Vendor Rating, Lowest Rating Supplier.
# Filters: Date Range, Vendor Category.
# Chart: Pie chart — PO value distribution by vendor category.



import frappe
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data    = get_data(filters)
    chart   = get_chart(data)
    summary = get_summary(data)
    return columns, data, None, chart, summary


def get_columns():
    return [
        {
            "label":     "Vendor Category",
            "fieldname": "vendor_category",
            "fieldtype": "Link",
            "options":   "Vendor Category",
            "width":     160,
        },
        {
            "label":     "Total Suppliers",
            "fieldname": "total_suppliers",
            "fieldtype": "Int",
            "width":     120,
        },
        {
            "label":     "Active Suppliers",
            "fieldname": "active_suppliers",
            "fieldtype": "Int",
            "width":     120,
        },
        {
            "label":     "Total POs",
            "fieldname": "total_pos",
            "fieldtype": "Int",
            "width":     90,
        },
        {
            "label":     "Total PO Value",
            "fieldname": "total_po_value",
            "fieldtype": "Currency",
            "width":     140,
        },
        {
            "label":     "Avg PO Value",
            "fieldname": "avg_po_value",
            "fieldtype": "Currency",
            "width":     130,
        },
        {
            "label":     "Total Items Qty",
            "fieldname": "total_items_qty",
            "fieldtype": "Float",
            "width":     120,
        },
        {
            "label":     "Avg Vendor Rating",
            "fieldname": "avg_rating",
            "fieldtype": "Float",
            "precision": 2,
            "width":     130,
        },
        {
            "label":     "Min Rating Threshold",
            "fieldname": "min_threshold",
            "fieldtype": "Float",
            "precision": 1,
            "width":     140,
        },
        {
            "label":     "Suppliers Below Threshold",
            "fieldname": "below_threshold_count",
            "fieldtype": "Int",
            "width":     170,
        },
        {
            "label":     "Best Supplier",
            "fieldname": "best_supplier",
            "fieldtype": "Data",
            "width":     180,
        },
        {
            "label":     "Lowest Rated Supplier",
            "fieldname": "lowest_supplier",
            "fieldtype": "Data",
            "width":     180,
        },
    ]


def get_data(filters):
    conditions = []
    values     = {}

    if filters.get("vendor_category"):
        conditions.append("vc.category_name = %(vendor_category)s")
        values["vendor_category"] = filters["vendor_category"]

    if filters.get("from_date"):
        conditions.append("po.transaction_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("po.transaction_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    # Apply date conditions only to PO join (not supplier count)
    po_date_cond = ""
    if filters.get("from_date"):
        po_date_cond += " AND po.transaction_date >= %(from_date)s"
    if filters.get("to_date"):
        po_date_cond += " AND po.transaction_date <= %(to_date)s"

    vc_where = ("WHERE " + " AND ".join(
        [c for c in conditions if c.startswith("vc.")]
    )) if any(c.startswith("vc.") for c in conditions) else ""

    raw = frappe.db.sql(f"""
        SELECT
            vc.category_name                                AS vendor_category,
            vc.minimum_rating_threshold                     AS min_threshold,
            COUNT(DISTINCT s.name)                          AS total_suppliers,
            SUM(CASE WHEN s.disabled = 0
                     THEN 1 ELSE 0 END)                     AS active_suppliers,
            SUM(CASE WHEN s.custom_vendor_rating IS NOT NULL
                      AND s.custom_total_rating_count > 0
                      AND s.custom_vendor_rating < vc.minimum_rating_threshold
                     THEN 1 ELSE 0 END)                     AS below_threshold_count,
            COUNT(DISTINCT po.name)                         AS total_pos,
            COALESCE(SUM(po.grand_total), 0)                AS total_po_value,
            COALESCE(AVG(po.grand_total), 0)                AS avg_po_value,
            COALESCE(SUM(poi.qty), 0)                       AS total_items_qty,
            AVG(s.custom_vendor_rating)                     AS avg_rating,
            (
                SELECT s2.supplier_name
                FROM `tabSupplier` s2
                WHERE s2.custom_vendor_category = vc.category_name
                  AND s2.custom_vendor_rating IS NOT NULL
                  AND s2.disabled = 0
                ORDER BY s2.custom_vendor_rating DESC
                LIMIT 1
            )                                               AS best_supplier,
            (
                SELECT s3.supplier_name
                FROM `tabSupplier` s3
                WHERE s3.custom_vendor_category = vc.category_name
                  AND s3.custom_vendor_rating IS NOT NULL
                  AND s3.custom_total_rating_count > 0
                  AND s3.disabled = 0
                ORDER BY s3.custom_vendor_rating ASC
                LIMIT 1
            )                                               AS lowest_supplier
        FROM `tabVendor Category` vc
        LEFT JOIN `tabSupplier` s
            ON s.custom_vendor_category = vc.category_name
        LEFT JOIN `tabPurchase Order` po
            ON po.supplier = s.name
            AND po.docstatus = 1
            {po_date_cond}
        LEFT JOIN `tabPurchase Order Item` poi
            ON poi.parent = po.name
        {vc_where}
        GROUP BY
            vc.category_name,
            vc.minimum_rating_threshold
        ORDER BY total_po_value DESC
    """, values, as_dict=True)

    # Round floats and fill nulls for clean display
    for row in raw:
        row["avg_rating"]            = round(flt(row.avg_rating), 2)    if row.avg_rating else 0
        row["total_po_value"]        = flt(row.total_po_value, 2)
        row["avg_po_value"]          = flt(row.avg_po_value, 2)
        row["total_items_qty"]       = flt(row.total_items_qty, 2)
        row["min_threshold"]         = flt(row.min_threshold, 1)
        row["below_threshold_count"] = row.below_threshold_count or 0
        row["best_supplier"]         = row.best_supplier   or "—"
        row["lowest_supplier"]       = row.lowest_supplier or "—"

    return raw


def get_chart(data):
    if not data:
        return None

    labels         = [r.get("vendor_category") or "Unknown" for r in data]
    po_values      = [flt(r.get("total_po_value"), 2) for r in data]
    avg_ratings    = [flt(r.get("avg_rating"), 2)     for r in data]

    return {
        "data": {
            "labels":   labels,
            "datasets": [
                {
                    "name":   "Total PO Value",
                    "values": po_values,
                    "chartType": "bar",
                },
                {
                    "name":   "Avg Rating (×10000 scale)",
                    "values": [r * 10000 for r in avg_ratings],
                    "chartType": "line",
                },
            ],
        },
        "type":   "axis-mixed",
        "colors": ["#2490EF", "#1D9E75"],
        "title":  "PO Value & Average Rating by Vendor Category",
        "height": 280,
        "axisOptions": {"xIsSeries": 1},
    }


def get_summary(data):
    if not data:
        return []

    total_categories = len(data)
    total_po_value   = sum(flt(r.get("total_po_value")) for r in data)
    total_suppliers  = sum(r.get("total_suppliers") or 0 for r in data)
    below_threshold  = sum(r.get("below_threshold_count") or 0 for r in data)

    rated = [r for r in data if r.get("avg_rating")]
    overall_avg = round(
        sum(r["avg_rating"] for r in rated) / len(rated), 2
    ) if rated else 0

    return [
        {
            "value":     total_categories,
            "label":     "Active Categories",
            "datatype":  "Int",
            "indicator": "blue",
        },
        {
            "value":     total_suppliers,
            "label":     "Total Suppliers",
            "datatype":  "Int",
            "indicator": "blue",
        },
        {
            "value":     total_po_value,
            "label":     "Total PO Value",
            "datatype":  "Currency",
            "indicator": "green",
        },
        {
            "value":     below_threshold,
            "label":     "Suppliers Below Threshold",
            "datatype":  "Int",
            "indicator": "red" if below_threshold > 0 else "green",
        },
    ]