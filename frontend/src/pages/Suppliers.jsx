import { useEffect, useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Building2, Plus, Loader2, Trash2, Coins, Landmark, Star, Pencil } from "lucide-react";
import { toast } from "sonner";

const TYPES = ["Airline", "Hotel", "Transport", "Visa Provider", "Tour Operator", "Guide", "Muthawwif", "Insurance", "Other"];
const AGING = { current: "bg-emerald-50 text-emerald-700 border-emerald-200", "1-30": "bg-amber-50 text-amber-700 border-amber-200", "31-60": "bg-orange-50 text-orange-700 border-orange-200", "60+": "bg-red-50 text-red-700 border-red-200" };
const PAY = { PAID: "bg-emerald-50 text-emerald-700 border-emerald-200", PARTIAL: "bg-amber-50 text-amber-700 border-amber-200", UNPAID: "bg-slate-100 text-slate-500 border-slate-200" };
const idr = (n) => "Rp " + Number(n || 0).toLocaleString("id-ID");

export default function Suppliers() {
  return (
    <div className="space-y-6" data-testid="suppliers-page">
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900">Supplier Management</h1>
        <p className="text-slate-500 mt-1">Kelola supplier, biaya per paket, dan pembayaran (aging). Data biaya bersifat sensitif — hanya Super Admin & Accounting.</p>
      </div>
      <Tabs defaultValue="suppliers">
        <TabsList>
          <TabsTrigger value="suppliers" data-testid="tab-suppliers">Suppliers</TabsTrigger>
          <TabsTrigger value="costs" data-testid="tab-supplier-costs">Supplier Costs</TabsTrigger>
          <TabsTrigger value="payments" data-testid="tab-supplier-payments">Payments & Aging</TabsTrigger>
        </TabsList>
        <TabsContent value="suppliers" className="pt-4"><SuppliersTab /></TabsContent>
        <TabsContent value="costs" className="pt-4"><CostsTab /></TabsContent>
        <TabsContent value="payments" className="pt-4"><PaymentsTab /></TabsContent>
      </Tabs>
    </div>
  );
}

