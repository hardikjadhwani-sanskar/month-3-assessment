import frappe
import unittest
from frappe.exceptions import ValidationError



# • test_gst_validation_format: Submit with invalid GST → ValidationError.
# • test_pan_validation_format: Submit with invalid PAN → ValidationError.
# • test_minimum_documents_required: Submit with fewer docs than min_documents_required → ValidationError.
# • test_approve_creates_supplier: Approve onboarding → assert Supplier record created with correct fields.
# • test_reject_sets_reason: Reject with reason → assert status = Rejected and reason saved.
# • test_duplicate_gst_blocked: Submit two onboardings with same GST → second blocked.



# ─── Shared test data factory ─────────────────────────────────────────────────

def make_vendor_category(name="Test Category VO"):
    if frappe.db.exists("Vendor Category", name):
        return frappe.get_doc("Vendor Category", name)
    doc = frappe.get_doc({
        "doctype":                  "Vendor Category",
        "category_name":            name,
        "minimum_rating_threshold": 3.0,
        "is_active":                1,
    })
    doc.insert(ignore_permissions=True)
    return doc


def make_onboarding(**overrides):
    """
    Returns an unsaved Vendor Onboarding doc with valid defaults.
    Pass overrides to selectively replace any field.
    """
    make_vendor_category()

    # Ensure min_documents_required = 0 so tests that
    # don't care about documents don't fail on that check.
    frappe.db.set_single_value("Vendor Portal Settings", "min_documents_required", 0)

    data = {
        "doctype":         "Vendor Onboarding",
        "supplier_name":   "Test Vendor Co",
        "company_name":    "Test Vendor Pvt Ltd",
        "email":           "vendor@testco.com",
        "phone":           "9876543210",
        "gst_number":      "27AAAAA0000A1Z5",
        "pan_number":      "AAAAA0000A",
        "vendor_category": "Test Category VO",
        "address_line_1":  "123 Test Lane",
        "city":            "Mumbai",
        "state":           "Maharashtra",
        "pincode":         "400001",
    }
    data.update(overrides)
    return frappe.get_doc(data)


def cleanup_onboardings(emails=None):
    """
    Delete all test onboarding records for the given email(s)
    and any linked Supplier records.
    """
    if emails is None:
        emails = ["vendor@testco.com", "vendor1@testco.com"]

    for email in emails:
        for name in frappe.get_all(
            "Vendor Onboarding",
            filters={"email": email},
            pluck="name"
        ):
            linked = frappe.db.get_value("Vendor Onboarding", name, "linked_supplier")
            if linked and frappe.db.exists("Supplier", linked):
                frappe.delete_doc("Supplier", linked, ignore_permissions=True, force=True)
            onboarding = frappe.get_doc("Vendor Onboarding", name)
            if(onboarding.docstatus == 1):  # Submitted
                onboarding.cancel()
            frappe.delete_doc("Vendor Onboarding", name, ignore_permissions=True, force=True)


def ensure_role(user, role):
    """
    Safely ensure a role is assigned to a user without stale-cache issues.
    Uses the parent User doc so Frappe's role cache is updated correctly.
    """
    if not frappe.db.exists("Has Role", {"parent": user, "role": role}):
        user_doc = frappe.get_doc("User", user)
        user_doc.append("roles", {"role": role})
        user_doc.save(ignore_permissions=True)


# ─── Test class ───────────────────────────────────────────────────────────────

