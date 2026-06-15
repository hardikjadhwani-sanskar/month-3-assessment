frappe.pages["vendor-dashboard"].on_page_load = function(wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Vendor Dashboard",
        single_column: true,
    });
 
    $(frappe.render_template("vendor_dashboard", {})).appendTo(page.main);
 
    // Load all charts
    load_rating_distribution(page);
    load_onboarding_pipeline(page);
    load_po_by_category(page);
    load_delivery_trend(page);
};
 
 
function load_rating_distribution(page) {
    frappe.call({
        method: "vendor_portal.api.get_onboarding_status_summary",
        callback(r) {
            const d = r.message || {};
            new frappe.Chart("#rating-dist-chart", {
                title:  "Onboarding Pipeline",
                type:   "bar",
                data: {
                    labels:   ["Draft", "Under Review", "Approved", "Rejected"],
                    datasets: [{
                        name: "Count",
                        values: [d.total_draft || 0, d.total_pending || 0,
                                 d.total_approved || 0, d.rejected || 0]
                    }]
                },
                colors: ["#888", "#2490EF", "#1DB954", "#E74C3C"],
                height: 250,
            });
        }
    });
}
 
 
function load_onboarding_pipeline(page) {
    frappe.db.sql = undefined; // use frappe.call for safety
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Vendor Rating Log",
            fields:  ["rating_type", "score"],
            limit:   500,
        },
        callback(r) {
            const logs = r.message || [];
            const buckets = {"1-2": 0, "2-3": 0, "3-4": 0, "4-5": 0};
            logs.forEach(l => {
                if (l.score <= 2) buckets["1-2"]++;
                else if (l.score <= 3) buckets["2-3"]++;
                else if (l.score <= 4) buckets["3-4"]++;
                else buckets["4-5"]++;
            });
 
            new frappe.Chart("#rating-histogram", {
                title:  "Rating Distribution",
                type:   "bar",
                data: {
                    labels:   Object.keys(buckets),
                    datasets: [{ name: "Count", values: Object.values(buckets) }]
                },
                colors:  ["#2490EF"],
                height:  250,
            });
        }
    });
}
 
 
function load_po_by_category(page) {
    frappe.call({
        method: "vendor_portal.report.purchase_analysis_by_vendor_category.purchase_analysis_by_vendor_category.execute",
        args: { filters: {} },
        callback(r) {
            const data = (r.message && r.message[1]) || [];
            new frappe.Chart("#po-category-chart", {
                title:  "PO Value by Vendor Category",
                type:   "pie",
                data: {
                    labels:   data.map(d => d.vendor_category || "Unknown"),
                    datasets: [{ values: data.map(d => d.total_po_value || 0) }]
                },
                height: 280,
            });
        }
    });
}
 
 
function load_delivery_trend(page) {
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype:  "Vendor Rating Log",
            fields:   ["rating_date", "score"],
            filters:  [["rating_type", "=", "Delivery"]],
            order_by: "rating_date asc",
            limit:    90,
        },
        callback(r) {
            const logs = r.message || [];
            new frappe.Chart("#delivery-trend-chart", {
                title:  "Delivery Score Trend (Last 90 entries)",
                type:   "line",
                data: {
                    labels:   logs.map(l => l.rating_date),
                    datasets: [{ name: "Delivery Score", values: logs.map(l => l.score) }]
                },
                colors:  ["#1DB954"],
                height:  250,
            });
        }
    });
}