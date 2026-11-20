frappe.query_reports["Refills Due"] = {
	filters: [
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Pharmacy Branch" },
		{ fieldname: "status", label: __("Status"), fieldtype: "Select", options: ["", "Overdue", "Due Soon", "Upcoming", "Not Started"] },
	],
};
