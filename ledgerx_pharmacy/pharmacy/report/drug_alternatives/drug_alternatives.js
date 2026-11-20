frappe.query_reports["Drug Alternatives"] = {
	filters: [
		{ fieldname: "item", label: __("Item"), fieldtype: "Link", options: "Item", get_query: () => ({ filters: { ph_is_drug: 1 } }) },
		{ fieldname: "active_ingredient", label: __("Active Ingredient"), fieldtype: "Link", options: "Active Ingredient" },
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Pharmacy Branch" },
		{ fieldname: "only_in_stock", label: __("Only What Is in Stock"), fieldtype: "Check", default: 1 },
	],
};
