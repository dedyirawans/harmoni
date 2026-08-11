import asyncio, os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

BASE = "http://localhost:8001/api"
passed = failed = 0


def chk(n, c):
    global passed, failed
    print(("  OK  " if c else " FAIL ") + n)
    passed += 1 if c else 0
    failed += 0 if c else 1


async def tok(c, e, p):
    return (await c.post(f"{BASE}/auth/login", json={"email": e, "password": p})).json()["token"]


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    await db.bookings.delete_many({"booking_number": "P4B-1"})
    await db.cancellation_requests.delete_many({"booking_number": "P4B-1"})
    await db.refund_requests.delete_many({"booking_number": "P4B-1"})
    sales = await db.users.find_one({"email": os.environ["SALES_EMAIL"]})
    bid = str((await db.bookings.insert_one({"booking_number": "P4B-1", "status": "CONFIRMED", "customer_id": "c1",
        "customer_name": "P4B Cust", "package_id": "p1", "package_name": "P4B Pkg", "pax": 2, "total": 30000000,
        "tax_amount": 1100000, "booking_source": "SALES", "sales_type": "MANUAL", "sales_pic_id": str(sales["_id"]),
        "sales_name": sales["name"], "created_at": "2026-06-01T00:00:00+00:00"})).inserted_id)
    await db.invoices.insert_one({"invoice_number": "P4B-INV", "booking_id": bid, "customer_id": "c1", "total": 30000000, "paid_amount": 25000000, "outstanding": 5000000, "status": "Partial"})
    for i in range(2):
        await db.travelers.insert_one({"booking_id": bid, "full_name": f"P4B T{i}", "created_at": "2026-06-01"})

    async with httpx.AsyncClient(timeout=60) as c:
        sa = {"Authorization": f"Bearer {await tok(c, os.environ['SUPER_ADMIN_EMAIL'], os.environ['SUPER_ADMIN_PASSWORD'])}"}
        ac = {"Authorization": f"Bearer {await tok(c, os.environ['ACCOUNTING_EMAIL'], os.environ['ACCOUNTING_PASSWORD'])}"}
        sl = {"Authorization": f"Bearer {await tok(c, os.environ['SALES_EMAIL'], os.environ['SALES_PASSWORD'])}"}

        # deduction types seeded + SA can add
        types = (await c.get(f"{BASE}/deduction-types", headers=ac)).json()
        chk("deduction types seeded (>=15)", len(types) >= 15)
        chk("sales add deduction type -> 403", (await c.post(f"{BASE}/deduction-types", headers=sl, json={"name": "X"})).status_code == 403)
        chk("SA add deduction type", (await c.post(f"{BASE}/deduction-types", headers=sa, json={"name": "P4B Custom Fee"})).status_code == 200)

        # cancellation full -> review -> approve => refund auto with deductions from review amounts
        cid = (await c.post(f"{BASE}/cancellations", headers=sl, json={"booking_id": bid, "reason": "batal"})).json()["_id"]
        await c.patch(f"{BASE}/cancellations/{cid}/review", headers=ac, json={"cancellation_fee": 2000000, "non_refundable_cost": 3000000, "other_deduction": 0, "recommendation": "ok"})
        await c.patch(f"{BASE}/cancellations/{cid}/approve", headers=sa, json={"action": "APPROVE"})
        rf = await db.refund_requests.find_one({"booking_number": "P4B-1"})
        rid = str(rf["_id"])
        chk("auto refund seeded deductions (fee+nonref)", len(rf["deductions"]) >= 2 and abs(rf["total_deduction"] - 5000000) < 1)
        chk("proposed = 25jt-5jt = 20jt", abs(rf["proposed_refund"] - 20000000) < 1)
        chk("tax adjustment computed", abs(rf["cancelled_tax"] - 1100000) < 1)

        # accounting adds PER_PAX deduction: Visa 1jt x 2 = 2jt
        r = await c.post(f"{BASE}/refund-requests/{rid}/deductions", headers=ac, json={"type": "Visa", "method": "PER_PAX", "qty": 2, "unit_amount": 1000000, "source": "Package", "non_refundable": True})
        chk("PER_PAX visa 2jt added, proposed=18jt", abs(r.json()["proposed_refund"] - 18000000) < 1)

        # PERCENTAGE deduction 10% of 25jt = 2.5jt -> proposed 15.5jt
        r = await c.post(f"{BASE}/refund-requests/{rid}/deductions", headers=ac, json={"type": "Handling", "method": "PERCENTAGE", "unit_amount": 10, "source": "Manual Adjustment"})
        chk("PERCENTAGE 10% -> 2.5jt, proposed=15.5jt", abs(r.json()["proposed_refund"] - 15500000) < 1)

        # sales cannot add deduction
        chk("sales add deduction -> 403", (await c.post(f"{BASE}/refund-requests/{rid}/deductions", headers=sl, json={"type": "X", "method": "FIXED", "unit_amount": 1})).status_code == 403)
        # accounting cannot adjust (SA only)
        chk("accounting adjustment -> 403", (await c.patch(f"{BASE}/refund-requests/{rid}/adjustment", headers=ac, json={"refund_adjustment": 100, "reason": "x"})).status_code == 403)

        # SA manual adjustment +500k, reason required
        chk("adjustment without reason -> 400", (await c.patch(f"{BASE}/refund-requests/{rid}/adjustment", headers=sa, json={"refund_adjustment": 500000})).status_code == 400)
        r = await c.patch(f"{BASE}/refund-requests/{rid}/adjustment", headers=sa, json={"refund_adjustment": 500000, "reason": "goodwill"})
        chk("adjustment +500k -> proposed 16jt", abs(r.json()["proposed_refund"] - 16000000) < 1)

        # versioning captured
        rf2 = await db.refund_requests.find_one({"_id": ObjectId(rid)})
        chk("versions recorded (>=4)", len(rf2.get("versions", [])) >= 4)

        # impact hidden from sales, visible accounting
        chk("sales impact -> 403", (await c.get(f"{BASE}/refund-requests/{rid}/impact", headers=sl)).status_code == 403)
        chk("accounting impact -> 200", (await c.get(f"{BASE}/refund-requests/{rid}/impact", headers=ac)).status_code == 200)

        # review submit -> approve -> process cap
        await c.patch(f"{BASE}/refund-requests/{rid}/review", headers=ac, json={"bank": {"bank_name": "BCA", "account_number": "1", "account_holder": "P4B"}, "recommendation": "ok"})
        await c.patch(f"{BASE}/refund-requests/{rid}/approve", headers=sa, json={"action": "APPROVE"})
        # process more than approved -> 400
        over = await c.post(f"{BASE}/refund-requests/{rid}/process", headers=ac, json={"amount": 99000000})
        chk("process over approved -> 400", over.status_code == 400)
        # partial then full
        p1 = await c.post(f"{BASE}/refund-requests/{rid}/process", headers=ac, json={"amount": 6000000})
        chk("partial -> PARTIALLY_REFUNDED", p1.json()["status"] == "PARTIALLY_REFUNDED")
        p2 = await c.post(f"{BASE}/refund-requests/{rid}/process", headers=ac, json={"amount": 10000000})
        chk("final -> REFUNDED", p2.json()["status"] == "REFUNDED")

        # reports
        rep = (await c.get(f"{BASE}/refund-reports/summary", headers=ac)).json()
        chk("refund summary has totals", rep["total_refund_paid"] >= 16000000)
        brk = (await c.get(f"{BASE}/refund-reports/deduction-breakdown", headers=ac)).json()
        chk("deduction breakdown grouped", any(x["type"] == "Visa" for x in brk["breakdown"]))

    await db.bookings.delete_many({"booking_number": "P4B-1"})
    await db.cancellation_requests.delete_many({"booking_number": "P4B-1"})
    await db.refund_requests.delete_many({"booking_number": "P4B-1"})
    await db.invoices.delete_many({"invoice_number": "P4B-INV"})
    await db.travelers.delete_many({"full_name": {"$regex": "^P4B T"}})
    await db.deduction_types.delete_many({"name": "P4B Custom Fee"})
    print(f"\nRESULT: {passed} passed, {failed} failed -> {'ALL PASS' if failed == 0 else 'SOME FAILED'}")

asyncio.run(main())
