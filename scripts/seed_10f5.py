"""Phase 10F-5 — Seed Suppliers (+bank accounts) + DEMO WhatsApp conversations (DB only, no real WA).
Conversations reference ACTUAL demo packages/prices. Idempotent (10F5).
Does not call WhatsApp API. Does not touch Tax/AI config/API.co.id/SA/Accounting/customer contact-of-record."""
import asyncio, random
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import uuid

random.seed(9051)
ENV = {}
with open("/app/backend/.env") as fh:
    for ln in fh:
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1); ENV[k] = v.strip().strip('"')
db = AsyncIOMotorClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
def iso(dt): return dt.astimezone(timezone.utc).isoformat()
NOW = datetime.now(timezone.utc)

SUPPLIERS = [
    ("PT Garuda Mitra Tours", "Airline", "Reservation", "021-55501001", "res@garudamitra.co.id"),
    ("PT Saudi Hospitality Services", "Hotel", "Booking Dept", "021-55501002", "booking@saudihospitality.co.id"),
    ("PT Global Hotel Services", "Hotel", "Sales", "021-55501003", "sales@globalhotel.co.id"),
    ("PT Nusantara Wisata Transport", "Transport", "Operasional", "031-55501004", "ops@nusantaratransport.co.id"),
    ("PT Amanah Travel Services", "Tour Operator", "Partnership", "022-55501005", "partner@amanahtravel.co.id"),
    ("PT Barokah Visa Center", "Visa Provider", "Visa Dept", "021-55501006", "visa@barokahvisa.co.id"),
    ("PT Sakinah Muthawwif Services", "Muthawwif", "Koordinator", "021-55501007", "koordinator@sakinah.co.id"),
    ("PT Lintas Benua Airlines Agent", "Airline", "Ticketing", "021-55501008", "ticket@lintasbenua.co.id"),
    ("PT Aman Sentosa Insurance", "Insurance", "Corporate", "021-55501009", "corp@amansentosa.co.id"),
    ("PT Madinah Hospitality Group", "Hotel", "Reservation", "021-55501010", "reservasi@madinahgroup.co.id"),
    ("PT Cahaya Tour Operator", "Tour Operator", "Sales", "0274-55501011", "sales@cahayatour.co.id"),
    ("PT Armada Prima Transport", "Transport", "Fleet", "0341-55501012", "fleet@armadaprima.co.id"),
]
BANKS = ["BCA", "Mandiri", "BNI", "BRI", "CIMB Niaga"]

async def seed_suppliers():
    n = 0
    for name, typ, contact, phone, email in SUPPLIERS:
        if await db.suppliers.find_one({"name": name}):
            continue
        accts = []
        for j in range(random.choice([1, 1, 2])):
            accts.append({"id": str(ObjectId()), "bank_name": random.choice(BANKS), "account_holder": name,
                          "account_number": "".join(random.choice("0123456789") for _ in range(10)),
                          "is_primary": (j == 0), "status": "ACTIVE", "created_at": iso(NOW)})
        await db.suppliers.insert_one({"name": name, "type": typ, "contact": contact, "email": email, "phone": phone,
            "address": "Jakarta, Indonesia", "tax_info": "", "bank_account": accts[0]["bank_name"] + " " + accts[0]["account_number"],
            "bank_accounts": accts, "status": "ACTIVE", "is_deleted": False,
            "created_at": iso(NOW), "created_by": "System (10F5)", "seed_batch": "10F5"})
        n += 1
    return n

def price_txt(v): return "Rp" + f"{int(v):,}".replace(",", ".")

