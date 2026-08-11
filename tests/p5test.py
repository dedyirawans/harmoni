import requests
API = open('/app/frontend/.env').read().split('REACT_APP_BACKEND_URL=')[1].split('\n')[0].strip()
def login(e,p): return requests.post(f"{API}/api/auth/login", json={"email":e,"password":p}, timeout=20).json()["token"]
S=login("sales@safarcrm.com","Sales@123"); A=login("dedyirawan18@gmail.com","Admin@123"); AC=login("accounting@safarcrm.com","Account@123")
HS={"Authorization":f"Bearer {S}"}; HA={"Authorization":f"Bearer {A}"}; HAC={"Authorization":f"Bearer {AC}"}
def code(m,path,h,**kw): return requests.request(m,f"{API}/api{path}",headers=h,timeout=25,**kw).status_code

print("=== SECURITY MATRIX ===")
print("Sales -> HPP report:", code("GET","/reports/hpp",HS), "(expect 403)")
print("Sales -> tax-masters:", code("GET","/tax-masters",HS), "(expect 403)")
print("Sales -> expenses:", code("GET","/expenses",HS), "(expect 403)")
print("Sales -> reports/revenue:", code("GET","/reports/revenue",HS), "(expect 403)")
print("Accounting -> HPP report:", code("GET","/reports/hpp",HAC), "(expect 200)")
print("Accounting -> tax-masters:", code("GET","/tax-masters",HAC), "(expect 200)")
print("Accounting -> commission-settings:", code("GET","/commission-settings",HAC), "(expect 403)")
print("Accounting -> n8n settings:", code("GET","/integrations/n8n",HAC), "(expect 403)")
print("SuperAdmin -> commission-settings:", code("GET","/commission-settings",HA), "(expect 200)")
print("SuperAdmin -> n8n settings:", code("GET","/integrations/n8n",HA), "(expect 200)")

print("=== TAX MASTER CRUD (accounting) ===")
tm=requests.post(f"{API}/api/tax-masters",headers=HAC,timeout=20,json={"tax_code":"TEST5","tax_name":"Test 5%","tax_type":"PPN","rate":5,"tax_base":"DPP","effective_from":"2026-01-01","treatment":"CUSTOM_TAX"}).json()
print("created tax master:", tm.get("tax_code"), "rate", tm.get("rate"), "id", tm.get("_id"))
upd=requests.put(f"{API}/api/tax-masters/{tm['_id']}",headers=HAC,timeout=20,json={**{k:tm[k] for k in ['tax_code','tax_name','tax_type','tax_base','effective_from','treatment']},"rate":6,"effective_until":"2027-12-31","active":True}).json()
print("updated rate ->", upd.get("rate"), "effective_until", upd.get("effective_until"))

print("=== EXPENSE + REFUND ===")
ex=requests.post(f"{API}/api/expenses",headers=HAC,timeout=20,json={"category":"Hotel","amount":12000000,"description":"Hotel Madinah","date":"2026-06-10"}).json()
print("expense:", ex.get("category"), ex.get("amount"))
rf=requests.post(f"{API}/api/refunds",headers=HAC,timeout=20,json={"customer_name":"Test","amount":2000000,"reason":"Cancel","date":"2026-06-11"}).json()
print("refund:", rf.get("amount"), rf.get("status"))

print("=== REPORTS ===")
rev=requests.get(f"{API}/api/reports/revenue",headers=HAC,timeout=25).json()
print("revenue summary:", rev["summary"])
tax=requests.get(f"{API}/api/reports/tax",headers=HAC,timeout=25).json()
print("tax summary:", tax["summary"], "by_period", len(tax["by_period"]))

print("=== EXPORT ===")
for fmt in ("xlsx","csv","pdf"):
    r=requests.get(f"{API}/api/reports/tax/export?format={fmt}&auth={AC}",timeout=30)
    print(f"tax export {fmt}: {r.status_code} {r.headers.get('content-type')} bytes {len(r.content)}")
print("Sales export revenue:", requests.get(f"{API}/api/reports/revenue/export?format=csv&auth={S}",timeout=20).status_code, "(expect 403)")
print("DONE")
