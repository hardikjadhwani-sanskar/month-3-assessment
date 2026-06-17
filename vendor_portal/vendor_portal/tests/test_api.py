import frappe
import unittest
from frappe.exceptions import ValidationError
from frappe.utils import today, add_days, flt


# ─── Shared fixtures ──────────────────────────────────────────────────────────

def get_default_company():
    return frappe.db.get_single_value("Global Defaults", "default_company")


def get_default_warehouse():
    company = get_default_company()
    return frappe.db.get_value(
        "Warehouse",
        {"company": company, "disabled": 0},
        "name"
    )


def get_default_expense_account():
    company = get_default_company()
    return frappe.db.get_value(
        "Account",
        {"company": company, "account_type": "Cost of Goods Sold", "is_group": 0},
        "name"
    )


def make_vendor_category(name="API Test Category", threshold=3.0):
    if frappe.db.exists("Vendor Category", name):
        cat = frappe.get_doc("Vendor Category", name)
        cat.minimum_rating_threshold = threshold
        cat.save(ignore_permissions=True)
        return cat
    return frappe.get_doc({
        "doctype":                  "Vendor Category",
        "category_name":            name,
        "minimum_rating_threshold": threshold,
        "is_active":                1,
    }).insert(ignore_permissions=True)


def make_test_supplier(
    name="API Test Supplier",
    rating=4.0,
    rating_count=0,
    blacklisted=False,
    blacklist_reason="",
    category="API Test Category",
    threshold=3.0,
):
    make_vendor_category(category, threshold)

    existing = frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
    if existing:
        sup_name = existing
    else:
        sup = frappe.get_doc({
            "doctype":        "Supplier",
            "supplier_name":  name,
            "supplier_group": frappe.db.get_value("Supplier Group", {}, "name"),
        })
        sup.insert(ignore_permissions=True)
        sup_name = sup.name

    # db_set bypasses on_update hook — rating won't be recalculated
    frappe.db.set_value("Supplier", sup_name, {
        "custom_vendor_category":    category,
        "custom_vendor_rating":      rating,
        "custom_total_rating_count": rating_count,
        "custom_is_blacklisted":     1 if blacklisted else 0,
        "custom_blacklist_reason":   blacklist_reason,
    })
    frappe.db.commit()

    return frappe.get_doc("Supplier", sup_name)


def make_test_item(code="VP-TEST-ITEM"):
    if frappe.db.exists("Item", code):
        return frappe.get_doc("Item", code)
    return frappe.get_doc({
        "doctype":          "Item",
        "item_code":        code,
        "item_name":        code,
        "item_group":       frappe.db.get_value("Item Group", {}, "name"),
        "stock_uom":        "Nos",
        "is_purchase_item": 1,
    }).insert(ignore_permissions=True)


def make_purchase_order(supplier_name, schedule_date=None, qty=10, rate=100):
    """Creates and returns a saved (not submitted) Purchase Order."""
    supplier = frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
    item     = make_test_item()
    company  = get_default_company()
    wh       = get_default_warehouse()

    effective_date  = schedule_date or today()
 
    po = frappe.get_doc({
        "doctype":         "Purchase Order",
        "supplier":        supplier,
        "transaction_date": effective_date,   # ← keep PO date in sync with schedule_date
        "schedule_date":   effective_date,
        "company":         company,
        "items": [{
            "item_code":     item.name,
            "qty":           qty,
            "rate":          rate,
            "schedule_date": effective_date,
            "warehouse":     wh,
        }],
    })
    po.insert(ignore_permissions=True)
    return po



def make_purchase_receipt(po, accepted_qty=None, posting_date=None):
    """
    Creates a Purchase Receipt against a submitted PO.
    Sets expense_account on each item to handle ERPNext configs
    where the field is mandatory.
    """
    from erpnext.buying.doctype.purchase_order.purchase_order import (
        make_purchase_receipt as _make_pr,
    )

    pr              = frappe.get_doc(_make_pr(po.name))
    pr.posting_date = posting_date or today()
    expense_account = get_default_expense_account()

    for item in pr.items:
        if accepted_qty is not None:
            item.qty          = accepted_qty
            item.received_qty = accepted_qty
            item.rejected_qty = 0
        if expense_account:
            item.expense_account = expense_account

    pr.insert(ignore_permissions=True)
    return pr


def ensure_role(user, role):
    """
    Safely ensure a role is assigned to a user.
    Uses the parent User doc so Frappe's role cache is updated correctly.
    """
    if not frappe.db.exists("Has Role", {"parent": user, "role": role}):
        user_doc = frappe.get_doc("User", user)
        user_doc.append("roles", {"role": role})
        user_doc.save(ignore_permissions=True)


