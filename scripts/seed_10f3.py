"""Phase 10F-3 — Seed Quotations + Bookings (converted). Reuses 10F-2 leads + 10F-1 packages/departures.
This CRM has NO separate Order entity: Quotation converts directly to Booking (Booking = the order record).
Idempotent (demo_seed_flags 10F3). No payments/commission (those are 10F-4). Does not touch SA/Accounting/Tax/AI/WA/packages."""
import asyncio, random
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

random.seed(773)
ENV = {}
with open("/app/backend/.env") as fh:
    for ln in fh:
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1); ENV[k] = v.strip().strip('"')
client = AsyncIOMotorClient(ENV["MONGO_URL"])
db = client[ENV["DB_NAME"]]
NOW = datetime.now(timezone.utc).isoformat()

async def next_num(prefix, coll, field):
    n = await coll.count_documents({}) + 1
    while await coll.find_one({field: f"{prefix}-{n:05d}"}):
        n += 1
    return f"{prefix}-{n:05d}"

# quotation status plan for the ~50 quotations (non-converted mix)
NONCONV = (["SENT"]*6 + ["NEGOTIATION"]*4 + ["FOLLOW UP"]*3 + ["DRAFT"]*3 + ["EXPIRED"]*2 + ["CANCELLED"]*2)
TARGET_CONVERTED = 30
BOOK_STATUS = (["CONFIRMED"]*18 + ["PENDING"]*5 + ["COMPLETED"]*4 + ["CANCELLED"]*3)

async def main():
    if await db.demo_seed_flags.find_one({"batch": "10F3"}):
        print("Already seeded (10F3). Skipping."); return
    leads = await db.leads.find({"seed_batch": "10F2"}).to_list(500)
    if not leads:
        print("ERROR: no 10F2 leads"); return
    # departures per package (with live capacity)
    deps = {}
    async for d in db.departures.find({}):
        deps.setdefault(d.get("package_id"), []).append(d)
    pkg_cache = {}
    async def pkg(pid):
        if pid not in pkg_cache:
            pkg_cache[pid] = await db.packages.find_one({"_id": ObjectId(pid)}) if ObjectId.is_valid(pid) else None
        return pkg_cache[pid]

    random.shuffle(leads)
    quotes_total = 50
    chosen = leads[:quotes_total] if len(leads) >= quotes_total else leads
    conv_idx = set(range(min(TARGET_CONVERTED, len(chosen))))  # first N are conversion candidates

    q_count = o_count = b_count = auto_count = manual_count = 0
    conv_made = 0
    status_dist = {}
    nonconv_i = 0
    total_pax_book = 0

    for i, ld in enumerate(chosen):
        p = await pkg(ld["package_id"])
        if not p:
            continue
        pax = int(ld.get("pax") or 1)
        per_pax = float(p.get("selling_price") or 0)
        subtotal = per_pax * pax
        pct = random.choice([0, 0, 5, 10])
        disc = round(subtotal * pct / 100)
        total = subtotal - disc
        # pick a departure for this package
        dep = None
        for cand in deps.get(ld["package_id"], []):
            avail = int(cand.get("quota") or 0) - int(cand.get("confirmed_pax") or 0)
            if avail >= pax and cand.get("status") not in ("CLOSED", "CANCELLED"):
                dep = cand; break
        make_conv = (i in conv_idx) and dep is not None
        status = "CONVERTED" if make_conv else NONCONV[nonconv_i % len(NONCONV)]
        if not make_conv:
            nonconv_i += 1
        qnum = await next_num("QT", db.quotations, "quotation_number")
        qdoc = {"quotation_number": qnum, "customer_id": ld["customer_id"], "customer_name": ld["customer_name"],
                "package_id": ld["package_id"], "package_name": p["package_name"], "package_version": p.get("version", 1),
                "departure_id": str(dep["_id"]) if dep else None, "lead_id": str(ld["_id"]), "pax": pax, "room_type": "QUAD",
                "addons": [], "per_pax_price": per_pax, "base_price": per_pax, "gross": subtotal, "addon_total": 0,
                "subtotal": subtotal, "discount_type": "PERCENT", "discount_value": pct, "discount_percent": pct,
                "discount_amount": disc, "tax_percent": 0, "tax_amount": 0, "total": total,
                "discount_status": "APPROVED", "discount_level": "NONE", "status": status,
                "notes": f"Penawaran {p['package_name']} untuk {pax} pax.", "terms": p.get("terms", ""),
                "sales_pic_id": ld["sales_pic_id"], "sales_pic_name": ld["sales_pic_name"], "branch": ld.get("branch", ""),
                "converted_booking_id": None, "created_at": NOW, "created_by": ld["sales_pic_name"], "seed_batch": "10F3"}
        qres = await db.quotations.insert_one(qdoc)
        qid = str(qres.inserted_id)
        q_count += 1
        status_dist[status] = status_dist.get(status, 0) + 1

        if make_conv:
            bstatus = BOOK_STATUS[conv_made % len(BOOK_STATUS)]
            is_auto = (conv_made % 4 == 0)  # ~25% AUTO SALES
            bnum = await next_num("BKG", db.bookings, "booking_number")
            booking = {"booking_number": bnum, "quotation_id": qid, "customer_id": ld["customer_id"],
                       "customer_name": ld["customer_name"], "package_id": ld["package_id"], "package_name": p["package_name"],
                       "package_version": p.get("version", 1), "departure_id": str(dep["_id"]), "pax": pax, "room_type": "QUAD",
                       "addons": [], "booking_source": "AUTO SALES" if is_auto else "SALES",
                       "per_pax_price": per_pax, "subtotal": subtotal, "discount_percent": pct, "discount_amount": disc,
                       "tax_percent": 0, "tax_amount": 0, "total": total, "payment_schedule": [], "status": bstatus,
                       "sales_pic_id": ld["sales_pic_id"], "sales_pic_name": ld["sales_pic_name"],
                       "sales_type": "AI" if is_auto else "MANUAL", "sales_user_id": ld["sales_pic_id"],
                       "sales_name": ("AI Agent" if is_auto else ld["sales_pic_name"]),
                       "idempotency_key": None, "external_order_id": None, "n8n_workflow_id": None,
                       "branch": ld.get("branch", ""), "created_at": NOW,
                       "created_by": "AI AGENT" if is_auto else ld["sales_pic_name"], "seed_batch": "10F3"}
            bres = await db.bookings.insert_one(booking)
            bid = str(bres.inserted_id)
            await db.quotations.update_one({"_id": qres.inserted_id}, {"$set": {"converted_booking_id": bid, "status": "CONVERTED"}})
            # consume seats unless cancelled
            if bstatus != "CANCELLED":
                await db.departures.update_one({"_id": dep["_id"]}, {"$inc": {"confirmed_pax": pax}})
                dep["confirmed_pax"] = int(dep.get("confirmed_pax") or 0) + pax
            b_count += 1; o_count += 1; total_pax_book += pax
            if is_auto:
                auto_count += 1
            else:
                manual_count += 1
            conv_made += 1

    await db.demo_seed_flags.insert_one({"batch": "10F3", "created_at": NOW})
    print(f"SEED DONE | quotations={q_count} converted={status_dist.get('CONVERTED',0)} "
          f"orders={o_count} bookings={b_count} book_pax={total_pax_book} "
          f"auto_sales={auto_count} sales={manual_count}")
    print("quotation_status_dist:", status_dist)

asyncio.run(main())
