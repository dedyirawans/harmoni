import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { Navigate } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { Loader2, Zap, RefreshCw, PlugZap } from "lucide-react";

const stColor = (s) => s === "SUCCESS" || s === "CONNECTED" ? "bg-emerald-50 text-emerald-700 border-emerald-200"
  : s === "FAILED" || s === "REJECTED" ? "bg-red-50 text-red-700 border-red-200"
    : s === "RETRY" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-slate-100 text-slate-600 border-slate-200";

export default function N8N() {
  const { user } = useAuth();
  const [d, setD] = useState(null);
  const [testing, setTesting] = useState(false);
  const load = () => api.get("/integrations/n8n/monitor").then((r) => setD(r.data)).catch(() => setD(false));
  useEffect(() => { load(); }, []);
  if (user.role !== "super_admin") return <Navigate to="/dashboard" replace />;

  const testConn = async () => {
    setTesting(true);
    try { const r = await api.post("/integrations/n8n/test"); toast.success(`Connected (${r.data?.response_time_ms ?? "-"} ms)`); }
    catch { toast.error("Connection Failed"); }
    finally { setTesting(false); }
  };

  if (d === null) return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  if (d === false) return <div className="p-8 text-slate-400">Gagal memuat data N8N.</div>;
  const S = d.stats;
  const kpis = [["Messages Today", S.total_today], ["Incoming", S.inbound], ["Outgoing", S.outbound], ["AI Responses", S.ai_responses], ["Human Handover", S.human_handover], ["Orders Today", S.orders_today], ["AUTO SALES Orders", S.auto_sales_orders], ["Failed Requests", S.failed_requests], ["API Errors", S.api_errors]];

  return (
    <div className="space-y-5" data-testid="n8n-page">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-slate-900 flex items-center justify-center"><Zap className="h-6 w-6 text-white" /></div>
          <div><h1 className="font-display text-3xl font-bold text-slate-900">N8N Automation</h1>
            <p className="text-slate-500 mt-0.5">Monitoring komunikasi customer &amp; order AUTO SALES.</p></div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={load} data-testid="n8n-refresh"><RefreshCw className="h-4 w-4 mr-1" />Refresh</Button>
          <Button onClick={testConn} disabled={testing} data-testid="n8n-test-btn"><PlugZap className="h-4 w-4 mr-1" />{testing ? "Testing..." : "Test Connection"}</Button>
        </div>
      </div>

      <Card className="border-slate-200 shadow-sm" data-testid="n8n-connection">
        <CardContent className="p-4 flex flex-wrap items-center gap-3">
          <Badge className={stColor(d.connection.status)}>{d.connection.status}</Badge>
          <span className="text-sm text-slate-500">Base URL: {d.connection.base_url || "—"}</span>
          <span className="text-sm text-slate-400 ml-auto">Last Sync: {(d.connection.last_sync || "—").toString().replace("T", " ").slice(0, 16)}</span>
        </CardContent>
      </Card>

      <Tabs defaultValue="dashboard">
        <TabsList data-testid="n8n-tabs">
          <TabsTrigger value="dashboard" data-testid="tab-n8n-dashboard">Dashboard</TabsTrigger>
          <TabsTrigger value="conversations" data-testid="tab-n8n-conversations">Conversations</TabsTrigger>
          <TabsTrigger value="orders" data-testid="tab-n8n-orders">Orders</TabsTrigger>
          <TabsTrigger value="logs" data-testid="tab-n8n-logs">Sync Logs</TabsTrigger>
        </TabsList>
        <TabsContent value="dashboard">
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3" data-testid="n8n-kpis">
            {kpis.map(([l, v], i) => (
              <Card key={i} className="border-slate-200 shadow-sm"><CardContent className="p-4"><p className="text-xs text-slate-400">{l}</p><p className="text-2xl font-bold text-slate-900 mt-0.5">{v}</p></CardContent></Card>
            ))}
          </div>
        </TabsContent>
        <TabsContent value="conversations">
          <Tbl testid="n8n-conv-table" cols={["Customer", "WhatsApp", "Last Message", "AI", "Status", "Last Activity"]} rows={d.conversations}
            render={(r) => [r.customer_name || "-", r.whatsapp, (r.last_message || "").slice(0, 60), r.ai_status || "-", <Badge className={stColor(r.status)}>{r.status}</Badge>, (r.last_activity || "").toString().replace("T", " ").slice(0, 16)]} />
        </TabsContent>
        <TabsContent value="orders">
          <Tbl testid="n8n-orders-table" cols={["Order ID", "Customer", "Package", "Departure", "Pax", "Date", "Source", "Booking", "Payment"]} rows={d.orders}
            render={(r) => [r.order_id, r.customer, r.package, r.departure || "-", r.pax, r.order_date, <Badge className="bg-slate-900 text-white">{r.source}</Badge>, r.booking_status, r.payment_status]} />
        </TabsContent>
        <TabsContent value="logs">
          <Tbl testid="n8n-logs-table" cols={["Request ID", "Event", "Method", "Direction", "Timestamp", "Status", "Response", "Error"]} rows={d.sync_logs}
            render={(r) => [(r.request_id || "").slice(-8), r.event, r.method, r.direction, (r.timestamp || "").toString().replace("T", " ").slice(0, 16), <Badge className={stColor(r.status)}>{r.status}</Badge>, r.response, (r.error || "").slice(0, 40)]} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Tbl({ cols, rows, render, testid }) {
  return (
    <Card className="border-slate-200 shadow-sm"><CardContent className="p-0"><div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid={testid}>
        <thead><tr className="bg-slate-900 text-white text-left">{cols.map((c) => <th key={c} className="px-3 py-2.5 border-l border-slate-700 first:border-l-0">{c}</th>)}</tr></thead>
        <tbody>
          {(rows || []).length === 0 ? <tr><td colSpan={cols.length} className="px-4 py-8 text-center text-slate-400">Tidak ada data.</td></tr>
            : rows.map((r, i) => <tr key={i} className={i % 2 ? "bg-slate-50" : "bg-white"}>{render(r).map((c, j) => <td key={j} className="px-3 py-2.5 border-l border-slate-100 first:border-l-0">{c}</td>)}</tr>)}
        </tbody>
      </table>
    </div></CardContent></Card>
  );
}