def cleanup_test_suppliers():
    """
    Delete VRL entries, POs, and Supplier records for all known test
    suppliers. Committed immediately so the next test class's setUp
    starts from a genuinely clean database state.
    """
    test_supplier_names = [
        "API Test Supplier",
        "API Test Supplier BL",
        "API Test Supplier LR",
        "API Comp Supplier A",
        "API Comp Supplier B",
    ]
    for s_name in test_supplier_names:
        supplier_id = frappe.db.get_value("Supplier", {"supplier_name": s_name}, "name")
        if not supplier_id:
            continue

        frappe.db.delete("Vendor Rating Log", {"supplier": supplier_id})

        for po_name in frappe.get_all(
            "Purchase Order",
            filters={"supplier": supplier_id},
            pluck="name"
        ):
            try:
                po_doc = frappe.get_doc("Purchase Order", po_name)
                if po_doc.docstatus == 1:
                    po_doc.cancel()
                frappe.delete_doc("Purchase Order", po_name,
                                  ignore_permissions=True, force=True)
            except Exception:
                pass

        frappe.delete_doc("Supplier", supplier_id,
                          ignore_permissions=True, force=True)

 
    frappe.db.commit()


# ─── TestPurchaseOrderOverride ────────────────────────────────────────────────

class TestPurchaseOrderOverride(unittest.TestCase):
    """Tests for CustomPurchaseOrder (override_doctype_class pattern)."""

    def setUp(self):
        frappe.set_user("Administrator")
        cleanup_test_suppliers()
        frappe.db.set_single_value("Vendor Portal Settings", "auto_rating_enabled", 1)
        frappe.db.commit()

    def tearDown(self):
        cleanup_test_suppliers()
        frappe.db.rollback()

    # ── Blacklist checks ──────────────────────────────────────────────────────

    def test_blacklisted_supplier_blocks_po(self):
        """PO creation must be blocked for a blacklisted supplier."""
        supplier = make_test_supplier(
            name="API Test Supplier BL",
            blacklisted=True,
            blacklist_reason="Fraud detected",
            rating_count=0,   # isolate: testing blacklist only
        )
        with self.assertRaises(
            (ValidationError, frappe.exceptions.ValidationError),
            msg="PO creation must be blocked for blacklisted supplier"
        ):
            make_purchase_order(supplier.supplier_name)

    # ── Rating threshold checks ───────────────────────────────────────────────

    def test_low_rating_blocks_po(self):
        """
        Supplier with rating below category threshold AND at least 1
        existing rating must block PO creation.
        """
        supplier = make_test_supplier(
            name="API Test Supplier LR",
            rating=1.5,
            rating_count=3,
            threshold=3.0,
        )
        with self.assertRaises(
            (ValidationError, frappe.exceptions.ValidationError),
            msg="PO must be blocked when supplier rating < category threshold"
        ):
            make_purchase_order(supplier.supplier_name)

    # ── Pricing VRL on PO submit ──────────────────────────────────────────────

    def test_po_submit_creates_pricing_rating(self):
        """
        Submitting a PO must auto-create exactly one Vendor Rating Log
        with rating_type = Pricing.
        """

        frappe.db.set_single_value("Vendor Portal Settings", "auto_rating_enabled", 1)
        supplier = make_test_supplier(
            name="API Test Supplier",
            rating=4.0,
            rating_count=0,
        )
        po = make_purchase_order(supplier.supplier_name)
        po.submit()

        logs = frappe.get_all(
            "Vendor Rating Log",
            filters={"purchase_order": po.name, "rating_type": "Pricing"},
            fields=["name", "score", "supplier"]
        )

        self.assertEqual(len(logs), 1,
                         "Exactly one Pricing VRL must be created on PO submit")
        self.assertIn(logs[0].score, [2.0, 3.0, 4.0, 5.0],
                      "Score must be one of the defined pricing score values")

    # ── PO cancel deletes VRL ─────────────────────────────────────────────────

    def test_po_cancel_deletes_rating(self):
        """Cancelling a PO must delete all linked Vendor Rating Log entries."""
        supplier = make_test_supplier(
            name="API Test Supplier",
            rating=4.0,
            rating_count=0,
        )
        po = make_purchase_order(supplier.supplier_name)
        po.submit()

        before = frappe.get_all("Vendor Rating Log", {"purchase_order": po.name})
        self.assertEqual(len(before), 1, "VRL must exist before cancel")

        po.cancel()

        after = frappe.get_all("Vendor Rating Log", {"purchase_order": po.name})
        self.assertEqual(len(after), 0, "VRL must be deleted after PO cancel")


