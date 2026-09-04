"""Seed QA4B booking + drive cancellation to CALCULATED refund. Usage: python qa4b_seed.py [seed|cleanup]"""
import asyncio, os, sys, httpx
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
from motor.motor_asyncio import AsyncIOMotorClient

PFX = "QA4B-"
BASE = os.environ["PUBLIC_BASE"] if "PUBLIC_BASE" in os.environ else "https://git-continue-5.preview.emergentagent.com/api"

async def cleanup(db):
    await db.bookings.delete_many({"booking_number": {"$regex": f"^{PFX}"}})
    await db.cancellation_requests.delete_many({"booking_number": {"$regex": f"^{PFX}"}})
    await db.refund_requests.delete_many({"booking_number": {"$regex": f"^{PFX}"}})
    await db.invoices.delete_many({"invoice_number": {"$regex": f"^{PFX}"}})
    await db.travelers.delete_many({"full_name": {"$regex": f"^{PFX}"}})
    await db.departures.delete_many({"package_name": {"$regex": f"^{PFX}"}})
    await db.notifications.delete_many({"message": {"$regex": PFX}})
    print("cleanup done")

async def login(c, email, pwd):
    r = await c.post(f"{BASE}/auth/login", json={"email": email, "password": pwd})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}

async def main(action):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    await cleanup(db)
    if action == "cleanup":
        return
    sales = await db.users.find_one({"email": os.environ["SALES_EMAIL"]})
    dep = await db.departures.insert_one({"package_id": "px", "package_name": PFX+"DEP", "departure_date": "2026-12-15", "quota": 50, "confirmed_pax": 12})
    b = await db.bookings.insert_one({
        "booking_number": PFX+"B1", "status": "CONFIRMED", "customer_id": "cx", "customer_name": PFX+"Cust",
        "package_id": "pk", "package_name": PFX+"Pkg", "departure_id": str(dep.inserted_id),
        "departure_date": "2026-12-15", "pax": 3, "total": 30000000,
        "booking_source": "SALES", "sales_type": "MANUAL",
        "sales_pic_id": str(sales["_id"]), "sales_pic_name": sales["name"], "sales_name": sales["name"],
        "created_at": "2026-06-01T00:00:00+00:00",
    })
    bid = str(b.inserted_id)
    await db.invoices.insert_one({"invoice_number": PFX+"INV1", "booking_id": bid, "customer_id": "cx",
        "customer_name": PFX+"Cust", "total": 30000000, "paid_amount": 20000000, "outstanding": 10000000, "status": "Partial"})
    for i in range(3):
        await db.travelers.insert_one({"booking_id": bid, "full_name": f"{PFX}Trav{i}", "created_at": "2026-06-01"})

    # Drive cancellation flow -> refund CALCULATED via API
    async with httpx.AsyncClient(timeout=30) as c:
        sl = await login(c, os.environ["SALES_EMAIL"], "Sales@123")
        ac = await login(c, os.environ["ACCOUNTING_EMAIL"], "Account@123")
        sa = await login(c, os.environ["SUPER_ADMIN_EMAIL"], os.environ["SUPER_ADMIN_PASSWORD"])
        r = await c.post(f"{BASE}/cancellations", headers=sl, json={"booking_id": bid, "reason": PFX+"batal"})
        r.raise_for_status()
        cid = r.json()["_id"]
        r = await c.patch(f"{BASE}/cancellations/{cid}/review", headers=ac,
                          json={"cancellation_fee": 2000000, "non_refundable_cost": 0, "other_deduction": 0, "recommendation": PFX+"ok"})
        r.raise_for_status()
        r = await c.patch(f"{BASE}/cancellations/{cid}/approve", headers=sa, json={"action": "APPROVE"})
        r.raise_for_status()
        rf = await db.refund_requests.find_one({"booking_number": PFX+"B1"})
        print(f"BID={bid}")
        print(f"RID={rf['_id']}")
        print(f"RSTATUS={rf['status']} PROPOSED={rf['proposed_refund']}")

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "seed"))
