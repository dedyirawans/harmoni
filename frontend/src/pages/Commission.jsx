import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, Plus, Trash2, Calculator, Percent, Wallet, Eye, RotateCcw, Save } from "lucide-react";

const rp = (v) => "Rp " + (Number(v || 0)).toLocaleString("id-ID");
const CLOSING_COLORS = {
  OPEN: "bg-slate-100 text-slate-600 border-slate-200",
  CALCULATING: "bg-sky-50 text-sky-700 border-sky-200",
  REVIEW: "bg-amber-50 text-amber-700 border-amber-200",
  APPROVED: "bg-indigo-50 text-indigo-700 border-indigo-200",
  CLOSED: "bg-emerald-50 text-emerald-700 border-emerald-200",
  PAID: "bg-blue-600 text-white border-blue-600",
};
const BASES = ["BOOKED", "CONFIRMED", "PAID", "COMPLETED"];
const PRODUCT_TYPES = ["ALL", "UMROH", "TOUR", "UMROH_PLUS"];

export default function Commission() {
  const { user } = useAuth();
  const perms = user.permissions || [];
  const canManage = perms.includes("commission.manage");
  const isAdmin = user.role === "super_admin";

  if (!canManage) return <MyCommission />;
  return (
    <div className="space-y-6" data-testid="commission-page">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-blue-600 flex items-center justify-center">
          <Percent className="h-6 w-6 text-white" aria-hidden="true" />
        </div>
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">Sales Commission</h1>
          <p className="text-slate-500 mt-0.5">Scheme komisi, monthly closing, dan pembayaran komisi sales.</p>
        </div>
      </div>
      <Tabs defaultValue="closings">
        <TabsList data-testid="commission-tabs">
          <TabsTrigger value="closings" data-testid="tab-closings">Monthly Closing</TabsTrigger>
          <TabsTrigger value="schemes" data-testid="tab-schemes">Commission Scheme</TabsTrigger>
          {isAdmin && <TabsTrigger value="settings" data-testid="tab-comm-settings">Settings</TabsTrigger>}
        </TabsList>
        <TabsContent value="closings"><ClosingsTab isAdmin={isAdmin} /></TabsContent>
        <TabsContent value="schemes"><SchemesTab isAdmin={isAdmin} /></TabsContent>
        {isAdmin && <TabsContent value="settings"><CommSettings /></TabsContent>}
      </Tabs>
    </div>
  );
}

