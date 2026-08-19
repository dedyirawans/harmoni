"""Phase 10F-1 — Seed realistic Sales users + Destinations + Tour/Umrah packages + Departures.
Idempotent (guarded by demo_seed_flags). Does NOT touch Super Admin/Accounting/AI/WhatsApp/Tax."""
import asyncio, os, bcrypt
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

ENV = {}
with open("/app/backend/.env") as fh:
    for ln in fh:
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            ENV[k] = v.strip().strip('"')

client = AsyncIOMotorClient(ENV["MONGO_URL"])
db = client[ENV["DB_NAME"]]
now = datetime.now(timezone.utc).isoformat()
def hp(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

SALES = [
    ("Andi Pratama", "andi.pratama@harmoniwisata.co.id", "andi.pratama", "081234500011", "Jakarta"),
    ("Rina Maharani", "rina.maharani@harmoniwisata.co.id", "rina.maharani", "081234500012", "Jakarta"),
    ("Fajar Ramadhan", "fajar.ramadhan@harmoniwisata.co.id", "fajar.ramadhan", "081234500013", "Bandung"),
    ("Siti Aulia", "siti.aulia@harmoniwisata.co.id", "siti.aulia", "081234500014", "Surabaya"),
    ("Rizky Saputra", "rizky.saputra@harmoniwisata.co.id", "rizky.saputra", "081234500015", "Yogyakarta"),
]

DESTS = [
    ("Japan", "Japan", "International"), ("South Korea", "South Korea", "International"),
    ("Thailand", "Thailand", "International"), ("Singapore", "Singapore", "International"),
    ("Malaysia", "Malaysia", "International"), ("Turkiye", "Turkiye", "International"),
    ("Saudi Arabia", "Saudi Arabia", "International"), ("Switzerland", "Switzerland", "International"),
    ("France", "France", "International"), ("Bali", "Indonesia", "Domestic"),
    ("Lombok", "Indonesia", "Domestic"), ("Yogyakarta", "Indonesia", "Domestic"),
    ("Labuan Bajo", "Indonesia", "Domestic"), ("Raja Ampat", "Indonesia", "Domestic"),
]

# (name, dest, country, duration, sell, hpp, seats[(quota,confirmed)], itinerary[(loc,act)])
TOURS = [
    ("Japan Autumn 2026", "Japan", "Japan", "7 Days", 32500000, 25500000, [(30, 18), (25, 7)], "2026-10-12"),
    ("Korea Winter 2026", "South Korea", "South Korea", "6 Days", 24500000, 18800000, [(30, 22)], "2026-12-18"),
    ("Turkiye Heritage 2026", "Turkiye", "Turkiye", "9 Days", 28900000, 22000000, [(35, 35)], "2026-09-05"),
    ("Thailand Family Holiday", "Thailand", "Thailand", "5 Days", 12900000, 9500000, [(40, 12)], "2026-08-20"),
    ("Swiss Summer Experience", "Switzerland", "Switzerland", "8 Days", 45900000, 36500000, [(25, 5)], "2026-11-10"),
    ("Bali Family Escape", "Bali", "Indonesia", "4 Days", 6900000, 4700000, [(40, 28)], "2026-08-15"),
    ("Singapore Malaysia Holiday", "Singapore", "Singapore", "5 Days", 11500000, 8600000, [(30, 9)], "2026-09-22"),
    ("Bangkok Pattaya", "Thailand", "Thailand", "4 Days", 8900000, 6400000, [(35, 30)], "2026-10-03"),
    ("Japan Family Holiday", "Japan", "Japan", "6 Days", 29900000, 23200000, [(30, 15)], "2026-11-25"),
    ("Europe Highlights", "France", "France", "11 Days", 52900000, 42000000, [(25, 19)], "2027-01-09"),
]

# (name, dest, dur, sell, hpp, seats, makkah_hotel, madinah_hotel, airline, dep)
UMRAHS = [
    ("Umrah Reguler 9 Hari", "Saudi Arabia", "9 Days", 27500000, 22500000, [(45, 30), (45, 12)], "Fairmont Makkah", "Anwar Al Madinah Movenpick", "Saudia", "2026-09-14"),
    ("Umrah Executive 12 Hari", "Saudi Arabia", "12 Days", 39500000, 31500000, [(40, 35)], "Swissotel Al Maqam", "Dar Al Taqwa", "Garuda Indonesia", "2026-10-20"),
    ("Umrah Plus Turki", "Saudi Arabia", "14 Days", 42500000, 34000000, [(35, 8)], "Hilton Suites Makkah", "Millennium Taibah", "Turkish Airlines", "2026-11-08"),
    ("Umrah Ramadhan", "Saudi Arabia", "10 Days", 45900000, 37000000, [(45, 41)], "Conrad Makkah", "Anwar Al Madinah Movenpick", "Saudia", "2027-01-05"),
    ("Umrah Family Package", "Saudi Arabia", "9 Days", 29900000, 24000000, [(40, 16)], "Pullman ZamZam", "Le Meridien Madinah", "Lion Air", "2026-08-28"),
    ("Umrah Exclusive", "Saudi Arabia", "11 Days", 54900000, 44000000, [(25, 6)], "Raffles Makkah Palace", "The Oberoi Madinah", "Emirates", "2026-12-02"),
]

async def main():
    if await db.demo_seed_flags.find_one({"batch": "10F1"}):
        print("Already seeded (10F1). Skipping.")
        return
    # 1) Sales users (only if email not present)
    su = 0
    for name, email, uname, phone, branch in SALES:
        if await db.users.find_one({"email": email}):
            continue
        await db.users.insert_one({
            "name": name, "email": email, "username": uname, "phone": phone,
            "role": "sales", "status": "active", "branch": branch, "data_scope": "own",
            "password_hash": hp("Sales@123"), "is_deleted": False, "created_at": now, "created_by": "System (10F1)"})
        su += 1
    # 2) Destinations
    de = 0
    for name, country, typ in DESTS:
        if await db.destinations.find_one({"name": name}):
            continue
        await db.destinations.insert_one({"name": name, "country": country, "type": typ,
            "status": "ACTIVE", "created_at": now, "created_by": "System (10F1)", "seed_batch": "10F1"})
        de += 1

    async def add_pkg(doc, comps, itin, deps):
        airline = doc.pop("_airline", "")
        res = await db.packages.insert_one(doc)
        pid = str(res.inserted_id)
        await db.package_costs.insert_one({"package_id": pid, "components": comps,
            "total_cost": doc["hpp"], "cost_per_pax": doc["hpp"], "gross_profit": doc["gross_profit"],
            "gross_margin": doc["gross_margin"], "updated_at": now})
        for i, (loc, act) in enumerate(itin, 1):
            await db.package_itineraries.insert_one({"package_id": pid, "day": i, "location": loc,
                "activity": act, "hotel": "", "meal": "Breakfast", "transport": "Bus", "flight": "",
                "description": act, "notes": "", "images": [], "created_at": now})
        for (quota, confirmed, ddate) in deps:
            avail = max(quota - confirmed, 0)
            status = "FULL" if avail <= 0 else ("ALMOST FULL" if quota and avail / quota <= 0.2 else "OPEN")
            await db.departures.insert_one({"package_id": pid, "departure_date": ddate, "return_date": "",
                "quota": quota, "confirmed_pax": confirmed, "available_seat": avail, "flight": airline,
                "hotel": "", "price": doc["selling_price"], "status": status, "created_at": now})
        return pid

    tp = up = deps_n = 0
    for i, (name, dest, country, dur, sell, hpp, seats, ddate) in enumerate(TOURS):
        gp = sell - hpp
        doc = {"package_code": f"TOUR-1{i+1:03d}", "package_name": name, "product_type": "TOUR",
               "category": dest, "destination": dest, "country": country, "duration": dur,
               "description": f"Paket tour {name} bersama Harmoni Wisata Internusa.", "cover_image": "", "gallery": [],
               "min_pax": 2, "max_pax": max(s[0] for s in seats), "selling_price": sell, "child_price": round(sell*0.9),
               "infant_price": round(sell*0.2), "single_supplement": round(sell*0.2), "currency": "IDR",
               "tax_treatment": "Non-PPN", "commission_eligibility": True, "status": "ACTIVE",
               "promo_text": "Early bird tersedia", "terms": "DP 50%, pelunasan H-30.", "version": 1, "umrah": {},
               "included": "Tiket pesawat PP, hotel, tour, makan sesuai program, tour leader.",
               "excluded": "Pengeluaran pribadi, tipping, kelebihan bagasi.",
               "hpp": hpp, "total_cost": hpp, "cost_per_pax": hpp, "gross_profit": gp,
               "gross_margin": round(gp/sell*100, 2), "created_at": now, "created_by": "System (10F1)", "seed_batch": "10F1"}
        deplist = [(q, c, ddate) for (q, c) in seats]
        await add_pkg(doc, {"flight": round(hpp*0.5), "hotel": round(hpp*0.3), "transport": round(hpp*0.1),
                            "guide": round(hpp*0.05), "meal": round(hpp*0.05), "visa": 0, "muthawwif": 0,
                            "handling": 0, "insurance": 0, "other": 0},
                     [(dest, "City tour & sightseeing"), (dest, "Free program & shopping")], deplist)
        tp += 1; deps_n += len(deplist)

    for i, (name, dest, dur, sell, hpp, seats, mh, dh, air, ddate) in enumerate(UMRAHS):
        gp = sell - hpp
        doc = {"package_code": f"UMR-1{i+1:03d}", "package_name": name, "product_type": "UMRAH",
               "category": "Umrah", "destination": "Makkah & Madinah", "country": "Saudi Arabia", "duration": dur,
               "description": f"Paket {name} — bimbingan ibadah lengkap.", "cover_image": "", "gallery": [],
               "min_pax": 4, "max_pax": max(s[0] for s in seats), "selling_price": sell, "child_price": round(sell*0.9),
               "infant_price": round(sell*0.2), "single_supplement": round(sell*0.22), "currency": "IDR",
               "tax_treatment": "Non-PPN", "commission_eligibility": True, "status": "ACTIVE",
               "promo_text": "Kuota terbatas", "terms": "DP Rp5jt, pelunasan H-40.", "version": 1,
               "umrah": {"makkah_hotel": mh, "madinah_hotel": dh, "makkah_nights": 4, "madinah_nights": 3,
                         "airline": air, "visa": "Umrah Visa", "transport": "Bus VIP", "handling": "Included",
                         "muthawwif": "Included", "manasik": "2x", "zamzam": "5L", "insurance": "Included",
                         "baggage": "23kg + 7kg", "room_type": "QUAD"},
               "_airline": air,
               "included": "Tiket pesawat PP, visa umrah, hotel, makan full board, muthawwif, manasik, air zamzam.",
               "excluded": "Pengeluaran pribadi, kelebihan bagasi, vaksin.",
               "hpp": hpp, "total_cost": hpp, "cost_per_pax": hpp, "gross_profit": gp,
               "gross_margin": round(gp/sell*100, 2), "created_at": now, "created_by": "System (10F1)", "seed_batch": "10F1"}
        deplist = [(q, c, ddate) for (q, c) in seats]
        await add_pkg(doc, {"flight": round(hpp*0.45), "hotel": round(hpp*0.3), "visa": round(hpp*0.07),
                            "transport": round(hpp*0.05), "muthawwif": round(hpp*0.03), "handling": round(hpp*0.03),
                            "meal": round(hpp*0.05), "guide": 0, "insurance": round(hpp*0.02), "other": 0},
                     [("Jakarta → Jeddah", "Keberangkatan & penerbangan"), ("Makkah", "Umrah & ibadah"),
                      ("Madinah", "Ziarah & Raudhah")], deplist)
        up += 1; deps_n += len(deplist)

    await db.demo_seed_flags.insert_one({"batch": "10F1", "created_at": now})
    print(f"SEED DONE | sales_users={su} destinations={de} tour_packages={tp} umrah_packages={up} departures={deps_n}")

asyncio.run(main())