async def add_thread(cust, msgs, base_dt, status="LOGGED", lead_id=None, booking_id=None, attribution=None):
    """msgs = list of (sender_type, text). sender_type in CUSTOMER/AI/SALES."""
    wa = cust.get("whatsapp") or ""
    t = base_dt
    docs = []
    for st, text in msgs:
        t = t + timedelta(minutes=random.randint(1, 8))
        direction = "INBOUND" if st == "CUSTOMER" else "OUTBOUND"
        aioh = "HUMAN" if st == "SALES" else ("AUTO" if st == "AI" else "")
        docs.append({"conversation_id": str(uuid.uuid4()), "customer_id": str(cust["_id"]),
            "customer_name": cust.get("full_name"), "whatsapp": wa, "channel": "WHATSAPP", "direction": direction,
            "message": text, "message_type": "TEXT", "sender_type": st,
            "sender_name": ("AI Agent" if st == "AI" else (cust.get("sales_pic_name") if st == "SALES" else cust.get("full_name"))),
            "ai_or_human": aioh, "status": "SENT", "lead_id": lead_id, "booking_id": booking_id,
            "attribution": attribution, "timestamp": iso(t), "created_at": iso(t), "seed_batch": "10F5"})
    # last message status (e.g. requires human handover) applied to final doc
    if status != "LOGGED" and docs:
        docs[-1]["status"] = status
    await db.conversations.insert_many(docs)
    return len(docs)

