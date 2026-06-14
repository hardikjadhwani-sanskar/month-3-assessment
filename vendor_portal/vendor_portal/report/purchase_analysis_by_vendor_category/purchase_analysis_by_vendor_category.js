// vendor_portal/report/purchase_analysis_by_vendor_category/purchase_analysis_by_vendor_category.js

frappe.query_reports["Purchase Analysis by Vendor Category"] = {

    filters: [
        {
            fieldname:   "vendor_category",
            label:       __("Vendor Category"),
            fieldtype:   "Link",
            options:     "Vendor Category",
            width:       160,
            get_query: () => ({
                filters: { is_active: 1 }
            }),
        },
        {
            fieldname:   "from_date",
            label:       __("From Date"),
            fieldtype:   "Date",
            width:       120,
            default:     frappe.datetime.add_months(frappe.datetime.get_today(), -6),
        },
        {
            fieldname:   "to_date",
            label:       __("To Date"),
            fieldtype:   "Date",
            width:       120,
            default:     frappe.datetime.get_today(),
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        // Color-code avg_rating column
        if (column.fieldname === "avg_rating" && data) {
            const rating = flt(data.avg_rating);
            let color;
            if      (rating >= 4) color = "#1D9E75";
            else if (rating >= 3) color = "#FF9500";
            else if (rating >  0) color = "#E74C3C";
            else                  color = "#aaa";

            value = `<span style="color:${color}; font-weight:500;">
                        ${rating ? rating.toFixed(1) + " / 5" : "—"}
                     </span>`;
        }

        // Highlight suppliers below threshold in red
        if (column.fieldname === "below_threshold_count" && data) {
            const count = parseInt(data.below_threshold_count) || 0;
            if (count > 0) {
                value = `<span style="color:#E74C3C; font-weight:600;">${count}</span>`;
            }
        }

        // Highlight best_supplier in green
        if (column.fieldname === "best_supplier" && data && data.best_supplier !== "—") {
            value = `<span style="color:#1D9E75; font-weight:500;">
                        ${frappe.utils.escape_html(data.best_supplier)}
                     </span>`;
        }

        // Highlight lowest_supplier in red if they exist
        if (column.fieldname === "lowest_supplier" && data && data.lowest_supplier !== "—") {
            value = `<span style="color:#E74C3C;">
                        ${frappe.utils.escape_html(data.lowest_supplier)}
                     </span>`;
        }

        return value;
    },

	onload(report) {
		report.page.add_action_item(__("Export to Excel"), () => {
			report.export_report("Excel");
		});
	},
};