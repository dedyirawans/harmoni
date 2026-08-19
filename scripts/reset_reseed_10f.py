"""MASTER RESET & RESEED for all Phase 10F demo data.
- Deletes ALL previous demo/transactional data + all non-(super_admin/accounting) users.
- Preserves Super Admin, Accounting, roles/permissions, Tax, AI config, WhatsApp/API.co.id config, company_files.
- Ensures an ACTIVE UMRAH commission scheme.
- Reseeds 10F-1..10F-5 in order, then runs the EXISTING commission engine + approval flow (REVIEW->APPROVED->CLOSED->PAID).
Usage: python /app/scripts/reset_reseed_10f.py
"""
import asyncio, subprocess, sys, json, urllib.request
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

ENV = {}
for path in ("/app/backend/.env",):
    for ln in open(path):
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1); ENV[k] = v.strip().strip('"')
FENV = {}
for ln in open("/app/frontend/.env"):
    ln = ln.strip()
    if ln and "=" in ln:
        k, v = ln.split("=", 1); FENV[k] = v.strip().strip('"')
API = FENV["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
db = AsyncIOMotorClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
NOW = datetime.now(timezone.utc).isoformat()

WIPE = ["customers", "leads", "follow_ups", "sales_activities", "lead_activities",
        "quotations", "bookings", "invoices", "payments",
        "packages", "package_costs", "package_itineraries", "departures", "destinations", "suppliers",
        "conversations", "whatsapp_messages", "whatsapp_conversations",
        "commission_lines", "commission_items", "commission_closings", "commission_adjustments",
        "demo_seed_flags"]

def http(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode() if e.fp else "")

async def wipe_and_prepare():
    for c in WIPE:
        res = await db[c].delete_many({})
        print(f"  wiped {c}: {res.deleted_count}")
    ures = await db.users.delete_many({"role": {"$nin": ["super_admin", "accounting"]}})
    print(f"  deleted non-admin/accounting users: {ures.deleted_count}")
    # ensure UMRAH commission scheme (config, not wiped)
    if not await db.commission_schemes.find_one({"product_type": "UMRAH", "status": "ACTIVE"}):
        await db.commission_schemes.insert_one({
            "scheme_name": "Skema Komisi Umrah", "product_type": "UMRAH", "package_id": "",
            "effective_from": "2026-08-01", "effective_until": "", "calculation_basis": "PAID",
            "tiers": [{"min_pax": 0, "max_pax": 9, "rate_per_pax": 250000},
                      {"min_pax": 10, "max_pax": 29, "rate_per_pax": 350000},
                      {"min_pax": 30, "max_pax": None, "rate_per_pax": 500000}],
            "auto_sales": False, "status": "ACTIVE", "created_at": NOW, "created_by": "System (reset_10f)"})
        print("  UMRAH commission scheme created")
    else:
        print("  UMRAH commission scheme already exists")

def run_seed(name):
    print(f"== running {name} ==")
    r = subprocess.run([sys.executable, f"/app/scripts/{name}"], capture_output=True, text=True, cwd="/app/backend")
    print("  " + (r.stdout.strip() or r.stderr.strip()))
    if r.returncode != 0:
        print("  STDERR:", r.stderr.strip()); raise SystemExit(f"seed {name} failed")

async def main():
    print("STEP 1: wipe + prepare")
    await wipe_and_prepare()
    print("STEP 2: reseed 10F-1..10F-5")
    for s in ("seed_10f1.py", "seed_10f2.py", "seed_10f3.py", "seed_10f4.py", "seed_10f5.py"):
        run_seed(s)
    print("STEP 3: recompute departure seat availability")
    async for d in db.departures.find({}):
        q = int(d.get("quota") or 0); c = int(d.get("confirmed_pax") or 0); a = max(q - c, 0)
        stt = "FULL" if a <= 0 and q > 0 else ("ALMOST FULL" if q and a / q <= 0.2 else "OPEN")
        if d.get("available_seat") != a or d.get("status") != stt:
            await db.departures.update_one({"_id": d["_id"]}, {"$set": {"available_seat": a, "status": stt}})
    print("  departures recomputed (available = quota - confirmed_pax)")
    print("STEP 4: commission engine + SA approval (2026-08)")
    st, res = http("POST", "/auth/login", body={"email": ENV.get("SEED_ADMIN_EMAIL", "dedyirawan18@gmail.com"),
                                                "password": ENV.get("SEED_ADMIN_PASSWORD", "Admin@123")})
    if st != 200:
        print("  admin login failed (skip commission step):", st)
    else:
        tok = res["token"]; period = "2026-08"
        http("POST", f"/commissions/closings/{period}/reopen", tok)
        st, res = http("POST", f"/commissions/closings/{period}/calculate", tok)
        print("  calculate:", st, "commission Rp", (res or {}).get("total_commission") if isinstance(res, dict) else res)
        http("PATCH", f"/commissions/closings/{period}/approval", tok, {"decision": "APPROVED"})
        st, _ = http("PATCH", f"/commissions/closings/{period}/status", tok, {"status": "CLOSED"})
        print(f"  SA APPROVED + CLOSED (payable): http {st}. Payout->PAID gated to payout_month by existing rule.")
    # summary
    print("STEP 5: summary")
    print("  customers:", await db.customers.count_documents({}),
          "| leads:", await db.leads.count_documents({}),
          "| packages:", await db.packages.count_documents({}),
          "| departures:", await db.departures.count_documents({}),
          "| quotations:", await db.quotations.count_documents({}),
          "| bookings:", await db.bookings.count_documents({}),
          "| suppliers:", await db.suppliers.count_documents({}),
          "| conversations:", await db.conversations.count_documents({}),
          "| sales_users:", await db.users.count_documents({"role": "sales"}))
    print("RESET & RESEED COMPLETE")

asyncio.run(main())
