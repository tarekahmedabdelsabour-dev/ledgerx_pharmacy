import itertools
import random
import unittest
from datetime import date, timedelta

from ledgerx_pharmacy.engine import pricing, refill, replenish, stock

T = date(2026, 11, 20)


class TestStock(unittest.TestCase):
	def test_status(self):
		self.assertEqual(stock.expiry_status(T - timedelta(days=1), T), "Expired")
		self.assertEqual(stock.expiry_status(T, T), "Critical")
		self.assertEqual(stock.expiry_status(T + timedelta(days=30), T), "Critical")
		self.assertEqual(stock.expiry_status(T + timedelta(days=31), T), "Near Expiry")
		self.assertEqual(stock.expiry_status(T + timedelta(days=91), T), "OK")
		self.assertEqual(stock.expiry_status(None, T), "No Expiry")

	def test_fefo_order_and_split(self):
		b = [{"batch_no": "B", "qty": 5, "expiry": T + timedelta(days=200)}, {"batch_no": "A", "qty": 3, "expiry": T + timedelta(days=60)},
			{"batch_no": "X", "qty": 9, "expiry": T - timedelta(days=1)}, {"batch_no": "N", "qty": 4, "expiry": None}]
		alloc, short = stock.fefo_allocate(b, 7, T)
		self.assertEqual(alloc, [("A", 3), ("B", 4)])
		self.assertEqual(short, 0)
		alloc, short = stock.fefo_allocate(b, 20, T)
		self.assertEqual(alloc, [("A", 3), ("B", 5), ("N", 4)])  # expired batch never used, no-expiry last
		self.assertEqual(short, 8)

	def test_min_days(self):
		b = [{"batch_no": "A", "qty": 3, "expiry": T + timedelta(days=10)}, {"batch_no": "B", "qty": 5, "expiry": T + timedelta(days=100)}]
		alloc, short = stock.fefo_allocate(b, 4, T, min_days=30)
		self.assertEqual(alloc, [("B", 4)])
		self.assertEqual(stock.usable_qty(b, T, 30), 5)

	def test_conservation_random(self):
		rnd = random.Random(7)
		for _ in range(300):
			b = [{"batch_no": f"B{i}", "qty": rnd.choice([0, 1, 2.5, 7, 12]), "expiry": rnd.choice([None, T - timedelta(days=3), T + timedelta(days=rnd.randint(0, 400))])} for i in range(rnd.randint(0, 6))]
			q = rnd.choice([0, 1, 3, 10, 50])
			alloc, short = stock.fefo_allocate(b, q, T)
			self.assertAlmostEqual(sum(x[1] for x in alloc) + short, q, places=5)
			per = {x["batch_no"]: x for x in b}
			for no, a in alloc:
				self.assertLessEqual(a, per[no]["qty"] + 1e-9)
				self.assertTrue(per[no]["expiry"] is None or per[no]["expiry"] >= T)
			# FEFO: any batch skipped while a later-expiring one was used must be empty/expired
			used = {n for n, _a in alloc}
			dated = [x for x in b if x["expiry"] is not None and x["expiry"] >= T and x["qty"] > 0]
			for x in dated:
				for y in dated:
					if y["batch_no"] in used and x["batch_no"] not in used and x["expiry"] < y["expiry"]:
						self.fail("older batch skipped")


class TestPricing(unittest.TestCase):
	def test_split_basic(self):
		r = pricing.split_insurance([{"amount": 100}, {"amount": 50, "covered": False}], 80)
		self.assertEqual(r, {"gross": 150.0, "covered": 100.0, "uncovered": 50.0, "insurer": 80.0, "patient": 70.0})

	def test_cap_and_copay(self):
		r = pricing.split_insurance([{"amount": 1000}], 50, patient_cap=100)
		self.assertEqual((r["insurer"], r["patient"]), (900.0, 100.0))
		r = pricing.split_insurance([{"amount": 20}], 100, min_copay=5)
		self.assertEqual((r["insurer"], r["patient"]), (15.0, 5.0))
		r = pricing.split_insurance([{"amount": 3}], 100, min_copay=5)
		self.assertEqual((r["insurer"], r["patient"]), (0.0, 3.0))

	def test_cosmetics_excluded(self):
		r = pricing.split_insurance([{"amount": 100, "klass": "Cosmetic"}, {"amount": 100, "klass": "Prescription"}], 100, exclude_cosmetics=True)
		self.assertEqual((r["insurer"], r["patient"]), (100.0, 100.0))

	def test_sum_always_exact(self):
		rnd = random.Random(3)
		for _ in range(500):
			lines = [{"amount": round(rnd.uniform(0.01, 300), 2), "covered": rnd.random() < 0.7} for _ in range(rnd.randint(1, 6))]
			r = pricing.split_insurance(lines, rnd.choice([0, 20, 33.3, 80, 100]), patient_cap=rnd.choice([0, 15, 80]), min_copay=rnd.choice([0, 5]))
			self.assertAlmostEqual(r["insurer"] + r["patient"], r["gross"], places=2)
			self.assertGreaterEqual(r["insurer"], 0)
			self.assertLessEqual(r["insurer"], r["covered"] + 1e-9)

	def test_line(self):
		self.assertEqual(pricing.line_amount(12.5, 3, 10), 33.75)
		self.assertEqual(pricing.line_amount(10, 2, 150), 0.0)


