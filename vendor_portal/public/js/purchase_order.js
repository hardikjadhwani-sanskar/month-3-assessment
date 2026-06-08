frappe.ui.form.on("Purchase Order", {
 
    setup(frm) {
        // Set query filter on supplier field — show only non-disabled suppliers
        frm.set_query("supplier", () => ({
            filters: { disabled: 0 }
        }));
    },
 
    refresh(frm) {
        // Delay banner so ERPNext's own PO refresh doesn't overwrite it
        if (frm.doc.supplier) {
            setTimeout(() => update_supplier_banner(frm), 300);
        }
 
        if (!frm.is_new()) {
            // View Rating History — always visible if supplier set
            if (frm.doc.supplier) {
                frm.add_custom_button(__("View Vendor Rating History"), () => {
                    show_rating_history_dialog(frm.doc.supplier);
                }, __("Actions"));
            }
 
            // Rate This Supplier — only after submit
            if (frm.doc.docstatus === 1 && frm.doc.supplier) {
                frm.add_custom_button(__("Rate This Supplier"), () => {
                    show_rate_supplier_dialog(frm);
                }, __("Actions"));
            }
        }
    },
 
    supplier(frm) {
        if (!frm.doc.supplier) {
            frm.dashboard.set_headline_alert("");
            frm.enable_save();
            return;
        }
        setTimeout(() => update_supplier_banner(frm), 300);
    },
});
 
 
function update_supplier_banner(frm) {
    if (!frm.doc.supplier) return;
 
    frappe.db.get_value(
        "Supplier",
        frm.doc.supplier,
        [
            "custom_vendor_rating",
            "custom_vendor_category",
            "custom_total_rating_count",
            "custom_is_blacklisted",
            "custom_blacklist_reason",
        ]
    ).then(r => {
        const d = r.message;
        if (!d) return;
 
        if (d.custom_is_blacklisted) {
            const reason = d.custom_blacklist_reason
                ? ` — Reason: ${frappe.utils.escape_html(d.custom_blacklist_reason)}`
                : "";
            frm.dashboard.set_headline_alert(
                `<div style="color:#fff; font-weight:600;">
                    ⚠️ WARNING: This supplier is blacklisted!${reason}
                </div>`,
                "red"
            );
            frm.disable_save();
            return;
        }
 
        frm.enable_save();
 
        const rating   = d.custom_vendor_rating || 0;
        const count    = d.custom_total_rating_count || 0;
        const category = d.custom_vendor_category || "N/A";
        const stars    = _render_stars(rating);
        const color    = rating >= 4 ? "#1DB954" : rating >= 3 ? "#FF9500" : "#E74C3C";
 
        frm.dashboard.set_headline_alert(
            `<div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap;padding:2px 0;">
                <div>
                    <span style="font-size:11px;opacity:.6;text-transform:uppercase;
                                 letter-spacing:.05em;">Category</span>&nbsp;
                    <strong>${frappe.utils.escape_html(category)}</strong>
                </div>
                <div>
                    <span style="font-size:11px;opacity:.6;text-transform:uppercase;
                                 letter-spacing:.05em;">Rating</span>&nbsp;
                    <span style="color:${color};font-weight:700;font-size:15px;">
                        ${stars} ${flt(rating, 1)}
                    </span>
                    <span style="font-size:11px;opacity:.6;">
                        (${count} review${count !== 1 ? "s" : ""})
                    </span>
                </div>
            </div>`,
            rating >= 3 ? "blue" : "orange"
        );
    });
}
 
 
function _render_stars(rating) {
    const full  = Math.floor(rating);
    const half  = (rating - full) >= 0.5 ? 1 : 0;
    const empty = 5 - full - half;
    return "★".repeat(full) + (half ? "½" : "") + "☆".repeat(empty);
}
 
 
function show_rating_history_dialog(supplier) {
    const dialog = new frappe.ui.Dialog({
        title: __("Vendor Rating History — {0}", [supplier]),
        size: "large",
        fields: [{ fieldname: "rating_html", fieldtype: "HTML" }]
    });
 
    dialog.fields_dict.rating_html.$wrapper.html(`
        <div style="text-align:center;padding:40px;color:var(--text-muted);">
            ${__("Loading...")}
        </div>
    `);
    dialog.show();
 
    frappe.call({
        method: "vendor_portal.api.get_vendor_rating_history",
        args: { supplier },
        callback(r) {
            const logs = r.message || [];
            if (!logs.length) {
                dialog.fields_dict.rating_html.$wrapper.html(
                    `<div style="text-align:center;padding:40px;color:var(--text-muted);">
                        ${__("No rating history found.")}
                    </div>`
                );
                return;
            }
 
            const badge = {
                Delivery: "#2490EF", Quality: "#1DB954",
                Pricing: "#FF6B35", Communication: "#9B59B6"
            };
 
            const rows = logs.map(log => {
                const sc = log.score >= 4 ? "#1DB954" : log.score >= 3 ? "#FF9500" : "#E74C3C";
                const bc = badge[log.rating_type] || "#888";
                return `<tr style="border-bottom:1px solid var(--border-color);">
                    <td style="padding:10px 12px;font-size:12px;color:var(--text-muted);">
                        ${log.creation || "—"}
                    </td>
                    <td style="padding:10px 12px;">
                        <span style="background:${bc}18;color:${bc};border:1px solid ${bc}40;
                                     padding:2px 10px;border-radius:12px;font-size:11px;
                                     font-weight:600;">${log.rating_type}</span>
                    </td>
                    <td style="padding:10px 12px;text-align:center;">
                        <span style="color:${sc};font-weight:700;font-size:16px;">
                            ${flt(log.score, 1)}
                        </span>
                        <span style="font-size:11px;color:var(--text-muted);">/5</span>
                    </td>
                    <td style="padding:10px 12px;font-size:12px;color:var(--text-muted);">
                        ${frappe.utils.escape_html(log.remarks || "—")}
                    </td>
                    
                </tr>`;
            }).join("");
 
            dialog.fields_dict.rating_html.$wrapper.html(`
                <div style="overflow-x:auto;">
                    <table style="width:100%;border-collapse:collapse;">
                        <thead>
                            <tr style="border-bottom:2px solid var(--border-color);">
                                ${["Date","Type","Score","Remarks","Rated By"].map(h =>
                                    `<th style="padding:10px 12px;text-align:left;font-size:11px;
                                                text-transform:uppercase;letter-spacing:.05em;
                                                color:var(--text-muted);">${h}</th>`
                                ).join("")}
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            `);
        }
    });
}
 
 
function show_rate_supplier_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __("Rate Supplier — {0}", [frm.doc.supplier]),
        size: "small",
        fields: [
            {
                label: "Rating Type",
                fieldname: "rating_type",
                fieldtype: "Select",
                options: "Delivery\nQuality\nPricing\nCommunication",
                reqd: 1,
            },
            {
                label: "Score (1–5)",
                fieldname: "score",
                fieldtype: "Rating",
                reqd: 1,
            },
            {
                label: "Remarks",
                fieldname: "remarks",
                fieldtype: "Small Text",
            },
        ],
        primary_action_label: __("Submit Rating"),
        primary_action(values) {
            if (!values.score) {
                frappe.msgprint(__("Please select a score."));
                return;
            }
            dialog.disable_primary_action();
 
            frappe.call({
                method: "vendor_portal.api.create_vendor_rating_log",
                args: {
                    supplier:       frm.doc.supplier,
                    purchase_order: frm.doc.name,
                    rating_type:    values.rating_type,
                    // Frappe Rating fieldtype returns 0–1; multiply by 5
                    score:          values.score * 5,
                    remarks:        values.remarks || "",
                },
                callback(r) {
                    if (r.message) {
                        frappe.show_alert({ message: __("Rating submitted!"), indicator: "green" }, 4);
                        dialog.hide();
                        setTimeout(() => update_supplier_banner(frm), 400);
                    }
                },
                error() {
                    dialog.enable_primary_action();
                    frappe.msgprint(__("Failed to submit rating. Please try again."));
                }
            });
        }
    });
    dialog.show();
}
 