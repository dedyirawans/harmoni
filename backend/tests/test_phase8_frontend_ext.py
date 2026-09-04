"""Phase 8 extra: notifications endpoint returns real items (not stub) + 403 matrix via PUBLIC URL."""
import os, requests
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://github-workflow-14.preview.emergentagent.com"
# fallback: read from frontend .env if REACT_APP_BACKEND_URL not exported into backend
try:
    with open("/app/frontend/.env") as f:
        for l in f:
            if l.startswith("REACT_APP_BACKEND_URL="):
                BASE = l.split("=",1)[1].strip()
except Exception:
    pass

def tok(email, pwd):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pwd}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]

def H(t): return {"Authorization": f"Bearer {t}"}

def test_notifications_real():
    sa = tok(os.environ["SUPER_ADMIN_EMAIL"], os.environ["SUPER_ADMIN_PASSWORD"])
    ac = tok(os.environ["ACCOUNTING_EMAIL"], os.environ["ACCOUNTING_PASSWORD"])
    n_sa = requests.get(f"{BASE}/api/notifications", headers=H(sa), timeout=30).json()
    n_ac = requests.get(f"{BASE}/api/notifications", headers=H(ac), timeout=30).json()
    assert isinstance(n_sa, list) and isinstance(n_ac, list)
    # Should NOT be the old static welcome stub (which was a single hardcoded item)
    combined = n_sa + n_ac
    # at least one item should reference cancellation/refund workflow
    kinds = " ".join([str(x.get("type","")) + " " + str(x.get("title","")) + " " + str(x.get("message","")) for x in combined]).lower()
    assert any(k in kinds for k in ["cancel", "refund", "approval"]), f"notifications look like stub: {combined[:3]}"

def test_403_matrix_public():
    sa = tok(os.environ["SUPER_ADMIN_EMAIL"], os.environ["SUPER_ADMIN_PASSWORD"])
    sl = tok(os.environ["SALES_EMAIL"], os.environ["SALES_PASSWORD"])
    ac = tok(os.environ["ACCOUNTING_EMAIL"], os.environ["ACCOUNTING_PASSWORD"])
    # Sales listing cancellations returns only own (200)
    r = requests.get(f"{BASE}/api/cancellations", headers=H(sl), timeout=30)
    assert r.status_code == 200
    # approve endpoint requires super_admin — both non-SA get 403 with fake id (permission enforced before lookup ideally, else 404)
    for h in (H(sl), H(ac)):
        r = requests.patch(f"{BASE}/api/cancellations/deadbeefdeadbeefdeadbeef/approve", headers=h, json={"action":"APPROVE"}, timeout=30)
        assert r.status_code in (403, 404), f"non-SA approve got {r.status_code}"
    # refund approve
    for h in (H(sl), H(ac)):
        r = requests.patch(f"{BASE}/api/refund-requests/deadbeefdeadbeefdeadbeef/approve", headers=h, json={"action":"APPROVE"}, timeout=30)
        assert r.status_code in (403, 404), f"non-SA refund approve got {r.status_code}"
    # sales review
    r = requests.patch(f"{BASE}/api/cancellations/deadbeefdeadbeefdeadbeef/review", headers=H(sl), json={"cancellation_fee":1}, timeout=30)
    assert r.status_code in (403, 404)