# ─── TestPurchaseReceiptHook ──────────────────────────────────────────────────

class TestPurchaseReceiptHook(unittest.TestCase):
    """Tests for Purchase Receipt doc_events hook (on_submit delivery scoring)."""

    def setUp(self):
        frappe.set_user("Administrator")
        cleanup_test_suppliers()
        frappe.db.set_single_value("Vendor Portal Settings", "auto_rating_enabled", 1)
        self.supplier = make_test_supplier(
            name="API Test Supplier",
            rating=4.0,
            rating_count=0,
        )
        frappe.db.commit()

    def tearDown(self):
        cleanup_test_suppliers()
        frappe.db.rollback()

    def _submit_pr(self, schedule_date, accepted_qty, posting_date=None):
        """Helper: create PO → submit → create PR → submit → return PR."""
        po = make_purchase_order(
            self.supplier.supplier_name,
            schedule_date=schedule_date,
            qty=10,
        )
        po.submit()
        pr = make_purchase_receipt(
            po,
            accepted_qty=accepted_qty,
            posting_date=posting_date or today(),
        )
        pr.submit()
        return pr

    def test_pr_submit_creates_delivery_rating(self):
        """
        Submitting a PR must create a Vendor Rating Log with
        rating_type = Delivery using the score matrix:
          5 = on-time + full qty  (accepted >= 90% of ordered)
          4 = on-time + short qty (accepted <  90% of ordered)
          3 = late    + full qty
          2 = late    + short qty
        """
        cases = [
            (today(),                10, today(), 5, "on-time full qty → 5"),
            (today(),                 8, today(), 4, "on-time short qty → 4"),
            (add_days(today(), -5), 10, today(), 3, "late full qty → 3"),
            (add_days(today(), -5),  8, today(), 2, "late short qty → 2"),
        ]

        for schedule_date, accepted_qty, posting_date, expected_score, label in cases:
            with self.subTest(label=label):
                pr = self._submit_pr(schedule_date, accepted_qty, posting_date)

                logs = frappe.get_all(
                    "Vendor Rating Log",
                    filters={
                        "purchase_receipt": pr.name,
                        "rating_type":      "Delivery",
                    },
                    fields=["score"]
                )

                self.assertEqual(len(logs), 1,
                                 f"Expected 1 Delivery VRL for case: {label}")
                self.assertEqual(
                    logs[0].score, expected_score,
                    f"{label}: expected score {expected_score}, got {logs[0].score}"
                )

                # Rollback only this iteration's PO/PR.
                # Supplier survives because it was committed in setUp.
                frappe.db.rollback()


# ─── TestVendorRatingAPI ──────────────────────────────────────────────────────

