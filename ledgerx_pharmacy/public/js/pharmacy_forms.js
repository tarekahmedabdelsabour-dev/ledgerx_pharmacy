(function () {
	const ROW = "Dispense Item";

	async function fill_row(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code || !frm.doc.branch) return;
		const r = await frappe.call({ method: "ledgerx_pharmacy.api.item_details", args: { item_code: row.item_code, branch: frm.doc.branch, uom: row.uom || null } });
		const d = r.message;
		if (!d) return;
		await frappe.model.set_value(cdt, cdn, { item_name: d.item_name, uom: d.uom, conversion_factor: d.conversion_factor, price: d.price, klass: d.klass, is_controlled: d.is_controlled });
		if (d.is_controlled) frappe.show_alert({ message: __("{0} is a controlled drug: prescription number, doctor and patient ID are required.", [d.item_name]), indicator: "orange" }, 8);
		if (d.sellable <= 0) frappe.show_alert({ message: __("{0}: nothing sellable in this branch (expired stock is never sold).", [d.item_name]), indicator: "red" }, 8);
		else if (d.status === "Critical" || d.status === "Near Expiry")
			frappe.show_alert({ message: __("{0}: nearest expiry {1} ({2} days left). Sellable: {3}", [d.item_name, d.nearest_expiry, d.days_left, d.sellable]), indicator: "orange" }, 8);
		else frappe.show_alert({ message: __("{0}: sellable {1}", [d.item_name, d.sellable]), indicator: "green" }, 4);
		line_amount(frm, cdt, cdn);
	}

	function line_amount(frm, cdt, cdn) {
		const r = locals[cdt][cdn];
		const amount = flt(r.price) * flt(r.qty) * (1 - Math.min(Math.max(flt(r.discount_pct), 0), 100) / 100);
		frappe.model.set_value(cdt, cdn, "amount", flt(amount, 2));
		preview(frm);
	}

	let timer = null;
	function preview(frm) {
		clearTimeout(timer);
		timer = setTimeout(async () => {
			const items = (frm.doc.items || []).filter((r) => r.item_code).map((r) => ({ price: r.price, qty: r.qty, discount_pct: r.discount_pct, covered: r.covered, klass: r.klass }));
			if (!items.length) return;
			const r = await frappe.call({ method: "ledgerx_pharmacy.api.split_preview", args: { items, plan: frm.doc.insurance_plan || null } });
			if (!r.message) return;
			frm.set_value({ gross_total: r.message.gross, insurer_share: r.message.insurer, patient_share: r.message.patient });
		}, 300);
	}

	frappe.ui.form.on("Pharmacy Dispense", {
		setup(frm) {
			frm.set_query("insurance_plan", () => ({ filters: { active: 1 } }));
			frm.set_query("item_code", "items", () => ({ filters: { is_stock_item: 1, disabled: 0 } }));
		},
		onload(frm) {
			if (frm.is_new() && !frm.doc.branch) {
				frappe.db.get_list("Pharmacy Branch", { filters: { active: 1 }, fields: ["name"], limit: 2 }).then((rows) => rows.length === 1 && frm.set_value("branch", rows[0].name));
			}
		},
		refresh(frm) {
			if (frm.doc.docstatus === 0) frm.get_field("scan_barcode") && frm.set_df_property("scan_barcode", "hidden", 0);
			if (frm.doc.docstatus === 1 && frm.doc.customer) {
				frm.add_custom_button(__("Refill Plan"), () => frappe.new_doc("Refill Plan", { customer: frm.doc.customer, branch: frm.doc.branch, item_code: (frm.doc.items[0] || {}).item_code }), __("Create"));
			}
		},
		customer(frm) {
			if (!frm.doc.customer) return;
			frappe.db.get_value("Customer", frm.doc.customer, ["ph_insurance_plan", "ph_member_no", "ph_national_id"]).then((r) => {
				const v = r.message || {};
				if (v.ph_insurance_plan && !frm.doc.insurance_plan) frm.set_value("insurance_plan", v.ph_insurance_plan);
				if (v.ph_member_no && !frm.doc.member_no) frm.set_value("member_no", v.ph_member_no);
				if (v.ph_national_id) frm.set_value("patient_id", v.ph_national_id);
			});
		},
		insurance_plan: preview,
		async scan_barcode(frm) {
			const code = frm.doc.scan_barcode;
			if (!code) return;
			const r = await frappe.call({ method: "ledgerx_pharmacy.api.item_by_barcode", args: { code } });
			frm.set_value("scan_barcode", "");
			if (!r.message) return frappe.show_alert({ message: __("No item has barcode {0}", [code]), indicator: "red" }, 6);
			const existing = (frm.doc.items || []).find((x) => x.item_code === r.message);
			if (existing) return frappe.model.set_value(existing.doctype, existing.name, "qty", flt(existing.qty) + 1);
			const row = frm.add_child("items", { item_code: r.message, qty: 1 });
			frm.refresh_field("items");
			fill_row(frm, row.doctype, row.name);
		},
	});

	frappe.ui.form.on(ROW, {
		item_code(frm, cdt, cdn) { fill_row(frm, cdt, cdn); },
		uom(frm, cdt, cdn) { fill_row(frm, cdt, cdn); },
		qty: line_amount,
		price: line_amount,
		discount_pct: line_amount,
		covered(frm) { preview(frm); },
		items_remove(frm) { preview(frm); },
	});

	frappe.ui.form.on("Pharmacy Transfer", {
		setup(frm) {
			frm.set_query("item_code", "items", () => ({ filters: { is_stock_item: 1, disabled: 0 } }));
		},
		refresh(frm) {
			if (frm.doc.docstatus !== 0) return;
			const add = (rows) => {
				if (!rows || !rows.length) return frappe.show_alert({ message: __("Nothing to add"), indicator: "blue" });
				rows.forEach((r) => frm.add_child("items", r));
				frm.refresh_field("items");
				frm.dirty();
			};
			if (frm.doc.transfer_type === "Branch Transfer" && frm.doc.from_branch && frm.doc.to_branch) {
				frm.add_custom_button(__("Fill from What the Branch Needs"), () =>
					frappe.call({ method: "ledgerx_pharmacy.pharmacy.doctype.pharmacy_transfer.pharmacy_transfer.needs_rows", args: { from_branch: frm.doc.from_branch, to_branch: frm.doc.to_branch }, freeze: true }).then((r) => add(r.message)),
					__("Get Items"));
			}
			if (frm.doc.transfer_type !== "Branch Transfer" && frm.doc.from_branch) {
				frm.add_custom_button(__("Fill from Expired Batches"), () =>
					frappe.prompt({ fieldname: "within_days", label: __("Also include batches expiring within (days)"), fieldtype: "Int", default: 0 }, (v) =>
						frappe.call({ method: "ledgerx_pharmacy.pharmacy.doctype.pharmacy_transfer.pharmacy_transfer.expired_rows", args: { from_branch: frm.doc.from_branch, within_days: v.within_days }, freeze: true }).then((r) => add(r.message)),
						__("Expired Batches")), __("Get Items"));
			}
		},
	});

	// Decision analysis from the branch: opens the Operations Research plans filled with this branch
	frappe.ui.form.on("Pharmacy Branch", {
		refresh(frm) {
			if (frm.is_new()) return;
			if (frappe.model.can_create("Reorder Plan")) {
				frm.add_custom_button(__("Reorder Plan for This Branch"), () =>
					frappe.new_doc("Reorder Plan", { company: frm.doc.company, warehouse: frm.doc.warehouse }), __("Analysis"));
			}
			if (frappe.model.can_create("Distribution Plan")) {
				frm.add_custom_button(__("Distribution Plan for Branch Needs"), () =>
					frappe.new_doc("Distribution Plan", { company: frm.doc.company, include_branch_needs: 1 }), __("Analysis"));
			}
		},
	});

	frappe.ui.form.on("Pharmacy Purchase Plan", {
		refresh(frm) {
			if (frm.is_new()) return;
			if (frm.doc.status !== "Ordered") {
				frm.add_custom_button(__("Load Needs"), () => frm.call({ doc: frm.doc, method: "load_needs", freeze: true, freeze_message: __("Counting stock and sales...") }).then((r) => { frm.reload_doc(); frappe.show_alert({ message: __("{0} items need ordering", [r.message || 0]), indicator: "green" }); }), __("Plan")).addClass("btn-primary");
			}
			if (frm.doc.status === "Loaded" && (frm.doc.rows || []).length) {
				frm.add_custom_button(__("Create Purchase Orders"), () => frappe.confirm(__("Create one draft purchase order per supplier for the ticked rows?"), () => frm.call({ doc: frm.doc, method: "create_orders", freeze: true }).then(() => frm.reload_doc())), __("Plan"));
			}
		},
	});
})();
