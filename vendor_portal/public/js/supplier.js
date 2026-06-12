// • Add a dashboard section showing: Total POs (count), Total PO Value (sum of grand_total), Avg Rating, Total Ratings.
// • Add custom button "Blacklist Supplier" (visible to Purchase Manager only) that opens a frappe.prompt for reason, 
// then sets is_blacklisted = 1 and saves.
// • Add custom button "View Onboarding" (visible if onboarding_reference is set) that navigates to the 
// linked Vendor Onboarding record.
// • On form refresh, if vendor_rating < low_rating_threshold from settings, 
// show orange indicator: "Low Rating — Review Required".

frappe.ui.form.on("Supplier", {

    refresh(frm) {
        _load_supplier_dashboard(frm);

        const roles = frappe.user_roles;
        const is_manager = roles.includes("Purchase Manager") || roles.includes("Vendor Manager");

        // Blacklist button — Purchase Manager only, not already blacklisted
        if (is_manager && !frm.doc.custom_is_blacklisted && !frm.is_new()) {
            frm.add_custom_button(__("Blacklist Supplier"), () => {
                frappe.prompt(
                    [{ fieldname: "reason", fieldtype: "Small Text",
                       label: __("Reason for Blacklisting"), reqd: 1 }],
                    (values) => {
                        frm.set_value("custom_is_blacklisted", 1);
                        frm.set_value("custom_blacklist_reason", values.reason);
                        frm.save().then(() => {
                            frappe.show_alert({
                                message: __("Supplier blacklisted."),
                                indicator: "red"
                            });
                        });
                    },
                    __("Blacklist Supplier"),
                    __("Confirm")
                );
            }, __("Actions"));
        }

        // Remove blacklist button
        if (is_manager && frm.doc.custom_is_blacklisted && !frm.is_new()) {
            frm.add_custom_button(__("Remove Blacklist"), () => {
                frm.set_value("custom_is_blacklisted", 0);
                frm.set_value("custom_blacklist_reason", "");
                frm.save();
            }, __("Actions"));
        }

        // View Onboarding button
        if (frm.doc.custom_onboarding_reference) {
            frm.add_custom_button(__("View Onboarding"), () => {
                frappe.set_route("Form", "Vendor Onboarding", frm.doc.custom_onboarding_reference);
            }, __("Actions"));
        }

        // Low rating indicator
        frappe.call({
            method: "frappe.client.get_single_value",
            args: { doctype: "Vendor Portal Settings", field: "low_rating_threshold" },
            callback(r) {
                const threshold = r.message || 2.5;
                const rating    = frm.doc.custom_vendor_rating || 0;
                if (rating && rating < threshold) {
                    frm.set_intro(
                        __("⚠️ Low Rating — Review Required (Rating: {0}/5)", [flt(rating, 1)]),
                        "orange"
                    );
                }
            }
        });
    },
});


function _load_supplier_dashboard(frm) {
    if (frm.is_new()) return;

    frappe.call({
        method: "vendor_portal.api.get_vendor_dashboard",
        args: { supplier: frm.doc.name },
        callback(r) {
            if (!r.message) return;
            const d = r.message;

            frm.dashboard.add_section(
                `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));
                             gap:12px;padding:8px 0;">
                    ${_stat_card("Total POs",    d.total_pos)}
                    ${_stat_card("PO Value",      frappe.format(d.total_po_value, {fieldtype:"Currency"}))}
                    ${_stat_card("Avg Rating",    flt(d.avg_rating, 1) + "/5")}
                    ${_stat_card("Total Ratings", d.total_ratings)}
                    ${_stat_card("Outstanding",   frappe.format(d.outstanding_amount, {fieldtype:"Currency"}))}
                </div>`,
                __("Vendor Summary")
            );
            frm.dashboard.show();
        }
    });
}


function _stat_card(label, value) {
    return `
        <div style="background:var(--bg-color);border:1px solid var(--border-color);
                    border-radius:8px;padding:12px;text-align:center;">
            <div style="font-size:11px;opacity:.6;text-transform:uppercase;
                        letter-spacing:.05em;margin-bottom:4px;">${label}</div>
            <div style="font-size:20px;font-weight:700;">${value}</div>
        </div>`;
}
