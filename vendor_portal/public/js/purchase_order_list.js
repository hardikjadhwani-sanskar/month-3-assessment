
// • Override the default list columns for Purchase Order list view: 
// add supplier_name, grand_total, per_received, status.

// In your app_include_js, override frappe.listview_settings["Purchase Order"] to add custom indicators: 
// Green = Completed, Orange = To Receive, Red = Overdue (where expected delivery date has passed but per_received <100). 
// Add a right-click menu item "Quick Rate Supplier" that opens a rating dialog.


frappe.listview_settings["Purchase Order"] = {
    add_fields: ["supplier_name", "grand_total", "per_received", "status", "schedule_date"],

    get_indicator(doc) {
        const today = frappe.datetime.get_today();
        // Overdue: delivery expected but not fully received
        if (
            doc.schedule_date &&
            doc.schedule_date < today &&
            flt(doc.per_received) < 100 &&
            doc.status !== "Completed" &&
            doc.status !== "Cancelled"
        ) {
            return [__("Overdue"), "red", "schedule_date,<," + today];
        }
        const map = {
            "Draft":               ["Draft",               "grey"],
            "To Receive and Bill": ["To Receive and Bill", "orange"],
            "To Bill":             ["To Bill",             "yellow"],
            "To Receive":          ["To Receive",          "blue"],
            "Completed":           ["Completed",           "green"],
            "Cancelled":           ["Cancelled",           "red"],
            "Closed":              ["Closed",              "darkgrey"],
        };
        return map[doc.status] || [doc.status, "grey"];
    },

    formatters: {
        grand_total(value) {
            return frappe.format(value, { fieldtype: "Currency" });
        },
        per_received(value) {
            const pct   = flt(value, 1);
            const color = pct >= 100 ? "#1DB954" : pct > 0 ? "#FF9500" : "#aaa";
            return `<span style="color:${color};font-weight:600;">${pct}%</span>`;
        }
    },

    right_column: "grand_total",

    // Right-click context menu
    onload(listview) {
        listview.page.add_action_item(__("Quick Rate Supplier"), () => {
            const checked = listview.get_checked_items();
            if (!checked.length) {
                frappe.msgprint(__("Please select at least one Purchase Order."));
                return;
            }
            const supplier = checked[0].supplier;
            if (!supplier) return;

            const d = new frappe.ui.Dialog({
                title: __("Quick Rate Supplier"),
                fields: [
                    { fieldname: "rating_type", fieldtype: "Select",
                      label: __("Rating Type"),
                      options: "Delivery\nQuality\nPricing\nCommunication", reqd: 1 },
                    { fieldname: "score", fieldtype: "Rating",
                      label: __("Score"), reqd: 1 },
                    { fieldname: "remarks", fieldtype: "Small Text",
                      label: __("Remarks") },
                ],
                primary_action_label: __("Submit"),
                primary_action(values) {
                    frappe.call({
                        method: "vendor_portal.api.create_vendor_rating_log",
                        args: {
                            supplier:       supplier,
                            purchase_order: checked[0].name,
                            rating_type:    values.rating_type,
                            score:          values.score * 5,
                            remarks:        values.remarks || "",
                        },
                        callback() {
                            frappe.show_alert({ message: __("Rating submitted!"), indicator: "green" });
                            d.hide();
                        }
                    });
                }
            });
            d.show();
        });
    },
};