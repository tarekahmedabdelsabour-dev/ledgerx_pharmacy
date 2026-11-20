# LedgerX Pharmacy

A pharmacy-chain app for LedgerX: many branches with a central store, batch and expiry control, insurance and chronic patients, controlled drugs and smart purchasing. It adds no parallel stock or accounts: every sale is a real Sales Invoice, every transfer a real Stock Entry, every purchase a real Purchase Order, so the existing Stock, Accounts, HR, CRM and Operations Research modules work on pharmacy data unchanged.

## What it does

- **Branches and central store**: each branch has its own warehouse, cost center, price list, license and manager; one or more branches are marked central. Reports and purchasing count any set of branches together.
- **Medicines**: extra fields on the Item (class, active ingredient, strength, form, public price, refrigerated). A pharmacy product is automatically batch and expiry tracked. The public price is kept in the public price list.
- **Dispense**: scan or pick items, the price comes from the public price list, batches are chosen first-expiry-first-out and an expired batch is never sold. Submitting creates the Sales Invoice (stock out), the Payment Entry for what the patient pays and a Journal Entry that moves the insurer's share to the insurance company's account.
- **Insurance**: insurance companies (each with its own customer account) and plans: percentage paid by the insurer, a cap and a minimum for the patient, cosmetics and supplements not covered. The Insurance Receivable report ages what each insurer owes (payments settle the oldest bills first).
- **Controlled drugs**: a sale needs prescription number, doctor and the patient's national ID (any invoice, also from the normal POS). Every sale is written to a read-only log with the balance left; the Controlled Drug Register report prints it.
- **Transfers**: between branches (with a button that fills what the receiving branch needs and the sender can spare), move expired stock to the quarantine warehouse, or write it off.
- **Purchasing**: supplier offers (price, discount, minimum quantity, "buy 10 get 1 free", validity). The purchase plan counts stock, orders on the way and recent sales of the chosen branches, proposes quantities rounded to the pack, picks the cheapest effective offer per item and creates one draft Purchase Order per supplier.
- **Chronic patients**: refill plans (medicine, quantity, every N days); the status moves with time, a daily task reminds the branch manager, and every dispense updates the plan.
- **Reports**: Expiry, Drug Alternatives (same active ingredient, price, stock), Branch Performance, Controlled Drug Register, Insurance Receivable, Refills Due.

## Connections to the rest of LedgerX

Stock, Accounts (invoices, payments, journal entries), Buying, HR (branch manager is an Employee), CRM/Customers (patients are customers), POS and barcode label printing of the core app, and Operations Research (reorder, distribution and route plans read the same warehouses and items).

## Install

See `docs/INSTALL.md`.

## Honest limits

The calculations (first-expiry-first-out, insurance split, order quantities, offers, aging, refill dates) are covered by unit tests. The parts that talk to the database (creating invoices, payments, stock entries, purchase orders) were written against the ERPNext v16 source but have not yet been run on a live site: run the first-day checklist in `docs/INSTALL.md`.
