import asyncio, os, sys
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

MONGO = os.environ["MONGO_URL"]; DBN = os.environ["DB_NAME"]
BASE = "http://localhost:8001/api"
AUG = "2026-08"; SEP = "2026-09"


async def login(c, email, pw):
    r = await c.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    return r.json()["token"]


async def main():
    cl = AsyncIOMotorClient(MONGO); db = cl[DBN]
    # cleanup previous test data
    await db.commission_items.delete_many({"period": {"$in": [AUG, SEP]}})
    await db.commission_lines.delete_many({"period": {"$in": [AUG, SEP]}})
    await db.commission_closings.delete_many({"period": {"$in": [AUG, SEP]}})
    await db.commission_schemes.delete_many({"scheme_name": "ACC-TEST"})
    await db.bookings.delete_many({"booking_number": {"$regex": "^ACCTEST-"}})
    await db.travelers.delete_many({"full_name": {"$regex": "^ACCT "}})

    # dedicated package so scheme matches ONLY test bookings (isolation from demo data)
    await db.packages.delete_many({"package_name": "ACCTEST-PKG"})
    pid = (await db.packages.insert_one({"package_name": "ACCTEST-PKG", "product_type": "UMROH",
           "selling_price": 1, "status": "ACTIVE", "created_at": "2026-01-01"})).inserted_id
    pkg = await db.packages.find_one({"_id": pid})
    pkg_id = str(pkg["_id"])

    # sales users
    async def sid(email):
        u = await db.users.find_one({"email": email}); return str(u["_id"]), u["name"]
    sa_id, sa_name = await sid(os.environ["SALES_EMAIL"])
    sb_id, sb_name = await sid(os.environ["SALES_B_EMAIL"])
    # sales C = accounting? no, use super admin as third distinct sales bucket
    su = await db.users.find_one({"email": os.environ["SUPER_ADMIN_EMAIL"]}); sc_id, sc_name = str(su["_id"]), su["name"]

    created_bookings = []
    async def make(sales_id, sales_name, npax, idx):
        b = {"booking_number": f"ACCTEST-{idx}", "status": "CONFIRMED", "booking_source": "SALES",
             "package_id": pkg_id, "package_name": "Acc Test Pkg", "pax": npax,
             "sales_pic_id": sales_id, "sales_pic_name": sales_name, "branch": "",
             "created_at": f"{AUG}-10T00:00:00+00:00", "total": 1000}
        bid = str((await db.bookings.insert_one(b)).inserted_id)
        created_bookings.append(bid)
        for i in range(npax):
            await db.travelers.insert_one({"booking_id": bid, "full_name": f"ACCT {idx}-{i}", "created_at": f"{AUG}-10T00:00:00+00:00"})
    await make(sa_id, sa_name, 5, "A")
    await make(sb_id, sb_name, 12, "B")
    await make(sc_id, sc_name, 25, "C")

    async with httpx.AsyncClient(timeout=60) as c:
        tok = await login(c, os.environ["SUPER_ADMIN_EMAIL"], os.environ["SUPER_ADMIN_PASSWORD"])
        H = {"Authorization": f"Bearer {tok}"}
        # scheme BOOKED basis so created_at drives period, tiers per spec
        scheme = {"scheme_name": "ACC-TEST", "product_type": "ALL", "package_id": pkg_id,
                  "effective_from": f"{AUG}-01", "effective_until": "", "calculation_basis": "BOOKED",
                  "tiers": [{"min_pax": 0, "max_pax": 9, "rate_per_pax": 100000},
                            {"min_pax": 10, "max_pax": 19, "rate_per_pax": 150000},
                            {"min_pax": 20, "max_pax": None, "rate_per_pax": 250000}],
                  "auto_sales": False, "status": "ACTIVE"}
        await c.post(f"{BASE}/commissions/schemes", json=scheme, headers=H)

        # calculate August
        r = await c.post(f"{BASE}/commissions/closings/{AUG}/calculate", headers=H)
        print("AUG calc:", r.json())
        det = (await c.get(f"{BASE}/commissions/closings/{AUG}", headers=H)).json()
        by = {l["sales_pic_id"]: l for l in det["lines"]}
        exp = {sa_id: (5, "0-9", 500000), sb_id: (12, "10-19", 1800000), sc_id: (25, "20-∞", 6250000)}
        ok = True
        for sid_, (pax, tier, comm) in exp.items():
            ln = by.get(sid_)
            if not ln:
                print("FAIL missing line for", sid_); ok = False; continue
            good = ln["total_pax"] == pax and abs(ln["total_commission"] - comm) < 1
            print(f"  {ln['sales_pic_name']}: pax={ln['total_pax']} tier={ln['tier']} comm={ln['total_commission']} -> {'OK' if good else 'FAIL'}")
            if not good: ok = False

        # close August
        await c.patch(f"{BASE}/commissions/closings/{AUG}/status", json={"status": "APPROVED"}, headers=H)
        await c.patch(f"{BASE}/commissions/closings/{AUG}/status", json={"status": "CLOSED"}, headers=H)

        # calculate September -> August travelers must NOT reappear
        r2 = await c.post(f"{BASE}/commissions/closings/{SEP}/calculate", headers=H)
        print("SEP calc:", r2.json())
        sep_items = await db.commission_items.count_documents({"period": SEP, "booking_id": {"$in": created_bookings}})
        antidup_ok = sep_items == 0
        print("  anti-dup (sept items from aug bookings) =", sep_items, "->", "OK" if antidup_ok else "FAIL")

        # verify locked closing rejects recalc
        rlock = await c.post(f"{BASE}/commissions/closings/{AUG}/calculate", headers=H)
        lock_ok = rlock.status_code == 400
        print("  CLOSED recalc rejected:", rlock.status_code, "->", "OK" if lock_ok else "FAIL")

    print("\nRESULT:", "ALL PASS" if (ok and antidup_ok and lock_ok) else "SOME FAILED")
    cl.close()

asyncio.run(main())
