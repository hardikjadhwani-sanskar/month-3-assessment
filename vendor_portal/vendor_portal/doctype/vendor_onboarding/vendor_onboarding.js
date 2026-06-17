
// • Add custom buttons "Approve" and "Reject" (visible to Purchase Manager when status = Under Review) 
// that call the respective whitelisted APIs.
// • On selecting vendor_category, auto-fetch and display the minimum_rating_threshold.
// • Validate GST format on client side before save (redundant with server, but better UX).
// • Show a progress indicator for documents: "2 of 3 documents verified" based on child table is_verified status.



frappe.ui.form.on("Vendor Onboarding", {

    refresh(frm) {
        const roles = frappe.user_roles;
        const is_manager = roles.includes("Purchase Manager") || roles.includes("Vendor Manager");

        // Approve / Reject buttons — Purchase Manager, Under Review only
        if (is_manager && frm.doc.onboarding_status === "Under Review" && frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Approve"), () => {
                frappe.confirm(
                    __("Are you sure you want to approve this vendor onboarding?"),
                    () => {
                        frappe.call({
                            method: "vendor_portal.vendor_portal.doctype.vendor_onboarding.vendor_onboarding.approve_onboarding",
                            args: { onboarding_name: frm.doc.name },
                            callback(r) {
                                if (r.message) {
                                    frappe.show_alert({
                                        message: __("Vendor approved! Supplier {0} created.", [r.message]),
                                        indicator: "green"
                                    });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }, __("Actions"));

            frm.add_custom_button(__("Reject"), () => {
                frappe.prompt(
                    [{ fieldname: "reason", fieldtype: "Small Text",
                       label: __("Rejection Reason"), reqd: 1 }],
                    (values) => {
                        frappe.call({
                            method: "vendor_portal.vendor_portal.doctype.vendor_onboarding.vendor_onboarding.reject_onboarding",
                            args: {
                                onboarding_name: frm.doc.name,
                                reason: values.reason
                            },
                            callback() {
                                frappe.show_alert({
                                    message: __("Onboarding rejected."),
                                    indicator: "red"
                                });
                                frm.reload_doc();
                            }
                        });
                    },
                    __("Reject Vendor Onboarding"),
                    __("Reject")
                );
            }, __("Actions"));
        }

        // Document verification progress
        _show_document_progress(frm);
    },

    vendor_category(frm) {
        if (!frm.doc.vendor_category) return;
        frappe.db.get_value(
            "Vendor Category",
            frm.doc.vendor_category,
            "minimum_rating_threshold",
            (r) => {
                if (r && r.minimum_rating_threshold) {
                    frappe.show_alert({
                        message: __("Minimum rating threshold for this category: {0}", [
                            r.minimum_rating_threshold
                        ]),
                        indicator: "blue"
                    }, 5);
                }
            }
        );
    },

    gst_number(frm) {
        // Client-side GST validation (UX only — server also validates)
        const gst = frm.doc.gst_number || "";
        if (!gst) return;
        const pattern = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
        if (!pattern.test(gst)) {
            frappe.show_alert({
                message: __("Invalid GST format. Expected: 22AAAAA0000A1Z5"),
                indicator: "orange"
            }, 4);
        }
    },
});


function _show_document_progress(frm) {
    const docs   = frm.doc.documents || [];
    const total  = docs.length;
    const verified = docs.filter(d => d.is_verified).length;

    if (total === 0) return;

    const pct   = Math.round((verified / total) * 100);
    const color = pct === 100 ? "green" : pct >= 50 ? "orange" : "red";

    frm.dashboard.add_progress(
        __("{0} of {1} documents verified", [verified, total]),
        pct,
        color
    );
}