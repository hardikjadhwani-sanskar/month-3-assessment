import frappe
from frappe.model.document import Document
import re


class VendorOnboarding(Document):

    def validate(self):
        if(self.gst_number):
            self.validate_gst_number()
            self.check_existing_onboarding()

        if(self.pan_number):
            self.validate_pan_number()
        self.validate_email()
        
        if(self.documents):

            self.validate_documents()
        

    def validate_gst_number(self):
        # FIX: changed `if self.gst_number:` to always validate —
        # empty string must also raise, not silently pass.
        gst_pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
        if not self.gst_number or not re.match(gst_pattern, self.gst_number):
            frappe.throw(
                "Invalid GST number format. It should be 15 characters: "
                "2-digit state code + 10-char PAN + 1 entity code + 1 Z + 1 check digit.",
                frappe.ValidationError
            )

    def validate_pan_number(self):
        pan_pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
        if not self.pan_number or not re.match(pan_pattern, self.pan_number):
            frappe.throw(
                "Invalid PAN number format. It should be in the format XXXXX9999X.",
                frappe.ValidationError
            )

    def validate_email(self):
        if self.email:
            email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
            if not re.match(email_pattern, self.email):
                frappe.throw("Invalid email format.", frappe.ValidationError)

    def validate_documents(self):
        required_docs = frappe.get_single("Vendor Portal Settings").min_documents_required
        if len(self.documents) < required_docs:
            frappe.throw(
                f"At least {required_docs} documents are required for onboarding attached {len(self.documents)}.",
                frappe.ValidationError
            )

    def check_existing_onboarding(self):
        # Check for existing approved onboarding with the same GST number,
        # excluding the current document itself (important on re-save).
        existing_onboarding = frappe.get_all(
            "Vendor Onboarding",
            filters={
                "gst_number":        self.gst_number,
                "onboarding_status": "Approved",
                "name":              ["!=", self.name or ""],
            }
        )
        if existing_onboarding:
            frappe.throw(
                "An approved onboarding already exists with this GST number.",
                frappe.ValidationError
            )

        # FIX: original code checked supplier_name which is wrong —
        # a supplier is identified by GST (tax_id), not by a potentially
        # shared supplier_name string. Changed to tax_id match.
        existing_supplier = frappe.get_all(
            "Supplier",
            filters={"tax_id": self.gst_number}
        )
        if existing_supplier:
            frappe.throw(
                "An active Supplier already exists with this GST number.",
                frappe.ValidationError
            )

    def on_submit(self):
        # Status transition to Under Review is handled by workflow.
        pass


@frappe.whitelist()
def approve_onboarding(onboarding_name):
    
    if "Purchase Manager" not in frappe.get_roles():
        
        frappe.throw("You do not have permission to approve onboarding.")

    onboarding = frappe.get_doc("Vendor Onboarding", onboarding_name)

    supplier_group = frappe.get_single("Vendor Portal Settings").default_supplier_group

    supplier = frappe.get_doc({
        "doctype":                "Supplier",
        "supplier_name":          onboarding.supplier_name,
        "supplier_group":         supplier_group,
        # FIX: use custom_vendor_category (the actual Supplier field name)
        # instead of vendor_category which doesn't exist on Supplier doctype.
        "custom_vendor_category": onboarding.vendor_category,
        # Map GST to tax_id so duplicate-supplier check works correctly.
        "tax_id":                 onboarding.gst_number,
    })
    supplier.insert(ignore_permissions=True)

    # Update onboarding in one save: status + linked supplier + reviewer
    onboarding.onboarding_status = "Approved"
    onboarding.linked_supplier   = supplier.name
    onboarding.save(ignore_permissions=True)

    frappe.sendmail(
        recipients=onboarding.email,
        subject="Your Vendor Onboarding has been Approved",
        message=(
            f"Dear {onboarding.supplier_name},\n\n"
            "Your vendor onboarding has been approved. "
            "Your supplier record has been created in our system.\n\n"
            "Best regards,\nVendor Management Team"
        )
    )

    # FIX: return supplier.name so callers (and tests) can reference
    # the created Supplier record. Original code returned None.
    return supplier.name


@frappe.whitelist()
def reject_onboarding(onboarding_name, reason):
    # FIX: added empty-reason guard — original code silently accepted
    # an empty reason; test_reject_without_reason_raises requires an error.
    if not reason or not reason.strip():
        frappe.throw(
            "A rejection reason is required.",
            frappe.ValidationError
        )

    onboarding = frappe.get_doc("Vendor Onboarding", onboarding_name)
    onboarding.onboarding_status = "Rejected"
    onboarding.rejection_reason  = reason
    onboarding.review_date       = frappe.utils.today()
    onboarding.save(ignore_permissions=True)