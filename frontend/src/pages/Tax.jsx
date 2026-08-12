import { useEffect, useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, Plus, Receipt, FileText, Percent, Layers, BarChart3 } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from "recharts";

const rp = (v) => "Rp " + Number(v || 0).toLocaleString("id-ID");
const short = (v) => "Rp " + (Number(v || 0) / 1e6).toFixed(1) + "jt";
const COLORS = ["#2563eb", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];
const TAX_TYPES = ["PPN", "PPh21", "PPh23", "OTHER"];

export default function Tax() {
  return (
    <div className="space-y-6" data-testid="tax-page">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-indigo-600 flex items-center justify-center"><Receipt className="h-6 w-6 text-white" /></div>
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">Tax Management</h1>
          <p className="text-slate-500 mt-0.5">Konfigurasi PPN, tax master, transaksi pajak &amp; laporan.</p>
        </div>
      </div>
      <Tabs defaultValue="dashboard">
        <TabsList data-testid="tax-tabs">
          <TabsTrigger value="dashboard" data-testid="tab-tax-dashboard">Dashboard</TabsTrigger>
          <TabsTrigger value="transactions" data-testid="tab-tax-transactions">Tax Transactions</TabsTrigger>
          <TabsTrigger value="master" data-testid="tab-tax-master">Tax Master</TabsTrigger>
          <TabsTrigger value="ppn" data-testid="tab-ppn-config">PPN Configuration</TabsTrigger>
          <TabsTrigger value="reports" data-testid="tab-tax-reports">Tax Reports</TabsTrigger>
        </TabsList>
        <TabsContent value="dashboard"><TaxDashboard /></TabsContent>
        <TabsContent value="transactions"><TaxTransactions /></TabsContent>
        <TabsContent value="master"><TaxMaster /></TabsContent>
        <TabsContent value="ppn"><PPNConfig /></TabsContent>
        <TabsContent value="reports"><TaxReports /></TabsContent>
      </Tabs>
    </div>
  );
}

