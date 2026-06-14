# vendor_portal/report/vendor_performance_report/vendor_performance_report.py

# Columns: Supplier Name, Vendor Category, Total POs, Total PO Value, Avg Delivery Score, Avg Quality Score, Avg Pricing Score, Overall Rating, Total Receipts, On-Time Delivery %, Short Delivery Count.
# Filters: Vendor Category (Link), Supplier (Link), Date Range (from_date, to_date), Minimum Rating (Float).
# SQL: JOIN across Supplier, Purchase Order, Purchase Receipt, Vendor Rating Log with GROUP BY and conditional aggregation.
# Chart: Bar chart — top 10 suppliers by overall rating.



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
            "label":     "Supplier",
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options":   "Supplier",
            "width":     140,
        },
        {
            "label":     "Supplier Name",
            "fieldname": "supplier_name",
            "fieldtype": "Data",
            "width":     160,
        },
        {
            "label":     "Vendor Category",
            "fieldname": "vendor_category",
            "fieldtype": "Link",
            "options":   "Vendor Category",
            "width":     130,
        },
        {
            "label":     "Total POs",
            "fieldname": "total_pos",
            "fieldtype": "Int",
            "width":     85,
        },
        {
            "label":     "Total PO Value",
            "fieldname": "total_po_value",
            "fieldtype": "Currency",
            "width":     130,
        },
        {
            "label":     "Avg Delivery Score",
            "fieldname": "avg_delivery",
            "fieldtype": "Float",
            "precision": 2,
            "width":     130,
        },
        {
            "label":     "Avg Quality Score",
            "fieldname": "avg_quality",
            "fieldtype": "Float",
            "precision": 2,
            "width":     120,
        },
        {
            "label":     "Avg Pricing Score",
            "fieldname": "avg_pricing",
            "fieldtype": "Float",
            "precision": 2,
            "width":     120,
        },
        {
            "label":     "Avg Communication Score",
            "fieldname": "avg_communication",
            "fieldtype": "Float",
            "precision": 2,
            "width":     150,
        },
        {
            "label":     "Overall Rating",
            "fieldname": "overall_rating",
            "fieldtype": "Float",
            "precision": 2,
            "width":     110,
        },
        {
            "label":     "Total Ratings",
            "fieldname": "total_ratings",
            "fieldtype": "Int",
            "width":     100,
        },
        {
            "label":     "Total Receipts",
            "fieldname": "total_receipts",
            "fieldtype": "Int",
            "width":     110,
        },
        {
            "label":     "On-Time Delivery %",
            "fieldname": "on_time_pct",
            "fieldtype": "Percent",
            "width":     130,
        },
        {
            "label":     "Short Deliveries",
            "fieldname": "short_delivery_count",
            "fieldtype": "Int",
            "width":     120,
        },
        {
            "label":     "Blacklisted",
            "fieldname": "is_blacklisted",
            "fieldtype": "Check",
            "width":     90,
        },
    ]


