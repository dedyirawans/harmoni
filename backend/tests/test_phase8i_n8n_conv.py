import os, time, json, hmac, hashlib, requests, subprocess

API = subprocess.check_output("grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2", shell=True).decode().strip() + "/api"


def login(email, pw):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": pw}).json()["token"]


def gen_creds(sa):
    r = requests.post(f"{API}/integrations/n8n/api-config/generate", headers={"Authorization": f"Bearer {sa}"})
    return r.json()


def signed(method, path, creds, body=None, idem=None):
    ts = str(time.time())
    raw = json.dumps(body) if body is not None else ""
    sig = hmac.new(creds["api_secret"].encode(), (ts + "." + raw).encode(), hashlib.sha256).hexdigest()
    h = {"X-API-Key": creds["api_key"], "X-Timestamp": ts, "X-Signature": sig, "Content-Type": "application/json"}
    if idem:
        h["X-Idempotency-Key"] = idem
    url = f"{API}{path}"
    if method == "GET":
        return requests.get(url, headers=h)
    return requests.post(url, headers=h, data=raw)


def main():
    sa = login("dedyirawan18@gmail.com", "Admin@123")
    creds = gen_creds(sa)
    print("creds ok:", bool(creds.get("api_key")))

    # get an ACTIVE package via v1
    pkgs = signed("GET", "/v1/packages", creds).json()["packages"]
    assert pkgs, "no active packages"
    pid = pkgs[0].get("id") or pkgs[0].get("_id")
    print("package:", pid, pkgs[0].get("package_name") or pkgs[0].get("name"))

    # availability
    av = signed("GET", f"/v1/packages/{pid}/availability", creds).json()
    print("availability:", av)
    assert av["success"] and "available_seat" in av

    wa = "+628123999" + str(int(time.time()))[-4:]
    # inbound customer message (auto-create customer)
    r1 = signed("POST", "/v1/conversations", creds, {"whatsapp": wa, "customer_name": "Budi Test", "direction": "INBOUND", "message": "Ada paket Jepang Oktober?", "n8n_workflow_id": "wf1"}).json()
    cid = r1["conversation"]["customer_id"]
    print("inbound logged, customer:", cid, "sender:", r1["conversation"]["sender_type"])
    assert r1["conversation"]["sender_type"] == "CUSTOMER"

    # AI response
    r2 = signed("POST", "/v1/conversations", creds, {"customer_id": cid, "whatsapp": wa, "direction": "OUTBOUND", "sender_type": "AI", "message": "Ada, Japan Autumn 2026...", "n8n_workflow_id": "wf1"}).json()
    print("AI reply sender:", r2["conversation"]["sender_type"])

    # handover
    r3 = signed("POST", "/v1/conversations", creds, {"customer_id": cid, "whatsapp": wa, "direction": "INBOUND", "message": "mau bicara CS", "requires_human": True}).json()
    print("handover status:", r3["conversation"]["status"])
    assert r3["conversation"]["status"] == "REQUIRES_HUMAN"

    # chronological history
    hist = signed("GET", f"/v1/conversations?customer_id={cid}", creds).json()["conversations"]
    print("history count:", len(hist))
    assert len(hist) == 3 and hist[0]["message"].startswith("Ada paket")

    # order (idempotent) — reuse existing v1 booking; needs departure
    deps = signed("GET", f"/v1/departures?package_id={pid}", creds).json()["departures"]
    depid = (deps[0].get("id") or deps[0].get("_id")) if deps else None
    idem = "ORD-" + str(int(time.time()))
    body = {"customer_id": cid, "package_id": pid, "departure_id": depid, "pax": 2, "booking_source": "AUTO SALES", "external_booking_id": idem}
    b1 = signed("POST", "/v1/bookings", creds, body).json()
    b2 = signed("POST", "/v1/bookings", creds, body).json()  # duplicate
    print("booking1:", b1.get("success"), "source:", (b1.get("booking") or {}).get("booking_source"), "sales_id:", (b1.get("booking") or {}).get("sales_pic_id"))
    print("booking2 idempotent:", b2.get("idempotent"))
    assert b2.get("idempotent") is True, "duplicate not prevented"

    # RBAC: no signature -> 401
    nos = requests.get(f"{API}/v1/packages/{pid}/availability", headers={"X-API-Key": creds["api_key"]})
    print("no-signature status:", nos.status_code)
    assert nos.status_code == 401
    print("ALL 8I ACCEPTANCE CHECKS PASSED")


if __name__ == "__main__":
    main()