/* -------- DASHBOARD -------- */
function TaxDashboard() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/tax-dashboard").then((r) => setD(r.data)).catch(() => setD(false)); }, []);
  if (d === null) return <Spin />;
  if (d === false) return <div className="p-8 text-slate-400">Gagal memuat.</div>;
  const kpis = [
    ["Total DPP", short(d.total_dpp)], ["Total PPN", short(d.total_ppn)],
    ["Taxable Sales", short(d.taxable)], ["Non-Taxable", short(d.non_taxable)], ["Transactions", d.transaction_count],
  ];
  return (
    <div className="space-y-4">
      {d.active_config && (
        <Card className="border-indigo-200 bg-indigo-50/50 shadow-sm" data-testid="active-config-banner">
          <CardContent className="p-4 flex flex-wrap items-center gap-3">
            <Badge className="bg-indigo-600 text-white">Konfigurasi Aktif</Badge>
            <span className="font-semibold text-slate-800">{d.active_config.config_name}</span>
            <span className="text-sm text-slate-500">{d.active_config.tax_type} · Rate {d.active_config.tax_rate}% · DPP {d.active_config.dpp_percentage}% · berlaku {d.active_config.effective_from || "-"} s/d {d.active_config.effective_until || "∞"}</span>
          </CardContent>
        </Card>
      )}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {kpis.map(([l, v], i) => (
          <Card key={i} className="border-slate-200 shadow-sm" data-testid={`tax-kpi-${i}`}>
            <CardContent className="p-4"><p className="text-xs text-slate-400">{l}</p><p className="text-xl font-bold text-slate-900 mt-0.5">{v}</p></CardContent>
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="PPN per Bulan (6 Bulan)">
          <BarChart data={d.by_month}><CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" /><XAxis dataKey="month" tick={{ fontSize: 11 }} /><YAxis tickFormatter={(v) => (v / 1e6).toFixed(0) + "jt"} tick={{ fontSize: 11 }} /><Tooltip formatter={(v) => rp(v)} /><Bar dataKey="value" fill="#2563eb" radius={[4, 4, 0, 0]} /></BarChart>
        </ChartCard>
        <ChartCard title="Pajak per Tipe">
          <BarChart data={d.by_type}><CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" /><XAxis dataKey="type" tick={{ fontSize: 11 }} /><YAxis tickFormatter={(v) => (v / 1e6).toFixed(0) + "jt"} tick={{ fontSize: 11 }} /><Tooltip formatter={(v) => rp(v)} /><Bar dataKey="value" radius={[4, 4, 0, 0]}>{d.by_type.map((e, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Bar></BarChart>
        </ChartCard>
      </div>
    </div>
  );
}

/* -------- TAX TRANSACTIONS -------- */
function TaxTransactions() {
  const [rows, setRows] = useState(null);
  const [range, setRange] = useState({ frm: "", to: "" });
  const load = () => { const q = []; if (range.frm) q.push(`frm=${range.frm}`); if (range.to) q.push(`to=${range.to}`); api.get(`/tax-transactions${q.length ? "?" + q.join("&") : ""}`).then((r) => setRows(r.data || [])).catch(() => setRows([])); };
  useEffect(() => { load(); }, []);
  return (
    <div className="space-y-4">
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-4 flex flex-wrap items-end gap-3">
          <div><Label>Dari</Label><Input type="date" value={range.frm} onChange={(e) => setRange({ ...range, frm: e.target.value })} className="w-40" data-testid="txn-from" /></div>
          <div><Label>Sampai</Label><Input type="date" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} className="w-40" data-testid="txn-to" /></div>
          <Button onClick={load} data-testid="txn-filter-btn">Filter</Button>
        </CardContent>
      </Card>
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="tax-transactions-table">
              <thead><tr className="bg-indigo-600 text-white text-left">
                <th className="px-3 py-2.5">Invoice</th><th className="px-3 py-2.5 border-l border-indigo-500">Tanggal</th><th className="px-3 py-2.5 border-l border-indigo-500">Customer</th>
                <th className="px-3 py-2.5 border-l border-indigo-500">Tax Type</th><th className="px-3 py-2.5 border-l border-indigo-500">Rate %</th><th className="px-3 py-2.5 border-l border-indigo-500">DPP</th>
                <th className="px-3 py-2.5 border-l border-indigo-500">Tax Amount</th><th className="px-3 py-2.5 border-l border-indigo-500">Config Version</th>
              </tr></thead>
              <tbody>
                {rows === null ? <tr><td colSpan={8} className="px-4 py-8 text-center"><Loader2 className="h-5 w-5 animate-spin text-indigo-600 mx-auto" /></td></tr> :
                  rows.length === 0 ? <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Belum ada transaksi pajak.</td></tr> :
                    rows.map((r, i) => (
                      <tr key={r.id} className={i % 2 ? "bg-slate-50" : "bg-white"} data-testid={`tax-txn-${r.invoice_number}`}>
                        <td className="px-3 py-2.5 font-medium">{r.invoice_number}</td>
                        <td className="px-3 py-2.5 border-l border-slate-100">{r.transaction_date}</td>
                        <td className="px-3 py-2.5 border-l border-slate-100">{r.customer_name || "-"}</td>
                        <td className="px-3 py-2.5 border-l border-slate-100">{r.tax_type}</td>
                        <td className="px-3 py-2.5 border-l border-slate-100">{r.tax_rate}%</td>
                        <td className="px-3 py-2.5 border-l border-slate-100">{rp(r.dpp)}</td>
                        <td className="px-3 py-2.5 border-l border-slate-100 font-semibold">{rp(r.tax_amount)}</td>
                        <td className="px-3 py-2.5 border-l border-slate-100"><Badge className="bg-slate-100 text-slate-600 border-slate-200">{r.tax_config_version}</Badge></td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/* -------- TAX MASTER -------- */
const EMPTY_MASTER = { tax_code: "", tax_name: "", tax_type: "PPN", rate: 0, tax_base: "SELLING_PRICE", effective_from: "", effective_until: "", treatment: "PPN_STANDARD", tax_account: "", description: "", active: true };
function TaxMaster() {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_MASTER);
  const [editId, setEditId] = useState(null);
  const load = () => api.get("/tax-masters").then((r) => setRows(r.data || [])).catch(() => {});
  useEffect(() => { load(); }, []);
  const save = async () => {
    if (!form.tax_code || !form.tax_name) return toast.error("Tax Code & Name wajib");
    const payload = { ...form, rate: Number(form.rate) || 0 };
    try { if (editId) await api.put(`/tax-masters/${editId}`, payload); else await api.post("/tax-masters", payload); toast.success("Tax master tersimpan"); setOpen(false); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  return (
    <div className="space-y-4">
      <Button onClick={() => { setForm(EMPTY_MASTER); setEditId(null); setOpen(true); }} data-testid="new-master-btn"><Plus className="h-4 w-4 mr-1" /> Tax Master Baru</Button>
      <Card className="border-slate-200 shadow-sm"><CardContent className="p-0"><div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="tax-master-table">
          <thead><tr className="bg-indigo-600 text-white text-left">
            <th className="px-3 py-2.5">Code</th><th className="px-3 py-2.5 border-l border-indigo-500">Name</th><th className="px-3 py-2.5 border-l border-indigo-500">Type</th>
            <th className="px-3 py-2.5 border-l border-indigo-500">Rate %</th><th className="px-3 py-2.5 border-l border-indigo-500">Base</th><th className="px-3 py-2.5 border-l border-indigo-500">Effective</th>
            <th className="px-3 py-2.5 border-l border-indigo-500">Status</th><th className="px-3 py-2.5 border-l border-indigo-500"></th>
          </tr></thead>
          <tbody>
            {rows.length === 0 ? <tr><td colSpan={8} className="px-4 py-8 text-center text-slate-400">Belum ada tax master.</td></tr> :
              rows.map((s, i) => (
                <tr key={s.id || i} className={i % 2 ? "bg-slate-50" : "bg-white"} data-testid={`master-row-${i}`}>
                  <td className="px-3 py-2.5 font-medium">{s.tax_code}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{s.tax_name}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{s.tax_type}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{s.rate}%</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{s.tax_base}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{s.effective_from || "-"} s/d {s.effective_until || "∞"}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100"><Badge className={s.active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-500 border-slate-200"}>{s.active ? "ACTIVE" : "INACTIVE"}</Badge></td>
                  <td className="px-3 py-2.5 border-l border-slate-100"><Button size="sm" variant="ghost" onClick={() => { setForm({ ...EMPTY_MASTER, ...s }); setEditId(s.id); setOpen(true); }} data-testid={`edit-master-${i}`}>Edit</Button></td>
                </tr>
              ))}
          </tbody>
        </table>
      </div></CardContent></Card>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-xl" data-testid="master-dialog">
          <DialogHeader><DialogTitle>{editId ? "Edit" : "New"} Tax Master</DialogTitle><DialogDescription className="sr-only">Form tax master</DialogDescription></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Tax Code</Label><Input value={form.tax_code} onChange={(e) => setForm({ ...form, tax_code: e.target.value })} data-testid="master-code" /></div>
            <div><Label>Tax Name</Label><Input value={form.tax_name} onChange={(e) => setForm({ ...form, tax_name: e.target.value })} data-testid="master-name" /></div>
            <div><Label>Tax Type</Label>
              <Select value={form.tax_type} onValueChange={(v) => setForm({ ...form, tax_type: v })}>
                <SelectTrigger data-testid="master-type"><SelectValue /></SelectTrigger>
                <SelectContent>{TAX_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Rate %</Label><Input type="number" value={form.rate} onChange={(e) => setForm({ ...form, rate: e.target.value })} data-testid="master-rate" /></div>
            <div><Label>Effective From</Label><Input type="date" value={form.effective_from || ""} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} data-testid="master-from" /></div>
            <div><Label>Effective Until</Label><Input type="date" value={form.effective_until || ""} onChange={(e) => setForm({ ...form, effective_until: e.target.value })} data-testid="master-until" /></div>
            <div className="col-span-2"><Label>Description</Label><Input value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="master-desc" /></div>
          </div>
          <DialogFooter><Button onClick={save} data-testid="save-master-btn">Simpan</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* -------- PPN CONFIGURATION -------- */
const EMPTY_PPN = { config_name: "", tax_type: "PPN", tax_rate: 0, dpp_percentage: 100, effective_from: "", effective_until: "", status: "ACTIVE", description: "" };
function PPNConfig() {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_PPN);
  const [editId, setEditId] = useState(null);
  const [reason, setReason] = useState("");
  const load = () => api.get("/ppn-configurations").then((r) => setRows(r.data || [])).catch(() => {});
  useEffect(() => { load(); }, []);
  const save = async () => {
    if (!form.config_name) return toast.error("Configuration Name wajib");
    if (editId && !reason) return toast.error("Reason perubahan wajib diisi");
    const payload = { ...form, tax_rate: Number(form.tax_rate) || 0, dpp_percentage: Number(form.dpp_percentage) || 0 };
    try {
      if (editId) await api.put(`/ppn-configurations/${editId}`, { ...payload, reason });
      else await api.post("/ppn-configurations", payload);
      toast.success("PPN configuration tersimpan"); setOpen(false); setReason(""); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const deactivate = async (id) => { try { await api.delete(`/ppn-configurations/${id}`); toast.success("Dinonaktifkan"); load(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">Tarif PPN &amp; DPP ter-versioning. Perubahan tarif → buat konfigurasi baru; transaksi lama tetap memakai versi saat transaksi.</p>
        <Button onClick={() => { setForm(EMPTY_PPN); setEditId(null); setReason(""); setOpen(true); }} data-testid="new-ppn-btn"><Plus className="h-4 w-4 mr-1" /> PPN Config Baru</Button>
      </div>
      <Card className="border-slate-200 shadow-sm"><CardContent className="p-0"><div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="ppn-config-table">
          <thead><tr className="bg-indigo-600 text-white text-left">
            <th className="px-3 py-2.5">Configuration Name</th><th className="px-3 py-2.5 border-l border-indigo-500">Tax Type</th><th className="px-3 py-2.5 border-l border-indigo-500">Rate %</th>
            <th className="px-3 py-2.5 border-l border-indigo-500">DPP %</th><th className="px-3 py-2.5 border-l border-indigo-500">Effective</th><th className="px-3 py-2.5 border-l border-indigo-500">Status</th><th className="px-3 py-2.5 border-l border-indigo-500"></th>
          </tr></thead>
          <tbody>
            {rows.length === 0 ? <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Belum ada konfigurasi PPN.</td></tr> :
              rows.map((s, i) => (
                <tr key={s.id || i} className={i % 2 ? "bg-slate-50" : "bg-white"} data-testid={`ppn-row-${i}`}>
                  <td className="px-3 py-2.5 font-medium">{s.config_name}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{s.tax_type}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{s.tax_rate}%</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{s.dpp_percentage}%</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{s.effective_from || "-"} s/d {s.effective_until || "∞"}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100"><Badge className={s.status === "ACTIVE" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-500 border-slate-200"}>{s.status}</Badge></td>
                  <td className="px-3 py-2.5 border-l border-slate-100 space-x-1">
                    <Button size="sm" variant="ghost" onClick={() => { setForm({ ...EMPTY_PPN, ...s }); setEditId(s.id); setReason(""); setOpen(true); }} data-testid={`edit-ppn-${i}`}>Edit</Button>
                    {s.status === "ACTIVE" && <Button size="sm" variant="ghost" className="text-red-500" onClick={() => deactivate(s.id)} data-testid={`deact-ppn-${i}`}>Nonaktifkan</Button>}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div></CardContent></Card>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-xl" data-testid="ppn-dialog">
          <DialogHeader><DialogTitle>{editId ? "Edit" : "New"} PPN Configuration</DialogTitle><DialogDescription className="sr-only">Form konfigurasi PPN</DialogDescription></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2"><Label>Configuration Name</Label><Input value={form.config_name} onChange={(e) => setForm({ ...form, config_name: e.target.value })} data-testid="ppn-name" /></div>
            <div><Label>Tax Type</Label>
              <Select value={form.tax_type} onValueChange={(v) => setForm({ ...form, tax_type: v })}>
                <SelectTrigger data-testid="ppn-type"><SelectValue /></SelectTrigger>
                <SelectContent>{TAX_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                <SelectTrigger data-testid="ppn-status"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="ACTIVE">ACTIVE</SelectItem><SelectItem value="INACTIVE">INACTIVE</SelectItem></SelectContent>
              </Select>
            </div>
            <div><Label>Tax Rate %</Label><Input type="number" value={form.tax_rate} onChange={(e) => setForm({ ...form, tax_rate: e.target.value })} data-testid="ppn-rate" /></div>
            <div><Label>DPP Percentage %</Label><Input type="number" value={form.dpp_percentage} onChange={(e) => setForm({ ...form, dpp_percentage: e.target.value })} data-testid="ppn-dpp" /></div>
            <div><Label>Effective Date</Label><Input type="date" value={form.effective_from || ""} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} data-testid="ppn-from" /></div>
            <div><Label>End Date</Label><Input type="date" value={form.effective_until || ""} onChange={(e) => setForm({ ...form, effective_until: e.target.value })} data-testid="ppn-until" /></div>
            <div className="col-span-2"><Label>Description</Label><Input value={form.description || ""} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="ppn-desc" /></div>
            {editId && <div className="col-span-2"><Label>Reason (wajib untuk perubahan)</Label><Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="ppn-reason" /></div>}
          </div>
          <DialogFooter><Button onClick={save} data-testid="save-ppn-btn">Simpan</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* -------- TAX REPORTS -------- */
function TaxReports() {
  const [rep, setRep] = useState(null);
  const [range, setRange] = useState({ frm: "", to: "" });
  const load = () => { const q = []; if (range.frm) q.push(`frm=${range.frm}`); if (range.to) q.push(`to=${range.to}`); api.get(`/tax-reports${q.length ? "?" + q.join("&") : ""}`).then((r) => setRep(r.data)).catch(() => setRep(false)); };
  useEffect(() => { load(); }, []);
  return (
    <div className="space-y-4">
      <Card className="border-slate-200 shadow-sm"><CardContent className="p-4 flex flex-wrap items-end gap-3">
        <div><Label>Dari</Label><Input type="date" value={range.frm} onChange={(e) => setRange({ ...range, frm: e.target.value })} className="w-40" data-testid="rep-from" /></div>
        <div><Label>Sampai</Label><Input type="date" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} className="w-40" data-testid="rep-to" /></div>
        <Button onClick={load} data-testid="rep-filter-btn">Filter</Button>
      </CardContent></Card>
      {rep === null ? <Spin /> : rep === false ? <div className="p-8 text-slate-400">Gagal memuat.</div> : (
        <Card className="border-slate-200 shadow-sm" data-testid="tax-report-card">
          <CardHeader className="border-b border-slate-100"><CardTitle className="font-display text-lg">{rep.title}</CardTitle></CardHeader>
          <CardContent className="p-4 space-y-3">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {Object.entries(rep.summary || {}).map(([k, v]) => (
                <div key={k} className="rounded-lg border border-slate-100 px-4 py-3" data-testid={`rep-sum-${k}`}>
                  <p className="text-xs text-slate-400">{k.replace(/_/g, " ")}</p>
                  <p className="text-lg font-bold text-slate-900 mt-0.5">{rp(v)}</p>
                </div>
              ))}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="tax-report-table">
                <thead><tr className="bg-slate-800 text-white text-left">{(rep.columns || []).map((c) => <th key={c} className="px-3 py-2 border-l border-slate-600 first:border-l-0">{c}</th>)}</tr></thead>
                <tbody>
                  {(rep.rows || []).length === 0 ? <tr><td colSpan={(rep.columns || []).length} className="px-4 py-8 text-center text-slate-400">Tidak ada data.</td></tr> :
                    rep.rows.map((row, i) => (
                      <tr key={i} className={i % 2 ? "bg-slate-50" : "bg-white"}>
                        {row.map((cell, j) => <td key={j} className="px-3 py-2 border-l border-slate-100 first:border-l-0">{typeof cell === "number" ? cell.toLocaleString("id-ID") : cell}</td>)}
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

const Spin = () => <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-indigo-600" /></div>;
const ChartCard = ({ title, children }) => (
  <Card className="border-slate-200 shadow-sm">
    <CardHeader className="border-b border-slate-100 py-3"><CardTitle className="text-sm font-display">{title}</CardTitle></CardHeader>
    <CardContent className="p-3"><div style={{ width: "100%", height: 240 }}><ResponsiveContainer>{children}</ResponsiveContainer></div></CardContent>
  </Card>
);
