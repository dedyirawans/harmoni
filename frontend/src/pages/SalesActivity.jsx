import { useEffect, useState, useCallback } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { fmtIDR } from "@/config/crm";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Activity, Plus, Loader2, Phone, MessageCircle, Mail, Users, ClipboardList, FileText, CalendarCheck, Trophy, Target, Pencil, CalendarRange } from "lucide-react";
import { toast } from "sonner";

const MANUAL_TYPES = ["Call", "WhatsApp", "Email", "Meeting"];
const TYPE_META = {
  Call: { icon: Phone, cls: "bg-blue-50 text-blue-700 border-blue-200" },
  WhatsApp: { icon: MessageCircle, cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  Email: { icon: Mail, cls: "bg-violet-50 text-violet-700 border-violet-200" },
  Meeting: { icon: Users, cls: "bg-amber-50 text-amber-700 border-amber-200" },
  "Follow Up": { icon: ClipboardList, cls: "bg-cyan-50 text-cyan-700 border-cyan-200" },
  Quotation: { icon: FileText, cls: "bg-indigo-50 text-indigo-700 border-indigo-200" },
  Booking: { icon: CalendarCheck, cls: "bg-rose-50 text-rose-700 border-rose-200" },
};
const RANK_TABS = [
  ["by_revenue", "Revenue", (v) => fmtIDR(v)],
  ["by_pax", "Pax", (v) => v],
  ["by_booking", "Booking", (v) => v],
  ["by_conversion", "Conversion", (v) => `${v}%`],
  ["by_activity", "Activity Score", (v) => v],
];

export default function SalesActivity() {
  const { user } = useAuth();
  const isAdmin = user?.role === "super_admin";
  const now = new Date();
  const defMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [month, setMonth] = useState(defMonth);
  const [salesId, setSalesId] = useState("all");
  const [perf, setPerf] = useState(null);
  const [feed, setFeed] = useState(null);

  const load = useCallback(() => {
    const params = {};
    if (month) params.period = month;
    if (isAdmin && salesId !== "all") params.sales_id = salesId;
    setPerf(null); setFeed(null);
    api.get("/sales/performance", { params }).then((r) => setPerf(r.data)).catch(() => setPerf({ rows: [], rankings: {} }));
    api.get("/sales/activities", { params: { ...params, limit: 60 } }).then((r) => setFeed(r.data)).catch(() => setFeed([]));
  }, [month, isAdmin, salesId]);
  useEffect(() => { load(); }, [load]);

  const rows = perf?.rows || [];

  return (
    <div className="space-y-6" data-testid="sales-activity-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">Sales Activity &amp; Performance</h1>
          <p className="text-slate-500 mt-1">KPI, aktivitas, target, dan ranking sales. {isAdmin ? "Anda melihat seluruh tim." : "Anda hanya melihat data Anda sendiri."}</p>
        </div>
        <div className="flex items-center gap-2">
          <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-40 h-9" data-testid="period-month" />
          {month && <Button variant="ghost" size="sm" onClick={() => setMonth("")} data-testid="clear-period">All time</Button>}
          <LogActivityDialog isAdmin={isAdmin} sales={rows} onSaved={load} />
        </div>
      </div>

      {isAdmin && (
        <div className="flex items-center gap-2">
          <Label className="text-xs text-slate-500">Sales</Label>
          <Select value={salesId} onValueChange={setSalesId}>
            <SelectTrigger className="w-56 h-9" data-testid="sales-filter"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-white">
              <SelectItem value="all">Semua Sales</SelectItem>
              {rows.map((r) => <SelectItem key={r.sales_id} value={r.sales_id}>{r.sales}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      )}

      {perf === null ? <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
        : rows.length === 0 ? <p className="p-8 text-center text-sm text-slate-400" data-testid="perf-empty">Belum ada data.</p>
        : (
          <>
            {rows.length === 1 ? <SalesCards row={rows[0]} /> : <KpiTable rows={rows} />}
            <TargetsCard rows={rows} month={month} isAdmin={isAdmin} onSaved={load} />
            <ActivityBreakdown rows={rows} weights={perf.score_weights} />
            {rows.length > 1 && <Rankings rankings={perf.rankings} />}
            <ActivityFeed feed={feed} />
          </>
        )}
    </div>
  );
}

function Stat({ label, value, testid }) {
  return (
    <Card className="border-slate-200"><CardContent className="p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-xl font-bold text-slate-900 mt-1" data-testid={testid}>{value}</p>
    </CardContent></Card>
  );
}

function SalesCards({ row }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="sales-kpi-cards">
      <Stat label="Leads" value={row.leads} testid="kpi-leads" />
      <Stat label="Follow Up" value={row.follow_up} testid="kpi-followup" />
      <Stat label="Quotation" value={row.quotation} testid="kpi-quotation" />
      <Stat label="Conversion" value={`${row.conversion_rate}%`} testid="kpi-conversion" />
      <Stat label="Booking" value={row.booking} testid="kpi-booking" />
      <Stat label="Pax" value={row.pax} testid="kpi-pax" />
      <Stat label="Revenue" value={fmtIDR(row.revenue)} testid="kpi-revenue" />
      <Stat label="Commission" value={fmtIDR(row.commission)} testid="kpi-commission" />
    </div>
  );
}

function KpiTable({ rows }) {
  return (
    <Card className="border-slate-200 overflow-hidden">
      <div className="p-3 border-b border-slate-100 text-sm font-medium text-slate-600">KPI per Sales</div>
      <Table data-testid="kpi-table">
        <TableHeader><TableRow className="bg-slate-50">
          <TableHead>Sales</TableHead><TableHead className="text-right">Leads</TableHead><TableHead className="text-right">Follow Up</TableHead>
          <TableHead className="text-right">Quotation</TableHead><TableHead className="text-right">Conversion</TableHead><TableHead className="text-right">Booking</TableHead>
          <TableHead className="text-right">Pax</TableHead><TableHead className="text-right">Revenue</TableHead><TableHead className="text-right">Commission</TableHead>
          <TableHead className="text-right">Activity Score</TableHead>
        </TableRow></TableHeader>
        <TableBody>{rows.map((r) => (
          <TableRow key={r.sales_id} data-testid={`kpi-row-${r.sales_id}`}>
            <TableCell className="font-medium text-slate-900">{r.sales}</TableCell>
            <TableCell className="text-right">{r.leads}</TableCell>
            <TableCell className="text-right">{r.follow_up}</TableCell>
            <TableCell className="text-right">{r.quotation}</TableCell>
            <TableCell className="text-right">{r.conversion_rate}%</TableCell>
            <TableCell className="text-right">{r.booking}</TableCell>
            <TableCell className="text-right">{r.pax}</TableCell>
            <TableCell className="text-right font-medium text-slate-900">{fmtIDR(r.revenue)}</TableCell>
            <TableCell className="text-right text-emerald-700">{fmtIDR(r.commission)}</TableCell>
            <TableCell className="text-right"><Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">{r.activity_score}</Badge></TableCell>
          </TableRow>))}</TableBody>
      </Table>
    </Card>
  );
}

function Bar({ pct, color }) {
  const w = Math.min(100, Math.max(0, pct));
  return (
    <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${w}%` }} />
    </div>
  );
}

function TargetsCard({ rows, month, isAdmin, onSaved }) {
  const [edit, setEdit] = useState(null); // row for single-month edit
  const [yearly, setYearly] = useState(null); // row for yearly bulk edit
  return (
    <Card className="border-slate-200" data-testid="targets-card">
      <CardHeader className="pb-2 flex flex-row items-center justify-between">
        <CardTitle className="font-display text-lg flex items-center gap-2"><Target className="h-4 w-4 text-blue-600" />Target Bulanan {month && `· ${month}`}</CardTitle>
        {isAdmin && <span className="text-xs text-slate-400">Hanya Super Admin yang dapat mengatur target</span>}
      </CardHeader>
      <CardContent className="space-y-4">
        {!month ? <p className="text-sm text-slate-400" data-testid="targets-hint">Pilih bulan di atas untuk melihat{isAdmin ? " & menetapkan" : ""} target revenue/pax.</p>
          : rows.map((r) => {
            const hasT = r.revenue_target > 0 || r.pax_target > 0;
            return (
              <div key={r.sales_id} className="space-y-2 border-b border-slate-100 pb-3 last:border-0 last:pb-0" data-testid={`target-${r.sales_id}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-slate-800">{r.sales}</span>
                  {isAdmin && (
                    <div className="flex items-center gap-1">
                      <Button size="sm" variant="ghost" onClick={() => setEdit(r)} data-testid={`edit-target-${r.sales_id}`}><Pencil className="h-3.5 w-3.5 mr-1" />Edit Bulan Ini</Button>
                      <Button size="sm" variant="outline" onClick={() => setYearly(r)} data-testid={`yearly-target-${r.sales_id}`}><CalendarRange className="h-3.5 w-3.5 mr-1" />Set 1 Tahun</Button>
                    </div>
                  )}
                </div>
                {!hasT ? <p className="text-xs text-slate-400" data-testid={`no-target-${r.sales_id}`}>Belum ada target.</p>
                  : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <div className="flex justify-between text-xs mb-1"><span className="text-slate-500">Revenue</span><span className="text-slate-700"><b data-testid={`rev-progress-${r.sales_id}`}>{r.revenue_progress}%</b> · {fmtIDR(r.revenue)} / {fmtIDR(r.revenue_target)}</span></div>
                        <Bar pct={r.revenue_progress} color={r.revenue_progress >= 100 ? "bg-emerald-500" : "bg-blue-500"} />
                      </div>
                      <div>
                        <div className="flex justify-between text-xs mb-1"><span className="text-slate-500">Pax</span><span className="text-slate-700"><b data-testid={`pax-progress-${r.sales_id}`}>{r.pax_progress}%</b> · {r.pax} / {r.pax_target}</span></div>
                        <Bar pct={r.pax_progress} color={r.pax_progress >= 100 ? "bg-emerald-500" : "bg-indigo-500"} />
                      </div>
                    </div>
                  )}
              </div>
            );
          })}
      </CardContent>
      {edit && <SetTargetDialog row={edit} month={month} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); onSaved(); }} />}
      {yearly && <YearlyTargetDialog row={yearly} startMonth={month} onClose={() => setYearly(null)} onSaved={() => { setYearly(null); onSaved(); }} />}
    </Card>
  );
}