class TestVendorRatingAPI(unittest.TestCase):
    """Tests for vendor_portal.api functions."""

    def setUp(self):
        frappe.set_user("Administrator")
        cleanup_test_suppliers()
        self.supplier = make_test_supplier(
            name="API Test Supplier",
            rating=0,
            rating_count=0,
        )
        frappe.db.delete("Vendor Rating Log", {"supplier": self.supplier.name})
        frappe.db.commit()

    def tearDown(self):
        frappe.db.delete("Vendor Rating Log", {"supplier": self.supplier.name})
        cleanup_test_suppliers()
        frappe.db.rollback()

    # ── Weighted average recalculation ────────────────────────────────────────

    def test_vendor_rating_recalculation(self):
        """
        After inserting multiple VRL entries, _recalculate_supplier_rating()
        must update custom_vendor_rating to the correct weighted average.

        Weights : Delivery=0.3, Quality=0.3, Pricing=0.2, Communication=0.2
        Scores  : Delivery=5,   Quality=3,   Pricing=4,   Communication=4
        Expected: (5×0.3)+(3×0.3)+(4×0.2)+(4×0.2) = 1.5+0.9+0.8+0.8 = 4.0
        """
        from vendor_portal.api import _recalculate_supplier_rating

        frappe.db.set_single_value("Vendor Portal Settings", "rating_weight_delivery",      0.3)
        frappe.db.set_single_value("Vendor Portal Settings", "rating_weight_quality",       0.3)
        frappe.db.set_single_value("Vendor Portal Settings", "rating_weight_pricing",       0.2)
        frappe.db.set_single_value("Vendor Portal Settings", "rating_weight_communication", 0.2)
        frappe.db.commit()

        for rating_type, score in [
            ("Delivery",      5.0),
            ("Quality",       3.0),
            ("Pricing",       4.0),
            ("Communication", 4.0),
        ]:
            frappe.get_doc({
                "doctype":     "Vendor Rating Log",
                "supplier":    self.supplier.name,
                "rating_type": rating_type,
                "score":       score,
                "rating_date": today(),
                "rated_by":    "Administrator",
            }).insert(ignore_permissions=True, ignore_links=True)

        frappe.db.commit()
        _recalculate_supplier_rating(self.supplier.name)

        actual_rating = frappe.db.get_value(
            "Supplier", self.supplier.name, "custom_vendor_rating"
        )
        actual_count = frappe.db.get_value(
            "Supplier", self.supplier.name, "custom_total_rating_count"
        )

        self.assertAlmostEqual(
            flt(actual_rating), 4.0, places=1,
            msg=f"Expected weighted avg 4.0, got {actual_rating}"
        )
        self.assertEqual(actual_count, 4,
                         f"Expected total_rating_count = 4, got {actual_count}")

    # ── Supplier comparison API ───────────────────────────────────────────────

    def test_supplier_comparison_api(self):
        """
        get_supplier_comparison() must return suppliers who supplied the
        item, sorted by vendor_rating descending, with required fields.
        """
        from vendor_portal.api import get_supplier_comparison

        item    = make_test_item("VP-COMP-ITEM")
        company = get_default_company()
        wh      = get_default_warehouse()

        sup_a = make_test_supplier(
            name="API Comp Supplier A",
            rating=4.5,
            rating_count=5,
            threshold=0.0,   # comparison test — disable threshold block
        )
        sup_b = make_test_supplier(
            name="API Comp Supplier B",
            rating=2.5,
            rating_count=3,
            threshold=0.0,   # comparison test — disable threshold block
        )

        for supplier in [sup_a, sup_b]:
            po = frappe.get_doc({
                "doctype":       "Purchase Order",
                "supplier":      supplier.name,
                "schedule_date": today(),
                "company":       company,
                "items": [{
                    "item_code":     item.name,
                    "qty":           5,
                    "rate":          100,
                    "schedule_date": today(),
                    "warehouse":     wh,
                }],
            })
            po.insert(ignore_permissions=True)

            frappe.db.set_single_value(
                "Vendor Portal Settings", "auto_rating_enabled", 0
            )
            po.submit()


        frappe.db.set_value("Supplier", sup_a.name, "custom_vendor_rating", 4.5)
        frappe.db.set_value("Supplier", sup_b.name, "custom_vendor_rating", 2.5)
        frappe.db.commit()

        result = get_supplier_comparison("VP-COMP-ITEM")

        self.assertIsInstance(result, list)
        self.assertGreaterEqual(len(result), 2)

        supplier_names = [r.get("supplier") for r in result]
        self.assertIn(sup_a.name, supplier_names)
        self.assertIn(sup_b.name, supplier_names)

        idx_a = supplier_names.index(sup_a.name)
        idx_b = supplier_names.index(sup_b.name)
        self.assertLess(idx_a, idx_b,
            "Higher-rated supplier must appear first in results")

        first = result[0]
        for field in ["supplier", "supplier_name", "vendor_rating",
                    "avg_rate", "last_rate", "total_supplied_qty"]:
            self.assertIn(field, first, f"Field '{field}' missing from API response")


# ─── TestPermissions ──────────────────────────────────────────────────────────

class TestPermissions(unittest.TestCase):
    """Tests for role-based permission hooks in permissions.py."""

    def setUp(self):
        frappe.set_user("Administrator")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def test_permission_own_ratings_only_write(self):
        """
        A non-Vendor-Manager user must only be able to write
        their own VRL entries (rated_by == current_user).
        """
        from vendor_portal.permissions import has_permission

        doc_other = frappe._dict({
            "doctype":  "Vendor Rating Log",
            "rated_by": "other_user@example.com",
            "name":     "VRL-FAKE-001",
        })
        doc_own = frappe._dict({
            "doctype":  "Vendor Rating Log",
            "rated_by": "purchase_user@example.com",
            "name":     "VRL-FAKE-002",
        })

        test_user = "purchase_user@example.com"

        result_other = has_permission(doc_other, "write", user=test_user)
        self.assertFalse(result_other,
                         "Purchase User must NOT be able to write another user's VRL")

        result_own = has_permission(doc_own, "write", user=test_user)
        self.assertTrue(result_own,
                        "Purchase User must be able to write their own VRL")


if __name__ == "__main__":
    unittest.main()