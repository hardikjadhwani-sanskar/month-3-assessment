# Copyright (c) 2026, hardik and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe.model.document import Document


class VendorRatingLog(Document):
	
	def validate(self):
		# Ensure that the rating is between 1 and 5
		if self.score < 1 or self.score > 5:
			frappe.throw("Rating must be between 1 and 5.")