function SuppliersTab() {
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: "", type: "Hotel", contact: "", email: "", phone: "", address: "", tax_info: "", bank_account: "" });
  const [saving, setSaving] = useState(false);
  const [manageBank, setManageBank] = useState(null);
  const load = () => api.get("/suppliers").then((r) => setRows(r.data)).catch(() => setRows([]));
  useEffect(() => { load(); }, []);
  const set = (k) => (e) => setF((o) => ({ ...o, [k]: e.target.value }));
  const save = async () => {
    if (!f.name.trim()) return toast.error("Nama supplier wajib diisi");
    setSaving(true);
    try { await api.post("/suppliers", f); toast.success("Supplier ditambahkan"); setOpen(false); setF({ name: "", type: "Hotel", contact: "", email: "", phone: "", address: "", tax_info: "", bank_account: "" }); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setSaving(false); }
  };
  return (
    <Card className="border-slate-200 shadow-sm overflow-hidden">
      <div className="p-3 border-b border-slate-100 flex justify-between items-center">
        <span className="text-sm font-medium text-slate-600 flex items-center gap-2"><Building2 className="h-4 w-4 text-blue-600" /> Supplier Master</span>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button size="sm" className="bg-blue-600 hover:bg-blue-700" data-testid="add-supplier-btn"><Plus className="h-4 w-4 mr-1" />Tambah Supplier</Button></DialogTrigger>
          <DialogContent className="bg-white max-w-lg" data-testid="supplier-dialog">
            <DialogHeader><DialogTitle className="font-display">Tambah Supplier</DialogTitle><DialogDescription>Isi data supplier baru.</DialogDescription></DialogHeader>
            <div className="grid grid-cols-2 gap-3 py-2">
              <div className="space-y-1 col-span-2"><Label className="text-xs">Nama Supplier</Label><Input value={f.name} onChange={set("name")} data-testid="supplier-name" /></div>
              <div className="space-y-1"><Label className="text-xs">Tipe</Label>
                <Select value={f.type} onValueChange={(v) => setF((o) => ({ ...o, type: v }))}><SelectTrigger data-testid="supplier-type"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-white">{TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent></Select></div>
              <div className="space-y-1"><Label className="text-xs">Contact Person</Label><Input value={f.contact} onChange={set("contact")} data-testid="supplier-contact" /></div>
              <div className="space-y-1"><Label className="text-xs">Email</Label><Input value={f.email} onChange={set("email")} data-testid="supplier-email" /></div>
              <div className="space-y-1"><Label className="text-xs">Phone</Label><Input value={f.phone} onChange={set("phone")} data-testid="supplier-phone" /></div>
              <div className="space-y-1 col-span-2"><Label className="text-xs">Alamat</Label><Input value={f.address} onChange={set("address")} data-testid="supplier-address" /></div>
              <div className="space-y-1"><Label className="text-xs">Tax Info (NPWP)</Label><Input value={f.tax_info} onChange={set("tax_info")} data-testid="supplier-tax" /></div>
              <div className="space-y-1"><Label className="text-xs">Bank Account</Label><Input value={f.bank_account} onChange={set("bank_account")} data-testid="supplier-bank" /></div>
            </div>
            <DialogFooter><Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="supplier-save">{saving ? "..." : "Simpan"}</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      {rows === null ? <div className="p-8 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
       : rows.length === 0 ? <p className="p-6 text-center text-sm text-slate-400" data-testid="suppliers-empty">Belum ada supplier.</p>
       : <Table data-testid="suppliers-table"><TableHeader><TableRow className="bg-slate-50"><TableHead>Nama</TableHead><TableHead>Tipe</TableHead><TableHead>Kontak</TableHead><TableHead>Bank Utama</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Aksi</TableHead></TableRow></TableHeader>
         <TableBody>{rows.map((s) => {
           const primary = (s.bank_accounts || []).find((a) => a.is_primary) || (s.bank_accounts || [])[0];
           const count = (s.bank_accounts || []).length;
           return (
           <TableRow key={s._id} data-testid={`supplier-${s._id}`}>
             <TableCell className="font-medium text-slate-900">{s.name}</TableCell>
             <TableCell><Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">{s.type}</Badge></TableCell>
             <TableCell className="text-slate-600 text-sm">{s.contact || "—"}<div className="text-xs text-slate-400">{s.phone} {s.email}</div></TableCell>
             <TableCell className="text-slate-600 text-sm">
               {primary ? (<div><div className="flex items-center gap-1 font-medium text-slate-800">{primary.bank_name}{count > 1 && <Badge variant="outline" className="ml-1 text-[9px] bg-slate-50 text-slate-500">+{count - 1}</Badge>}</div><div className="text-xs text-slate-400">{primary.account_holder} · {primary.account_number}</div></div>)
                 : (s.bank_account || <span className="text-slate-400">—</span>)}
             </TableCell>
             <TableCell><Badge variant="outline" className={s.status === "ACTIVE" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-500"}>{s.status}</Badge></TableCell>
             <TableCell className="text-right">
               <Button size="sm" variant="outline" onClick={() => setManageBank(s)} data-testid={`manage-bank-${s._id}`}><Landmark className="h-4 w-4 mr-1 text-blue-600" />Kelola Bank</Button>
             </TableCell>
           </TableRow>);})}</TableBody></Table>}
      <BankAccountsDialog supplier={manageBank} onClose={() => setManageBank(null)} onSaved={load} />
    </Card>
  );
}

