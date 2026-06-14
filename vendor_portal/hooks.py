app_name = "vendor_portal"
app_title = "Vendor Portal"
app_publisher = "hardik"
app_description = "app for vendors"
app_email = "hardik.jadhwani@gmail.com"
app_license = "mit"


fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["dt", "=", "Supplier"]
        ]
    },
    {
        "dt": "Workflow",
        "filters": [
            ["name", "in", ["Vendor Onboarding Approval"]]
        ]
    },
      {
        "dt": "Custom DocPerm"
    },
    {
        "dt": "Role",
        "filters": [
            ["name", "in", [
                "Vendor Manager",
                "Purchase Team"
            ]]
        ]
    },
   

]

override_doctype_class = {
    "Purchase Order": "vendor_portal.overrides.purchase_order.CustomPurchaseOrder"
}

doc_events = {
    "Purchase Receipt": {
        "validate": "vendor_portal.overrides.purchase_receipt.validate",
        "on_submit": "vendor_portal.overrides.purchase_receipt.on_submit"
    }
}

# app_include_js = [
#     "/assets/vendor_portal/js/purchase_order.js",
#     "/assets/vendor_portal/js/purchase_order_list.js",
#     "/assets/vendor_portal/js/supplier.js",
#     "/assets/vendor_portal/js/purchase_invoice.js"
# ]

doctype_js = {
    "Purchase Order": "public/js/purchase_order.js",
    "Supplier": "public/js/supplier.js",
    "Purchase Invoice": "public/js/purchase_invoice.js"
}

doctype_list_js = {
    "Purchase Order": "public/js/purchase_order_list.js"
}

# ─── Permissions ──────────────────────────────────────────────────────────────
has_permission = {
    "Vendor Rating Log":  "vendor_portal.permissions.has_permission",
    "Vendor Onboarding":  "vendor_portal.permissions.has_permission_onboarding",
}

permission_query_conditions = {
    "Vendor Onboarding": "vendor_portal.permissions.get_onboarding_query_conditions",
}


scheduler_events = {
    "daily": [
        "vendor_portal.tasks.auto_calculate_vendor_ratings",
        
    ],
    "hourly": [
        "vendor_portal.tasks.auto_rate_deliveries",
    ],
    "weekly": [
        "vendor_portal.tasks.vendor_performance_digest",
    ],
    "cron": {
        "0 9 * * *": [
            "vendor_portal.tasks.auto_expire_stale_onboardings",
        ]
    },
}


jinja = {

    "filters": [
        "vendor_portal.utils.jinja_filters.rating_to_stars",
    ]
}
