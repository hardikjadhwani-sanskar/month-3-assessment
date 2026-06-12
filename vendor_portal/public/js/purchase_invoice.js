

// Hook into Purchase Invoice’s refresh event via your app_include_js. When PI is loaded, check 
// if the supplier’s vendor_rating < 3. If so, add a comment-style banner:
//  "Note: This supplier has a low vendor rating ({rating}/5). Consider reviewing vendor performance."



frappe.ui.form.on("Purchase Invoice", {

    refresh(frm) {
        if (!frm.doc.supplier) return;

        frappe.db.get_value(
            "Supplier",
            frm.doc.supplier,
            ["custom_vendor_rating", "custom_total_rating_count"]
        ).then(r => {
            const d = r.message;
            if (!d || !d.custom_vendor_rating) return;

            const rating = flt(d.custom_vendor_rating, 1);
            if (rating < 3) {
                frm.dashboard.set_headline_alert(
                    `<div style="color:var(--text-color);">
                        ℹ️ Note: This supplier has a low vendor rating
                        (<strong>${rating}/5</strong>). Consider reviewing vendor performance.
                    </div>`,
                    "orange"
                );
            }
        });
    },
});