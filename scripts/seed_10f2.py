"""Phase 10F-2 — Seed realistic Indonesian Customers + Leads + Follow-ups + Sales Activities.
Idempotent (demo_seed_flags batch=10F2). Leads reference ACTUAL 10F-1 packages.
Does NOT create bookings/payments/invoices/commission. Does NOT touch SA/Accounting/Packages/Tax/AI/WhatsApp."""
import asyncio, random
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

random.seed(1042)
ENV = {}
with open("/app/backend/.env") as fh:
    for ln in fh:
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            ENV[k] = v.strip().strip('"')
client = AsyncIOMotorClient(ENV["MONGO_URL"])
db = client[ENV["DB_NAME"]]
NOW = datetime.now(timezone.utc)
def iso(dt): return dt.replace(tzinfo=timezone.utc).isoformat() if dt.tzinfo is None else dt.astimezone(timezone.utc).isoformat()

FIRST = ["Budi","Siti","Agus","Dewi","Rudi","Ani","Joko","Rina","Andi","Sri","Bambang","Wati","Hendra","Nur","Eko",
         "Yuni","Dedi","Lestari","Fajar","Maya","Rizky","Indah","Arif","Putri","Doni","Ratna","Wahyu","Fitri","Iwan",
         "Ayu","Taufik","Novi","Gunawan","Diah","Hakim","Sari","Reza","Mega","Bayu","Intan","Surya","Citra","Adi","Yanti"]
LAST = ["Santoso","Wijaya","Pratama","Nugroho","Halim","Saputra","Kusuma","Hidayat","Setiawan","Wibowo","Permana",
        "Maulana","Firmansyah","Suryadi","Handoko","Cahyono","Anggraini","Puspita","Ramadhan","Kurniawan","Susanto",
        "Hartono","Gunawan","Prabowo","Yulianto","Rahmawati","Sihombing","Simatupang","Tanuwijaya","Iskandar"]
CITY_PROV = {"Jakarta":"DKI Jakarta","Surabaya":"Jawa Timur","Sidoarjo":"Jawa Timur","Malang":"Jawa Timur",
    "Bandung":"Jawa Barat","Semarang":"Jawa Tengah","Yogyakarta":"DI Yogyakarta","Denpasar":"Bali",
    "Makassar":"Sulawesi Selatan","Medan":"Sumatera Utara","Bekasi":"Jawa Barat","Tangerang":"Banten","Depok":"Jawa Barat"}
CITIES = list(CITY_PROV.keys())
STATUSES = ["NEW","PROSPECT","ACTIVE","CUSTOMER","REPEAT CUSTOMER","INACTIVE"]
STATUS_W = [18,22,20,18,12,10]
TYPE_MAP = {"NEW":"Prospect","PROSPECT":"Prospect","ACTIVE":"Customer","CUSTOMER":"Customer","REPEAT CUSTOMER":"VIP","INACTIVE":"Prospect"}
SOURCES = ["WhatsApp","Instagram","Facebook","Website","Referral","Google","TikTok","Walk In","Existing Customer","Event"]
LEAD_STAGES = ["NEW","CONTACTED","QUALIFIED","QUOTATION","NEGOTIATION","BOOKING"]
LEAD_STAGE_W = [22,20,18,16,14,10]
FU_TYPES = ["WhatsApp","Call","Email","Meeting"]
ACT_TYPES = ["Call","WhatsApp","Email","Meeting"]
TIMELINE = [("customer_contacted","Customer dihubungi"),("whatsapp_chat","Percakapan WhatsApp"),
    ("phone_call","Telepon ke customer"),("package_presentation","Presentasi paket"),
    ("quotation_requested","Quotation diminta"),("meeting","Meeting dengan customer")]

