// • Override the default list columns for Purchase Order list view: add supplier_name, grand_total, per_received, status.


frappe.listview_settings['Purchase Order'] = {
    add_fields: ['supplier_name', 'grand_total', 'per_received', 'status'],
    get_indicator: function(doc) {
        if (doc.status === 'Closed') {
            return [__('Closed'), 'green', 'status,=,Closed'];
        }
        else if (doc.status === 'To Receive and Bill') {
            return [__('To Receive and Bill'), 'orange', 'status,=,To Receive and Bill'];
        }
        else if (doc.status === 'To Receive') {
            return [__('To Receive'), 'blue', 'status,=,To Receive'];
        }
        else if (doc.status === 'To Bill') {
            return [__('To Bill'), 'purple', 'status,=,To Bill'];
        }
        else {
            return [__(doc.status), 'grey', 'status,=,' + doc.status];
        }
    }
};