/* ---------------- MY COMMISSION (Sales) ---------------- */
function MyCommission() {
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/commissions/my").then((r) => setData(r.data)).catch(() => setData({ current: {}, previous: [] })); }, []);
  if (!data) return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  const c = data.current || {};
  const cards = [
    ["Current Period", data.period, Wallet],
    ["Total Eligible Pax", c.total_pax || 0, null],
    ["Current Tier", c.tier || "-", null],
    ["Estimated Commission", rp(c.total_commission), null],
  ];
  return (
    <div className="space-y-6" data-testid="my-commission-page">
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900">My Commission</h1>
        <p className="text-slate-500 mt-1">Estimasi komisi periode berjalan &amp; riwayat pembayaran Anda.</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map(([label, val], i) => (
          <Card key={i} className="border-slate-200 shadow-sm" data-testid={`my-card-${i}`}>
            <CardContent className="p-5">
              <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{val}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="border-b border-slate-100"><CardTitle className="font-display text-lg">Previous Closing</CardTitle></CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm" data-testid="my-previous-table">
            <thead><tr className="bg-blue-600 text-white text-left">
              <th className="px-4 py-2.5">Period</th><th className="px-4 py-2.5 border-l border-blue-500">Pax</th>
              <th className="px-4 py-2.5 border-l border-blue-500">Tier</th><th className="px-4 py-2.5 border-l border-blue-500">Final Commission</th>
              <th className="px-4 py-2.5 border-l border-blue-500">Payment</th><th className="px-4 py-2.5 border-l border-blue-500">Closing</th>
            </tr></thead>
            <tbody>
              {(data.previous || []).length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Belum ada riwayat closing.</td></tr>
              ) : data.previous.map((l, i) => (
                <tr key={l.id || i} className={i % 2 ? "bg-slate-50" : "bg-white"}>
                  <td className="px-4 py-2.5 font-medium">{l.period}</td>
                  <td className="px-4 py-2.5 border-l border-slate-100">{l.total_pax}</td>
                  <td className="px-4 py-2.5 border-l border-slate-100">{l.tier}</td>
                  <td className="px-4 py-2.5 border-l border-slate-100 font-semibold">{rp(l.final_commission)}</td>
                  <td className="px-4 py-2.5 border-l border-slate-100"><Badge className={l.payment_status === "PAID" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-500 border-slate-200"}>{l.payment_status}</Badge></td>
                  <td className="px-4 py-2.5 border-l border-slate-100">{l.closing_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

/* ---------------- CLOSINGS TAB ---------------- */
function ClosingsTab({ isAdmin }) {
  const [closings, setClosings] = useState([]);
  const [period, setPeriod] = useState("");
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [drill, setDrill] = useState(null);

  const load = () => api.get("/commissions/closings").then((r) => setClosings(r.data || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const openDetail = (p) => { setSelected(p); api.get(`/commissions/closings/${p}`).then((r) => setDetail(r.data)).catch(() => {}); };

  const createPeriod = async () => {
    if (!period) return toast.error("Pilih periode dulu");
    try { await api.post("/commissions/closings", { period }); toast.success("Periode dibuat"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const calculate = async (p) => {
    setBusy(true);
    try { const r = await api.post(`/commissions/closings/${p}/calculate`); toast.success(`Dihitung: ${r.data.lines} sales, ${r.data.total_pax} pax`); load(); openDetail(p); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setBusy(false); }
  };
  const setStatus = async (p, status) => {
    try { await api.patch(`/commissions/closings/${p}/status`, { status }); toast.success(`Status → ${status}`); load(); openDetail(p); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const reopen = async (p) => {
    try { await api.post(`/commissions/closings/${p}/reopen`); toast.success("Closing di-REOPEN"); load(); openDetail(p); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const saveAdjustment = async (line) => {
    try { await api.patch(`/commissions/lines/${line.id}/adjustment`, { adjustment: Number(line._adj ?? line.adjustment ?? 0) }); toast.success("Adjustment tersimpan"); openDetail(selected); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const togglePayment = async (line) => {
    const next = line.payment_status === "PAID" ? "UNPAID" : "PAID";
    try { await api.patch(`/commissions/lines/${line.id}/payment`, { payment_status: next }); openDetail(selected); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const openDrill = (sid) => api.get(`/commissions/closings/${selected}/sales/${sid}`).then((r) => setDrill(r.data)).catch(() => {});

  const st = detail?.closing?.status;
  const locked = st === "CLOSED" || st === "PAID";

  return (
    <div className="space-y-5">
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-5 flex flex-wrap items-end gap-3">
          <div>
            <Label>Periode (bulan)</Label>
            <Input type="month" value={period} onChange={(e) => setPeriod(e.target.value)} className="mt-1 w-48" data-testid="closing-period-input" />
          </div>
          <Button onClick={createPeriod} data-testid="create-closing-btn"><Plus className="h-4 w-4 mr-1" /> Buat Periode</Button>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="border-b border-slate-100"><CardTitle className="font-display text-lg">Daftar Closing</CardTitle></CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm" data-testid="closings-table">
            <thead><tr className="bg-blue-600 text-white text-left">
              <th className="px-4 py-2.5">Period</th><th className="px-4 py-2.5 border-l border-blue-500">Status</th>
              <th className="px-4 py-2.5 border-l border-blue-500">Total Pax</th><th className="px-4 py-2.5 border-l border-blue-500">Total Commission</th>
              <th className="px-4 py-2.5 border-l border-blue-500">Aksi</th>
            </tr></thead>
            <tbody>
              {closings.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Belum ada closing.</td></tr>
              ) : closings.map((c, i) => (
                <tr key={c.period} className={i % 2 ? "bg-slate-50" : "bg-white"} data-testid={`closing-row-${c.period}`}>
                  <td className="px-4 py-2.5 font-medium">{c.period}</td>
                  <td className="px-4 py-2.5 border-l border-slate-100"><Badge className={CLOSING_COLORS[c.status]}>{c.status}</Badge></td>
                  <td className="px-4 py-2.5 border-l border-slate-100">{c.total_pax || 0}</td>
                  <td className="px-4 py-2.5 border-l border-slate-100 font-semibold">{rp(c.total_commission)}</td>
                  <td className="px-4 py-2.5 border-l border-slate-100 space-x-2">
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => calculate(c.period)} data-testid={`calc-${c.period}`}><Calculator className="h-3.5 w-3.5 mr-1" /> Calculate</Button>
                    <Button size="sm" variant="ghost" onClick={() => openDetail(c.period)} data-testid={`view-${c.period}`}><Eye className="h-3.5 w-3.5 mr-1" /> Report</Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {detail?.closing && (
        <Card className="border-slate-200 shadow-sm" data-testid="closing-detail">
          <CardHeader className="border-b border-slate-100 flex flex-row items-center justify-between">
            <CardTitle className="font-display text-lg flex items-center gap-2">Report {selected} <Badge className={CLOSING_COLORS[st]}>{st}</Badge></CardTitle>
            <div className="space-x-2">
              {st === "REVIEW" && <Button size="sm" onClick={() => setStatus(selected, "APPROVED")} data-testid="btn-approve">Approve</Button>}
              {st === "APPROVED" && <Button size="sm" onClick={() => setStatus(selected, "CLOSED")} data-testid="btn-close">Close</Button>}
              {st === "CLOSED" && <Button size="sm" onClick={() => setStatus(selected, "PAID")} data-testid="btn-paid">Mark Paid</Button>}
              {isAdmin && locked && <Button size="sm" variant="outline" onClick={() => reopen(selected)} data-testid="btn-reopen"><RotateCcw className="h-3.5 w-3.5 mr-1" /> Reopen</Button>}
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-sm" data-testid="report-table">
              <thead><tr className="bg-slate-800 text-white text-left">
                <th className="px-3 py-2.5">Sales</th><th className="px-3 py-2.5 border-l border-slate-600">Pax</th>
                <th className="px-3 py-2.5 border-l border-slate-600">Tier</th><th className="px-3 py-2.5 border-l border-slate-600">Rate</th>
                <th className="px-3 py-2.5 border-l border-slate-600">Commission</th><th className="px-3 py-2.5 border-l border-slate-600">Adjustment</th>
                <th className="px-3 py-2.5 border-l border-slate-600">Final</th><th className="px-3 py-2.5 border-l border-slate-600">Payment</th>
                <th className="px-3 py-2.5 border-l border-slate-600"></th>
              </tr></thead>
              <tbody>
                {(detail.lines || []).length === 0 ? (
                  <tr><td colSpan={9} className="px-4 py-8 text-center text-slate-400">Belum dihitung. Klik Calculate.</td></tr>
                ) : detail.lines.map((l, i) => (
                  <tr key={l.id} className={i % 2 ? "bg-slate-50" : "bg-white"} data-testid={`line-${l.sales_pic_id}`}>
                    <td className="px-3 py-2.5 font-medium">{l.sales_pic_name}</td>
                    <td className="px-3 py-2.5 border-l border-slate-100">{l.total_pax}</td>
                    <td className="px-3 py-2.5 border-l border-slate-100">{l.tier}</td>
                    <td className="px-3 py-2.5 border-l border-slate-100">{rp(l.commission_rate)}</td>
                    <td className="px-3 py-2.5 border-l border-slate-100">{rp(l.total_commission)}</td>
                    <td className="px-3 py-2.5 border-l border-slate-100">
                      <div className="flex items-center gap-1">
                        <Input type="number" defaultValue={l.adjustment || 0} disabled={locked} className="w-24 h-8"
                          onChange={(e) => { l._adj = e.target.value; }} data-testid={`adj-input-${l.sales_pic_id}`} />
                        {!locked && <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => saveAdjustment(l)} data-testid={`adj-save-${l.sales_pic_id}`}><Save className="h-4 w-4" /></Button>}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 border-l border-slate-100 font-semibold">{rp(l.final_commission)}</td>
                    <td className="px-3 py-2.5 border-l border-slate-100">
                      <button onClick={() => togglePayment(l)} data-testid={`pay-toggle-${l.sales_pic_id}`}>
                        <Badge className={l.payment_status === "PAID" ? "bg-emerald-50 text-emerald-700 border-emerald-200 cursor-pointer" : "bg-slate-100 text-slate-500 border-slate-200 cursor-pointer"}>{l.payment_status}</Badge>
                      </button>
                    </td>
                    <td className="px-3 py-2.5 border-l border-slate-100">
                      <Button size="sm" variant="ghost" onClick={() => openDrill(l.sales_pic_id)} data-testid={`drill-${l.sales_pic_id}`}><Eye className="h-3.5 w-3.5" /></Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      <Dialog open={!!drill} onOpenChange={(o) => !o && setDrill(null)}>
        <DialogContent className="max-w-3xl" data-testid="drill-dialog">
          <DialogHeader><DialogTitle>Commission Detail</DialogTitle></DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto">
            <table className="w-full text-sm">
              <thead><tr className="bg-slate-100 text-left"><th className="px-3 py-2">Booking</th><th className="px-3 py-2">Traveler</th><th className="px-3 py-2">Package</th><th className="px-3 py-2">Departure</th><th className="px-3 py-2">Tier</th><th className="px-3 py-2">Rate</th></tr></thead>
              <tbody>
                {(drill?.items || []).map((it, i) => (
                  <tr key={i} className="border-t border-slate-100">
                    <td className="px-3 py-2">{it.booking_number}</td><td className="px-3 py-2">{it.traveler_name}</td>
                    <td className="px-3 py-2">{it.package_name}</td><td className="px-3 py-2">{it.departure_date || "-"}</td>
                    <td className="px-3 py-2">{it.tier}</td><td className="px-3 py-2">{rp(it.commission_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ---------------- SCHEMES TAB ---------------- */
const EMPTY_SCHEME = { scheme_name: "", product_type: "ALL", package_id: "", effective_from: "", effective_until: "", calculation_basis: "PAID", tiers: [{ min_pax: 0, max_pax: 9, rate_per_pax: 100000 }], auto_sales: false, status: "ACTIVE" };

function SchemesTab({ isAdmin }) {
  const [schemes, setSchemes] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_SCHEME);
  const [editId, setEditId] = useState(null);

  const load = () => api.get("/commissions/schemes").then((r) => setSchemes(r.data || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const openNew = () => { setForm(EMPTY_SCHEME); setEditId(null); setOpen(true); };
  const openEdit = (s) => { setForm({ ...EMPTY_SCHEME, ...s, tiers: s.tiers?.length ? s.tiers : EMPTY_SCHEME.tiers }); setEditId(s.id); setOpen(true); };

  const save = async () => {
    if (!form.scheme_name) return toast.error("Nama scheme wajib diisi");
    const payload = { ...form, tiers: form.tiers.map((t) => ({ min_pax: Number(t.min_pax) || 0, max_pax: t.max_pax === "" || t.max_pax === null ? null : Number(t.max_pax), rate_per_pax: Number(t.rate_per_pax) || 0 })) };
    try {
      if (editId) await api.put(`/commissions/schemes/${editId}`, payload);
      else await api.post("/commissions/schemes", payload);
      toast.success("Scheme tersimpan"); setOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const del = async (id) => { try { await api.delete(`/commissions/schemes/${id}`); toast.success("Scheme dihapus"); load(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };

  const setTier = (i, k, v) => { const t = [...form.tiers]; t[i] = { ...t[i], [k]: v }; setForm({ ...form, tiers: t }); };
  const addTier = () => setForm({ ...form, tiers: [...form.tiers, { min_pax: 0, max_pax: null, rate_per_pax: 0 }] });
  const rmTier = (i) => setForm({ ...form, tiers: form.tiers.filter((_, x) => x !== i) });

  return (
    <div className="space-y-4">
      {isAdmin && <Button onClick={openNew} data-testid="new-scheme-btn"><Plus className="h-4 w-4 mr-1" /> Scheme Baru</Button>}
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-0">
          <table className="w-full text-sm" data-testid="schemes-table">
            <thead><tr className="bg-blue-600 text-white text-left">
              <th className="px-4 py-2.5">Scheme</th><th className="px-4 py-2.5 border-l border-blue-500">Product</th>
              <th className="px-4 py-2.5 border-l border-blue-500">Basis</th><th className="px-4 py-2.5 border-l border-blue-500">Tiers</th>
              <th className="px-4 py-2.5 border-l border-blue-500">Auto Sales</th><th className="px-4 py-2.5 border-l border-blue-500">Status</th>
              {isAdmin && <th className="px-4 py-2.5 border-l border-blue-500"></th>}
            </tr></thead>
            <tbody>
              {schemes.length === 0 ? (
                <tr><td colSpan={isAdmin ? 7 : 6} className="px-4 py-8 text-center text-slate-400">Belum ada scheme.</td></tr>
              ) : schemes.map((s, i) => (
                <tr key={s.id} className={i % 2 ? "bg-slate-50" : "bg-white"} data-testid={`scheme-row-${i}`}>
                  <td className="px-4 py-2.5 font-medium">{s.scheme_name}</td>
                  <td className="px-4 py-2.5 border-l border-slate-100">{s.product_type}</td>
                  <td className="px-4 py-2.5 border-l border-slate-100">{s.calculation_basis}</td>
                  <td className="px-4 py-2.5 border-l border-slate-100">{(s.tiers || []).map((t) => `${t.min_pax}-${t.max_pax ?? "∞"}:${rp(t.rate_per_pax)}`).join(" | ")}</td>
                  <td className="px-4 py-2.5 border-l border-slate-100">{s.auto_sales ? "Yes" : "No"}</td>
                  <td className="px-4 py-2.5 border-l border-slate-100"><Badge className={s.status === "ACTIVE" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-500 border-slate-200"}>{s.status}</Badge></td>
                  {isAdmin && <td className="px-4 py-2.5 border-l border-slate-100 space-x-1">
                    <Button size="sm" variant="ghost" onClick={() => openEdit(s)} data-testid={`edit-scheme-${i}`}>Edit</Button>
                    <Button size="icon" variant="ghost" className="h-8 w-8 text-red-500" onClick={() => del(s.id)} data-testid={`del-scheme-${i}`}><Trash2 className="h-4 w-4" /></Button>
                  </td>}
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl" data-testid="scheme-dialog">
          <DialogHeader><DialogTitle>{editId ? "Edit" : "New"} Commission Scheme</DialogTitle></DialogHeader>
          <div className="space-y-4 max-h-[65vh] overflow-y-auto pr-1">
            <div><Label>Scheme Name</Label><Input value={form.scheme_name} onChange={(e) => setForm({ ...form, scheme_name: e.target.value })} data-testid="scheme-name-input" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Product Type</Label>
                <Select value={form.product_type} onValueChange={(v) => setForm({ ...form, product_type: v })}>
                  <SelectTrigger data-testid="scheme-product-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{PRODUCT_TYPES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div><Label>Calculation Basis</Label>
                <Select value={form.calculation_basis} onValueChange={(v) => setForm({ ...form, calculation_basis: v })}>
                  <SelectTrigger data-testid="scheme-basis-select"><SelectValue /></SelectTrigger>
                  <SelectContent>{BASES.map((b) => <SelectItem key={b} value={b}>{b}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Effective From</Label><Input type="date" value={form.effective_from || ""} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} data-testid="scheme-from-input" /></div>
              <div><Label>Effective Until</Label><Input type="date" value={form.effective_until || ""} onChange={(e) => setForm({ ...form, effective_until: e.target.value })} data-testid="scheme-until-input" /></div>
            </div>
            <div className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-2.5">
              <div><p className="font-medium text-slate-800 text-sm">Scheme untuk AUTO SALES</p><p className="text-xs text-slate-400">Aktifkan jika scheme ini khusus booking AUTO SALES.</p></div>
              <Switch checked={!!form.auto_sales} onCheckedChange={(v) => setForm({ ...form, auto_sales: v })} data-testid="scheme-autosales-switch" />
            </div>
            <div>
              <div className="flex items-center justify-between mb-2"><Label>Tier Commission (rate per pax)</Label><Button size="sm" variant="outline" onClick={addTier} data-testid="add-tier-btn"><Plus className="h-3.5 w-3.5 mr-1" /> Tier</Button></div>
              <div className="space-y-2">
                {form.tiers.map((t, i) => (
                  <div key={i} className="grid grid-cols-12 gap-2 items-center">
                    <Input className="col-span-3" type="number" placeholder="Min Pax" value={t.min_pax} onChange={(e) => setTier(i, "min_pax", e.target.value)} data-testid={`tier-min-${i}`} />
                    <Input className="col-span-3" type="number" placeholder="Max Pax (kosong=∞)" value={t.max_pax ?? ""} onChange={(e) => setTier(i, "max_pax", e.target.value)} data-testid={`tier-max-${i}`} />
                    <Input className="col-span-5" type="number" placeholder="Rate/Pax (Rp)" value={t.rate_per_pax} onChange={(e) => setTier(i, "rate_per_pax", e.target.value)} data-testid={`tier-rate-${i}`} />
                    <Button size="icon" variant="ghost" className="col-span-1 h-8 w-8 text-red-500" onClick={() => rmTier(i)} data-testid={`tier-rm-${i}`}><Trash2 className="h-4 w-4" /></Button>
                  </div>
                ))}
              </div>
            </div>
            <div><Label>Status</Label>
              <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                <SelectTrigger data-testid="scheme-status-select"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="ACTIVE">ACTIVE</SelectItem><SelectItem value="INACTIVE">INACTIVE</SelectItem></SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter><Button onClick={save} data-testid="save-scheme-btn">Simpan</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ---------------- COMM SETTINGS (Admin) ---------------- */
function CommSettings() {
  const [cfg, setCfg] = useState(null);
  useEffect(() => { api.get("/commissions/settings").then((r) => setCfg(r.data)).catch(() => setCfg({ auto_sales_commission: false })); }, []);
  const save = async (v) => {
    setCfg({ ...cfg, auto_sales_commission: v });
    try { await api.put("/commissions/settings", { auto_sales_commission: v }); toast.success("Settings tersimpan"); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  if (!cfg) return <div className="p-8 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>;
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="border-b border-slate-100"><CardTitle className="font-display text-lg">Commission Settings</CardTitle></CardHeader>
      <CardContent className="p-5">
        <div className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3">
          <div><p className="font-medium text-slate-800">AUTO SALES Commission</p><p className="text-xs text-slate-400">Default OFF. Jika ON, booking AUTO SALES dapat komisi via scheme khusus AUTO SALES.</p></div>
          <Switch checked={!!cfg.auto_sales_commission} onCheckedChange={save} data-testid="autosales-commission-switch" />
        </div>
      </CardContent>
    </Card>
  );
}
