"""Phase: Document Template Preview + Terms rich-text sanitizer regression tests.

Covers:
- POST /api/doc-template/preview for kind=invoice/quotation/receipt with dirty HTML (raw <br>, <ol><li>...) → 200 application/pdf
- PUT /api/doc-template persists invoice_terms/quotation_terms with rich HTML
- Regression: staff GET /api/invoices/{id}/pdf and quotation PDF still 200
"""
import os
import requests
import pytest

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://github-workflow-14.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "dedyirawan18@gmail.com"
ADMIN_PASS = "Admin@123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---- Preview endpoint with dirty HTML ------------------------------------------------
DIRTY_FOOTER = "Terima kasih.<br>Hormat kami<br>Safar Travel"
DIRTY_TERMS_OL = "<ol><li>DP 50%</li><li>Pelunasan H-30</li><li>Tidak refund</li></ol>"
DIRTY_TERMS_UL = "<ul><li>Bawa paspor</li><li>Suntik meningitis</li></ul>"
DIRTY_TERMS_FMT = "<b>Wajib</b>: <i>lunas</i> <u>H-30</u>.<div>Baris 2</div><p>Baris 3</p>"


@pytest.mark.parametrize("kind,extra", [
    ("invoice", {"invoice_terms": DIRTY_TERMS_OL}),
    ("quotation", {"quotation_terms": DIRTY_TERMS_OL + DIRTY_TERMS_FMT}),
    ("receipt", {}),
])
def test_preview_ok_with_dirty_html(h, kind, extra):
    body = {"kind": kind, "footer_text": DIRTY_FOOTER, **extra}
    r = requests.post(f"{BASE_URL}/api/doc-template/preview", headers=h, json=body, timeout=60)
    assert r.status_code == 200, f"kind={kind} status={r.status_code} body={r.text[:400]}"
    assert r.headers.get("content-type", "").startswith("application/pdf"), r.headers
    assert r.content[:4] == b"%PDF", f"kind={kind} not a PDF magic: {r.content[:10]}"
    assert len(r.content) > 800


def test_preview_quotation_with_ul(h):
    r = requests.post(f"{BASE_URL}/api/doc-template/preview", headers=h,
                      json={"kind": "quotation", "quotation_terms": DIRTY_TERMS_UL, "footer_text": DIRTY_FOOTER}, timeout=60)
    assert r.status_code == 200, r.text[:400]
    assert r.content[:4] == b"%PDF"


ATTR_TERMS_1 = '<i style="color:red">x</i>'
ATTR_TERMS_2 = '<ol><li style="margin:0">Bayar <b class="foo">DP</b> 50%</li><li>Pelunasan <u style="text-decoration:underline">H-30</u></li></ol>'
ATTR_TERMS_3 = '<i style="font-size:0.875rem; color:rgb(15,23,41)">Syarat quotation</i><div><i style="color:blue">Berlaku 30 hari</i></div>'
ATTR_TERMS_BR = 'Line1<br style="clear:both">Line2<br />Line3<br class="foo"/>'


@pytest.mark.parametrize("terms", [ATTR_TERMS_1, ATTR_TERMS_2, ATTR_TERMS_3, ATTR_TERMS_BR])
def test_preview_quotation_attributed_html(h, terms):
    """Regression: iteration_36 CRITICAL — <i style=..>/<b class=..>/<br .../> in Chrome contentEditable must not 500."""
    r = requests.post(f"{BASE_URL}/api/doc-template/preview", headers=h,
                      json={"kind": "quotation", "quotation_terms": terms}, timeout=60)
    assert r.status_code == 200, f"terms={terms!r} status={r.status_code} body={r.text[:400]}"
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


@pytest.mark.parametrize("kind,key", [("invoice", "invoice_terms"), ("quotation", "quotation_terms")])
def test_preview_all_kinds_attributed(h, kind, key):
    r = requests.post(f"{BASE_URL}/api/doc-template/preview", headers=h,
                      json={"kind": kind, key: ATTR_TERMS_2}, timeout=60)
    assert r.status_code == 200, f"kind={kind} body={r.text[:400]}"
    assert r.content[:4] == b"%PDF"


def test_preview_invoice_defaults(h):
    r = requests.post(f"{BASE_URL}/api/doc-template/preview", headers=h, json={"kind": "invoice"}, timeout=60)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


# ---- Save + read back ----------------------------------------------------------------
def test_put_and_get_doc_template_persists_terms(h):
    payload = {
        "invoice_terms": DIRTY_TERMS_OL,
        "quotation_terms": DIRTY_TERMS_UL + "<p>Ekstra</p>",
        "footer_text": DIRTY_FOOTER,
    }
    r = requests.put(f"{BASE_URL}/api/doc-template", headers=h, json=payload, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("invoice_terms") == DIRTY_TERMS_OL
    assert data.get("quotation_terms") == DIRTY_TERMS_UL + "<p>Ekstra</p>"

    # GET returns same values
    g = requests.get(f"{BASE_URL}/api/doc-template", headers=h, timeout=30)
    assert g.status_code == 200
    gd = g.json()
    assert gd.get("invoice_terms") == DIRTY_TERMS_OL
    assert gd.get("quotation_terms") == DIRTY_TERMS_UL + "<p>Ekstra</p>"


# ---- Regression: staff invoice/quotation PDF ----------------------------------------
def test_regression_invoice_and_quotation_pdf(h):
    # Find any invoice
    inv_list = requests.get(f"{BASE_URL}/api/invoices?limit=5", headers=h, timeout=30)
    if inv_list.status_code != 200:
        pytest.skip(f"cannot list invoices: {inv_list.status_code}")
    items = inv_list.json()
    if isinstance(items, dict):
        items = items.get("items") or items.get("data") or []
    if not items:
        pytest.skip("no invoices to regress")
    inv_id = items[0].get("id") or items[0].get("_id")
    if not inv_id:
        pytest.skip("no invoice id")
    # Staff endpoint uses ?auth= token
    tok = h["Authorization"].split(" ", 1)[1]
    p = requests.get(f"{BASE_URL}/api/invoices/{inv_id}/pdf?auth={tok}", timeout=60)
    assert p.status_code == 200, f"invoice pdf status={p.status_code} body={p.text[:200]}"
    assert p.content[:4] == b"%PDF"


def test_regression_quotation_pdf(h):
    q_list = requests.get(f"{BASE_URL}/api/quotations?limit=5", headers=h, timeout=30)
    if q_list.status_code != 200:
        pytest.skip(f"cannot list quotations: {q_list.status_code}")
    items = q_list.json()
    if isinstance(items, dict):
        items = items.get("items") or items.get("data") or []
    if not items:
        pytest.skip("no quotations")
    qid = items[0].get("id") or items[0].get("_id")
    if not qid:
        pytest.skip("no id")
    tok = h["Authorization"].split(" ", 1)[1]
    p = requests.get(f"{BASE_URL}/api/quotations/{qid}/pdf?auth={tok}", timeout=60)
    assert p.status_code == 200, f"quotation pdf status={p.status_code} body={p.text[:200]}"
    assert p.content[:4] == b"%PDF"
