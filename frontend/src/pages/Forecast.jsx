import { useEffect, useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import {
  Loader2, TrendingUp, Wallet, ArrowDownCircle, ArrowUpCircle, Percent, RefreshCw, Target,
  Plus, Eye, Pencil, Trash2, ClipboardList,
} from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";

const rp = (v) => "Rp " + Number(v || 0).toLocaleString("id-ID");
const rpShort = (v) => {
  const n = Number(v || 0);
  if (Math.abs(n) >= 1e9) return "Rp " + (n / 1e9).toFixed(1) + "M";
  if (Math.abs(n) >= 1e6) return "Rp " + (n / 1e6).toFixed(1) + "jt";
  if (Math.abs(n) >= 1e3) return "Rp " + (n / 1e3).toFixed(0) + "rb";
  return "Rp " + n;
};
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Ags", "Sep", "Okt", "Nov", "Des"];
const mLabel = (mk) => (mk && mk.length >= 7 ? `${MONTHS[+mk.slice(5, 7) - 1]} ${mk.slice(2, 4)}` : "—");

const STAGE_COLORS = {
  NEW: "#94a3b8", CONTACTED: "#60a5fa", QUALIFIED: "#818cf8",
  QUOTATION: "#a78bfa", NEGOTIATION: "#f59e0b", BOOKING: "#10b981",
};
const STATUS_COLORS = {
  DRAFT: "bg-slate-100 text-slate-600 border-slate-200",
  SUBMITTED: "bg-blue-50 text-blue-700 border-blue-200",
  APPROVED: "bg-indigo-50 text-indigo-700 border-indigo-200",
  ACHIEVED: "bg-emerald-50 text-emerald-700 border-emerald-200",
  MISSED: "bg-red-50 text-red-700 border-red-200",
};

const ActualBadge = () => (
  <Badge className="bg-slate-700 text-white border-slate-700 text-[10px] tracking-wide" data-testid="badge-actual">ACTUAL</Badge>
);
const ForecastBadge = () => (
  <Badge className="bg-indigo-100 text-indigo-700 border-indigo-200 text-[10px] tracking-wide" data-testid="badge-forecast">FORECAST</Badge>
);

export default function Forecast() {
  return (
    <div className="space-y-6" data-testid="forecast-page">
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900 flex items-center gap-2">
          <Target className="h-7 w-7 text-indigo-600" aria-hidden="true" /> Forecasting
        </h1>
        <p className="text-sm text-slate-500 mt-1">Proyeksi penjualan &amp; keuangan. Dibedakan tegas dari data akuntansi aktual.</p>
      </div>
      <Tabs defaultValue="dashboard">
        <TabsList data-testid="forecast-tabs">
          <TabsTrigger value="dashboard" data-testid="tab-forecast-dashboard"><TrendingUp className="h-4 w-4 mr-1" />Dashboard</TabsTrigger>
          <TabsTrigger value="manual" data-testid="tab-forecast-manual"><ClipboardList className="h-4 w-4 mr-1" />Forecast Manual</TabsTrigger>
        </TabsList>
        <TabsContent value="dashboard" className="mt-4"><ForecastDashboard /></TabsContent>
        <TabsContent value="manual" className="mt-4"><ForecastRecords /></TabsContent>
      </Tabs>
    </div>
  );
}

/* ============================ MANUAL FORECAST CRUD ============================ */
const EMPTY_FORM = {
  period: "", salesperson_id: "", salesperson_name: "", team: "", branch: "",
  forecast_revenue: "", forecast_pax: "", forecast_gross_profit: "", forecast_margin: "",
  category: "UMRAH", status: "DRAFT", notes: "",
};

function ForecastRecords() {
  const [records, setRecords] = useState(null);
  const [summary, setSummary] = useState(null);
  const [meta, setMeta] = useState({ categories: [], statuses: [], salespeople: [] });
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [view, setView] = useState(null);
  const [toDelete, setToDelete] = useState(null);

  const load = () => api.get("/forecast/records").then((r) => { setRecords(r.data.records); setSummary(r.data.summary); })
    .catch(() => { setRecords([]); setSummary(null); });
  useEffect(() => {
    load();
    api.get("/forecast/meta").then((r) => setMeta(r.data)).catch(() => {});
  }, []);

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));
  const onSalesperson = (id) => {
    const sp = meta.salespeople.find((s) => s.id === id);
    setForm((f) => ({ ...f, salesperson_id: id, salesperson_name: sp?.name || "", branch: f.branch || sp?.branch || "" }));
  };

  const openCreate = () => { setEditing(null); setForm(EMPTY_FORM); setOpen(true); };
  const openEdit = (rec) => {
    setEditing(rec);
    setForm({
      period: rec.period || "", salesperson_id: rec.salesperson_id || "", salesperson_name: rec.salesperson_name || "",
      team: rec.team || "", branch: rec.branch || "",
      forecast_revenue: rec.forecast_revenue ?? "", forecast_pax: rec.forecast_pax ?? "",
      forecast_gross_profit: rec.forecast_gross_profit ?? "", forecast_margin: rec.forecast_margin ?? "",
      category: rec.category || "UMRAH", status: rec.status || "DRAFT", notes: rec.notes || "",
    });
    setOpen(true);
  };

  const save = async () => {
    if (!form.period) return toast.error("Periode wajib diisi");
    if (!form.salesperson_name) return toast.error("Salesperson wajib dipilih");
    setSaving(true);
    const payload = {
      period: form.period,
      salesperson_id: form.salesperson_id || null,
      salesperson_name: form.salesperson_name,
      team: form.team, branch: form.branch,
      forecast_revenue: Number(form.forecast_revenue || 0),
      forecast_pax: parseInt(form.forecast_pax || 0, 10),
      forecast_gross_profit: Number(form.forecast_gross_profit || 0),
      forecast_margin: form.forecast_margin === "" || form.forecast_margin === null ? null : Number(form.forecast_margin),
      category: form.category, status: form.status, notes: form.notes,
    };
    try {
      if (editing) { await api.put(`/forecast/records/${editing.id}`, payload); toast.success("Forecast diperbarui"); }
      else { await api.post("/forecast/records", payload); toast.success("Forecast dibuat"); }
      setOpen(false);
      load();
    } catch (e) {
      const st = e.response?.status;
      const d = e.response?.data?.detail;
      if (st === 409) toast.error(typeof d === "string" ? d : "Forecast duplikat.");
      else toast.error(formatApiErrorDetail(d));
    } finally { setSaving(false); }
  };

  const doDelete = async () => {
    try {
      await api.delete(`/forecast/records/${toDelete.id}`, { params: { reason: "Dihapus dari UI" } });
      toast.success("Forecast dihapus");
      setToDelete(null);
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  if (records === null) return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-indigo-600" /></div>;

  return (
    <div className="space-y-5" data-testid="forecast-manual">
      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="forecast-summary">
          <SumCard label="Total Forecast Revenue" value={rp(summary.total_revenue)} icon={TrendingUp} testid="sum-revenue" />
          <SumCard label="Total Forecast Pax" value={Number(summary.total_pax || 0).toLocaleString("id-ID")} icon={Target} testid="sum-pax" />
          <SumCard label="Total Gross Profit" value={rp(summary.total_gross_profit)} icon={Wallet} testid="sum-gp" />
          <SumCard label="Avg Margin" value={`${summary.total_margin}%`} icon={Percent} testid="sum-margin" />
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-slate-500"><ForecastBadge /> Forecast manual (terpisah dari data aktual akuntansi)</div>
        <Button className="bg-indigo-600 hover:bg-indigo-700" onClick={openCreate} data-testid="add-forecast-btn">
          <Plus className="h-4 w-4 mr-1" /> Add Forecast
        </Button>
      </div>

      {/* By period summary */}
      {summary && summary.by_period.length > 0 && (
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-2"><CardTitle className="text-sm text-slate-700">Ringkasan per Periode</CardTitle></CardHeader>
          <CardContent className="p-4 pt-0 overflow-x-auto">
            <table className="w-full text-sm" data-testid="forecast-period-summary">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-400 border-b border-slate-100">
                  <th className="py-2">Periode</th><th className="py-2 text-right">Jml</th>
                  <th className="py-2 text-right">Revenue</th><th className="py-2 text-right">Pax</th>
                  <th className="py-2 text-right">Gross Profit</th><th className="py-2 text-right">Margin</th>
                </tr>
              </thead>
              <tbody>
                {summary.by_period.map((p) => (
                  <tr key={p.period} className="border-b border-slate-50">
                    <td className="py-2 font-medium">{mLabel(p.period)}</td>
                    <td className="py-2 text-right">{p.count}</td>
                    <td className="py-2 text-right text-slate-600">{rpShort(p.revenue)}</td>
                    <td className="py-2 text-right">{p.pax}</td>
                    <td className="py-2 text-right text-emerald-700">{rpShort(p.gross_profit)}</td>
                    <td className="py-2 text-right font-semibold text-indigo-700">{p.margin}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Records table */}
      <Card className="border-slate-200 shadow-sm overflow-hidden">
        {records.length === 0 ? (
          <div className="p-12 text-center text-slate-500" data-testid="forecast-empty">
            <ClipboardList className="h-8 w-8 mx-auto text-slate-300" />
            <p className="mt-2">Belum ada forecast manual. Klik "Add Forecast" untuk membuat.</p>
          </div>
        ) : (
          <Table data-testid="forecast-table">
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead>Periode</TableHead><TableHead>Salesperson</TableHead><TableHead>Kategori</TableHead>
                <TableHead>Team / Cabang</TableHead><TableHead className="text-right">Revenue</TableHead>
                <TableHead className="text-right">Pax</TableHead><TableHead className="text-right">GP</TableHead>
                <TableHead className="text-right">Margin</TableHead><TableHead>Status</TableHead>
                <TableHead className="text-right">Aksi</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {records.map((r) => (
                <TableRow key={r.id} className="hover:bg-slate-50" data-testid={`forecast-row-${r.id}`}>
                  <TableCell className="font-medium">{mLabel(r.period)}</TableCell>
                  <TableCell>{r.salesperson_name}</TableCell>
                  <TableCell><Badge variant="outline" className="bg-slate-50 text-slate-600">{r.category}</Badge></TableCell>
                  <TableCell className="text-slate-500 text-xs">{[r.team, r.branch].filter(Boolean).join(" · ") || "—"}</TableCell>
                  <TableCell className="text-right text-slate-700">{rpShort(r.forecast_revenue)}</TableCell>
                  <TableCell className="text-right">{r.forecast_pax}</TableCell>
                  <TableCell className="text-right text-emerald-700">{rpShort(r.forecast_gross_profit)}</TableCell>
                  <TableCell className="text-right font-semibold text-indigo-700">{r.forecast_margin}%</TableCell>
                  <TableCell><Badge variant="outline" className={STATUS_COLORS[r.status] || STATUS_COLORS.DRAFT}>{r.status}</Badge></TableCell>
                  <TableCell className="text-right whitespace-nowrap">
                    <Button variant="ghost" size="icon" onClick={() => setView(r)} data-testid={`view-forecast-${r.id}`} title="Lihat"><Eye className="h-4 w-4 text-slate-500" /></Button>
                    <Button variant="ghost" size="icon" onClick={() => openEdit(r)} data-testid={`edit-forecast-${r.id}`} title="Edit"><Pencil className="h-4 w-4 text-blue-600" /></Button>
                    <Button variant="ghost" size="icon" onClick={() => setToDelete(r)} data-testid={`delete-forecast-${r.id}`} title="Hapus"><Trash2 className="h-4 w-4 text-red-600" /></Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      {/* Add / Edit dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-white max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="forecast-dialog">
          <DialogHeader>
            <DialogTitle className="font-display">{editing ? "Edit Forecast" : "Add Forecast"}</DialogTitle>
            <DialogDescription>Isi target forecast. Margin dihitung otomatis dari Revenue &amp; Gross Profit bila dikosongkan.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-2">
            <div className="space-y-1">
              <Label className="text-xs">Periode Forecast *</Label>
              <Input type="month" value={form.period} onChange={(e) => set("period")(e.target.value)} data-testid="forecast-period" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Salesperson *</Label>
              <Select value={form.salesperson_id} onValueChange={onSalesperson}>
                <SelectTrigger data-testid="forecast-salesperson"><SelectValue placeholder="Pilih salesperson" /></SelectTrigger>
                <SelectContent className="bg-white">
                  {meta.salespeople.map((s) => <SelectItem key={s.id} value={s.id} data-testid={`sp-opt-${s.id}`}>{s.name} ({s.role})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Team</Label>
              <Input value={form.team} onChange={(e) => set("team")(e.target.value)} data-testid="forecast-team" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Cabang</Label>
              <Input value={form.branch} onChange={(e) => set("branch")(e.target.value)} data-testid="forecast-branch" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Forecast Revenue (Rp) *</Label>
              <Input type="number" min="0" value={form.forecast_revenue} onChange={(e) => set("forecast_revenue")(e.target.value)} data-testid="forecast-revenue" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Forecast Pax *</Label>
              <Input type="number" min="0" value={form.forecast_pax} onChange={(e) => set("forecast_pax")(e.target.value)} data-testid="forecast-pax" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Forecast Gross Profit (Rp)</Label>
              <Input type="number" min="0" value={form.forecast_gross_profit} onChange={(e) => set("forecast_gross_profit")(e.target.value)} data-testid="forecast-gp" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Forecast Margin (%) — kosongkan untuk auto</Label>
              <Input type="number" step="0.01" value={form.forecast_margin} onChange={(e) => set("forecast_margin")(e.target.value)} data-testid="forecast-margin" placeholder="auto" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Kategori</Label>
              <Select value={form.category} onValueChange={set("category")}>
                <SelectTrigger data-testid="forecast-category"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white">
                  {meta.categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Status</Label>
              <Select value={form.status} onValueChange={set("status")}>
                <SelectTrigger data-testid="forecast-status"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white">
                  {meta.statuses.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label className="text-xs">Catatan</Label>
              <Textarea value={form.notes} onChange={(e) => set("notes")(e.target.value)} data-testid="forecast-notes" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Batal</Button>
            <Button className="bg-indigo-600 hover:bg-indigo-700" onClick={save} disabled={saving} data-testid="forecast-save-btn">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : editing ? "Simpan Perubahan" : "Buat Forecast"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View dialog */}
      <Dialog open={!!view} onOpenChange={(o) => !o && setView(null)}>
        <DialogContent className="bg-white" data-testid="forecast-view-dialog">
          <DialogHeader>
            <DialogTitle className="font-display">Detail Forecast</DialogTitle>
            <DialogDescription>{view && `${mLabel(view.period)} · ${view.salesperson_name}`}</DialogDescription>
          </DialogHeader>
          {view && (
            <div className="grid grid-cols-2 gap-3 text-sm py-2">
              <Field l="Periode" v={mLabel(view.period)} /><Field l="Salesperson" v={view.salesperson_name} />
              <Field l="Team" v={view.team} /><Field l="Cabang" v={view.branch} />
              <Field l="Kategori" v={view.category} /><Field l="Status" v={view.status} />
              <Field l="Forecast Revenue" v={rp(view.forecast_revenue)} /><Field l="Forecast Pax" v={view.forecast_pax} />
              <Field l="Gross Profit" v={rp(view.forecast_gross_profit)} /><Field l="Margin" v={`${view.forecast_margin}%`} />
              <div className="col-span-2"><Field l="Catatan" v={view.notes || "—"} /></div>
              <div className="col-span-2 text-[11px] text-slate-400 border-t pt-2">Dibuat oleh {view.created_by || "—"} · {view.created_at?.slice(0, 16).replace("T", " ")}{view.updated_by ? ` · diedit oleh ${view.updated_by}` : ""}</div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent className="bg-white" data-testid="forecast-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Hapus Forecast</AlertDialogTitle>
            <AlertDialogDescription>Apakah Anda yakin ingin menghapus forecast ini?</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Batal</AlertDialogCancel>
            <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={doDelete} data-testid="forecast-delete-confirm">Hapus</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function SumCard({ label, value, icon: Icon, testid }) {
  return (
    <Card className="border-slate-200 shadow-sm" data-testid={testid}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <p className="text-xs uppercase tracking-wide font-semibold text-slate-500">{label}</p>
          <Icon className="h-4 w-4 text-indigo-400" aria-hidden="true" />
        </div>
        <p className="font-display text-xl font-bold text-slate-900 mt-2">{value}</p>
      </CardContent>
    </Card>
  );
}

function Field({ l, v }) {
  return <div><span className="text-slate-400 text-xs">{l}</span><p className="text-slate-800 font-medium">{v || "—"}</p></div>;
}

/* ============================ COMPUTED DASHBOARD ============================ */
function ForecastDashboard() {
  const [data, setData] = useState(undefined);
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    api.get("/forecast/dashboard").then((r) => setData(r.data)).catch((e) => {
      setData(null);
      toast.error(e.response?.data?.detail || "Gagal memuat forecast");
    }).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  if (data === undefined) return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-indigo-600" /></div>;
  if (data === null) return <div className="p-12 text-center text-red-600" data-testid="forecast-error">Forecast tidak tersedia (khusus Super Admin).</div>;

  const sf = data.sales_forecast;
  const cf = data.cash_flow_forecast;
  const rf = data.receivable_forecast;
  const ue = data.upcoming_expense;
  const uc = data.upcoming_commission;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-end gap-3">
        <div className="flex items-center gap-2 text-xs text-slate-500"><ActualBadge /> = realisasi <span className="mx-1">·</span> <ForecastBadge /> = proyeksi</div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="forecast-refresh">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </Button>
      </div>

      {/* 1. SALES FORECAST */}
      <section data-testid="section-sales-forecast">
        <SectionTitle icon={TrendingUp} color="text-indigo-600" title="Sales Forecast" subtitle="Pipeline weighted by probability" />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <KpiCard label="Pipeline Value" value={rp(sf.pipeline_value)} hint="Total nilai deal terbuka" badge="forecast" icon={TrendingUp} testid="kpi-pipeline-value" />
          <KpiCard label="Probability Weighted Value" value={rp(sf.weighted_value)} hint="Σ nilai × probability stage" badge="forecast" icon={Percent} testid="kpi-weighted-value" />
          <KpiCard label="Expected Closing (3 bln)" value={rp(sf.buckets.next_3_months.weighted)} hint={sf.buckets.next_3_months.label} badge="forecast" icon={Target} testid="kpi-expected-closing" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
          {[["Current Month", sf.buckets.current_month], ["Next Month", sf.buckets.next_month], ["Next 3 Months", sf.buckets.next_3_months]].map(([lbl, b], i) => (
            <Card key={i} className="border-slate-200 shadow-sm" data-testid={`sales-bucket-${i}`}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <p className="text-xs uppercase tracking-wide font-semibold text-slate-500">{lbl}</p>
                  <span className="text-[11px] text-slate-400">{b.label}</span>
                </div>
                <div className="mt-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-xs text-slate-500"><ForecastBadge /> Weighted</span>
                    <span className="font-display text-lg font-bold text-indigo-700">{rpShort(b.weighted)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-400">Pipeline (raw)</span>
                    <span className="text-sm font-medium text-slate-600">{rpShort(b.pipeline)}</span>
                  </div>
                  <div className="flex items-center justify-between border-t border-slate-100 pt-2">
                    <span className="flex items-center gap-1.5 text-xs text-slate-500"><ActualBadge /> Booked</span>
                    <span className="text-sm font-semibold text-slate-800">{rpShort(b.actual)}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
        <Card className="border-slate-200 shadow-sm mt-4">
          <CardHeader className="pb-2"><CardTitle className="text-sm text-slate-700">Pipeline per Stage</CardTitle></CardHeader>
          <CardContent className="p-4 pt-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="stage-summary-table">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-400 border-b border-slate-100">
                    <th className="py-2">Stage</th><th className="py-2">Probability</th><th className="py-2 text-right">Deals</th>
                    <th className="py-2 text-right">Pipeline Value</th><th className="py-2 text-right">Weighted</th>
                  </tr>
                </thead>
                <tbody>
                  {sf.stage_summary.map((s) => (
                    <tr key={s.stage} className="border-b border-slate-50" data-testid={`stage-row-${s.stage}`}>
                      <td className="py-2"><span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: STAGE_COLORS[s.stage] }} />{s.stage}</span></td>
                      <td className="py-2 text-slate-500">{Math.round(s.probability * 100)}%</td>
                      <td className="py-2 text-right">{s.count}</td>
                      <td className="py-2 text-right text-slate-600">{rp(s.value)}</td>
                      <td className="py-2 text-right font-semibold text-indigo-700">{rp(s.weighted)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* 2. CASH FLOW FORECAST */}
      <section data-testid="section-cash-flow">
        <SectionTitle icon={Wallet} color="text-emerald-600" title="Cash Flow Forecast" subtitle="Proyeksi arus kas 6 bulan (In − Out)" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card className="border-slate-200 shadow-sm lg:col-span-2">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2"><span className="text-sm font-medium text-slate-700">Cash In vs Cash Out</span><ForecastBadge /></div>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={cf.series.map((s) => ({ ...s, name: mLabel(s.month) }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tickFormatter={rpShort} tick={{ fontSize: 11 }} width={70} />
                  <Tooltip formatter={(v) => rp(v)} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="cash_in" name="Cash In" fill="#10b981" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="cash_out" name="Cash Out" fill="#ef4444" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <ResponsiveContainer width="100%" height={120}>
                <LineChart data={cf.series.map((s) => ({ ...s, name: mLabel(s.month) }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tickFormatter={rpShort} tick={{ fontSize: 11 }} width={70} />
                  <Tooltip formatter={(v) => rp(v)} />
                  <Line type="monotone" dataKey="net" name="Net Cash Flow" stroke="#6366f1" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
          <div className="space-y-4">
            <Card className="border-slate-700 bg-slate-800 text-white shadow-sm" data-testid="cf-actual-card">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2"><span className="text-xs uppercase tracking-wide font-semibold text-slate-300">Bulan Ini (Realisasi)</span><ActualBadge /></div>
                <p className="text-[11px] text-slate-400">{mLabel(cf.actual_current_month.month)}</p>
                <div className="mt-2 space-y-1.5 text-sm">
                  <Row l="Cash In" v={rp(cf.actual_current_month.cash_in)} c="text-emerald-300" />
                  <Row l="Cash Out" v={rp(cf.actual_current_month.cash_out)} c="text-red-300" />
                  <div className="border-t border-slate-700 pt-1.5"><Row l="Net" v={rp(cf.actual_current_month.net)} c="text-white font-bold" /></div>
                </div>
              </CardContent>
            </Card>
            <Card className="border-indigo-200 bg-indigo-50/50 shadow-sm">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2"><span className="text-xs uppercase tracking-wide font-semibold text-indigo-600">Total Proyeksi (6 bln)</span><ForecastBadge /></div>
                <div className="mt-1 space-y-1.5 text-sm">
                  <Row l="Total Cash In" v={rp(cf.forecast_total_in)} c="text-emerald-700" />
                  <Row l="Total Cash Out" v={rp(cf.forecast_total_out)} c="text-red-700" />
                  <div className="border-t border-indigo-200 pt-1.5"><Row l="Net" v={rp(cf.forecast_total_in - cf.forecast_total_out)} c="text-indigo-800 font-bold" /></div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* 3-5 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section data-testid="section-receivable">
          <SectionTitle icon={ArrowDownCircle} color="text-emerald-600" title="Receivable Forecast" subtitle={`Outstanding ${rpShort(rf.total_outstanding)}`} small />
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-end mb-1"><ForecastBadge /></div>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={rf.by_month.map((m) => ({ name: mLabel(m.month), amount: m.amount }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={rpShort} tick={{ fontSize: 10 }} width={55} />
                  <Tooltip formatter={(v) => rp(v)} />
                  <Bar dataKey="amount" name="Receivable" fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <ItemList testid="receivable-items" items={rf.items} render={(it) => (
                <><div><p className="font-medium text-slate-800">{it.booking_number}</p><p className="text-[11px] text-slate-400">{it.customer} · {it.label} · {it.due_date}</p></div>
                <span className="text-sm font-semibold text-emerald-700">{rpShort(it.amount)}</span></>
              )} />
            </CardContent>
          </Card>
        </section>

        <section data-testid="section-expense">
          <SectionTitle icon={ArrowUpCircle} color="text-red-600" title="Upcoming Expense" subtitle={`Supplier + Refund ${rpShort(ue.total)}`} small />
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-end mb-1"><ForecastBadge /></div>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={ue.by_month.map((m) => ({ name: mLabel(m.month), supplier: m.supplier, refund: m.refund }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={rpShort} tick={{ fontSize: 10 }} width={55} />
                  <Tooltip formatter={(v) => rp(v)} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="supplier" name="Supplier" stackId="a" fill="#ef4444" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="refund" name="Refund" stackId="a" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <ItemList testid="expense-items" items={ue.items} render={(it) => (
                <><div><p className="font-medium text-slate-800 flex items-center gap-1">{it.name}<Badge className={`text-[9px] ${it.type === "REFUND" ? "bg-amber-100 text-amber-700 border-amber-200" : "bg-red-100 text-red-700 border-red-200"}`}>{it.type}</Badge></p><p className="text-[11px] text-slate-400">{it.invoice_number} · {it.due_date}</p></div>
                <span className="text-sm font-semibold text-red-700">{rpShort(it.amount)}</span></>
              )} />
            </CardContent>
          </Card>
        </section>

        <section data-testid="section-commission">
          <SectionTitle icon={Percent} color="text-purple-600" title="Upcoming Commission" subtitle={`Payable ${rpShort(uc.total)}`} small />
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-end mb-1"><ForecastBadge /></div>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={uc.by_month.map((m) => ({ name: mLabel(m.month), amount: m.amount }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={rpShort} tick={{ fontSize: 10 }} width={55} />
                  <Tooltip formatter={(v) => rp(v)} />
                  <Bar dataKey="amount" name="Commission" fill="#a855f7" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <ItemList testid="commission-items" items={uc.items} render={(it) => (
                <><div><p className="font-medium text-slate-800">{it.sales}</p><p className="text-[11px] text-slate-400">{it.customer} · {it.booking_number} · {mLabel(it.payout_month)}</p></div>
                <span className="text-sm font-semibold text-purple-700">{rpShort(it.amount)}</span></>
              )} />
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}

function SectionTitle({ icon: Icon, color, title, subtitle, small }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon className={`h-5 w-5 ${color}`} aria-hidden="true" />
      <div>
        <h2 className={`font-display font-bold text-slate-900 ${small ? "text-base" : "text-lg"}`}>{title}</h2>
        {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
      </div>
    </div>
  );
}

function KpiCard({ label, value, hint, badge, icon: Icon, testid }) {
  return (
    <Card className="border-slate-200 shadow-sm" data-testid={testid}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <p className="text-xs uppercase tracking-wide font-semibold text-slate-500">{label}</p>
          {badge === "forecast" ? <ForecastBadge /> : <ActualBadge />}
        </div>
        <div className="flex items-center gap-2 mt-2">
          <Icon className="h-5 w-5 text-indigo-400" aria-hidden="true" />
          <p className="font-display text-2xl font-bold text-slate-900">{value}</p>
        </div>
        <p className="text-[11px] text-slate-400 mt-1">{hint}</p>
      </CardContent>
    </Card>
  );
}

function Row({ l, v, c }) {
  return <div className="flex items-center justify-between"><span className="text-slate-400 text-xs">{l}</span><span className={c}>{v}</span></div>;
}

function ItemList({ items, render, testid }) {
  if (!items || items.length === 0) return <p className="text-xs text-slate-400 text-center py-4">Tidak ada data.</p>;
  return (
    <div className="mt-3 space-y-1.5 max-h-64 overflow-y-auto" data-testid={testid}>
      {items.map((it, i) => (
        <div key={i} className="flex items-center justify-between border border-slate-100 rounded-md px-3 py-2">{render(it)}</div>
      ))}
    </div>
  );
}