async def main():
    if await db.demo_seed_flags.find_one({"batch": "10F5"}):
        print("Already seeded (10F5). Skipping."); return
    n_sup = await seed_suppliers()

    pkgs = {str(p["_id"]): p for p in await db.packages.find({"seed_batch": "10F1"}).to_list(100)}
    tours = [p for p in pkgs.values() if p.get("product_type") == "TOUR"]
    umrahs = [p for p in pkgs.values() if p.get("product_type") == "UMRAH"]
    bookings = await db.bookings.find({"seed_batch": "10F3"}).to_list(500)
    auto_bk = [b for b in bookings if b.get("booking_source") == "AUTO SALES"]
    sales_bk = [b for b in bookings if b.get("booking_source") == "SALES"]

    async def cust(cid):
        return await db.customers.find_one({"_id": ObjectId(cid)}) if ObjectId.is_valid(cid) else None

    conv_threads = 0
    conv_msgs = 0

    # --- AUTO SALES threads: AI -> Lead -> Booking ---
    for b in auto_bk[:3]:
        c = await cust(b["customer_id"])
        if not c:
            continue
        p = pkgs.get(b["package_id"]); pax = int(b.get("pax") or 1); total = int(b.get("total") or 0)
        pname = b.get("package_name"); dep = ""
        msgs = [
            ("CUSTOMER", f"Halo Kak, ada paket {pname}?"),
            ("AI", f"Ada Kak. Tersedia paket {pname}. Untuk berapa pax rencananya?"),
            ("CUSTOMER", f"Untuk {pax} orang berapa ya?"),
            ("AI", f"Untuk {pax} pax totalnya sekitar {price_txt(total)} Kak."),
            ("CUSTOMER", "Oke saya minat, tolong dibooking ya."),
            ("AI", f"Baik Kak, booking {b.get('booking_number')} sudah kami buatkan. Silakan lanjut pembayaran DP ya 🙏"),
        ]
        conv_msgs += await add_thread(c, msgs, NOW - timedelta(days=random.randint(5, 40)),
                                      lead_id=None, booking_id=str(b["_id"]), attribution="AUTO SALES")
        conv_threads += 1

    # --- Human Handover threads: AI -> REQUIRES_HUMAN -> SALES -> Booking ---
    for b in sales_bk[:3]:
        c = await cust(b["customer_id"])
        if not c:
            continue
        pname = b.get("package_name"); pax = int(b.get("pax") or 1); total = int(b.get("total") or 0)
        msgs = [
            ("CUSTOMER", f"Kak saya mau tanya detail {pname}, bisa nego harga?"),
            ("AI", "Baik Kak, untuk permintaan khusus/nego harga akan saya hubungkan ke tim Sales kami ya."),
            ("SALES", f"Halo Kak, saya {c.get('sales_pic_name')} dari tim Sales. Untuk {pax} pax bisa kami bantu penawaran terbaik."),
            ("CUSTOMER", "Siap, kalau cocok saya lanjut booking."),
            ("SALES", f"Sudah kami buatkan booking {b.get('booking_number')} ya Kak, total {price_txt(total)}."),
        ]
        conv_msgs += await add_thread(c, msgs, NOW - timedelta(days=random.randint(5, 40)),
                                      status="RESOLVED", booking_id=str(b["_id"]), attribution="SALES")
        conv_threads += 1

    # --- Varied inquiry types (reference real packages) ---
    other_custs = await db.customers.find({"seed_batch": "10F2"}).to_list(400)
    random.shuffle(other_custs)
    ci = 0
    def nextc():
        nonlocal ci
        c = other_custs[ci % len(other_custs)]; ci += 1; return c

    tour = random.choice(tours); um = random.choice(umrahs)
    tpax = 4; tprice = int(tour["selling_price"]) * tpax
    templates = [
        ("Package Inquiry", [("CUSTOMER", f"Halo Kak, ada paket {tour['package_name']}?"),
            ("AI", f"Ada Kak, paket {tour['package_name']} ke {tour.get('destination')} durasi {tour.get('duration')}.")]),
        ("Price Inquiry", [("CUSTOMER", f"Paket {tour['package_name']} untuk {tpax} orang berapa?"),
            ("AI", f"Untuk {tpax} pax totalnya sekitar {price_txt(tprice)} Kak.")]),
        ("Seat Inquiry", [("CUSTOMER", "Masih ada seat untuk keberangkatan terdekat?"),
            ("AI", f"Masih tersedia Kak untuk {tour['package_name']}, seat terbatas ya.")]),
        ("Itinerary Inquiry", [("CUSTOMER", "Boleh minta itinerary lengkapnya?"),
            ("AI", f"Tentu Kak, itinerary {tour['package_name']} sudah kami kirimkan via PDF.")]),
        ("Umrah Inquiry", [("CUSTOMER", f"Kak ada paket {um['package_name']}?"),
            ("AI", f"Ada Kak, {um['package_name']} sekitar {price_txt(int(um['selling_price']))}/pax, hotel dekat Masjidil Haram.")]),
        ("Payment Inquiry", [("CUSTOMER", "Pembayaran bisa dicicil?"),
            ("AI", "Bisa Kak, DP dulu lalu pelunasan sebelum keberangkatan.")]),
        ("Follow Up", [("SALES", "Halo Kak, apakah sudah ada keputusan untuk paketnya?"),
            ("CUSTOMER", "Masih diskusi keluarga dulu ya Kak.")]),
        ("Package Comparison", [("CUSTOMER", f"Bagusan {tour['package_name']} atau {random.choice(tours)['package_name']}?"),
            ("AI", "Keduanya bagus Kak, tergantung durasi & budget. Boleh saya bantu bandingkan?")]),
        ("Customer Not Interested", [("CUSTOMER", "Maaf Kak untuk sekarang belum jadi dulu."),
            ("AI", "Baik Kak, terima kasih. Kami kabari kalau ada promo ya 🙏")]),
        ("Repeat Customer", [("CUSTOMER", "Kak saya mau booking lagi seperti tahun lalu."),
            ("AI", "Senang sekali Kak! Untuk destinasi yang sama atau mau coba paket baru?")]),
    ]
    handover_i = 0
    for name, msgs in templates:
        c = nextc()
        st = "REQUIRES_HUMAN" if name in ("Package Comparison", "Follow Up") else "LOGGED"
        conv_msgs += await add_thread(c, msgs, NOW - timedelta(days=random.randint(1, 30)), status=st, attribution="AI")
        conv_threads += 1

    await db.demo_seed_flags.insert_one({"batch": "10F5", "created_at": iso(NOW)})
    print(f"SEED DONE | suppliers={n_sup} conv_threads={conv_threads} conv_messages={conv_msgs}")

asyncio.run(main())