function SetTargetDialog({ row, month, onClose, onSaved }) {
  const [rev, setRev] = useState(row.revenue_target || "");
  const [pax, setPax] = useState(row.pax_target || "");
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      await api.put("/sales/targets", { sales_id: row.sales_id, period: month, revenue_target: Number(rev || 0), pax_target: Number(pax || 0) });
      toast.success("Target disimpan"); onSaved();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setSaving(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-white max-w-sm" data-testid="set-target-dialog">
        <DialogHeader><DialogTitle className="font-display">Edit Target · {row.sales} · {month}</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div className="space-y-1"><Label className="text-xs">Target Revenue (Rp)</Label><Input type="number" value={rev} onChange={(e) => setRev(e.target.value)} data-testid="target-revenue" /></div>
          <div className="space-y-1"><Label className="text-xs">Target Pax</Label><Input type="number" value={pax} onChange={(e) => setPax(e.target.value)} data-testid="target-pax" /></div>
        </div>
        <DialogFooter><Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="target-save">{saving ? "..." : "Simpan"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function monthLabel(period) {
  const [y, m] = period.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("id-ID", { month: "long", year: "numeric" });
}

function YearlyTargetDialog({ row, startMonth, onClose, onSaved }) {
  const now = new Date();
  const start = startMonth || `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [sy, sm] = start.split("-").map(Number);
  const periods = Array.from({ length: 12 }, (_, i) => {
    const d = new Date(sy, sm - 1 + i, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
  const [items, setItems] = useState(periods.map((p) => ({ period: p, revenue_target: "", pax_target: "" })));
  const [baseRev, setBaseRev] = useState("");
  const [basePax, setBasePax] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/sales/targets", { params: { sales_id: row.sales_id } }).then((r) => {
      const map = {};
      (r.data || []).forEach((t) => { map[t.period] = t; });
      setItems(periods.map((p) => ({ period: p, revenue_target: map[p]?.revenue_target || "", pax_target: map[p]?.pax_target || "" })));
    }).catch(() => {}).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setItem = (i, k, v) => setItems((arr) => arr.map((it, idx) => (idx === i ? { ...it, [k]: v } : it)));
  const applyAll = () => setItems((arr) => arr.map((it) => ({ ...it, revenue_target: baseRev !== "" ? baseRev : it.revenue_target, pax_target: basePax !== "" ? basePax : it.pax_target })));
  const save = async () => {
    setSaving(true);
    try {
      const targets = items.map((it) => ({ period: it.period, revenue_target: Number(it.revenue_target || 0), pax_target: Number(it.pax_target || 0) }));
      const res = await api.put("/sales/targets/bulk", { sales_id: row.sales_id, targets });
      toast.success(`Target ${res.data?.count || targets.length} bulan disimpan`); onSaved();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setSaving(false); }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-white max-w-lg max-h-[88vh] overflow-hidden flex flex-col" data-testid="yearly-target-dialog">
        <DialogHeader><DialogTitle className="font-display">Set Target 1 Tahun · {row.sales}</DialogTitle></DialogHeader>
        <div className="rounded-md bg-slate-50 border border-slate-100 p-3 grid grid-cols-[1fr_1fr_auto] gap-2 items-end">
          <div className="space-y-1"><Label className="text-xs">Isi cepat · Revenue</Label><Input type="number" value={baseRev} onChange={(e) => setBaseRev(e.target.value)} placeholder="mis. 2000000000" data-testid="yt-base-revenue" /></div>
          <div className="space-y-1"><Label className="text-xs">Isi cepat · Pax</Label><Input type="number" value={basePax} onChange={(e) => setBasePax(e.target.value)} placeholder="mis. 50" data-testid="yt-base-pax" /></div>
          <Button variant="outline" onClick={applyAll} data-testid="yt-apply-all">Terapkan ke semua</Button>
        </div>
        <div className="flex-1 overflow-y-auto -mx-1 px-1 mt-2 space-y-2">
          {loading ? <div className="p-6 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
            : items.map((it, i) => (
              <div key={it.period} className="grid grid-cols-[130px_1fr_90px] gap-2 items-center" data-testid={`yt-row-${it.period}`}>
                <span className="text-sm text-slate-600 capitalize">{monthLabel(it.period)}</span>
                <Input type="number" value={it.revenue_target} onChange={(e) => setItem(i, "revenue_target", e.target.value)} placeholder="Revenue (Rp)" data-testid={`yt-rev-${it.period}`} />
                <Input type="number" value={it.pax_target} onChange={(e) => setItem(i, "pax_target", e.target.value)} placeholder="Pax" data-testid={`yt-pax-${it.period}`} />
              </div>
            ))}
        </div>
        <DialogFooter className="mt-2"><Button onClick={save} disabled={saving || loading} className="bg-blue-600 hover:bg-blue-700" data-testid="yt-save">{saving ? "Menyimpan..." : "Simpan 12 Bulan"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ActivityBreakdown({ rows, weights }) {
  const w = weights || {};
  const legend = Object.keys(w).map((k) => `${k} ${w[k]}`).join(" · ");
  return (
    <Card className="border-slate-200" data-testid="activity-breakdown">
      <CardHeader className="pb-2"><CardTitle className="font-display text-lg flex items-center gap-2"><Activity className="h-4 w-4 text-blue-600" />Aktivitas per Tipe</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {rows.map((r) => (
          <div key={r.sales_id} className="flex flex-wrap items-center gap-2" data-testid={`breakdown-${r.sales_id}`}>
            <span className="text-sm font-medium text-slate-700 w-40 truncate">{r.sales}</span>
            {Object.entries(r.activity_breakdown).map(([t, n]) => {
              const M = TYPE_META[t]; const Icon = M?.icon || Activity;
              return <Badge key={t} variant="outline" className={M?.cls}><Icon className="h-3 w-3 mr-1" />{t}: {n}</Badge>;
            })}
            <Badge variant="outline" className="bg-slate-900 text-white border-slate-900 ml-auto">Score {r.activity_score}</Badge>
          </div>
        ))}
        <p className="text-xs text-slate-400 pt-1">Activity Score = supporting KPI ({legend}). <b>Bukan pengganti revenue.</b></p>
      </CardContent>
    </Card>
  );
}

function Rankings({ rankings }) {
  return (
    <Card className="border-slate-200" data-testid="rankings-card">
      <CardHeader className="pb-2"><CardTitle className="font-display text-lg flex items-center gap-2"><Trophy className="h-4 w-4 text-amber-500" />Ranking</CardTitle></CardHeader>
      <CardContent>
        <Tabs defaultValue="by_revenue">
          <TabsList>{RANK_TABS.map(([k, l]) => <TabsTrigger key={k} value={k} data-testid={`rank-tab-${k}`}>{l}</TabsTrigger>)}</TabsList>
          {RANK_TABS.map(([k, l, fmt]) => (
            <TabsContent key={k} value={k} className="pt-3">
              <div className="space-y-1" data-testid={`rank-list-${k}`}>
                {(rankings?.[k] || []).map((r, i) => (
                  <div key={r.sales_id} className="flex items-center justify-between px-3 py-2 rounded-md border border-slate-100">
                    <span className="flex items-center gap-3">
                      <span className={`h-6 w-6 rounded-full flex items-center justify-center text-xs font-bold ${i === 0 ? "bg-amber-100 text-amber-700" : i === 1 ? "bg-slate-200 text-slate-700" : i === 2 ? "bg-orange-100 text-orange-700" : "bg-slate-50 text-slate-400"}`}>{i + 1}</span>
                      <span className="text-sm font-medium text-slate-800">{r.sales}</span>
                    </span>
                    <span className="text-sm font-semibold text-slate-900">{fmt(r.value)}</span>
                  </div>
                ))}
              </div>
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  );
}

function ActivityFeed({ feed }) {
  return (
    <Card className="border-slate-200" data-testid="activity-feed">
      <CardHeader className="pb-2"><CardTitle className="font-display text-lg">Aktivitas Terbaru</CardTitle></CardHeader>
      <CardContent>
        {feed === null ? <div className="p-6 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
          : feed.length === 0 ? <p className="text-sm text-slate-400 py-4 text-center" data-testid="feed-empty">Belum ada aktivitas.</p>
          : <div className="divide-y divide-slate-100">
              {feed.map((a) => {
                const M = TYPE_META[a.activity_type]; const Icon = M?.icon || Activity;
                return (
                  <div key={a.id} className="flex items-center gap-3 py-2" data-testid={`feed-item-${a.id}`}>
                    <span className={`h-8 w-8 rounded-md flex items-center justify-center ${M?.cls || "bg-slate-100"}`}><Icon className="h-4 w-4" /></span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-slate-800"><b>{a.activity_type}</b>{a.customer_name ? ` · ${a.customer_name}` : ""}</p>
                      <p className="text-xs text-slate-400 truncate">{a.detail || "—"} · {a.sales}</p>
                    </div>
                    <span className="text-xs text-slate-400 whitespace-nowrap">{(a.timestamp || "").slice(0, 16).replace("T", " ")}</span>
                  </div>
                );
              })}
            </div>}
      </CardContent>
    </Card>
  );
}

function LogActivityDialog({ isAdmin, sales, onSaved }) {
  const [open, setOpen] = useState(false);
  const [customers, setCustomers] = useState([]);
  const [saving, setSaving] = useState(false);
  const [f, setF] = useState({ activity_type: "Call", customer_id: "", notes: "", sales_id: "" });
  useEffect(() => { if (open) api.get("/customers").then((r) => setCustomers(r.data || [])).catch(() => {}); }, [open]);
  const save = async () => {
    setSaving(true);
    try {
      const body = { activity_type: f.activity_type, notes: f.notes };
      if (f.customer_id) body.customer_id = f.customer_id;
      if (isAdmin && f.sales_id) body.sales_id = f.sales_id;
      await api.post("/sales/activities", body);
      toast.success("Aktivitas dicatat"); setOpen(false); setF({ activity_type: "Call", customer_id: "", notes: "", sales_id: "" }); onSaved();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setSaving(false); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button size="sm" className="bg-blue-600 hover:bg-blue-700" data-testid="log-activity-btn"><Plus className="h-4 w-4 mr-1" />Log Activity</Button></DialogTrigger>
      <DialogContent className="bg-white max-w-md" data-testid="log-activity-dialog">
        <DialogHeader><DialogTitle className="font-display">Catat Aktivitas</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div className="space-y-1"><Label className="text-xs">Tipe Aktivitas</Label>
            <Select value={f.activity_type} onValueChange={(v) => setF((o) => ({ ...o, activity_type: v }))}><SelectTrigger data-testid="la-type"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-white">{MANUAL_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent></Select></div>
          {isAdmin && (
            <div className="space-y-1"><Label className="text-xs">Untuk Sales (opsional)</Label>
              <Select value={f.sales_id} onValueChange={(v) => setF((o) => ({ ...o, sales_id: v }))}><SelectTrigger data-testid="la-sales"><SelectValue placeholder="Diri sendiri" /></SelectTrigger>
                <SelectContent className="bg-white">{sales.map((s) => <SelectItem key={s.sales_id} value={s.sales_id}>{s.sales}</SelectItem>)}</SelectContent></Select></div>
          )}
          <div className="space-y-1"><Label className="text-xs">Customer (opsional)</Label>
            <Select value={f.customer_id} onValueChange={(v) => setF((o) => ({ ...o, customer_id: v }))}><SelectTrigger data-testid="la-customer"><SelectValue placeholder="Pilih customer" /></SelectTrigger>
              <SelectContent className="bg-white max-h-64">{customers.map((c) => <SelectItem key={c._id} value={c._id}>{c.full_name}</SelectItem>)}</SelectContent></Select></div>
          <div className="space-y-1"><Label className="text-xs">Catatan</Label><Textarea value={f.notes} onChange={(e) => setF((o) => ({ ...o, notes: e.target.value }))} data-testid="la-notes" /></div>
        </div>
        <DialogFooter><Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="la-save">{saving ? "..." : "Simpan"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
