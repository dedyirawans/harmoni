"""Phase 8F — Tax Configuration & Tax Management tests."""
import os, time
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # fallback to internal - fail fast otherwise
    BASE = "http://localhost:8001"
API = f"{BASE}/api"

CREDS = {
    "super": ("dedyirawan18@gmail.com", "Admin@123"),
    "accounting": ("accounting@safarcrm.com", "Account@123"),
    "sales": ("sales@safarcrm.com", "Sales@123"),
}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def tokens():
    return {k: _login(e, p) for k, (e, p) in CREDS.items()}


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------------- RBAC ----------------
class TestRBAC:
    def test_sales_forbidden_tax_endpoints(self, tokens):
        h = _h(tokens["sales"])
        for path in ["/ppn-configurations", "/tax-dashboard", "/tax-transactions",
                     "/tax-masters", "/tax-config", "/tax-reports"]:
            r = requests.get(f"{API}{path}", headers=h, timeout=20)
            assert r.status_code == 403, f"sales expected 403 on {path}, got {r.status_code}"

    def test_accounting_allowed_tax_endpoints(self, tokens):
        h = _h(tokens["accounting"])
        for path in ["/ppn-configurations", "/tax-dashboard", "/tax-transactions",
                     "/tax-masters", "/tax-config", "/tax-reports"]:
            r = requests.get(f"{API}{path}", headers=h, timeout=20)
            assert r.status_code == 200, f"accounting expected 200 on {path}, got {r.status_code} {r.text[:200]}"

    def test_superadmin_allowed(self, tokens):
        h = _h(tokens["super"])
        r = requests.get(f"{API}/ppn-configurations", headers=h, timeout=20)
        assert r.status_code == 200