async def main():
    if await db.demo_seed_flags.find_one({"batch": "10F2"}):
        print("Already seeded (10F2). Skipping."); return
    sales = await db.users.find({"email": {"$regex": "@harmoniwisata.co.id$"}, "role": "sales"}).to_list(50)
    if len(sales) < 5:
        print("ERROR: expected 5 harmoniwisata sales users, found", len(sales)); return
    sales_w = [30, 25, 20, 15, 10][:len(sales)]
    pkgs = await db.packages.find({"seed_batch": "10F1"}).to_list(100)
    if not pkgs:
        print("ERROR: no 10F1 packages found"); return
    deps_by_pkg = {}
    async for d in db.departures.find({}):
        deps_by_pkg.setdefault(d.get("package_id"), []).append(d.get("departure_date"))

    base_count = await db.customers.count_documents({})
    n_cust = 130
    cust_docs, used_wa = [], set()
    for i in range(n_cust):
        fn = f"{random.choice(FIRST)} {random.choice(LAST)}"
        while True:
            wa = "0812" + "".join(random.choice("0123456789") for _ in range(8))
            if wa not in used_wa:
                used_wa.add(wa); break
        city = random.choice(CITIES)
        sp = random.choices(sales, weights=sales_w)[0]
        status = random.choices(STATUSES, weights=STATUS_W)[0]
        created = NOW - timedelta(days=random.randint(3, 300))
        slug = fn.lower().replace(" ", ".")
        cust_docs.append({
            "customer_code": f"CUST-{base_count + i + 1:05d}", "full_name": fn,
            "whatsapp": wa, "phone": wa, "email": f"{slug}{random.randint(1,999)}@mail.demo",
            "gender": random.choice(["Male","Female"]), "date_of_birth": "",
            "address": f"Jl. {random.choice(LAST)} No. {random.randint(1,199)}", "city": city,
            "province": CITY_PROV[city], "postal_code": str(random.randint(10000, 99999)), "country": "Indonesia",
            "customer_type": TYPE_MAP[status], "status": status,
            "customer_source": random.choice(SOURCES), "tags": [], "notes": "",
            "sales_pic_id": sp["_id"] if isinstance(sp["_id"], str) else str(sp["_id"]),
            "sales_pic_name": sp["name"], "branch": sp.get("branch", ""),
            "is_deleted": False, "created_at": iso(created), "created_by": "System (10F2)", "seed_batch": "10F2"})
    res = await db.customers.insert_many(cust_docs)
    cust_ids = [str(x) for x in res.inserted_ids]
    for cid, cd in zip(cust_ids, cust_docs):
        cd["_id"] = cid

    # Leads for ~65% of customers
    lead_count = await db.leads.count_documents({})
    lead_customers = random.sample(cust_docs, 85)
    leads, li = [], 0
    for cd in lead_customers:
        p = random.choice(pkgs)
        pid = str(p["_id"])
        dep_dates = deps_by_pkg.get(pid) or []
        dep = random.choice(dep_dates) if dep_dates else ""
        stage = random.choices(LEAD_STAGES + ["LOST"], weights=LEAD_STAGE_W + [12])[0]
        pax = random.randint(1, 4)
        created = NOW - timedelta(days=random.randint(1, 90))
        leads.append({
            "lead_code": f"LEAD-{lead_count + li + 1:05d}", "customer_id": cd["_id"], "customer_name": cd["full_name"],
            "source": cd["customer_source"], "interested_package": p["package_name"], "package_id": pid,
            "package_type": p.get("product_type", ""), "package_name": p["package_name"],
            "destination_id": pid, "destination_name": p.get("destination", ""), "destination": p.get("destination", ""),
            "pax": pax, "budget": round(float(p.get("selling_price") or 0) * pax), "departure_date": dep,
            "status": stage, "next_follow_up": "", "notes": f"Tertarik {p['package_name']} untuk {pax} pax.",
            "sales_pic_id": cd["sales_pic_id"], "sales_pic_name": cd["sales_pic_name"], "branch": cd["branch"],
            "last_contact": iso(created), "created_at": iso(created), "is_deleted": False, "seed_batch": "10F2"})
        li += 1
    res = await db.leads.insert_many(leads)
    lead_ids = [str(x) for x in res.inserted_ids]
    for lid, ld in zip(lead_ids, leads):
        ld["_id"] = lid

    # Follow-ups (~75% of leads) with mixed pending/overdue/scheduled/completed
    fus = []
    for ld in leads:
        if random.random() > 0.75:
            continue
        n = random.randint(1, 2)
        for _ in range(n):
            roll = random.random()
            if roll < 0.4:  # completed
                due = NOW - timedelta(days=random.randint(2, 30))
                status, comp = "completed", iso(due + timedelta(hours=2))
            elif roll < 0.7:  # overdue (pending, past due)
                due = NOW - timedelta(days=random.randint(1, 10)); status, comp = "pending", None
            else:  # scheduled/pending (future)
                due = NOW + timedelta(days=random.randint(1, 21)); status, comp = "pending", None
            doc = {"customer_id": ld["customer_id"], "customer_name": ld["customer_name"], "lead_id": ld["_id"],
                   "activity_type": random.choice(FU_TYPES), "due_date": iso(due),
                   "notes": f"Follow up {ld['interested_package']}", "status": status,
                   "sales_pic_id": ld["sales_pic_id"], "sales_pic_name": ld["sales_pic_name"], "branch": ld["branch"],
                   "created_at": iso(due - timedelta(days=random.randint(1, 5))), "seed_batch": "10F2"}
            if comp:
                doc["completed_at"] = comp
            fus.append(doc)
    if fus:
        await db.follow_ups.insert_many(fus)

    # Sales activities (typed feed) + lead_activities (timeline)
    acts, tl = [], []
    for ld in leads:
        for _ in range(random.randint(1, 4)):
            ts = NOW - timedelta(days=random.randint(0, 60), hours=random.randint(0, 23))
            acts.append({"activity_type": random.choice(ACT_TYPES), "customer_id": ld["customer_id"],
                "customer_name": ld["customer_name"], "lead_id": ld["_id"],
                "notes": f"Aktivitas terkait {ld['interested_package']}",
                "sales_pic_id": ld["sales_pic_id"], "sales_pic_name": ld["sales_pic_name"], "branch": ld["branch"],
                "timestamp": iso(ts), "seed_batch": "10F2"})
        for _ in range(random.randint(1, 3)):
            t = random.choice(TIMELINE)
            ts = NOW - timedelta(days=random.randint(0, 70))
            tl.append({"customer_id": ld["customer_id"], "lead_id": ld["_id"], "type": t[0], "title": t[1],
                "detail": f"{t[1]} — {ld['interested_package']}", "user_id": ld["sales_pic_id"],
                "user_name": ld["sales_pic_name"], "timestamp": iso(ts), "seed_batch": "10F2"})
    if acts:
        await db.sales_activities.insert_many(acts)
    if tl:
        await db.lead_activities.insert_many(tl)

    await db.demo_seed_flags.insert_one({"batch": "10F2", "created_at": iso(NOW)})
    print(f"SEED DONE | customers={len(cust_docs)} leads={len(leads)} follow_ups={len(fus)} sales_activities={len(acts)} timeline_activities={len(tl)}")

asyncio.run(main())