function BankAccountsDialog({ supplier, onClose, onSaved }) {
  const [accounts, setAccounts] = useState([]);
  const [form, setForm] = useState(null); // {id?, bank_name, account_holder, account_number, is_primary, status}
  const [saving, setSaving] = useState(false);
  useEffect(() => { setAccounts(supplier?.bank_accounts || []); setForm(null); }, [supplier]);
  if (!supplier) return null;
  const sid = supplier._id;

  const refresh = (updated) => { setAccounts(updated.bank_accounts || []); onSaved && onSaved(); };
  const startAdd = () => setForm({ bank_name: "", account_holder: "", account_number: "", is_primary: (accounts.length === 0), status: "ACTIVE" });
  const startEdit = (a) => setForm({ ...a });
  const save = async () => {
    if (!form.bank_name.trim() || !form.account_holder.trim() || !form.account_number.trim())
      return toast.error("Nama bank, pemilik, dan nomor rekening wajib diisi");
    setSaving(true);
    try {
      const r = form.id
        ? await api.put(`/suppliers/${sid}/bank-accounts/${form.id}`, form)
        : await api.post(`/suppliers/${sid}/bank-accounts`, form);
      toast.success(form.id ? "Rekening diperbarui" : "Rekening ditambahkan");
      refresh(r.data); setForm(null);
    } catch (e) {
      const st = e.response?.status;
      toast.error(st === 409 ? (e.response?.data?.detail || "Nomor rekening duplikat") : formatApiErrorDetail(e.response?.data?.detail));
    } finally { setSaving(false); }
  };
  const setPrimary = async (aid) => {
    try { const r = await api.post(`/suppliers/${sid}/bank-accounts/${aid}/set-primary`); toast.success("Rekening utama diperbarui"); refresh(r.data); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const del = async (aid) => {
    try { const r = await api.delete(`/suppliers/${sid}/bank-accounts/${aid}`); toast.success("Rekening dihapus"); refresh(r.data); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <Dialog open={!!supplier} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-white max-w-2xl" data-testid="bank-accounts-dialog">
        <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><Landmark className="h-5 w-5 text-blue-600" />Rekening Bank — {supplier.name}</DialogTitle></DialogHeader>
        <div className="space-y-3 py-1">
          {accounts.length === 0 ? <p className="text-sm text-slate-400 text-center py-4" data-testid="bank-empty">Belum ada rekening bank.</p>
            : (
            <Table data-testid="bank-accounts-table">
              <TableHeader><TableRow className="bg-slate-50"><TableHead>Bank</TableHead><TableHead>Pemilik</TableHead><TableHead>No. Rekening</TableHead><TableHead>Primary</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Aksi</TableHead></TableRow></TableHeader>
              <TableBody>{accounts.map((a) => (
                <TableRow key={a.id} data-testid={`bank-row-${a.id}`}>
                  <TableCell className="font-medium text-slate-900">{a.bank_name}</TableCell>
                  <TableCell className="text-slate-600">{a.account_holder}</TableCell>
                  <TableCell className="font-mono text-slate-600">{a.account_number}</TableCell>
                  <TableCell>{a.is_primary ? <Badge className="bg-amber-100 text-amber-700 border-amber-200"><Star className="h-3 w-3 mr-1" />Primary</Badge> : <Button size="sm" variant="ghost" className="text-xs text-slate-500" onClick={() => setPrimary(a.id)} data-testid={`set-primary-${a.id}`}>Set Primary</Button>}</TableCell>
                  <TableCell><Badge variant="outline" className={a.status === "ACTIVE" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-500"}>{a.status}</Badge></TableCell>
                  <TableCell className="text-right whitespace-nowrap">
                    <Button size="icon" variant="ghost" onClick={() => startEdit(a)} data-testid={`edit-bank-${a.id}`}><Pencil className="h-4 w-4 text-blue-600" /></Button>
                    <Button size="icon" variant="ghost" className="text-red-600" onClick={() => del(a.id)} data-testid={`del-bank-${a.id}`}><Trash2 className="h-4 w-4" /></Button>
                  </TableCell>
                </TableRow>))}</TableBody>
            </Table>
          )}

          {form ? (
            <div className="border border-slate-200 rounded-lg p-3 space-y-3 bg-slate-50/60" data-testid="bank-form">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="space-y-1"><Label className="text-xs">Nama Bank *</Label><Input value={form.bank_name} onChange={(e) => setForm((o) => ({ ...o, bank_name: e.target.value }))} placeholder="BCA" data-testid="bank-name-input" /></div>
                <div className="space-y-1"><Label className="text-xs">Nama Pemilik *</Label><Input value={form.account_holder} onChange={(e) => setForm((o) => ({ ...o, account_holder: e.target.value }))} placeholder="PT ABC" data-testid="bank-holder-input" /></div>
                <div className="space-y-1"><Label className="text-xs">No. Rekening *</Label><Input value={form.account_number} onChange={(e) => setForm((o) => ({ ...o, account_number: e.target.value }))} placeholder="123456" data-testid="bank-number-input" /></div>
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" checked={!!form.is_primary} onChange={(e) => setForm((o) => ({ ...o, is_primary: e.target.checked }))} data-testid="bank-primary-check" /> Jadikan rekening utama</label>
                <Select value={form.status} onValueChange={(v) => setForm((o) => ({ ...o, status: v }))}>
                  <SelectTrigger className="w-36 h-9" data-testid="bank-status-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-white">{["ACTIVE", "INACTIVE"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setForm(null)}>Batal</Button>
                <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={save} disabled={saving} data-testid="bank-save-btn">{saving ? "..." : form.id ? "Simpan" : "Tambah"}</Button>
              </div>
            </div>
          ) : (
            <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={startAdd} data-testid="add-bank-btn"><Plus className="h-4 w-4 mr-1" />Add Bank Account</Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function CostsTab() {
  const [pkgs, setPkgs] = useState([]);
  const [sups, setSups] = useState([]);
  const [pkgId, setPkgId] = useState("");
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [f, setF] = useState({ supplier_id: "", service: "", quantity: "1", unit_cost: "", invoice_number: "", payment_status: "UNPAID" });

  useEffect(() => {
    api.get("/packages").then((r) => setPkgs(Array.isArray(r.data) ? r.data : (r.data?.items || []))).catch(() => setPkgs([]));
    api.get("/suppliers").then((r) => setSups(r.data || [])).catch(() => {});
  }, []);
  const load = (pid) => { if (!pid) return setRows(null); api.get(`/supplier-costs?package_id=${pid}`).then((r) => setRows(r.data)).catch(() => setRows([])); };
  useEffect(() => { load(pkgId); }, [pkgId]);

  const save = async () => {
    if (!pkgId) return toast.error("Pilih paket terlebih dahulu");
    if (!f.supplier_id) return toast.error("Pilih supplier");
    if (!Number(f.quantity) || Number(f.unit_cost) < 0) return toast.error("Qty / Unit Cost tidak valid");
    setSaving(true);
    try {
      await api.post("/supplier-costs", { ...f, package_id: pkgId, quantity: Number(f.quantity), unit_cost: Number(f.unit_cost) });
      toast.success("Supplier cost ditambahkan"); setOpen(false);
      setF({ supplier_id: "", service: "", quantity: "1", unit_cost: "", invoice_number: "", payment_status: "UNPAID" }); load(pkgId);
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setSaving(false); }
  };
  const del = async (cid) => { try { await api.delete(`/supplier-costs/${cid}`); toast.success("Cost dihapus"); load(pkgId); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  const total = (rows || []).reduce((a, r) => a + (r.total_cost || 0), 0);

  return (
    <Card className="border-slate-200 shadow-sm overflow-hidden">
      <div className="p-3 border-b border-slate-100 flex flex-wrap justify-between items-center gap-3">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-slate-600 flex items-center gap-2"><Coins className="h-4 w-4 text-blue-600" /> Biaya Supplier per Paket</span>
          <Select value={pkgId} onValueChange={setPkgId}>
            <SelectTrigger className="w-64 h-9" data-testid="cost-package-select"><SelectValue placeholder="Pilih paket" /></SelectTrigger>
            <SelectContent className="bg-white">{pkgs.map((p) => <SelectItem key={p._id} value={p._id}>{p.package_name}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-3">
          {pkgId && rows && <span className="text-sm text-slate-600">Total: <b className="text-blue-700" data-testid="cost-total">{idr(total)}</b></span>}
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button size="sm" disabled={!pkgId} className="bg-blue-600 hover:bg-blue-700" data-testid="add-supplier-cost-btn"><Plus className="h-4 w-4 mr-1" />Tambah Biaya</Button></DialogTrigger>
            <DialogContent className="bg-white max-w-md" data-testid="supplier-cost-dialog">
              <DialogHeader><DialogTitle className="font-display">Tambah Biaya Supplier</DialogTitle></DialogHeader>
              <div className="space-y-3 py-2">
                <div className="space-y-1"><Label className="text-xs">Supplier</Label>
                  <Select value={f.supplier_id} onValueChange={(v) => setF((o) => ({ ...o, supplier_id: v }))}><SelectTrigger data-testid="sc-supplier"><SelectValue placeholder="Pilih supplier" /></SelectTrigger>
                    <SelectContent className="bg-white">{sups.map((s) => <SelectItem key={s._id} value={s._id}>{s.name}</SelectItem>)}</SelectContent></Select></div>
                <div className="space-y-1"><Label className="text-xs">Layanan / Service</Label><Input value={f.service} onChange={(e) => setF((o) => ({ ...o, service: e.target.value }))} placeholder="e.g. Hotel Makkah 5 malam" data-testid="sc-service" /></div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1"><Label className="text-xs">Quantity</Label><Input type="number" value={f.quantity} onChange={(e) => setF((o) => ({ ...o, quantity: e.target.value }))} data-testid="sc-qty" /></div>
                  <div className="space-y-1"><Label className="text-xs">Unit Cost</Label><Input type="number" value={f.unit_cost} onChange={(e) => setF((o) => ({ ...o, unit_cost: e.target.value }))} data-testid="sc-unit" /></div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1"><Label className="text-xs">No. Invoice</Label><Input value={f.invoice_number} onChange={(e) => setF((o) => ({ ...o, invoice_number: e.target.value }))} data-testid="sc-invoice" /></div>
                  <div className="space-y-1"><Label className="text-xs">Status Bayar</Label>
                    <Select value={f.payment_status} onValueChange={(v) => setF((o) => ({ ...o, payment_status: v }))}><SelectTrigger data-testid="sc-status"><SelectValue /></SelectTrigger>
                      <SelectContent className="bg-white">{["UNPAID", "PARTIAL", "PAID"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
                </div>
                <div className="text-sm text-slate-500">Total: <b className="text-slate-800">{idr(Number(f.quantity || 0) * Number(f.unit_cost || 0))}</b></div>
              </div>
              <DialogFooter><Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="sc-save">{saving ? "..." : "Simpan"}</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>
      {!pkgId ? <p className="p-6 text-center text-sm text-slate-400" data-testid="cost-select-hint">Pilih paket untuk melihat biaya supplier.</p>
       : rows === null ? <div className="p-8 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
       : rows.length === 0 ? <p className="p-6 text-center text-sm text-slate-400" data-testid="supplier-costs-empty">Belum ada biaya supplier untuk paket ini.</p>
       : <Table data-testid="supplier-costs-table"><TableHeader><TableRow className="bg-slate-50"><TableHead>Supplier</TableHead><TableHead>Layanan</TableHead><TableHead>Qty</TableHead><TableHead>Unit Cost</TableHead><TableHead>Total</TableHead><TableHead>Invoice</TableHead><TableHead>Status</TableHead><TableHead></TableHead></TableRow></TableHeader>
         <TableBody>{rows.map((c) => (
           <TableRow key={c._id} data-testid={`supplier-cost-${c._id}`}>
             <TableCell className="font-medium text-slate-900">{c.supplier_name || "—"}</TableCell>
             <TableCell className="text-slate-600 text-sm">{c.service || "—"}</TableCell>
             <TableCell className="text-slate-600">{c.quantity}</TableCell>
             <TableCell className="text-slate-600">{idr(c.unit_cost)}</TableCell>
             <TableCell className="font-medium text-slate-900">{idr(c.total_cost)}</TableCell>
             <TableCell className="text-slate-600">{c.invoice_number || "—"}</TableCell>
             <TableCell><Badge variant="outline" className={PAY[c.payment_status]}>{c.payment_status}</Badge></TableCell>
             <TableCell><Button size="icon" variant="ghost" className="text-red-600" onClick={() => del(c._id)} data-testid={`del-cost-${c._id}`}><Trash2 className="h-4 w-4" /></Button></TableCell>
           </TableRow>))}</TableBody></Table>}
    </Card>
  );
}

function PaymentsTab() {
  const [sups, setSups] = useState([]);
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ supplier_id: "", invoice_number: "", due_date: "", amount: "", paid: "" });
  const [saving, setSaving] = useState(false);
  const load = () => api.get("/supplier-payments").then((r) => setRows(r.data)).catch(() => setRows([]));
  useEffect(() => { load(); api.get("/suppliers").then((r) => setSups(r.data || [])).catch(() => {}); }, []);
  const save = async () => {
    if (!f.supplier_id) return toast.error("Pilih supplier");
    if (!Number(f.amount)) return toast.error("Amount wajib diisi");
    setSaving(true);
    try { await api.post("/supplier-payments", { ...f, amount: Number(f.amount), paid: Number(f.paid || 0) }); toast.success("Invoice supplier ditambahkan"); setOpen(false); setF({ supplier_id: "", invoice_number: "", due_date: "", amount: "", paid: "" }); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setSaving(false); }
  };
  const totalOut = (rows || []).reduce((a, r) => a + (r.outstanding || 0), 0);
  return (
    <Card className="border-slate-200 shadow-sm overflow-hidden">
      <div className="p-3 border-b border-slate-100 flex justify-between items-center">
        <span className="text-sm font-medium text-slate-600">Supplier Payments · Outstanding: <b className="text-red-600" data-testid="supplier-total-outstanding">{idr(totalOut)}</b></span>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button size="sm" className="bg-blue-600 hover:bg-blue-700" data-testid="add-supplier-payment-btn"><Plus className="h-4 w-4 mr-1" />Tambah Invoice</Button></DialogTrigger>
          <DialogContent className="bg-white max-w-md" data-testid="supplier-payment-dialog">
            <DialogHeader><DialogTitle className="font-display">Invoice Supplier</DialogTitle></DialogHeader>
            <div className="space-y-3 py-2">
              <div className="space-y-1"><Label className="text-xs">Supplier</Label>
                <Select value={f.supplier_id} onValueChange={(v) => setF((o) => ({ ...o, supplier_id: v }))}><SelectTrigger data-testid="sp-supplier"><SelectValue placeholder="Pilih supplier" /></SelectTrigger>
                  <SelectContent className="bg-white">{sups.map((s) => <SelectItem key={s._id} value={s._id}>{s.name}</SelectItem>)}</SelectContent></Select></div>
              <div className="space-y-1"><Label className="text-xs">No. Invoice</Label><Input value={f.invoice_number} onChange={(e) => setF((o) => ({ ...o, invoice_number: e.target.value }))} data-testid="sp-invoice" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1"><Label className="text-xs">Due Date</Label><Input type="date" value={f.due_date} onChange={(e) => setF((o) => ({ ...o, due_date: e.target.value }))} data-testid="sp-due" /></div>
                <div className="space-y-1"><Label className="text-xs">Amount</Label><Input type="number" value={f.amount} onChange={(e) => setF((o) => ({ ...o, amount: e.target.value }))} data-testid="sp-amount" /></div>
              </div>
              <div className="space-y-1"><Label className="text-xs">Paid</Label><Input type="number" value={f.paid} onChange={(e) => setF((o) => ({ ...o, paid: e.target.value }))} data-testid="sp-paid" /></div>
            </div>
            <DialogFooter><Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="sp-save">{saving ? "..." : "Simpan"}</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      {rows === null ? <div className="p-8 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
       : rows.length === 0 ? <p className="p-6 text-center text-sm text-slate-400" data-testid="supplier-payments-empty">Belum ada invoice supplier.</p>
       : <Table data-testid="supplier-payments-table"><TableHeader><TableRow className="bg-slate-50"><TableHead>Supplier</TableHead><TableHead>Invoice</TableHead><TableHead>Due</TableHead><TableHead>Amount</TableHead><TableHead>Paid</TableHead><TableHead>Outstanding</TableHead><TableHead>Status</TableHead><TableHead>Aging</TableHead></TableRow></TableHeader>
         <TableBody>{rows.map((p) => (
           <TableRow key={p._id} data-testid={`supplier-payment-${p._id}`}>
             <TableCell className="font-medium text-slate-900">{p.supplier_name}</TableCell>
             <TableCell className="text-slate-600">{p.invoice_number || "—"}</TableCell>
             <TableCell className="text-slate-600">{(p.due_date || "").slice(0, 10) || "—"}</TableCell>
             <TableCell>{idr(p.amount)}</TableCell>
             <TableCell className="text-emerald-600">{idr(p.paid)}</TableCell>
             <TableCell className="text-red-600 font-medium">{idr(p.outstanding)}</TableCell>
             <TableCell><Badge variant="outline" className={PAY[p.status]}>{p.status}</Badge></TableCell>
             <TableCell><Badge variant="outline" className={AGING[p.aging]}>{p.aging}</Badge></TableCell>
           </TableRow>))}</TableBody></Table>}
    </Card>
  );
}
