# Copyright (c) 2026, hardik and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe.model.document import Document
import re

class VendorOnboarding(Document):
	#validate: Validate GST number format (15 characters, 
	# alphanumeric pattern: 2-digit state code + 10-char PAN + 1 entity code + 1 Z + 1 check digit). 
	# Validate PAN format (XXXXX9999X). Validate email format. Validate minimum documents as per Vendor Portal Settings. 
	# Check no existing approved onboarding or active Supplier with the same GST number.
	def validate(self):
		self.validate_gst_number()
		self.validate_pan_number()
		self.validate_email()
		self.validate_documents()
		self.check_existing_onboarding()

	def validate_gst_number(self):
		
		if self.gst_number:
			gst_pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
			if not re.match(gst_pattern, self.gst_number):
				frappe.throw("Invalid GST number format. It should be 15 characters: 2-digit state code + 10-char PAN + 1 entity code + 1 Z + 1 check digit.")
	
	def validate_pan_number(self):
		if self.pan_number:
			pan_pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
			if not re.match(pan_pattern, self.pan_number):
				frappe.throw("Invalid PAN number format. It should be in the format XXXXX9999X.")
	
	def validate_email(self):
		if self.email:
			email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
			if not re.match(email_pattern, self.email):
				frappe.throw("Invalid email format.")
	
	def validate_documents(self):
		required_docs = frappe.get_single("Vendor Portal Settings").min_documents_required # this return a number - minimum required documents like 2
		# check number of uploaded documents against the required number
		if len(self.documents) < required_docs:
			frappe.throw(f"At least {required_docs} documents are required for onboarding.")

	def check_existing_onboarding(self):
		# Check for existing approved onboarding with the same GST number
		existing_onboarding = frappe.get_all("Vendor Onboarding", filters={"gst_number": self.gst_number, "status": "Approved"})
		if existing_onboarding:
			frappe.throw("An approved onboarding already exists with this GST number.")
		
		# Check for active Supplier with the same GST number - there is no GST number and status field in Supplier doctype, 
		#.
		existing_supplier = frappe.get_all("Supplier", filters={"supplier_name": self.supplier_name})
		if existing_supplier:
			frappe.throw("An active Supplier already exists with this GST number.")

	#• on_submit: Set onboarding_status to Under Review - this is handled in workflow.
	def on_submit(self):
		pass


#• Create a whitelisted method 
# approve_onboarding(onboarding_name) that: validates permission (only Purchase Manager role), 
# sets onboarding_status to Approved, 
# auto-creates an ERPNext Supplier record using frappe.get_doc with all mapped fields 
# (supplier_name, supplier_group from settings, vendor_category, address, contact, bank details), 
# links the created Supplier back to the onboarding record (linked_supplier field), sends email notification to vendor.

@frappe.whitelist()
def approve_onboarding(onboarding_name):
	if not frappe.has_role("Purchase Manager"):
		frappe.throw("You do not have permission to approve onboarding.")
	
	onboarding = frappe.get_doc("Vendor Onboarding", onboarding_name)
	onboarding.onboarding_status = "Approved"
	onboarding.save()

	# Create Supplier record
	supplier_group = frappe.get_single("Vendor Portal Settings").default_supplier_group
	supplier = frappe.get_doc({
		"doctype": "Supplier",
		"supplier_name": onboarding.supplier_name,
		"supplier_group": supplier_group,
		"vendor_category": onboarding.vendor_category,
		"gst_number": onboarding.gst_number,
		"pan_number": onboarding.pan_number,
		"email_id": onboarding.email,
		"mobile_no": onboarding.phone,
	})
	supplier.insert() # Insert the new Supplier record into the database
	# Link Supplier to onboarding record
	onboarding.linked_supplier = supplier.name
	onboarding.save()

	# Send email notification to vendor
	frappe.sendmail(
		recipients=onboarding.email,
		subject="Your Vendor Onboarding has been Approved",
		message=f"Dear {onboarding.supplier_name},\n\nYour vendor onboarding has been approved. Your supplier record has been created in our system.\n\nBest regards,\nVendor Management Team"
	)


#Create reject_onboarding(onboarding_name, reason) whitelisted method that sets status to Rejected with reason

@frappe.whitelist()
def reject_onboarding(onboarding_name, reason):
	
	
	onboarding = frappe.get_doc("Vendor Onboarding", onboarding_name)
	onboarding.onboarding_status = "Rejected"
	onboarding.rejection_reason = reason
	onboarding.save()

	