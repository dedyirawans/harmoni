import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { Navigate } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Loader2, Zap, RefreshCw, PlugZap, Send, MessageSquare, RotateCcw } from "lucide-react";

const stColor = (s) => s === "SUCCESS" || s === "CONNECTED" ? "bg-emerald-50 text-emerald-700 border-emerald-200"
  : s === "FAILED" || s === "REJECTED" ? "bg-red-50 text-red-700 border-red-200"
    : s === "RETRY" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-slate-100 text-slate-600 border-slate-200";

const fmt = (t) => (t || "—").toString().replace("T", " ").slice(0, 16);

export default function N8N() {
  const { user } = useAuth();
  const [d, setD] = useState(null);
  const [testing, setTesting] = useState(false);
  const [retrying, setRetrying] = useState(null);
  const load = () => api.get("/integrations/n8n/monitor").then((r) => setD(r.data)).catch(() => setD(false));
  useEffect(() => { load(); }, []);
  if (user.role !== "super_admin") return <Navigate to="/dashboard" replace />;

  const testConn = async () => {
    setTesting(true);
    try { const r = await api.post("/integrations/n8n/test"); toast.success(`Connected (${r.data?.response_time_ms ?? "-"} ms)`); }
    catch { toast.error("Connection Failed"); }
    finally { setTesting(false); }
  };

  const retry = async (id) => {
    setRetrying(id);
    try {
      const r = await api.post(`/integrations/n8n/sync/${id}/retry`);
      if (r.data?.success) toast.success("Retry berhasil (SUCCESS)");
      else toast.error(`Retry gagal (${r.data?.status || "FAILED"})`);
      await load();
    } catch { toast.error("Retry gagal"); }
    finally { setRetrying(null); }
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
          <span className="text-sm text-slate-400 ml-auto">Last Sync: {fmt(d.connection.last_sync)}</span>
        </CardContent>
      </Card>

      <Tabs defaultValue="dashboard">
        <TabsList data-testid="n8n-tabs">
          <TabsTrigger value="dashboard" data-testid="tab-n8n-dashboard">Dashboard</TabsTrigger>
          <TabsTrigger value="inbox" data-testid="tab-n8n-inbox">Inbox</TabsTrigger>
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
        <TabsContent value="inbox">
          <Inbox conversations={d.conversations} onSent={load} />
        </TabsContent>
        <TabsContent value="conversations">
          <Tbl testid="n8n-conv-table" cols={["Customer", "WhatsApp", "Last Message", "AI", "Status", "Last Activity"]} rows={d.conversations}
            render={(r) => [r.customer_name || "-", r.whatsapp, (r.last_message || "").slice(0, 60), r.ai_status || "-", <Badge className={stColor(r.status)}>{r.status}</Badge>, fmt(r.last_activity)]} />
        </TabsContent>
        <TabsContent value="orders">
          <Tbl testid="n8n-orders-table" cols={["Order ID", "Customer", "Package", "Departure", "Pax", "Date", "Source", "Booking", "Payment"]} rows={d.orders}
            render={(r) => [r.order_id, r.customer, r.package, r.departure || "-", r.pax, r.order_date, <Badge className="bg-slate-900 text-white">{r.source}</Badge>, r.booking_status, r.payment_status]} />
        </TabsContent>
        <TabsContent value="logs">
          <Tbl testid="n8n-logs-table" cols={["Request ID", "Event", "Method", "Direction", "Timestamp", "Status", "Response", "Error", "Retry", "Action"]} rows={d.sync_logs}
            render={(r) => [(r.request_id || "").slice(-8), r.event, r.method, r.direction, fmt(r.timestamp), <Badge className={stColor(r.status)}>{r.status}</Badge>, r.response, (r.error || "").slice(0, 40), r.retry_count || 0,
              r.status === "FAILED"
                ? <Button size="sm" variant="outline" disabled={retrying === r.request_id} onClick={() => retry(r.request_id)} data-testid={`n8n-retry-${(r.request_id || "").slice(-8)}`}>
                    {retrying === r.request_id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <><RotateCcw className="h-3.5 w-3.5 mr-1" />Retry</>}
                  </Button>
                : <span className="text-slate-300">—</span>]} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Inbox({ conversations, onSent }) {
  const [active, setActive] = useState(null);
  const [thread, setThread] = useState([]);
  const [loading, setLoading] = useState(false);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);

  const open = async (c) => {
    setActive(c); setReply(""); setLoading(true);
    try {
      const params = c.customer_id ? { customer_id: c.customer_id } : { whatsapp: c.whatsapp };
      const r = await api.get("/integrations/n8n/conversations/thread", { params });
      setThread(r.data || []);
    } catch { setThread([]); toast.error("Gagal memuat percakapan"); }
    finally { setLoading(false); }
  };

  const send = async () => {
    const msg = reply.trim();
    if (!msg || !active) return;
    setSending(true);
    try {
      await api.post("/integrations/n8n/conversations/reply", { customer_id: active.customer_id, whatsapp: active.whatsapp, message: msg });
      toast.success("Balasan terkirim ke N8N");
      setReply("");
      await open(active);
      onSent && onSent();
    } catch { toast.error("Gagal mengirim balasan"); }
    finally { setSending(false); }
  };

  return (
    <Card className="border-slate-200 shadow-sm overflow-hidden" data-testid="n8n-inbox">
      <div className="grid grid-cols-1 md:grid-cols-3 h-[560px]">
        <div className="border-r border-slate-200 overflow-y-auto" data-testid="n8n-inbox-list">
          {(conversations || []).length === 0 ? <div className="p-6 text-sm text-slate-400">Belum ada percakapan.</div>
            : conversations.map((c, i) => (
              <button key={i} onClick={() => open(c)} data-testid={`n8n-inbox-item-${i}`}
                className={`w-full text-left px-4 py-3 border-b border-slate-100 hover:bg-slate-50 transition-colors ${active && (active.customer_id === c.customer_id && active.whatsapp === c.whatsapp) ? "bg-blue-50" : ""}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-slate-800 text-sm truncate">{c.customer_name || c.whatsapp || "Unknown"}</span>
                  {c.status === "REQUIRES_HUMAN" && <Badge className="bg-amber-50 text-amber-700 border-amber-200 text-[10px]">HANDOVER</Badge>}
                </div>
                <p className="text-xs text-slate-500 truncate mt-0.5">{c.last_message || "—"}</p>
                <p className="text-[10px] text-slate-400 mt-0.5">{fmt(c.last_activity)}</p>
              </button>
            ))}
        </div>
        <div className="md:col-span-2 flex flex-col">
          {!active ? (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-400">
              <MessageSquare className="h-10 w-10 mb-2 opacity-40" />
              <p className="text-sm">Pilih percakapan untuk membalas.</p>
            </div>
          ) : (
            <>
              <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
                <p className="font-semibold text-slate-800 text-sm">{active.customer_name || "Unknown"}</p>
                <p className="text-xs text-slate-500">{active.whatsapp || "—"}</p>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50/40" data-testid="n8n-inbox-thread">
                {loading ? <div className="flex justify-center pt-8"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
                  : thread.length === 0 ? <p className="text-sm text-slate-400 text-center pt-8">Tidak ada pesan.</p>
                    : thread.map((m, i) => {
                      const mine = m.direction === "OUTBOUND";
                      return (
                        <div key={i} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                          <div className={`max-w-[75%] rounded-2xl px-3.5 py-2 text-sm ${mine ? "bg-blue-600 text-white rounded-br-sm" : "bg-white border border-slate-200 text-slate-800 rounded-bl-sm"}`}>
                            <p className="whitespace-pre-wrap break-words">{m.message}</p>
                            <p className={`text-[10px] mt-1 ${mine ? "text-blue-100" : "text-slate-400"}`}>{m.sender_type} · {fmt(m.timestamp)}</p>
                          </div>
                        </div>
                      );
                    })}
              </div>
              <div className="p-3 border-t border-slate-200 flex items-end gap-2">
                <Textarea value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Tulis balasan CS…" rows={2}
                  className="resize-none" data-testid="n8n-reply-input"
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
                <Button onClick={send} disabled={sending || !reply.trim()} data-testid="n8n-reply-send">
                  {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </Card>
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
