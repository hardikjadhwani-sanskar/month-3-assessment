// • Add a dashboard section showing: Total POs (count), Total PO Value (sum of grand_total), Avg Rating, Total Ratings.
// • Add custom button "Blacklist Supplier" (visible to Purchase Manager only) that opens a frappe.prompt for reason, then sets is_blacklisted = 1 and saves.
// • Add custom button "View Onboarding" (visible if onboarding_reference is set) that navigates to the linked Vendor Onboarding record.
// • On form refresh, if vendor_rating < low_rating_threshold from settings, show orange indicator: "Low Rating — Review Required".

import frappe from 'frappe';

frappe.ui.form.on('Supplier', {

    refresh: function(frm) {
        // Add "View Onboarding" button if onboarding_reference is set
        if (frm.doc.onboarding_reference) {
            frm.add_custom_button('View Onboarding', function() {
                frappe.set_route('Form', 'Vendor Onboarding', frm.doc.onboarding_reference);
            });
        }
        // Add "Blacklist Supplier" button for Purchase Manager
        if (frappe.user.has_role('Purchase Manager') && !frm.doc.is_blacklisted) {
            frm.add_custom_button('Blacklist Supplier', function() {
                frappe.prompt({
                    fieldname: 'reason',
                    fieldtype: 'Small Text',
                    label: 'Reason for Blacklisting',
                    reqd: 1
                }, function(values) {
                    frappe.db.set_value('Supplier', frm.doc.name, {
                        custom_is_blacklisted: 1,
                        custom_blacklisting_reason: values.reason
                    });
                });
            });
        }
    }
});