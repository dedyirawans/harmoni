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
import { Activity, Plus, Loader2, Phone, MessageCircle, Mail, Users, ClipboardList, FileText, CalendarCheck, Trophy } from "lucide-react";
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
  const [month, setMonth] = useState("");
  const [salesId, setSalesId] = useState("all");
  const [perf, setPerf] = useState(null);
  const [feed, setFeed] = useState(null);

  const range = useCallback(() => {
    if (!month) return {};
    const [y, m] = month.split("-").map(Number);
    const last = new Date(y, m, 0).getDate();
    return { frm: `${month}-01`, to: `${month}-${String(last).padStart(2, "0")}` };
  }, [month]);

  const load = useCallback(() => {
    const params = { ...range() };
    if (isAdmin && salesId !== "all") params.sales_id = salesId;
    setPerf(null); setFeed(null);
    api.get("/sales/performance", { params }).then((r) => setPerf(r.data)).catch(() => setPerf({ rows: [], rankings: {} }));
    api.get("/sales/activities", { params: { ...params, limit: 60 } }).then((r) => setFeed(r.data)).catch(() => setFeed([]));
  }, [range, isAdmin, salesId]);
  useEffect(() => { load(); }, [load]);

  const rows = perf?.rows || [];
  const allSales = rows; // for admin selector fallback (populated after first load)

  return (
    <div className="space-y-6" data-testid="sales-activity-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">Sales Activity &amp; Performance</h1>
          <p className="text-slate-500 mt-1">KPI, aktivitas, dan ranking sales. {isAdmin ? "Anda melihat seluruh tim." : "Anda hanya melihat data Anda sendiri."}</p>
        </div>
        <div className="flex items-center gap-2">
          <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-40 h-9" data-testid="period-month" />
          {month && <Button variant="ghost" size="sm" onClick={() => setMonth("")} data-testid="clear-period">All time</Button>}
          <LogActivityDialog isAdmin={isAdmin} sales={allSales} onSaved={load} />
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