class TestVendorOnboarding(unittest.TestCase):

    # ── setUp / tearDown ──────────────────────────────────────────────────────

    def setUp(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()   # discard any uncommitted residue from prior test
        cleanup_onboardings()

    def tearDown(self):
        cleanup_onboardings()
        frappe.db.set_single_value("Vendor Portal Settings", "min_documents_required", 2)
        frappe.db.commit()

    # ── GST validation ────────────────────────────────────────────────────────

    def test_gst_validation_format(self):
        """Invalid GST number must raise ValidationError on save."""
        invalid_gsts = [
            "INVALIDGST",         # completely wrong
            "27AAAAA0000A1Z",     # 14 chars — too short
            "27aaaaa0000a1z5",    # lowercase — wrong
            "27-AAAA-0000-A1Z5", # has hyphens
            "27AAAAA0000A1Z55",   # 16 chars — too long
        ]

        for gst in invalid_gsts:
            with self.subTest(gst=gst):
                doc = make_onboarding(gst_number=gst)
                with self.assertRaises(
                    (ValidationError, frappe.exceptions.ValidationError),
                    msg=f"Expected ValidationError for GST: '{gst}'"
                ):
                    doc.insert(ignore_permissions=True)
                frappe.db.rollback()


    # ── PAN validation ────────────────────────────────────────────────────────

    def test_pan_validation_format(self):
        """Invalid PAN number must raise ValidationError on save."""
        invalid_pans = [
            "INVALIDPAN",   # completely wrong
            "AAAA00000A",   # 4 letters instead of 5 at start
            "AAAAA000A",    # 3 digits instead of 4
            "aaaaa0000a",   # lowercase
            "AAAAA0000",    # missing last letter
            "12345678901",  # all digits
        ]

        for pan in invalid_pans:
            with self.subTest(pan=pan):
                doc = make_onboarding(pan_number=pan)
                with self.assertRaises(
                    (ValidationError, frappe.exceptions.ValidationError),
                    msg=f"Expected ValidationError for PAN: '{pan}'"
                ):
                    doc.insert(ignore_permissions=True)
                frappe.db.rollback()


    # ── Document count validation ─────────────────────────────────────────────

    def test_minimum_documents_required(self):
        """
        When min_documents_required = 2 and vendor attaches 0 docs,
        save must raise ValidationError.
        """
        
        doc = make_onboarding()
        frappe.db.set_single_value("Vendor Portal Settings", "min_documents_required", 2)
        with self.assertRaises(
            (ValidationError, frappe.exceptions.ValidationError)
        ):
            doc.insert(ignore_permissions=True)

    # ── approve_onboarding() ──────────────────────────────────────────────────

    def test_approve_creates_supplier(self):
        """
        Calling approve_onboarding() must:
        1. Return the new Supplier name
        2. Create a Supplier with supplier_name and custom_vendor_category
        3. Set linked_supplier and onboarding_status = Approved on the onboarding

        Aligns to production code which:
        - returns supplier.name  (was None in original)
        - sets custom_vendor_category  (was vendor_category in original)
        - sets reviewed_by via frappe.session.user
        """
        from vendor_portal.vendor_portal.doctype.vendor_onboarding.vendor_onboarding import (
            approve_onboarding,
        )

        sg = frappe.db.get_value("Supplier Group", {}, "name")
        frappe.db.set_single_value("Vendor Portal Settings", "default_supplier_group", sg)
        ensure_role("Administrator", "Purchase Manager")

        doc = make_onboarding()
        doc.insert(ignore_permissions=True)
        doc.submit()
        doc.db_set("onboarding_status", "Under Review")

        # approve_onboarding now returns supplier.name
        supplier_name = approve_onboarding(doc.name)

        # 1. Return value must be a non-empty string
        self.assertIsNotNone(supplier_name,
                             "approve_onboarding must return the supplier name, not None")
        self.assertIsInstance(supplier_name, str)

        # 2. Supplier record must exist with correct fields
        self.assertTrue(
            frappe.db.exists("Supplier", supplier_name),
            f"Supplier '{supplier_name}' was not created in the database"
        )
        supplier = frappe.get_doc("Supplier", supplier_name)
        self.assertEqual(
            supplier.supplier_name, doc.supplier_name,
            "Supplier.supplier_name must match onboarding.supplier_name"
        )
        self.assertEqual(
            supplier.custom_vendor_category, doc.vendor_category,
            "Supplier.custom_vendor_category must match onboarding.vendor_category"
        )

        # 3. Onboarding must be updated
        doc.reload()
        self.assertEqual(doc.onboarding_status, "Approved")
        self.assertEqual(doc.linked_supplier, supplier_name)

    # ── reject_onboarding() ───────────────────────────────────────────────────

    def test_reject_sets_reason(self):
        """
        Calling reject_onboarding() with a reason must:
        1. Set onboarding_status = Rejected
        2. Set rejection_reason = provided reason
        """
        from vendor_portal.vendor_portal.doctype.vendor_onboarding.vendor_onboarding import (
            reject_onboarding,
        )

        doc = make_onboarding()
        doc.insert(ignore_permissions=True)
        doc.submit()
        doc.db_set("onboarding_status", "Under Review")

        rejection_reason = "Incomplete documentation and unverified GST."
        reject_onboarding(doc.name, rejection_reason)

        doc.reload()
        self.assertEqual(doc.onboarding_status, "Rejected")
        self.assertEqual(doc.rejection_reason, rejection_reason)


    # ── Duplicate GST check ───────────────────────────────────────────────────

    def test_duplicate_gst_blocked(self):
        """
        A second onboarding with the same GST where the first is Approved
        must be blocked on save by check_existing_onboarding().

        Uses addCleanup() immediately after insert so doc1 is always
        deleted even if an assertion fails mid-test.
        """
        gst = "27AAAAA0000A1Z5"

        doc1 = make_onboarding(gst_number=gst, email="vendor1@testco.com")
        doc1.insert(ignore_permissions=True)
        self.addCleanup(
            frappe.delete_doc,
            "Vendor Onboarding", doc1.name,
            ignore_permissions=True, force=True
        )

        doc1.db_set("onboarding_status", "Approved")

        doc2 = make_onboarding(
            gst_number=gst,
            email="vendor@testco.com",
            supplier_name="Another Vendor"
        )
        with self.assertRaises(
            (ValidationError, frappe.exceptions.ValidationError),
            msg="Should block second onboarding with same GST as an approved record"
        ):
            doc2.insert(ignore_permissions=True)


if __name__ == "__main__":
    unittest.main()