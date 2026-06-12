# vendor_portal/permissions.py
"""
Role-based permission hooks for Vendor Portal.
Registered in hooks.py under has_permission and permission_query_conditions.
"""

import frappe


def has_permission(doc, ptype, user=None):
    """
    Vendor Rating Log permissions:
    - Vendor Manager: full access to all ratings
    - Others: can only edit their own ratings (rated_by = current user)
    """
    user = user or frappe.session.user
    roles = frappe.get_roles(user)

    if "Vendor Manager" in roles or "System Manager" in roles:
        return True

    if ptype in ("write", "delete"):
        # Can only edit own ratings
        return doc.get("rated_by") == user

    return True  # read is open to all with doctype permission


def has_permission_onboarding(doc, ptype, user=None):
    """
    Vendor Onboarding permissions:
    - Vendor Manager: full access
    - Purchase Team: can only see/edit their own submissions
    """
    user = user or frappe.session.user
    roles = frappe.get_roles(user)

    if "Vendor Manager" in roles or "System Manager" in roles:
        return True

    if ptype in ("write", "delete", "read"):
        return doc.get("owner") == user

    return False


def get_onboarding_query_conditions(user=None):
    """
    permission_query_conditions for Vendor Onboarding list view.
    Vendor Manager: sees all records.
    Purchase Team: sees only their own submissions.
    """
    user = user or frappe.session.user
    roles = frappe.get_roles(user)

    if "Vendor Manager" in roles or "System Manager" in roles:
        return ""  # No filter — see all

    # Purchase Team: only own records
    return f"`tabVendor Onboarding`.owner = {frappe.db.escape(user)}"