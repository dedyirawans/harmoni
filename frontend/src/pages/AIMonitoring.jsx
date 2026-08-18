import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { Navigate } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { Gauge, ListChecks, AlertTriangle, Lightbulb, Loader2, RefreshCw, ThumbsUp, ThumbsDown, XCircle, BookX, FilePlus } from "lucide-react";

const err = (e) => toast.error(formatApiErrorDetail(e?.response?.data?.detail) || "Terjadi kesalahan");
const fmt = (t) => (t || "—").toString().replace("T", " ").slice(0, 19);
const flagColor = (f) => f === "GOOD" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : f === "INCORRECT" ? "bg-red-50 text-red-700 border-red-200" : f === "OUTDATED_KNOWLEDGE" ? "bg-orange-50 text-orange-700 border-orange-200" : f === "NEEDS_IMPROVEMENT" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-slate-100 text-slate-500";

function DashboardTab() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/ai/monitoring/dashboard").then((r) => setD(r.data)).catch(() => setD({})); }, []);
  if (!d) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  const c = d.counts || {}, p = d.performance || {};
  const cards = [["Total Conversations", c.total_conversations], ["AI Handled", c.ai_handled], ["Human Handover", c.human_handover], ["New Customers", c.new_customers], ["New Leads", c.new_leads], ["Orders", c.orders], ["Bookings", c.bookings], ["AUTO SALES", c.auto_sales], ["AI → SALES", c.ai_to_sales], ["Failed Responses", c.failed_responses]];
  const perf = [["AI Resolution Rate", p.ai_resolution_rate], ["Human Handover Rate", p.human_handover_rate], ["Lead Creation Rate", p.lead_creation_rate], ["Order Creation Rate", p.order_creation_rate], ["Booking Conversion", p.booking_conversion], ["Response Failure Rate", p.response_failure_rate]];
  return (
    <div className="space-y-5" data-testid="mon-dashboard-tab">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {cards.map(([k, v]) => (
          <Card key={k} data-testid={`mon-stat-${k}`}><CardContent className="p-4"><div className="text-2xl font-bold text-slate-800">{v ?? 0}</div><div className="text-xs text-slate-500 mt-1">{k}</div></CardContent></Card>
        ))}
      </div>
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-2">AI Performance</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {perf.map(([k, v]) => (
            <Card key={k}><CardContent className="p-4"><div className="text-xl font-bold text-indigo-600">{v ?? 0}%</div><div className="text-xs text-slate-500 mt-1">{k}</div></CardContent></Card>
          ))}
        </div>
      </div>
    </div>
  );
}

function QualityTab() {
  const [rows, setRows] = useState(null);
  const load = useCallback(() => api.get("/ai/monitoring/quality").then((r) => setRows(r.data)).catch(() => setRows([])), []);
  useEffect(() => { load(); }, [load]);
  const flag = async (m, f) => {
    try { await api.post("/ai/monitoring/flag", { message_id: m.message_id, conversation_id: m.conversation_id, flag: f, content: m.content }); toast.success(`Ditandai ${f}`); load(); }
    catch (e) { err(e); }
  };
  if (rows === null) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  return (
    <div className="space-y-3" data-testid="mon-quality-tab">
      <p className="text-sm text-slate-500">Tinjau respons AI & tandai kualitasnya. Perbaikan knowledge tetap manual via Super Admin.</p>
      {rows.length === 0 ? <p className="text-slate-400 text-center py-8">Belum ada respons AI.</p>
        : rows.map((m) => (
          <Card key={m.id} data-testid={`mon-quality-${m.id}`}><CardContent className="p-4 space-y-2">
            <div className="flex items-center justify-between"><span className="text-sm font-medium text-slate-700">{m.customer_name || "—"}</span>
              <span className="text-xs text-slate-400">{fmt(m.created_at)} {m.quality_flag && <Badge variant="outline" className={`ml-1 ${flagColor(m.quality_flag)}`}>{m.quality_flag}</Badge>}</span></div>
            <div className="text-sm text-slate-800 bg-blue-50 rounded-lg px-3 py-2 whitespace-pre-wrap">{m.content}</div>
            <div className="flex flex-wrap gap-1">
              <Button size="sm" variant="outline" onClick={() => flag(m, "GOOD")} data-testid={`mon-flag-good-${m.id}`}><ThumbsUp className="h-3.5 w-3.5 mr-1" />Good</Button>
              <Button size="sm" variant="outline" onClick={() => flag(m, "NEEDS_IMPROVEMENT")}><ThumbsDown className="h-3.5 w-3.5 mr-1" />Needs Improvement</Button>
              <Button size="sm" variant="outline" onClick={() => flag(m, "INCORRECT")}><XCircle className="h-3.5 w-3.5 mr-1" />Incorrect</Button>
              <Button size="sm" variant="outline" onClick={() => flag(m, "OUTDATED_KNOWLEDGE")}><BookX className="h-3.5 w-3.5 mr-1" />Outdated</Button>
            </div>
          </CardContent></Card>
        ))}
    </div>
  );
}

