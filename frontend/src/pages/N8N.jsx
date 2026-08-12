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
import { Loader2, Zap, RefreshCw, PlugZap, Send, MessageSquare, RotateCcw, Search, UserCheck } from "lucide-react";

const stColor = (s) => s === "SUCCESS" || s === "CONNECTED" ? "bg-emerald-50 text-emerald-700 border-emerald-200"
  : s === "FAILED" || s === "REJECTED" ? "bg-red-50 text-red-700 border-red-200"
    : s === "RETRY" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-slate-100 text-slate-600 border-slate-200";

const fmt = (t) => (t || "—").toString().replace("T", " ").slice(0, 16);

export default function N8N() {
  const { user } = useAuth();
  const [d, setD] = useState(null);
  const [testing, setTesting] = useState(false);
  const [retrying, setRetrying] = useState(null);
  const [templates, setTemplates] = useState(DEFAULT_TEMPLATES);
  const load = () => api.get("/integrations/n8n/monitor").then((r) => setD(r.data)).catch(() => setD(false));
  useEffect(() => {
    load();
    api.get("/system-settings").then((r) => {
      const t = r.data?.settings?.n8n_reply_templates;
      if (Array.isArray(t) && t.length) setTemplates(t);
    }).catch(() => {});
  }, []);
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
  const kpis = [["Messages Today", S.total_today], ["Incoming", S.inbound], ["Outgoing", S.outbound], ["AI Responses", S.ai_responses], ["Human Handover", S.human_handover], ["SLA Overdue", S.sla_overdue ?? 0], ["Orders Today", S.orders_today], ["AUTO SALES Orders", S.auto_sales_orders], ["Failed Requests", S.failed_requests], ["API Errors", S.api_errors]];
  const unreadTotal = (d.conversations || []).reduce((a, c) => a + (c.unread_count || 0), 0);

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
          <span className="text-sm text-slate-500">Webhook: {d.connection.base_url || "—"}</span>
          <span className="text-sm text-slate-400 ml-auto">Last Sync: {fmt(d.connection.last_sync)}</span>
        </CardContent>
      </Card>

      <Tabs defaultValue="dashboard">
        <TabsList data-testid="n8n-tabs">
          <TabsTrigger value="dashboard" data-testid="tab-n8n-dashboard">Dashboard</TabsTrigger>
          <TabsTrigger value="inbox" data-testid="tab-n8n-inbox">Inbox{unreadTotal > 0 && <span className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-semibold" data-testid="n8n-inbox-unread-total">{unreadTotal}</span>}</TabsTrigger>
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
          <Inbox conversations={d.conversations} refresh={load} templates={templates} me={user} slaMinutes={S.sla_minutes ?? 15} />
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

const DEFAULT_TEMPLATES = [
  { label: "Jam Operasional", text: "Halo, terima kasih sudah menghubungi kami. Jam operasional CS kami Senin–Sabtu pukul 08.00–17.00 WIB. Kami akan segera membantu Anda. 🙏" },
  { label: "Minta Data Jamaah", text: "Untuk proses pendaftaran, mohon kirimkan data jamaah: Nama sesuai paspor, NIK, No. Paspor & masa berlaku, tanggal lahir, dan nomor WhatsApp aktif. Terima kasih." },
  { label: "Cek Ketersediaan", text: "Baik, kami cek ketersediaan seat untuk tanggal keberangkatan yang Anda inginkan terlebih dahulu ya. Mohon ditunggu sebentar." },
  { label: "Info Pembayaran", text: "Untuk melanjutkan pemesanan, silakan lakukan pembayaran DP. Detail rekening & invoice akan kami kirimkan. Ada yang bisa kami bantu lagi?" },
];

function Inbox({ conversations, refresh, templates, me, slaMinutes }) {
  const [active, setActive] = useState(null);
  const [thread, setThread] = useState([]);
  const [loading, setLoading] = useState(false);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [q, setQ] = useState("");
  const [flt, setFlt] = useState("all");

  const humanCount = (conversations || []).filter((c) => c.status === "REQUIRES_HUMAN").length;
  const filtered = (conversations || []).filter((c) => {
    if (flt === "human" && c.status !== "REQUIRES_HUMAN") return false;
    const s = q.trim().toLowerCase();
    if (!s) return true;
    return (c.customer_name || "").toLowerCase().includes(s) || (c.whatsapp || "").toLowerCase().includes(s);
  });
  const senderLabel = (m) => {
    if (m.direction === "INBOUND") return m.customer_name || "Customer";
    if (m.sender_type === "AI") return "AI Bot";
    if (m.sender_type === "SYSTEM") return "AUTO SALES / System";
    if (m.sender_type === "SALES") return m.sender_name ? `${m.sender_name} · Sales/CS` : "Sales/CS";
    return m.sender_name || m.sender_type || "—";
  };

  const open = async (c) => {
    setActive(c); setReply(""); setLoading(true);
    try {
      const params = c.customer_id ? { customer_id: c.customer_id } : { whatsapp: c.whatsapp };
      const r = await api.get("/integrations/n8n/conversations/thread", { params });
      setThread(r.data || []);
      if (c.unread_count) {
        await api.post("/integrations/n8n/conversations/read", { customer_id: c.customer_id, whatsapp: c.whatsapp });
        refresh && refresh();
      }
    } catch { setThread([]); toast.error("Gagal memuat percakapan"); }
    finally { setLoading(false); }
  };

  const send = async (preset) => {
    const msg = (typeof preset === "string" ? preset : reply).trim();
    if (!msg || !active) return;
    if (active.assigned_to_name && me?.name && active.assigned_to_name !== me.name
        && !window.confirm(`Percakapan ini sedang ditangani oleh ${active.assigned_to_name}. Tetap kirim balasan?`)) return;
    setSending(true);
    try {
      await api.post("/integrations/n8n/conversations/reply", { customer_id: active.customer_id, whatsapp: active.whatsapp, message: msg });
      toast.success("Balasan terkirim ke N8N");
      setReply("");
      await open(active);
      refresh && refresh();
    } catch { toast.error("Gagal mengirim balasan"); }
    finally { setSending(false); }
  };

  const assign = async (release) => {
    if (!active) return;
    setAssigning(true);
    try {
      const r = await api.post("/integrations/n8n/conversations/assign", { customer_id: active.customer_id, whatsapp: active.whatsapp, release });
      setActive({ ...active, assigned_to_name: r.data.assigned_to_name, assigned_to_id: r.data.assigned_to_id });
      toast.success(release ? "Percakapan dilepas" : "Anda menangani percakapan ini");
      refresh && refresh();
    } catch { toast.error("Gagal memperbarui penanganan"); }
    finally { setAssigning(false); }
  };

  return (
    <Card className="border-slate-200 shadow-sm overflow-hidden" data-testid="n8n-inbox">
      <div className="grid grid-cols-1 md:grid-cols-3 h-[560px]">
        <div className="border-r border-slate-200 flex flex-col">
          <div className="p-2.5 border-b border-slate-100">
            <div className="relative">
              <Search className="h-4 w-4 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari nama / nomor…"
                className="w-full pl-8 pr-3 py-2 text-sm rounded-md border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300"
                data-testid="n8n-inbox-search" />
            </div>
            <div className="flex gap-1.5 mt-2">
              <button onClick={() => setFlt("all")} data-testid="n8n-filter-all"
                className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${flt === "all" ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"}`}>Semua</button>
              <button onClick={() => setFlt("human")} data-testid="n8n-filter-human"
                className={`text-xs px-2.5 py-1 rounded-full border flex items-center gap-1 transition-colors ${flt === "human" ? "bg-amber-500 text-white border-amber-500" : "bg-white text-amber-700 border-amber-200 hover:bg-amber-50"}`}>
                Perlu CS{humanCount > 0 && <span className="inline-flex items-center justify-center min-w-[16px] h-[16px] px-1 rounded-full bg-red-500 text-white text-[9px] font-semibold">{humanCount}</span>}
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto" data-testid="n8n-inbox-list">
            {filtered.length === 0 ? <div className="p-6 text-sm text-slate-400">Belum ada percakapan.</div>
              : filtered.map((c, i) => {
                const unread = (c.unread_count || 0) > 0;
                const sel = active && active.customer_id === c.customer_id && active.whatsapp === c.whatsapp;
                return (
                  <button key={i} onClick={() => open(c)} data-testid={`n8n-inbox-item-${i}`}
                    className={`w-full text-left px-4 py-3 border-b border-slate-100 hover:bg-slate-50 transition-colors ${sel ? "bg-blue-50" : unread ? "bg-blue-50/40" : ""}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className={`text-sm truncate flex items-center gap-1.5 ${unread ? "font-bold text-slate-900" : "font-medium text-slate-800"}`}>
                        {unread && <span className="h-2 w-2 rounded-full bg-blue-500 shrink-0" />}
                        {c.customer_name || c.whatsapp || "Unknown"}
                      </span>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {c.sla_overdue && <Badge className="bg-red-100 text-red-700 border-red-200 text-[10px]" data-testid={`n8n-sla-badge-${i}`}>SLA {c.waiting_minutes}m</Badge>}
                        {c.status === "REQUIRES_HUMAN" && <Badge className="bg-amber-50 text-amber-700 border-amber-200 text-[10px]">HANDOVER</Badge>}
                        {unread && <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] font-semibold" data-testid={`n8n-inbox-unread-${i}`}>{c.unread_count}</span>}
                      </div>
                    </div>
                    <p className={`text-xs truncate mt-0.5 ${unread ? "text-slate-700 font-medium" : "text-slate-500"}`}>{c.last_message || "—"}</p>
                    <div className="flex items-center justify-between mt-0.5">
                      <p className="text-[10px] text-slate-400">{fmt(c.last_activity)}</p>
                      {c.assigned_to_name && <span className="text-[10px] text-emerald-600 font-medium truncate max-w-[120px]" data-testid={`n8n-assigned-${i}`}>● {c.assigned_to_name}</span>}
                    </div>
                  </button>
                );
              })}
          </div>
        </div>
        <div className="md:col-span-2 flex flex-col">
          {!active ? (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-400">
              <MessageSquare className="h-10 w-10 mb-2 opacity-40" />
              <p className="text-sm">Pilih percakapan untuk membalas.</p>
            </div>
          ) : (
            <>
              <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-semibold text-slate-800 text-sm truncate">{active.customer_name || "Unknown"}</p>
                  <p className="text-xs text-slate-500">{active.whatsapp || "—"}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {active.assigned_to_name ? (
                    <>
                      <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[11px]" data-testid="n8n-assignee-badge">Ditangani: {active.assigned_to_name}</Badge>
                      <Button size="sm" variant="outline" disabled={assigning} onClick={() => assign(true)} data-testid="n8n-release-btn">
                        {assigning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Lepas"}
                      </Button>
                    </>
                  ) : (
                    <Button size="sm" disabled={assigning} onClick={() => assign(false)} data-testid="n8n-assign-btn">
                      {assigning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <><UserCheck className="h-3.5 w-3.5 mr-1" />Tangani</>}
                    </Button>
                  )}
                </div>
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
                            <p className={`text-[10px] mt-1 ${mine ? "text-blue-100" : "text-slate-400"}`}>{senderLabel(m)} · {fmt(m.timestamp)}</p>
                          </div>
                        </div>
                      );
                    })}
              </div>
              <div className="px-3 pt-2.5 border-t border-slate-200 flex flex-wrap gap-1.5" data-testid="n8n-quick-replies">
                {(templates || []).filter((t) => t.label && t.text).map((t, i) => (
                  <button key={i} onClick={() => send(t.text)} disabled={sending} data-testid={`n8n-template-${i}`}
                    className="text-xs px-2.5 py-1 rounded-full border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 disabled:opacity-50 transition-colors">
                    {t.label}
                  </button>
                ))}
              </div>
              <div className="p-3 flex items-end gap-2">
                <Textarea value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Tulis balasan CS…" rows={2}
                  className="resize-none" data-testid="n8n-reply-input"
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
                <Button onClick={() => send()} disabled={sending || !reply.trim()} data-testid="n8n-reply-send">
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
