# Install

```
cd ~/frappe-bench-v16
git clone <repo-url> apps/ledgerx_pharmacy
printf '\nledgerx_pharmacy\n' >> sites/apps.txt
./env/bin/pip install -e apps/ledgerx_pharmacy
ln -sfn ~/frappe-bench-v16/apps/ledgerx_pharmacy/ledgerx_pharmacy/public sites/assets/ledgerx_pharmacy
bench --site mysite.localhost install-app ledgerx_pharmacy
bench --site mysite.localhost migrate
bench --site mysite.localhost clear-cache
```

Then restart everything and hard-refresh the browser.

## First-day checklist (do these in order)

1. Pharmacy Settings: company, public price list, walk-in customer (created automatically).
2. Pharmacy Branch: one per branch (and the central store) with its warehouse, and a quarantine warehouse for expired stock.
3. Item: tick "Pharmacy Product", fill class, public price. Receive stock with a Purchase Receipt (a batch number and expiry date are asked for each line).
4. Insurance Company and Insurance Plan (if you sell on insurance).
5. Pharmacy Dispense: sell one cheap item and check the Sales Invoice, the stock and the payment.
6. With insurance: sell one item on a plan; check the journal entry on the insurance company's customer account.
7. Pharmacy Transfer: move one item from the central store to a branch; check both warehouses.
8. Pharmacy Purchase Plan: Load Needs, look at the rows, Create Purchase Orders (drafts).

Tell us the first error you meet, with a screenshot.
