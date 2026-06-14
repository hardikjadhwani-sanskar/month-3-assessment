// vendor_portal/report/vendor_performance_report/vendor_performance_report.js

frappe.query_reports["Vendor Performance Report"] = {

    filters: [
        {
            fieldname:  "supplier",
            label:      __("Supplier"),
            fieldtype:  "Link",
            options:    "Supplier",
            width:      160,
        },
        {
            fieldname:  "vendor_category",
            label:      __("Vendor Category"),
            fieldtype:  "Link",
            options:    "Vendor Category",
            width:      160,
            // Only show active categories in the dropdown
            get_query: () => ({
                filters: { is_active: 1 }
            }),
        },
        {
            fieldname:  "from_date",
            label:      __("From Date"),
            fieldtype:  "Date",
            width:      120,
            default:    frappe.datetime.add_months(frappe.datetime.get_today(), -3),
        },
        {
            fieldname:  "to_date",
            label:      __("To Date"),
            fieldtype:  "Date",
            width:      120,
            default:    frappe.datetime.get_today(),
        },
        {
            fieldname:  "minimum_rating",
            label:      __("Minimum Rating"),
            fieldtype:  "Float",
            width:      120,
            description: __("Filter suppliers with overall rating at or above this value (1–5)"),
        },
    ],

    // Color-code rows based on overall_rating value
    get_datatable_options(options) {
        return Object.assign(options, {
            cellHeight: 35,
        });
    },

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "overall_rating" && data) {
            const rating = flt(data.overall_rating);
            let color;
            if (rating >= 4)      color = "#1D9E75";   // green — good
            else if (rating >= 3) color = "#FF9500";   // orange — average
            else if (rating > 0)  color = "#E74C3C";   // red — poor
            else                  color = "#aaa";      // grey — unrated

            value = `<span style="color:${color}; font-weight:500;">
                        ${rating ? rating.toFixed(1) : "—"}
                     </span>`;
        }

        if (column.fieldname === "is_blacklisted" && data && data.is_blacklisted) {
            value = `<span style="background:#E74C3C18; color:#E74C3C;
                                  border:1px solid #E74C3C40; padding:2px 8px;
                                  border-radius:10px; font-size:11px; font-weight:600;">
                        Blacklisted
                     </span>`;
        }

        if (column.fieldname === "on_time_pct" && data) {
            const pct   = flt(data.on_time_pct, 1);
            const color = pct >= 90 ? "#1D9E75" : pct >= 70 ? "#FF9500" : "#E74C3C";
            value = `<span style="color:${color}; font-weight:500;">${pct}%</span>`;
        }

        return value;
    },

    // Summary cards at top of report
    onload(report) {
        report.page.add_action_item(__("Export to Excel"), () => {
            report.export_report("Excel");
        });
    },
};