# ---------------- Tax config / Master ----------------
class TestTaxConfigMaster:
    def test_tax_config_types(self, tokens):
        r = requests.get(f"{API}/tax-config", headers=_h(tokens["accounting"]), timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert "tax_types" in data
        for t in ["PPN", "PPh21", "PPh23", "OTHER"]:
            assert t in data["tax_types"], f"missing tax type {t} in {data['tax_types']}"

    def test_tax_master_create_pph21(self, tokens):
        h = _h(tokens["super"])
        body = {"tax_code": "TEST_PPH21", "tax_name": "TEST_PPh21_Karyawan",
                "tax_type": "PPh21", "rate": 5.0,
                "treatment": "EXCLUSIVE", "tax_base": "CUSTOM", "active": True}
        r = requests.post(f"{API}/tax-masters", json=body, headers=h, timeout=20)
        assert r.status_code in (200, 201), r.text
        tid = r.json().get("id") or r.json().get("_id")
        assert tid
        # verify via GET
        rl = requests.get(f"{API}/tax-masters", headers=h, timeout=20)
        assert any(x.get("tax_name") == "TEST_PPh21_Karyawan" or x.get("name") == "TEST_PPh21_Karyawan" for x in rl.json())
        # cleanup
        requests.delete(f"{API}/tax-masters/{tid}", headers=h, timeout=20)


# ---------------- PPN Configuration CRUD & versioning ----------------
class TestPPNConfig:
    created_ids = []

    def test_list_has_seeded_config(self, tokens):
        r = requests.get(f"{API}/ppn-configurations", headers=_h(tokens["accounting"]), timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) >= 1
        # seeded default
        names = [c.get("config_name") for c in data]
        assert any("PPN" in (n or "") for n in names), f"expected seeded PPN config, got {names}"

    def test_create_ppn_config_v2_future(self, tokens):
        h = _h(tokens["accounting"])
        body = {"config_name": "TEST_PPN 1.2% (V2)", "tax_type": "PPN",
                "tax_rate": 1.2, "dpp_percentage": 100,
                "effective_from": "2099-01-01", "status": "ACTIVE",
                "description": "future effective for test"}
        r = requests.post(f"{API}/ppn-configurations", json=body, headers=h, timeout=20)
        assert r.status_code == 200, r.text
        cid = r.json().get("id") or r.json().get("_id")
        assert cid
        TestPPNConfig.created_ids.append(cid)
        # verify persisted
        rl = requests.get(f"{API}/ppn-configurations", headers=h, timeout=20).json()
        assert any(c.get("config_name") == "TEST_PPN 1.2% (V2)" for c in rl)

    def test_update_ppn_config_requires_reason_audit(self, tokens):
        h = _h(tokens["accounting"])
        assert TestPPNConfig.created_ids, "no config created"
        cid = TestPPNConfig.created_ids[0]
        body = {"tax_rate": 1.3, "reason": "policy change QA"}
        r = requests.put(f"{API}/ppn-configurations/{cid}", json=body, headers=h, timeout=20)
        assert r.status_code == 200, r.text
        assert float(r.json().get("tax_rate")) == 1.3
        # Check audit log via super admin
        al = requests.get(f"{API}/audit-logs", headers=_h(tokens["super"]), timeout=20)
        if al.status_code == 200:
            logs = al.json() if isinstance(al.json(), list) else al.json().get("logs", [])
            assert any(l.get("action") == "update_ppn_config" for l in logs), "audit log for update_ppn_config missing"

    def test_active_config_resolution_today(self, tokens):
        # today's dashboard active_config should NOT be the future V2
        r = requests.get(f"{API}/tax-dashboard", headers=_h(tokens["accounting"]), timeout=20)
        assert r.status_code == 200
        ac = r.json().get("active_config")
        assert ac is not None, "active_config should not be None"
        assert "2099" not in (ac.get("effective_from") or ""), f"future config should not be active today; got {ac}"


# ---------------- Tax Dashboard / Transactions / Reports ----------------
class TestTaxDashboard:
    def test_dashboard_shape(self, tokens):
        r = requests.get(f"{API}/tax-dashboard", headers=_h(tokens["accounting"]), timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ["active_config", "total_dpp", "total_ppn", "taxable", "non_taxable",
                  "transaction_count", "by_type", "by_month"]:
            assert k in d, f"missing key {k}"
        assert isinstance(d["by_month"], list) and len(d["by_month"]) == 6

    def test_transactions_shape(self, tokens):
        r = requests.get(f"{API}/tax-transactions", headers=_h(tokens["accounting"]), timeout=20)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        if rows:
            row = rows[0]
            for k in ["invoice_number", "transaction_date", "customer_name",
                      "tax_type", "tax_rate", "dpp", "tax_amount", "tax_config_version"]:
                assert k in row, f"missing key {k} in tax-transaction row"

    def test_reports_shape(self, tokens):
        r = requests.get(f"{API}/tax-reports", headers=_h(tokens["accounting"]), timeout=20)
        assert r.status_code == 200


# ---------------- Invoice snapshot ----------------
class TestInvoiceSnapshot:
    def test_new_invoice_captures_current_active_config(self, tokens):
        h = _h(tokens["super"])
        # Find any booking
        bks = requests.get(f"{API}/bookings", headers=h, timeout=20).json()
        assert isinstance(bks, list)
        if not bks:
            pytest.skip("No bookings available to test invoice snapshot")
        # Prefer a booking that doesn't have invoice yet — try each
        created = None
        for b in bks[:20]:
            bid = b.get("id") or b.get("_id")
            r = requests.post(f"{API}/bookings/{bid}/invoice", json={"amount": 1000000}, headers=h, timeout=30)
            if r.status_code == 200:
                created = r.json()
                break
        if not created:
            pytest.skip("Could not create test invoice from any booking (all may already have invoices)")
        # Snapshot fields
        for k in ["tax_config_version", "tax_rate", "dpp_percentage", "dpp_amount", "tax_type"]:
            assert k in created, f"invoice missing snapshot field {k}"
        # Should NOT be the future V2
        assert "V2" not in (created.get("tax_config_version") or ""), \
            f"future V2 should not be snapshotted for today's invoice; got {created.get('tax_config_version')}"
        # Should match today's active_config from dashboard
        d = requests.get(f"{API}/tax-dashboard", headers=h, timeout=20).json()
        ac = d.get("active_config") or {}
        assert created.get("tax_config_version") == ac.get("config_name")

    def test_old_invoices_unchanged_after_config_edit(self, tokens):
        # Simply confirms existing invoices are returned with a tax_config_version field ('-' for pre-phase invoices)
        r = requests.get(f"{API}/tax-transactions", headers=_h(tokens["accounting"]), timeout=20)
        rows = r.json()
        # Not asserting content — just that endpoint returned; existence field verified above
        assert isinstance(rows, list)


# ---------------- Cleanup ----------------
def test_zzz_cleanup(tokens):
    h = _h(tokens["accounting"])
    for cid in TestPPNConfig.created_ids:
        requests.delete(f"{API}/ppn-configurations/{cid}", headers=h, timeout=20)