class TestReplenish(unittest.TestCase):
	def test_order_qty(self):
		self.assertEqual(replenish.order_qty(10, 0, 2, 14), 18)  # target 28
		self.assertEqual(replenish.order_qty(10, 0, 2, 14, pack=12), 24)
		self.assertEqual(replenish.order_qty(30, 0, 2, 14), 0)
		self.assertEqual(replenish.order_qty(10, 20, 2, 14), 0)  # on order counts
		self.assertEqual(replenish.order_qty(2, 0, 0, 14, min_level=5, max_level=20), 18)
		self.assertEqual(replenish.order_qty(8, 0, 0, 14, min_level=5), 0)  # no sales, above minimum

	def test_order_reaches_target(self):
		rnd = random.Random(5)
		for _ in range(300):
			s, o, d, c, p = rnd.randint(0, 50), rnd.randint(0, 20), rnd.choice([0, 0.5, 3]), rnd.choice([7, 14, 30]), rnd.choice([1, 6, 12])
			q = replenish.order_qty(s, o, d, c, 0, 0, p)
			self.assertEqual(q % p, 0)
			if q:
				self.assertGreaterEqual(s + o + q, d * c - 1e-9)
				self.assertLess(s + o + q - p, d * c + 1e-9)

	def test_offers(self):
		offers = [{"name": "O1", "supplier": "S1", "price": 10, "discount_pct": 5}, {"name": "O2", "supplier": "S2", "price": 10, "bonus_per": 10, "bonus_qty": 1, "min_qty": 20},
			{"name": "O3", "supplier": "S3", "price": 8, "valid_to": T - timedelta(days=1)}]
		b = replenish.best_offer(offers, 10, 11, T)
		self.assertEqual(b["supplier"], "S1")  # S2 needs 20, S3 expired
		b = replenish.best_offer(offers, 30, 11, T)
		self.assertEqual(b["supplier"], "S2")  # 10*30/33 = 9.09 < 9.5
		self.assertEqual(b["bonus"], 3)
		self.assertIsNone(replenish.best_offer([{"supplier": "S", "price": 0}], 5, 0, T))

	def test_base_price_used(self):
		c, bonus = replenish.effective_cost({"supplier": "S", "discount_pct": 10}, 5, 20, T)
		self.assertEqual((c, bonus), (18.0, 0))

	def test_paid_units(self):
		self.assertEqual(replenish.paid_units(33, {"bonus_per": 10, "bonus_qty": 1}), 30)
		for q in range(1, 80):
			n = replenish.paid_units(q, {"bonus_per": 7, "bonus_qty": 2})
			self.assertGreaterEqual(n + (n // 7) * 2, q)
			self.assertLess(n - 1 + ((n - 1) // 7) * 2, q)


class TestRefill(unittest.TestCase):
	def test_due(self):
		d = refill.next_due(T, 30)
		self.assertEqual(d, T + timedelta(days=30))
		self.assertEqual(refill.refill_status(d, T + timedelta(days=28)), "Due Soon")
		self.assertEqual(refill.refill_status(d, T + timedelta(days=31)), "Overdue")
		self.assertEqual(refill.refill_status(d, T), "Upcoming")
		self.assertIsNone(refill.next_due(None, 30))
		self.assertEqual(refill.next_due(None, 30, start=T), T + timedelta(days=30))


if __name__ == "__main__":
	unittest.main()


class TestAging(unittest.TestCase):
	def test_fifo(self):
		from ledgerx_pharmacy.engine.aging import fifo_aging

		deb = [(T - timedelta(days=100), 100), (T - timedelta(days=50), 200), (T - timedelta(days=5), 50)]
		r = fifo_aging(deb, 150, T)
		self.assertEqual(r["buckets"], [50.0, 150.0, 0.0, 0.0])  # oldest 100 settled, 50 of the next
		self.assertEqual(r["total"], 200.0)
		self.assertEqual(fifo_aging(deb, 0, T)["buckets"], [50.0, 200.0, 0.0, 100.0])
		r = fifo_aging(deb, 400, T)
		self.assertEqual((r["total"], r["unapplied"]), (0.0, -50.0))

	def test_conservation(self):
		from ledgerx_pharmacy.engine.aging import fifo_aging

		rnd = random.Random(2)
		for _ in range(200):
			deb = [(T - timedelta(days=rnd.randint(0, 200)), round(rnd.uniform(1, 500), 2)) for _i in range(rnd.randint(0, 6))]
			cr = round(rnd.uniform(0, 1500), 2)
			r = fifo_aging(deb, cr, T)
			owed = sum(a for _d, a in deb)
			self.assertAlmostEqual(r["total"], max(owed - cr, 0), places=1)
