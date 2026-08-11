"""Seed a QA8 booking for frontend Phase 8 testing. Usage: python qa8_seed.py [seed|cleanup]"""
import asyncio, os, sys
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
from motor.motor_asyncio import AsyncIOMotorClient

PFX = "QA8-"

async def cleanup(db):
    await db.bookings.delete_many({"booking_number": {"$regex": f"^{PFX}"}})
    await db.cancellation_requests.delete_many({"booking_number": {"$regex": f"^{PFX}"}})
    await db.refund_requests.delete_many({"booking_number": {"$regex": f"^{PFX}"}})
    await db.invoices.delete_many({"invoice_number": {"$regex": f"^{PFX}"}})
    await db.travelers.delete_many({"full_name": {"$regex": f"^{PFX}"}})
    await db.departures.delete_many({"package_name": {"$regex": f"^{PFX}"}})
    print("cleanup done")

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
    print("BID=" + bid)

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "seed"))