function ErrorsTab() {
  const [d, setD] = useState(null);
  const load = useCallback(() => api.get("/ai/monitoring/errors").then((r) => setD(r.data)).catch(() => setD({})), []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  const sect = (title, rows, cols) => (
    <Card><CardContent className="p-0"><div className="px-4 py-2 font-medium text-slate-700 border-b">{title}</div>
      <Table><TableHeader><TableRow>{cols.map((c) => <TableHead key={c}>{c}</TableHead>)}</TableRow></TableHeader>
        <TableBody>{(rows || []).length === 0 ? <TableRow><TableCell colSpan={cols.length} className="text-center py-4 text-slate-400">Tidak ada.</TableCell></TableRow>
          : rows.map((r, i) => <TableRow key={i}>{Object.values(r).map((v, j) => <TableCell key={j} className="text-xs">{fmt(v).length === 19 ? fmt(v) : String(v ?? "—").slice(0, 80)}</TableCell>)}</TableRow>)}
        </TableBody></Table></CardContent></Card>
  );
  return (
    <div className="space-y-4" data-testid="mon-errors-tab">
      <div className="flex justify-end"><Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4 mr-1" />Muat Ulang</Button></div>
      {sect("AI / Customer Handover Errors", d.ai_errors, ["Kind", "Ref", "Error", "Waktu"])}
      {sect("Tool Errors", d.tool_errors, ["Tool", "Error", "Waktu"])}
      {sect("API Errors", d.api_errors, ["Endpoint", "Kategori", "Waktu"])}
    </div>
  );
}

function GapsTab() {
  const [d, setD] = useState(null);
  const load = useCallback(() => api.get("/ai/monitoring/gaps").then((r) => setD(r.data)).catch(() => setD({})), []);
  useEffect(() => { load(); }, [load]);
  const toFaq = async (f) => {
    const q = window.prompt("Pertanyaan untuk FAQ:", f.content || "");
    if (!q) return;
    const a = window.prompt("Jawaban:", "");
    try { await api.post("/ai/monitoring/to-faq", { question: q, answer: a || "" }); toast.success("FAQ dibuat"); } catch (e) { err(e); }
  };
  if (!d) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  return (
    <div className="grid md:grid-cols-2 gap-4" data-testid="mon-gaps-tab">
      <Card><CardContent className="p-4"><h3 className="font-medium text-slate-700 mb-2">Top Handover Reasons</h3>
        {(d.top_handover_reasons || []).length === 0 ? <p className="text-slate-400 text-sm">—</p> : d.top_handover_reasons.map((r, i) => <div key={i} className="flex justify-between text-sm py-1 border-b last:border-0"><span className="truncate pr-2">{r.reason}</span><Badge variant="outline">{r.count}</Badge></div>)}
      </CardContent></Card>
      <Card><CardContent className="p-4"><h3 className="font-medium text-slate-700 mb-2">Top Packages (WhatsApp AI)</h3>
        {(d.top_packages || []).length === 0 ? <p className="text-slate-400 text-sm">—</p> : d.top_packages.map((r, i) => <div key={i} className="flex justify-between text-sm py-1 border-b last:border-0"><span className="truncate pr-2">{r.package}</span><Badge variant="outline">{r.count}</Badge></div>)}
      </CardContent></Card>
      <Card className="md:col-span-2"><CardContent className="p-4"><h3 className="font-medium text-slate-700 mb-2">Flagged Responses → Jadikan FAQ / Knowledge</h3>
        {(d.flagged_responses || []).length === 0 ? <p className="text-slate-400 text-sm">Belum ada respons yang ditandai perlu perbaikan.</p>
          : d.flagged_responses.map((f) => (
            <div key={f.id} className="flex items-center justify-between gap-2 py-2 border-b last:border-0" data-testid={`mon-gap-${f.id}`}>
              <div className="min-w-0"><Badge variant="outline" className={flagColor(f.flag)}>{f.flag}</Badge> <span className="text-sm text-slate-700">{(f.content || "").slice(0, 100)}</span></div>
              <Button size="sm" variant="outline" onClick={() => toFaq(f)} data-testid={`mon-tofaq-${f.id}`}><FilePlus className="h-3.5 w-3.5 mr-1" />FAQ</Button>
            </div>
          ))}
      </CardContent></Card>
    </div>
  );
}

export default function AIMonitoring() {
  const { user } = useAuth();
  const [tab, setTab] = useState("dashboard");
  if (user?.role !== "super_admin") return <Navigate to="/dashboard" replace />;
  return (
    <div className="space-y-5" data-testid="ai-monitoring-page">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-cyan-500/10 flex items-center justify-center"><Gauge className="h-6 w-6 text-cyan-600" /></div>
        <div><h1 className="text-2xl font-bold text-slate-800">AI Monitoring & Quality</h1>
          <p className="text-sm text-slate-500">Pantau kinerja AI, tinjau kualitas respons, dan temukan celah pengetahuan.</p></div>
      </div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList data-testid="mon-tabs-list">
          <TabsTrigger value="dashboard" data-testid="mon-tab-dashboard"><Gauge className="h-4 w-4 mr-1.5" />Dashboard</TabsTrigger>
          <TabsTrigger value="quality" data-testid="mon-tab-quality"><ListChecks className="h-4 w-4 mr-1.5" />Response Quality</TabsTrigger>
          <TabsTrigger value="errors" data-testid="mon-tab-errors"><AlertTriangle className="h-4 w-4 mr-1.5" />Error Log</TabsTrigger>
          <TabsTrigger value="gaps" data-testid="mon-tab-gaps"><Lightbulb className="h-4 w-4 mr-1.5" />Knowledge Gaps</TabsTrigger>
        </TabsList>
        <div className="mt-4">
          <TabsContent value="dashboard"><DashboardTab /></TabsContent>
          <TabsContent value="quality"><QualityTab /></TabsContent>
          <TabsContent value="errors"><ErrorsTab /></TabsContent>
          <TabsContent value="gaps"><GapsTab /></TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
