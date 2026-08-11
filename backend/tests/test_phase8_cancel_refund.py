import asyncio, os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

BASE = "http://localhost:8001/api"
passed = failed = 0


def chk(name, cond):
    global passed, failed
    print(("  OK  " if cond else " FAIL ") + name)
    passed += 1 if cond else 0
    failed += 0 if cond else 1


async def tok(c, e, p):
    return (await c.post(f"{BASE}/auth/login", json={"email": e, "password": p})).json()["token"]


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    await db.bookings.delete_many({"booking_number": "P8-TEST-1"})
    await db.cancellation_requests.delete_many({"booking_number": "P8-TEST-1"})
    await db.refund_requests.delete_many({"booking_number": "P8-TEST-1"})
    await db.departures.delete_many({"package_name": "P8-DEP"})

    sales = await db.users.find_one({"email": os.environ["SALES_EMAIL"]})
    dep_id = str((await db.departures.insert_one({"package_id": "x", "package_name": "P8-DEP", "departure_date": "2026-12-01", "quota": 40, "confirmed_pax": 10})).inserted_id)
    bid = str((await db.bookings.insert_one({"booking_number": "P8-TEST-1", "status": "CONFIRMED",
        "customer_id": "c1", "customer_name": "P8 Customer", "package_id": "p1", "package_name": "P8 Pkg",
        "departure_id": dep_id, "departure_date": "2026-12-01", "pax": 3, "total": 30000000,
        "booking_source": "SALES", "sales_type": "MANUAL", "sales_pic_id": str(sales["_id"]),
        "sales_name": sales["name"], "sales_pic_name": sales["name"], "created_at": "2026-06-01T00:00:00+00:00"})).inserted_id)
    await db.invoices.insert_one({"invoice_number": "P8-INV-1", "booking_id": bid, "customer_id": "c1",
        "customer_name": "P8 Customer", "total": 30000000, "paid_amount": 20000000, "outstanding": 10000000, "status": "Partial"})
    for i in range(3):
        await db.travelers.insert_one({"booking_id": bid, "full_name": f"P8 Trav {i}", "created_at": "2026-06-01"})

    async with httpx.AsyncClient(timeout=60) as c:
        sa = {"Authorization": f"Bearer {await tok(c, os.environ['SUPER_ADMIN_EMAIL'], os.environ['SUPER_ADMIN_PASSWORD'])}"}
        sl = {"Authorization": f"Bearer {await tok(c, os.environ['SALES_EMAIL'], os.environ['SALES_PASSWORD'])}"}
        ac = {"Authorization": f"Bearer {await tok(c, os.environ['ACCOUNTING_EMAIL'], os.environ['ACCOUNTING_PASSWORD'])}"}

        # Sales requests cancellation (full)
        r = await c.post(f"{BASE}/cancellations", headers=sl, json={"booking_id": bid, "reason": "Customer batal"})
        chk("sales request cancellation", r.status_code == 200 and r.json()["status"] == "REQUESTED")
        cid = r.json()["_id"]

        # Sales cannot review or approve
        chk("sales review -> 403", (await c.patch(f"{BASE}/cancellations/{cid}/review", headers=sl, json={"cancellation_fee": 1})).status_code == 403)
        chk("sales approve -> 403", (await c.patch(f"{BASE}/cancellations/{cid}/approve", headers=sl, json={"action": "APPROVE"})).status_code == 403)
        # Accounting cannot approve
        chk("accounting approve cancellation -> 403", (await c.patch(f"{BASE}/cancellations/{cid}/approve", headers=ac, json={"action": "APPROVE"})).status_code == 403)

        # Accounting reviews
        r = await c.patch(f"{BASE}/cancellations/{cid}/review", headers=ac, json={"cancellation_fee": 2000000, "non_refundable_cost": 1000000, "other_deduction": 0, "recommendation": "ok"})
        chk("accounting review -> ACCOUNTING_REVIEWED", r.json()["status"] == "ACCOUNTING_REVIEWED")
        chk("estimated refund = paid - fee - nonref (17jt)", abs(r.json()["accounting_review"]["estimated_refund"] - 17000000) < 1)

        # Super Admin approves -> booking CANCELLED + refund auto-created
        r = await c.patch(f"{BASE}/cancellations/{cid}/approve", headers=sa, json={"action": "APPROVE"})
        chk("super admin approve cancellation", r.json()["status"] == "APPROVED")
        bk = await db.bookings.find_one({"_id": ObjectId(bid)})
        chk("booking status CANCELLED", bk["status"] == "CANCELLED")
        dep = await db.departures.find_one({"_id": ObjectId(dep_id)})
        chk("departure seat decremented (10-3=7)", dep["confirmed_pax"] == 7)
        rf = await db.refund_requests.find_one({"booking_number": "P8-TEST-1"})
        chk("refund request auto-created CALCULATED", rf and rf["status"] == "CALCULATED" and abs(rf["proposed_refund"] - 17000000) < 1)
        rid = str(rf["_id"])

        # Accounting cannot process before approval -> 403
        chk("process before approval -> 403", (await c.post(f"{BASE}/refund-requests/{rid}/process", headers=ac, json={"amount": 100})).status_code == 403)

        # Accounting reviews refund (bank + submit)
        r = await c.patch(f"{BASE}/refund-requests/{rid}/review", headers=ac, json={"bank": {"bank_name": "BCA", "account_number": "123", "account_holder": "P8"}, "recommendation": "verified"})
        chk("accounting review refund -> ACCOUNTING_REVIEWED", r.json()["status"] == "ACCOUNTING_REVIEWED")

        # Sales cannot approve refund
        chk("sales approve refund -> 403", (await c.patch(f"{BASE}/refund-requests/{rid}/approve", headers=sl, json={"action": "APPROVE"})).status_code == 403)
        # Accounting cannot approve refund
        chk("accounting approve refund -> 403", (await c.patch(f"{BASE}/refund-requests/{rid}/approve", headers=ac, json={"action": "APPROVE"})).status_code == 403)

        # Super Admin approves refund
        r = await c.patch(f"{BASE}/refund-requests/{rid}/approve", headers=sa, json={"action": "APPROVE", "proposed_refund": 17000000})
        chk("super admin approve refund", r.json()["status"] == "APPROVED")

        # Accounting processes full refund -> REFUNDED
        r = await c.post(f"{BASE}/refund-requests/{rid}/process", headers=ac, json={"amount": 17000000, "bank": "BCA", "payment_date": "2026-06-10"})
        chk("process refund -> REFUNDED", r.json()["status"] == "REFUNDED" and abs(r.json()["refunded_amount"] - 17000000) < 1)

        # Notifications reached accounting + super admin
        note_ac = (await c.get(f"{BASE}/notifications", headers=ac)).json()
        chk("accounting received notifications", len(note_ac) >= 1)

    await db.bookings.delete_many({"booking_number": "P8-TEST-1"})
    await db.cancellation_requests.delete_many({"booking_number": "P8-TEST-1"})
    await db.refund_requests.delete_many({"booking_number": "P8-TEST-1"})
    await db.invoices.delete_many({"invoice_number": "P8-INV-1"})
    await db.travelers.delete_many({"full_name": {"$regex": "^P8 Trav"}})
    await db.departures.delete_many({"package_name": "P8-DEP"})
    print(f"\nRESULT: {passed} passed, {failed} failed -> {'ALL PASS' if failed == 0 else 'SOME FAILED'}")

asyncio.run(main())
