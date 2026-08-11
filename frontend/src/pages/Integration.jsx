import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { Loader2, Plug, Send, Webhook, MessageCircle, RefreshCw, BellRing } from "lucide-react";

const EVENT_LABELS = {
  "quotation.created": "Quotation dibuat",
  "quotation.sent": "Quotation dikirim",
  "quotation.accepted": "Quotation di-approve",
  "booking.created": "Booking dikonfirmasi",
  "invoice.created": "Invoice diterbitkan",
  "payment.recorded": "Pembayaran diterima",
  "payment.reminder": "Reminder pembayaran (WhatsApp)",
};

const TEMPLATE_KEYS = ["payment.reminder", "booking.created", "payment.recorded"];

export default function Integration() {
  const { user } = useAuth();
  const canManage = (user.permissions || []).includes("settings.manage");

  const [cfg, setCfg] = useState(null);
  const [events, setEvents] = useState([]);
  const [logs, setLogs] = useState([]);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [dispatching, setDispatching] = useState(false);

  const loadLogs = () => api.get("/integrations/n8n/logs").then((r) => setLogs(r.data || [])).catch(() => setLogs([]));

  useEffect(() => {
    api.get("/integrations/n8n").then((r) => {
      const d = r.data || {};
      setCfg({
        webhook_url: d.webhook_url || "",
        enabled: !!d.enabled,
        events: d.events || {},
        whatsapp_templates: d.whatsapp_templates || {},
      });
    }).catch(() => setCfg({ webhook_url: "", enabled: false, events: {}, whatsapp_templates: {} }));
    api.get("/integrations/n8n/events").then((r) => {
      setEvents(r.data?.events || []);
      setCfg((c) => c ? {
        ...c,
        whatsapp_templates: { ...(r.data?.default_templates || {}), ...(c.whatsapp_templates || {}) },
      } : c);
    }).catch(() => {});
    loadLogs();
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/integrations/n8n", cfg);
      toast.success("Konfigurasi n8n tersimpan");
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  const sendTest = async () => {
    setTesting(true);
    try {
      const r = await api.post("/integrations/n8n/test", { event: "test.ping" });
      if (r.data?.ok) toast.success("Test event terkirim ke n8n");
      else toast.error("Test gagal: " + (r.data?.reason || r.data?.error || "cek webhook & status"));
      loadLogs();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setTesting(false); }
  };

  const dispatchReminders = async () => {
    setDispatching(true);
    try {
      const r = await api.post("/payment-reminders/dispatch", {});
      if (!r.data?.n8n_enabled) toast.warning("n8n belum aktif — aktifkan & simpan dulu");
      toast.success(`${r.data?.dispatched || 0}/${r.data?.total || 0} reminder dikirim ke n8n`);
      loadLogs();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setDispatching(false); }
  };

  if (cfg === null)
    return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;

  const toggleEvent = (ev, v) => setCfg({ ...cfg, events: { ...cfg.events, [ev]: v } });
  const setTemplate = (k, v) => setCfg({ ...cfg, whatsapp_templates: { ...cfg.whatsapp_templates, [k]: v } });

  return (
    <div className="space-y-6" data-testid="integration-page">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-blue-600 flex items-center justify-center">
          <Plug className="h-6 w-6 text-white" aria-hidden="true" />
        </div>
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">Integration</h1>
          <p className="text-slate-500 mt-0.5">Automasi n8n & notifikasi WhatsApp (dikirim melalui n8n).</p>
        </div>
      </div>

      {/* Webhook config */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="border-b border-slate-100">
          <CardTitle className="font-display text-lg flex items-center gap-2">
            <Webhook className="h-5 w-5 text-blue-600" /> n8n Webhook
          </CardTitle>
        </CardHeader>
        <CardContent className="p-5 space-y-4">
          <div>
            <Label>Webhook URL</Label>
            <Input className="mt-1" placeholder="https://your-n8n.host/webhook/safar-crm"
              value={cfg.webhook_url} disabled={!canManage}
              onChange={(e) => setCfg({ ...cfg, webhook_url: e.target.value })}
              data-testid="n8n-webhook-url" />
            <p className="text-xs text-slate-400 mt-1">Setiap event dikirim sebagai POST JSON: {"{ event, timestamp, data }"}.</p>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3">
            <div>
              <p className="font-medium text-slate-800">Aktifkan integrasi n8n</p>
              <p className="text-xs text-slate-400">Jika nonaktif, event tidak dikirim (hanya dicatat di log).</p>
            </div>
            <Switch checked={cfg.enabled} disabled={!canManage}
              onCheckedChange={(v) => setCfg({ ...cfg, enabled: v })} data-testid="n8n-enabled-switch" />
          </div>
          <div className="flex flex-wrap gap-3">
            <Button onClick={save} disabled={!canManage || saving} data-testid="n8n-save-btn">
              {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />} Simpan Konfigurasi
            </Button>
            <Button variant="outline" onClick={sendTest} disabled={!canManage || testing} data-testid="n8n-test-btn">
              {testing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Send className="h-4 w-4 mr-2" />} Kirim Test Event
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Event toggles */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="border-b border-slate-100">
          <CardTitle className="font-display text-lg">Event Trigger</CardTitle>
        </CardHeader>
        <CardContent className="p-5 space-y-2">
          {(events.length ? events : Object.keys(EVENT_LABELS)).map((ev) => (
            <div key={ev} className="flex items-center justify-between rounded-lg border border-slate-100 px-4 py-2.5">
              <div>
                <p className="font-medium text-slate-800 text-sm">{EVENT_LABELS[ev] || ev}</p>
                <p className="text-xs text-slate-400 font-mono">{ev}</p>
              </div>
              <Switch checked={cfg.events?.[ev] !== false} disabled={!canManage}
                onCheckedChange={(v) => toggleEvent(ev, v)} data-testid={`event-toggle-${ev}`} />
            </div>
          ))}
        </CardContent>
      </Card>

      {/* WhatsApp templates */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="border-b border-slate-100">
          <CardTitle className="font-display text-lg flex items-center gap-2">
            <MessageCircle className="h-5 w-5 text-emerald-600" /> Template Pesan WhatsApp
          </CardTitle>
        </CardHeader>
        <CardContent className="p-5 space-y-5">
          <p className="text-xs text-slate-500">
            Placeholder tersedia: <code className="text-blue-600">{"{customer_name} {invoice_number} {outstanding} {due_date} {stage} {booking_number} {amount} {invoice_status} {company_name}"}</code>
          </p>
          {TEMPLATE_KEYS.map((k) => (
            <div key={k}>
              <Label className="flex items-center gap-2">{EVENT_LABELS[k] || k}</Label>
              <Textarea rows={4} className="mt-1 font-mono text-sm" disabled={!canManage}
                value={cfg.whatsapp_templates?.[k] || ""}
                onChange={(e) => setTemplate(k, e.target.value)}
                data-testid={`wa-template-${k}`} />
            </div>
          ))}
          <Button onClick={save} disabled={!canManage || saving} variant="outline" data-testid="wa-save-btn">
            {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />} Simpan Template
          </Button>
        </CardContent>
      </Card>

      {/* Reminder dispatch */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="border-b border-slate-100">
          <CardTitle className="font-display text-lg flex items-center gap-2">
            <BellRing className="h-5 w-5 text-amber-500" /> Reminder Pembayaran
          </CardTitle>
        </CardHeader>
        <CardContent className="p-5">
          <p className="text-sm text-slate-500 mb-4">
            Kirim reminder WhatsApp untuk invoice yang jatuh tempo H-30/H-14/H-7/H-3, hari-H, dan overdue ke n8n untuk diteruskan ke jamaah.
          </p>
          <Button onClick={dispatchReminders} disabled={dispatching} className="bg-amber-500 hover:bg-amber-600" data-testid="dispatch-reminders-btn">
            {dispatching ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <BellRing className="h-4 w-4 mr-2" />} Kirim Reminder Sekarang
          </Button>
        </CardContent>
      </Card>

      {/* Delivery logs */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="border-b border-slate-100 flex flex-row items-center justify-between">
          <CardTitle className="font-display text-lg">Log Pengiriman</CardTitle>
          <Button size="sm" variant="ghost" onClick={loadLogs} data-testid="refresh-logs-btn">
            <RefreshCw className="h-4 w-4 mr-1" /> Refresh
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="n8n-logs-table">
              <thead>
                <tr className="bg-blue-600 text-white text-left">
                  <th className="px-4 py-2.5 font-medium">Waktu</th>
                  <th className="px-4 py-2.5 font-medium border-l border-blue-500">Event</th>
                  <th className="px-4 py-2.5 font-medium border-l border-blue-500">Status</th>
                  <th className="px-4 py-2.5 font-medium border-l border-blue-500">Keterangan</th>
                </tr>
              </thead>
              <tbody>
                {logs.length === 0 ? (
                  <tr><td colSpan={4} className="px-4 py-8 text-center text-slate-400">Belum ada log pengiriman.</td></tr>
                ) : logs.map((l, i) => (
                  <tr key={l.id || i} className={i % 2 ? "bg-slate-50" : "bg-white"}>
                    <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap">{(l.created_at || "").replace("T", " ").slice(0, 19)}</td>
                    <td className="px-4 py-2.5 font-mono text-xs border-l border-slate-100">{l.event}</td>
                    <td className="px-4 py-2.5 border-l border-slate-100">
                      {l.ok ? <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200">Terkirim</Badge>
                        : l.skipped ? <Badge className="bg-slate-100 text-slate-500 border-slate-200">Dilewati</Badge>
                          : <Badge className="bg-red-50 text-red-700 border-red-200">Gagal</Badge>}
                    </td>
                    <td className="px-4 py-2.5 text-slate-500 border-l border-slate-100">{l.reason || l.error || (l.status_code ? `HTTP ${l.status_code}` : "-")}</td>
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