def get_data(filters):
    conditions = []
    values     = {}

    if filters.get("supplier"):
        conditions.append("s.name = %(supplier)s")
        values["supplier"] = filters["supplier"]

    if filters.get("vendor_category"):
        conditions.append("s.custom_vendor_category = %(vendor_category)s")
        values["vendor_category"] = filters["vendor_category"]

    if filters.get("from_date"):
        conditions.append("po.transaction_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("po.transaction_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Main query — joins Supplier, PO, PR, and pre-aggregated VRL subquery
    # VRL is pre-aggregated to avoid row multiplication when a supplier
    # has many rating log entries
    raw = frappe.db.sql(f"""
        SELECT
            s.name                                  AS supplier,
            s.supplier_name                         AS supplier_name,
            s.custom_vendor_category                AS vendor_category,
            s.custom_vendor_rating                  AS overall_rating,
            s.custom_is_blacklisted                 AS is_blacklisted,
            COUNT(DISTINCT po.name)                 AS total_pos,
            COALESCE(SUM(po.grand_total), 0)        AS total_po_value,
            COUNT(DISTINCT pr.name)                 AS total_receipts,
            vrl_agg.avg_delivery                    AS avg_delivery,
            vrl_agg.avg_quality                     AS avg_quality,
            vrl_agg.avg_pricing                     AS avg_pricing,
            vrl_agg.avg_communication               AS avg_communication,
            vrl_agg.total_ratings                   AS total_ratings,
            vrl_agg.on_time_count                   AS on_time_count,
            vrl_agg.total_delivery_ratings          AS total_delivery_ratings,
            vrl_agg.short_delivery_count            AS short_delivery_count
        FROM `tabSupplier` s
        LEFT JOIN `tabPurchase Order` po
            ON po.supplier = s.name
            AND po.docstatus = 1
        LEFT JOIN `tabPurchase Receipt` pr
            ON pr.supplier = s.name
            AND pr.docstatus = 1
        LEFT JOIN (
            SELECT
                supplier,
                COUNT(*)                                            AS total_ratings,
                AVG(CASE WHEN rating_type = 'Delivery'
                         THEN score END)                            AS avg_delivery,
                AVG(CASE WHEN rating_type = 'Quality'
                         THEN score END)                            AS avg_quality,
                AVG(CASE WHEN rating_type = 'Pricing'
                         THEN score END)                            AS avg_pricing,
                AVG(CASE WHEN rating_type = 'Communication'
                         THEN score END)                            AS avg_communication,
                SUM(CASE WHEN rating_type = 'Delivery'
                         THEN 1 ELSE 0 END)                        AS total_delivery_ratings,
                SUM(CASE WHEN rating_type = 'Delivery'
                          AND score >= 4
                         THEN 1 ELSE 0 END)                        AS on_time_count,
                SUM(CASE WHEN rating_type = 'Delivery'
                          AND score IN (2, 4)
                         THEN 1 ELSE 0 END)                        AS short_delivery_count
            FROM `tabVendor Rating Log`
            GROUP BY supplier
        ) vrl_agg ON vrl_agg.supplier = s.name
        {where}
        GROUP BY
            s.name, s.supplier_name, s.custom_vendor_category,
            s.custom_vendor_rating, s.custom_is_blacklisted,
            vrl_agg.avg_delivery, vrl_agg.avg_quality,
            vrl_agg.avg_pricing, vrl_agg.avg_communication,
            vrl_agg.total_ratings, vrl_agg.on_time_count,
            vrl_agg.total_delivery_ratings, vrl_agg.short_delivery_count
        ORDER BY s.custom_vendor_rating DESC
    """, values, as_dict=True)

    # Apply minimum rating filter post-query
    # (cannot use HAVING on a LEFT JOIN subquery column cleanly in MariaDB)
    min_rating = flt(filters.get("minimum_rating"))

    result = []
    for row in raw:
        if min_rating and flt(row.overall_rating or 0) < min_rating:
            continue

        # Calculate on-time % from delivery score counts
        total_del = row.total_delivery_ratings or 0
        on_time   = row.on_time_count or 0
        row["on_time_pct"] = round((on_time / total_del) * 100, 1) if total_del else 0

        # Round all float columns for display
        row["avg_delivery"]      = round(flt(row.avg_delivery), 2)      if row.avg_delivery      else 0
        row["avg_quality"]       = round(flt(row.avg_quality), 2)       if row.avg_quality       else 0
        row["avg_pricing"]       = round(flt(row.avg_pricing), 2)       if row.avg_pricing       else 0
        row["avg_communication"] = round(flt(row.avg_communication), 2) if row.avg_communication else 0
        row["overall_rating"]    = round(flt(row.overall_rating), 2)    if row.overall_rating    else 0
        row["total_ratings"]     = row.total_ratings or 0
        row["short_delivery_count"] = row.short_delivery_count or 0

        # Remove internal aggregation columns before returning
        for col in ("on_time_count", "total_delivery_ratings"):
            row.pop(col, None)

        result.append(row)

    return result


def get_chart(data):
    if not data:
        return None

    # Top 10 suppliers by overall rating for the bar chart
    top10 = sorted(data, key=lambda r: flt(r.get("overall_rating")), reverse=True)[:10]

    return {
        "data": {
            "labels": [r.get("supplier_name") or r.get("supplier") for r in top10],
            "datasets": [
                {
                    "name":   "Overall Rating",
                    "values": [flt(r.get("overall_rating"), 2) for r in top10],
                },
                {
                    "name":   "Avg Delivery",
                    "values": [flt(r.get("avg_delivery"), 2) for r in top10],
                },
            ],
        },
        "type":   "bar",
        "colors": ["#2490EF", "#1D9E75"],
        "title":  "Top 10 Suppliers — Overall vs Delivery Score",
        "barOptions": {"stacked": 0},
        "height": 280,
        "axisOptions": {"xIsSeries": 1},
    }


def get_summary(data):
    if not data:
        return []

    total_suppliers  = len(data)
    rated_suppliers  = [r for r in data if r.get("overall_rating")]
    avg_overall      = round(sum(r["overall_rating"] for r in rated_suppliers) / len(rated_suppliers), 2) if rated_suppliers else 0
    blacklisted      = sum(1 for r in data if r.get("is_blacklisted"))
    low_rated        = sum(1 for r in data if 0 < flt(r.get("overall_rating")) < 3)

    return [
        {
            "value":       total_suppliers,
            "label":       "Total Suppliers",
            "datatype":    "Int",
            "indicator":   "blue",
        },
        {
            "value":       avg_overall,
            "label":       "Avg Overall Rating",
            "datatype":    "Float",
            "indicator":   "green" if avg_overall >= 3.5 else "orange",
        },
        {
            "value":       low_rated,
            "label":       "Low Rated Suppliers",
            "datatype":    "Int",
            "indicator":   "red" if low_rated > 0 else "green",
        },
        {
            "value":       blacklisted,
            "label":       "Blacklisted Suppliers",
            "datatype":    "Int",
            "indicator":   "red" if blacklisted > 0 else "green",
        },
    ]