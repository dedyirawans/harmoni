import asyncio, os, json, hmac, hashlib, time
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
import httpx
from motor.motor_asyncio import AsyncIOMotorClient

BASE = "http://localhost:8001/api"


def sign(secret, ts, body):
    return hmac.new(secret.encode(), (ts + "." + body).encode(), hashlib.sha256).hexdigest()


def h(api_key, secret, body_str, idem=None):
    ts = str(int(time.time()))
    hd = {"X-API-Key": api_key, "X-Timestamp": ts, "X-Signature": sign(secret, ts, body_str), "Content-Type": "application/json"}
    if idem:
        hd["X-Idempotency-Key"] = idem
    return hd


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    await db.bookings.delete_many({"booking_number": {"$exists": True}, "external_booking_id": {"$regex": "^N8N-TEST-"}})
    await db.customers.delete_many({"whatsapp": "+62999TEST"})
    await db.idempotency_keys.delete_many({"key": {"$regex": "^N8N-TEST-"}})
    await db.packages.delete_many({"package_name": "N8N-PKG"})
    passed, failed = 0, 0

    def chk(name, cond):
        nonlocal passed, failed
        print(("  OK  " if cond else " FAIL ") + name)
        if cond: passed += 1
        else: failed += 1

    async with httpx.AsyncClient(timeout=60) as c:
        tok = (await c.post(f"{BASE}/auth/login", json={"email": os.environ["SUPER_ADMIN_EMAIL"], "password": os.environ["SUPER_ADMIN_PASSWORD"]})).json()["token"]
        H = {"Authorization": f"Bearer {tok}"}
        # active package
        pk = (await c.post(f"{BASE}/packages", headers=H, json={"package_name": "N8N-PKG", "product_type": "UMROH", "sub_category": "OPEN_TRIP", "selling_price": 20000000, "status": "ACTIVE", "min_quota_pax": 1})).json()
        pkg_id = pk["_id"]
        # generate creds
        creds = (await c.post(f"{BASE}/integrations/n8n/api-config/generate", headers=H)).json()
        ak, sec = creds["api_key"], creds["api_secret"]
        chk("generate credentials returns key+secret", bool(ak) and bool(sec))
        cfg = (await c.get(f"{BASE}/integrations/n8n/api-config", headers=H)).json()
        chk("GET api-config masks api_key", cfg["api_key"].startswith("••••") and cfg["has_secret"])

        # 401 no auth
        r = await c.post(f"{BASE}/v1/customers", content='{}', headers={"Content-Type": "application/json"})
        chk("v1 without signature -> 401", r.status_code == 401)
        # 401 bad signature
        r = await c.post(f"{BASE}/v1/customers", content='{}', headers={"X-API-Key": ak, "X-Timestamp": str(int(time.time())), "X-Signature": "bad", "Content-Type": "application/json"})
        chk("v1 bad signature -> 401", r.status_code == 401)

        # create customer
        body = json.dumps({"full_name": "N8N Cust", "whatsapp": "+62999TEST"})
        r = await c.post(f"{BASE}/v1/customers", content=body, headers=h(ak, sec, body))
        j = r.json(); chk("create customer success", r.status_code in (200, 201) and j["success"])
        cid = j["customer"]["_id"]
        chk("customer source N8N + no sales", j["customer"]["customer_source"] == "N8N" and j["customer"]["sales_pic_id"] is None)
        # dedupe
        r = await c.post(f"{BASE}/v1/customers", content=body, headers=h(ak, sec, body))
        chk("duplicate customer returns existing", r.json().get("existing") is True)

        # GET packages (HPP stripped)
        r = await c.get(f"{BASE}/v1/packages", headers=h(ak, sec, ""))
        pkgs = r.json()["packages"]; chk("v1 packages returns active only", all(p["status"] == "ACTIVE" for p in pkgs) and len(pkgs) >= 1)
        chk("v1 packages HPP stripped", all("hpp" not in p and "total_cost" not in p for p in pkgs))

        # booking validation: package not active
        badpk = (await c.post(f"{BASE}/packages", headers=H, json={"package_name": "N8N-PKG2", "product_type": "UMROH", "selling_price": 1, "status": "DRAFT"})).json()
        body = json.dumps({"customer_id": cid, "package_id": badpk["_id"], "pax": 2})
        r = await c.post(f"{BASE}/v1/bookings", content=body, headers=h(ak, sec, body))
        chk("booking PACKAGE_NOT_ACTIVE", r.status_code == 400 and r.json()["error_code"] == "PACKAGE_NOT_ACTIVE")
        await db.packages.delete_many({"package_name": "N8N-PKG2"})

        # create booking (AUTO SALES) with idempotency
        ext = "N8N-TEST-20260811-000125"
        body = json.dumps({"customer_id": cid, "package_id": pkg_id, "pax": 3, "external_booking_id": ext, "travelers": [{"full_name": "A"}, {"full_name": "B"}, {"full_name": "C"}]})
        r = await c.post(f"{BASE}/v1/bookings", content=body, headers=h(ak, sec, body, ext))
        j = r.json(); chk("create booking success", r.status_code in (200, 201) and j["success"])
        bk = j["booking"]
        chk("booking AUTO SALES fields", bk["booking_source"] == "AUTO SALES" and bk["sales_type"] == "AUTO" and bk["sales_user_id"] is None and bk["sales_name"] == "AUTO SALES" and bk["created_by"] == "SYSTEM")
        chk("auto invoice created", bool(j.get("invoice_number")))
        # idempotency: same ext -> same booking, no dup
        r2 = await c.post(f"{BASE}/v1/bookings", content=body, headers=h(ak, sec, body, ext))
        chk("idempotent booking (no duplicate)", r2.json().get("idempotent") is True and r2.json()["booking"]["booking_number"] == bk["booking_number"])
        cnt = await db.bookings.count_documents({"external_booking_id": ext})
        chk("only one booking for external id", cnt == 1)

        # payment via n8n
        body = json.dumps({"booking_id": bk["_id"], "amount": bk["total"], "payment_method": "Transfer"})
        r = await c.post(f"{BASE}/v1/payments", content=body, headers=h(ak, sec, body))
        chk("v1 payment -> Paid", r.json().get("invoice_status") == "Paid")

        # communication log
        body = json.dumps({"customer_id": cid, "phone": "+62999TEST", "direction": "inbound", "message": "Halo", "external_message_id": "wamid.1", "workflow_id": "wf1"})
        r = await c.post(f"{BASE}/v1/communications", content=body, headers=h(ak, sec, body))
        chk("v1 communication saved", r.json()["success"] and r.json()["communication"]["source"] == "N8N")
        # appears in customer 360
        c360 = (await c.get(f"{BASE}/customers/{cid}/360", headers=H)).json()
        chk("communication in customer timeline", any(x.get("kind") == "communication" or "WhatsApp" in (x.get("title") or "") for x in c360["timeline"]))

        # api logs
        logs = (await c.get(f"{BASE}/integrations/n8n/api-logs", headers=H)).json()
        chk("api logs recorded + masked", len(logs) >= 5 and all(l.get("api_key_mask", "").startswith("••••") for l in logs if l.get("api_key_mask")))

        # RBAC: sales/accounting cannot access n8n api-config
        for email, pw in [(os.environ["SALES_EMAIL"], os.environ["SALES_PASSWORD"]), (os.environ["ACCOUNTING_EMAIL"], os.environ["ACCOUNTING_PASSWORD"])]:
            t2 = (await c.post(f"{BASE}/auth/login", json={"email": email, "password": pw})).json()["token"]
            rr = await c.get(f"{BASE}/integrations/n8n/api-config", headers={"Authorization": f"Bearer {t2}"})
            chk(f"{email} n8n api-config -> 403", rr.status_code == 403)

        # cleanup
        await db.bookings.delete_many({"external_booking_id": ext})
        await db.invoices.delete_many({"customer_id": cid})
        await db.payments.delete_many({"booking_id": bk["_id"]})
        await db.travelers.delete_many({"booking_id": bk["_id"]})
        await db.communications.delete_many({"customer_id": cid})
        await db.customers.delete_many({"_id": __import__("bson").ObjectId(cid)})
        await db.packages.delete_many({"package_name": "N8N-PKG"})
        await db.idempotency_keys.delete_many({"key": ext})

    print(f"\nRESULT: {passed} passed, {failed} failed -> {'ALL PASS' if failed == 0 else 'SOME FAILED'}")

asyncio.run(main())
