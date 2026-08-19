import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { Navigate } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { MessageSquareHeart, Save, Loader2, RefreshCw, Play, Sparkles, Gauge, ListChecks, Users2, Settings2, Ban, Pause, PlayCircle } from "lucide-react";
import { ResponsiveContainer, ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";

const fmt = (t) => (t || "—").toString().replace("T", " ").slice(0, 16);
const err = (e) => toast.error(formatApiErrorDetail(e?.response?.data?.detail) || "Terjadi kesalahan");
const statusTone = (s) => ({
  ACTIVE: "bg-emerald-50 text-emerald-700 border-emerald-200", PAUSED: "bg-amber-50 text-amber-700 border-amber-200",
  STOPPED: "bg-slate-100 text-slate-600", COMPLETED: "bg-blue-50 text-blue-700 border-blue-200",
  CONVERTED: "bg-indigo-50 text-indigo-700 border-indigo-200", HANDOVER: "bg-red-50 text-red-700 border-red-200",
  "OPTED OUT": "bg-red-50 text-red-700 border-red-200",
}[s] || "bg-slate-100 text-slate-600");
const queueTone = (s) => ({
  SCHEDULED: "bg-amber-50 text-amber-700 border-amber-200", READY: "bg-blue-50 text-blue-700 border-blue-200",
  PROCESSING: "bg-indigo-50 text-indigo-700 border-indigo-200", SENT: "bg-emerald-50 text-emerald-700 border-emerald-200",
  CANCELLED: "bg-slate-100 text-slate-600", FAILED: "bg-red-50 text-red-700 border-red-200",
}[s] || "bg-slate-100 text-slate-600");

// ---------------- Analytics ----------------
function AnalyticsTab() {
  const [a, setA] = useState(null);
  const load = useCallback(() => api.get("/ai/followup/analytics").then((r) => setA(r.data)).catch(() => setA({})), []);
  useEffect(() => { load(); }, [load]);
  if (!a) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  const cards = [
    ["Total Leads", a.total_leads, "text-slate-700"], ["Active Follow-Up", a.active_followup, "text-emerald-600"],
    ["Follow-Up Sent", a.followup_sent, "text-blue-600"], ["Scheduled", a.followup_scheduled, "text-amber-600"],
    ["Response", a.followup_response, "text-indigo-600"], ["Converted", a.followup_converted, "text-indigo-700"],
    ["Booking", a.followup_booking, "text-emerald-700"], ["Revenue", `Rp${Number(a.followup_revenue || 0).toLocaleString("id-ID")}`, "text-emerald-700"],
    ["Stopped", a.stopped_followup, "text-slate-600"], ["Opt-Out", a.opt_out, "text-red-600"], ["Handover", a.human_handover, "text-red-600"],
  ];
  return (
    <div className="space-y-4" data-testid="afu-analytics-tab">
      <div className="flex justify-end"><Button size="sm" variant="outline" onClick={load} data-testid="afu-analytics-refresh"><RefreshCw className="h-3.5 w-3.5 mr-1" />Muat ulang</Button></div>
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        {cards.map(([l, v, cls]) => (
          <div key={l} className="rounded-lg border border-slate-100 bg-slate-50/60 p-3" data-testid={`afu-metric-${l}`}>
            <div className={`text-lg font-bold ${cls}`}>{v ?? 0}</div><div className="text-[11px] text-slate-500">{l}</div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[["Response Rate", a.response_rate], ["Conversion Rate", a.conversion_rate], ["Booking Rate", a.booking_rate]].map(([l, v]) => (
          <Card key={l}><CardContent className="p-4"><div className="text-2xl font-bold text-blue-600">{v ?? 0}%</div><div className="text-xs text-slate-500">{l}</div></CardContent></Card>
        ))}
      </div>
      <Card data-testid="afu-weekly-chart">
        <CardContent className="p-4">
          <div className="text-sm font-semibold text-slate-700 mb-3">Tren Mingguan — Follow-Up, Response & Konversi</div>
          {(!a.weekly || a.weekly.length === 0) ? (
            <div className="h-[260px] flex items-center justify-center text-sm text-slate-400">Belum ada data follow-up terkirim untuk ditampilkan.</div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <ComposedChart data={a.weekly} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                <YAxis yAxisId="left" tick={{ fontSize: 11 }} allowDecimals={false} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} unit="%" domain={[0, 100]} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar yAxisId="left" dataKey="sent" name="Terkirim" fill="#93c5fd" radius={[4, 4, 0, 0]} />
                <Bar yAxisId="left" dataKey="booking" name="Booking" fill="#6ee7b7" radius={[4, 4, 0, 0]} />
                <Line yAxisId="right" type="monotone" dataKey="response_rate" name="Response %" stroke="#6366f1" strokeWidth={2} dot={{ r: 3 }} />
                <Line yAxisId="right" type="monotone" dataKey="conversion_rate" name="Konversi %" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------- Settings ----------------
function SettingsTab() {
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);
  const upd = (k, v) => setS((p) => ({ ...p, [k]: v }));
  useEffect(() => { api.get("/ai/followup/settings").then((r) => setS(r.data)).catch(() => { setS({}); toast.error("Gagal memuat setting"); }); }, []);
  const setRule = (i, v) => { const sc = [...(s.schedule || [])]; sc[i] = { ...sc[i], delay_hours: Number(v) }; upd("schedule", sc); };
  const save = async () => {
    setBusy(true);
    try { const r = await api.put("/ai/followup/settings", s); setS(r.data); toast.success("Setting disimpan"); }
    catch (e) { err(e); } finally { setBusy(false); }
  };
  if (!s) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  return (
    <div className="space-y-4 max-w-3xl" data-testid="afu-settings-tab">
      <div className="p-3 rounded-lg bg-amber-50 border border-amber-100 text-sm text-amber-800">
        Auto Follow-Up hanya untuk lead dengan dasar interaksi (anti-spam). Hormati opt-out, consent & aturan WhatsApp.
      </div>
      <Card><CardContent className="p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div><div className="font-semibold text-slate-700">Enable Auto Follow-Up</div><div className="text-xs text-slate-400">Master switch. Saat OFF, sistem tetap menjadwalkan & preview (dry-run) tapi tidak mengirim.</div></div>
          <Switch checked={!!s.enabled} onCheckedChange={(v) => upd("enabled", v)} data-testid="afu-enabled" />
        </div>
      </CardContent></Card>
      <Card><CardContent className="p-5 space-y-3">
        <div className="font-semibold text-slate-700">Limit & Frekuensi</div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div><Label>Maksimum Follow-Up</Label><Input type="number" value={s.max_followup ?? ""} onChange={(e) => upd("max_followup", Number(e.target.value))} data-testid="afu-max" /></div>
          <div><Label>Min. Interval (jam)</Label><Input type="number" value={s.min_interval_hours ?? ""} onChange={(e) => upd("min_interval_hours", Number(e.target.value))} data-testid="afu-min-interval" /></div>
          <div><Label>Daily Limit / Customer</Label><Input type="number" value={s.daily_limit_per_customer ?? ""} onChange={(e) => upd("daily_limit_per_customer", Number(e.target.value))} data-testid="afu-daily" /></div>
          <div className="flex items-end"><div className="flex items-center gap-2"><Switch checked={!!s.handover_on_booking_intent} onCheckedChange={(v) => upd("handover_on_booking_intent", v)} data-testid="afu-handover-intent" /><span className="text-xs text-slate-500">Handover bila high intent</span></div></div>
        </div>
      </CardContent></Card>
      <Card><CardContent className="p-5 space-y-3">
        <div className="font-semibold text-slate-700">Follow-Up Rules (delay tanpa respons)</div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {(s.schedule || []).map((r, i) => (
            <div key={i} data-testid={`afu-rule-${r.number}`}><Label>Follow-Up {r.number} — delay (jam)</Label>
              <Input type="number" value={r.delay_hours} onChange={(e) => setRule(i, e.target.value)} data-testid={`afu-rule-input-${r.number}`} /></div>
          ))}
        </div>
        <div className="text-[11px] text-slate-400">Contoh default: 24 / 72 / 168 jam (1 / 3 / 7 hari). Setelah maksimum → status FOLLOW-UP COMPLETED.</div>
      </CardContent></Card>
      <Card><CardContent className="p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="font-semibold text-slate-700">Business Hours Follow-Up (UTC)</div>
          <Switch checked={!!s.business_hours_enabled} onCheckedChange={(v) => upd("business_hours_enabled", v)} data-testid="afu-bh-enabled" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div><Label>Jam buka</Label><Input type="time" value={s.opening_time || ""} onChange={(e) => upd("opening_time", e.target.value)} data-testid="afu-open" /></div>
          <div><Label>Jam tutup</Label><Input type="time" value={s.closing_time || ""} onChange={(e) => upd("closing_time", e.target.value)} data-testid="afu-close" /></div>
        </div>
      </CardContent></Card>
      <Card><CardContent className="p-5 space-y-3">
        <div className="font-semibold text-slate-700">Trigger Lanjutan & Opt-Out</div>
        <div className="flex items-center justify-between"><div><div className="text-sm font-medium text-slate-700">Quotation Follow-Up</div><div className="text-xs text-slate-400">Follow-up berbasis quotation aktif / expiry</div></div><Switch checked={!!s.quotation_followup_enabled} onCheckedChange={(v) => upd("quotation_followup_enabled", v)} data-testid="afu-quotation-enabled" /></div>
        <div className="flex items-center justify-between gap-3"><div><div className="text-sm font-medium text-slate-700">Departure Nudge</div><div className="text-xs text-slate-400">Ingatkan bila keberangkatan dekat (hari)</div></div><div className="flex items-center gap-2"><Input type="number" className="w-20" value={s.departure_nudge_days ?? ""} onChange={(e) => upd("departure_nudge_days", Number(e.target.value))} data-testid="afu-departure-days" /><Switch checked={!!s.departure_nudge_enabled} onCheckedChange={(v) => upd("departure_nudge_enabled", v)} data-testid="afu-departure-enabled" /></div></div>
        <div className="flex items-center justify-between gap-3"><div><div className="text-sm font-medium text-slate-700">Payment Follow-Up</div><div className="text-xs text-slate-400">Reminder pembayaran booking belum lunas (maks kirim)</div></div><div className="flex items-center gap-2"><Input type="number" className="w-20" value={s.payment_followup_max ?? ""} onChange={(e) => upd("payment_followup_max", Number(e.target.value))} data-testid="afu-payment-max" /><Switch checked={!!s.payment_followup_enabled} onCheckedChange={(v) => upd("payment_followup_enabled", v)} data-testid="afu-payment-enabled" /></div></div>
        <div className="text-[11px] text-slate-400">Opt-out & consent SELALU dihormati. High purchase intent → Sales Handover otomatis (lihat toggle "Handover bila high intent").</div>
      </CardContent></Card>
      <Card><CardContent className="p-5 space-y-3">
        <div className="font-semibold text-slate-700">Follow-Up Templates — Panduan Gaya per Intent</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {["PACKAGE_INQUIRY", "PRICE_INQUIRY", "AVAILABILITY_INQUIRY", "DOCUMENT_INQUIRY", "BOOKING_INTENT", "PAYMENT_PENDING", "QUOTATION_PENDING", "GENERAL_INTEREST"].map((it) => (
            <div key={it}><Label className="text-xs">{it}</Label>
              <Textarea rows={2} value={(s.intent_guidance || {})[it] || ""} onChange={(e) => upd("intent_guidance", { ...(s.intent_guidance || {}), [it]: e.target.value })} placeholder="Panduan gaya (opsional) — AI tetap pakai data CRM" data-testid={`afu-guidance-${it}`} /></div>
          ))}
        </div>
      </CardContent></Card>
      <ABCard s={s} upd={upd} />
      <div className="flex justify-end"><Button onClick={save} disabled={busy} data-testid="afu-save">{busy ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}Simpan Setting</Button></div>
    </div>
  );
}

// ---------------- Queue ----------------
function QueueTab() {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api.get("/ai/followup/queue").then((r) => setD(r.data)).catch(() => setD({ items: [], counts: {} })), []);
  useEffect(() => { load(); }, [load]);
  const runNow = async () => {
    setBusy(true);
    try { const r = await api.post("/ai/followup/run", { dry_run: true }); toast.success(`Scan selesai: ${r.data.scheduled.scheduled} dijadwalkan, ${r.data.scheduled.cancelled} dibatalkan`); load(); }
    catch (e) { err(e); } finally { setBusy(false); }
  };
  const cancel = async (id) => { try { await api.post(`/ai/followup/queue/${id}/cancel`); toast.success("Dibatalkan"); load(); } catch (e) { err(e); } };
  if (!d) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  return (
    <div className="space-y-3" data-testid="afu-queue-tab">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex flex-wrap gap-2">{Object.entries(d.counts || {}).map(([k, v]) => <Badge key={k} variant="outline" className={queueTone(k)} data-testid={`afu-qcount-${k}`}>{k}: {v}</Badge>)}</div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-3.5 w-3.5 mr-1" />Muat ulang</Button>
          <Button size="sm" onClick={runNow} disabled={busy} data-testid="afu-run-now">{busy ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : <Play className="h-3.5 w-3.5 mr-1" />}Jalankan Scan (dry-run)</Button>
        </div>
      </div>
      <Card><CardContent className="p-0">
        <Table><TableHeader><TableRow>
          <TableHead>Customer</TableHead><TableHead>FU#</TableHead><TableHead>Intent</TableHead><TableHead>Reason</TableHead>
          <TableHead>Pesan</TableHead><TableHead>Status</TableHead><TableHead>Jadwal</TableHead><TableHead></TableHead>
        </TableRow></TableHeader><TableBody>
          {(d.items || []).length === 0 ? <TableRow><TableCell colSpan={8} className="text-center text-slate-400 py-8">Belum ada item antrean follow-up</TableCell></TableRow>
            : d.items.map((i) => (
              <TableRow key={i.id} data-testid={`afu-qrow-${i.id}`}>
                <TableCell className="font-medium">{i.customer_name || i.wa_number}</TableCell>
                <TableCell>{i.followup_number}</TableCell>
                <TableCell><Badge variant="outline" className="text-[10px]">{i.intent}</Badge></TableCell>
                <TableCell className="text-xs text-slate-500 max-w-[160px]">{i.reason}{i.dry_run && <span className="ml-1 text-amber-600">(dry-run)</span>}</TableCell>
                <TableCell className="text-xs text-slate-600 max-w-[280px] truncate" title={i.message}>{i.message}</TableCell>
                <TableCell><Badge variant="outline" className={queueTone(i.status)}>{i.status}</Badge></TableCell>
                <TableCell className="text-xs text-slate-400">{fmt(i.sent_at || i.scheduled_at)}</TableCell>
                <TableCell>{["SCHEDULED", "READY"].includes(i.status) && <Button size="sm" variant="ghost" onClick={() => cancel(i.id)} data-testid={`afu-cancel-${i.id}`}><Ban className="h-3.5 w-3.5" /></Button>}</TableCell>
              </TableRow>
            ))}
        </TableBody></Table>
      </CardContent></Card>
    </div>
  );
}

// ---------------- Leads + Preview ----------------
function LeadsTab() {
  const [rows, setRows] = useState(null);
  const [preview, setPreview] = useState(null);
  const [pbusy, setPbusy] = useState("");
  const load = useCallback(() => api.get("/ai/followup/leads").then((r) => setRows(r.data)).catch(() => setRows([])), []);
  useEffect(() => { load(); }, [load]);
  const setStatus = async (id, status) => { try { await api.post(`/ai/followup/leads/${id}/status`, { status }); toast.success(`Status: ${status}`); load(); } catch (e) { err(e); } };
  const doPreview = async (id) => {
    setPbusy(id); setPreview(null);
    try { const r = await api.post("/ai/followup/preview", { lead_id: id }); setPreview(r.data); if (!r.data.ok && r.data.note) toast.info(r.data.note); }
    catch (e) { err(e); } finally { setPbusy(""); }
  };
  if (!rows) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  return (
    <div className="space-y-3" data-testid="afu-leads-tab">
      {preview && (
        <Card className="border-blue-200"><CardContent className="p-4 space-y-2" data-testid="afu-preview-panel">
          <div className="flex items-center gap-2 text-sm font-semibold text-blue-700"><Sparkles className="h-4 w-4" />Preview Follow-Up — {preview.customer_name} (FU#{preview.followup_number}, {preview.intent})</div>
          {preview.last_message && <div className="text-xs text-slate-500">Pesan terakhir customer: "{preview.last_message}"</div>}
          {preview.ok ? <div className="p-3 rounded-lg bg-blue-50 text-sm text-blue-900 whitespace-pre-wrap" data-testid="afu-preview-message">{preview.message}</div>
            : <div className="text-sm text-slate-500">{preview.note || "Tidak dapat membuat preview."}</div>}
        </CardContent></Card>
      )}
      <div className="flex justify-end"><Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-3.5 w-3.5 mr-1" />Muat ulang</Button></div>
      <Card><CardContent className="p-0">
        <Table><TableHeader><TableRow>
          <TableHead>Lead</TableHead><TableHead>Customer</TableHead><TableHead>Stage</TableHead><TableHead>Paket</TableHead>
          <TableHead>Intent</TableHead><TableHead>FU Count</TableHead><TableHead>Auto FU</TableHead><TableHead>Aksi</TableHead>
        </TableRow></TableHeader><TableBody>
          {rows.length === 0 ? <TableRow><TableCell colSpan={8} className="text-center text-slate-400 py-8">Belum ada lead pada tahap follow-up</TableCell></TableRow>
            : rows.map((l) => (
              <TableRow key={l.id} data-testid={`afu-lead-${l.id}`}>
                <TableCell className="font-medium">{l.lead_code}</TableCell>
                <TableCell>{l.customer_name || "—"}{!l.has_conversation && <Badge variant="outline" className="ml-1 text-[9px] bg-slate-100">no chat</Badge>}</TableCell>
                <TableCell><Badge variant="outline" className="text-[10px]">{l.stage}</Badge></TableCell>
                <TableCell className="text-xs text-slate-500 max-w-[160px] truncate">{l.interested_package || "—"}</TableCell>
                <TableCell className="text-xs">{l.customer_intent || "—"}</TableCell>
                <TableCell>{l.followup_count}</TableCell>
                <TableCell><Badge variant="outline" className={statusTone(l.auto_followup_status)}>{l.auto_followup_status}</Badge></TableCell>
                <TableCell><div className="flex gap-1">
                  <Button size="sm" variant="ghost" disabled={pbusy === l.id || !l.has_conversation} onClick={() => doPreview(l.id)} data-testid={`afu-preview-btn-${l.id}`} title="Test Follow-Up">{pbusy === l.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}</Button>
                  {l.auto_followup_status !== "PAUSED" ? <Button size="sm" variant="ghost" onClick={() => setStatus(l.id, "PAUSED")} data-testid={`afu-pause-${l.id}`} title="Pause"><Pause className="h-3.5 w-3.5" /></Button>
                    : <Button size="sm" variant="ghost" onClick={() => setStatus(l.id, "ACTIVE")} data-testid={`afu-resume-${l.id}`} title="Resume"><PlayCircle className="h-3.5 w-3.5" /></Button>}
                  <Button size="sm" variant="ghost" onClick={() => setStatus(l.id, "STOPPED")} data-testid={`afu-stop-${l.id}`} title="Stop"><Ban className="h-3.5 w-3.5" /></Button>
                </div></TableCell>
              </TableRow>
            ))}
        </TableBody></Table>
      </CardContent></Card>
    </div>
  );
}

function ABCard({ s, upd }) {
  const [ab, setAb] = useState(null);
  const load = useCallback(() => api.get("/ai/followup/ab").then((r) => setAb(r.data)).catch(() => setAb(null)), []);
  useEffect(() => { load(); }, [load]);
  const reset = async () => { try { await api.post("/ai/followup/ab/reset"); toast.success("A/B stats di-reset"); load(); } catch (e) { err(e); } };
  return (
    <Card><CardContent className="p-5 space-y-3" data-testid="afu-ab-card">
      <div className="flex items-center justify-between">
        <div><div className="font-semibold text-slate-700">A/B Testing Pesan Follow-Up</div><div className="text-xs text-slate-400">2 varian gaya, 50/50, auto-pilih pemenang by response rate</div></div>
        <Switch checked={!!s.ab_testing_enabled} onCheckedChange={(v) => upd("ab_testing_enabled", v)} data-testid="afu-ab-enabled" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div><Label className="text-xs">Varian A — gaya</Label><Textarea rows={2} value={s.ab_style_a || ""} onChange={(e) => upd("ab_style_a", e.target.value)} data-testid="afu-ab-style-a" /></div>
        <div><Label className="text-xs">Varian B — gaya</Label><Textarea rows={2} value={s.ab_style_b || ""} onChange={(e) => upd("ab_style_b", e.target.value)} data-testid="afu-ab-style-b" /></div>
      </div>
      <div><Label className="text-xs">Minimum sampel per varian sebelum pilih pemenang</Label><Input type="number" className="w-32" value={s.ab_min_sample ?? ""} onChange={(e) => upd("ab_min_sample", Number(e.target.value))} data-testid="afu-ab-min-sample" /></div>
      {ab && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Badge variant="outline" data-testid="afu-ab-stat-a">A: {ab.A.sent} kirim · {ab.A.response} balas · {ab.A.rate}%</Badge>
          <Badge variant="outline" data-testid="afu-ab-stat-b">B: {ab.B.sent} kirim · {ab.B.response} balas · {ab.B.rate}%</Badge>
          {ab.winner ? <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200" data-testid="afu-ab-winner">Pemenang: {ab.winner}</Badge> : <Badge variant="outline">Belum ada pemenang</Badge>}
          <Button size="sm" variant="ghost" onClick={reset} data-testid="afu-ab-reset"><RefreshCw className="h-3.5 w-3.5 mr-1" />Reset</Button>
        </div>
      )}
    </CardContent></Card>
  );
}

const TABS = [
  ["analytics", "Analytics", Gauge],
  ["settings", "Settings & Rules", Settings2],
  ["queue", "Follow-Up Queue", ListChecks],
  ["leads", "Leads & Preview", Users2],
];

export default function AutoFollowUp() {
  const { user } = useAuth();
  const [tab, setTab] = useState("analytics");
  if (user?.role !== "super_admin") return <Navigate to="/dashboard" replace />;
  return (
    <div className="space-y-5" data-testid="auto-followup-page">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-rose-500/10 flex items-center justify-center"><MessageSquareHeart className="h-6 w-6 text-rose-600" /></div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Auto Follow-Up</h1>
          <p className="text-sm text-slate-500">Lead nurturing otomatis berbasis konteks — aman, terbatas, dan menghormati preferensi customer.</p>
        </div>
      </div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex flex-wrap h-auto gap-1" data-testid="afu-tabs-list">
          {TABS.map(([k, label, Icon]) => (
            <TabsTrigger key={k} value={k} className="text-xs" data-testid={`afu-tab-${k}`}><Icon className="h-3.5 w-3.5 mr-1" />{label}</TabsTrigger>
          ))}
        </TabsList>
        <div className="mt-4">
          <TabsContent value="analytics"><AnalyticsTab /></TabsContent>
          <TabsContent value="settings"><SettingsTab /></TabsContent>
          <TabsContent value="queue"><QueueTab /></TabsContent>
          <TabsContent value="leads"><LeadsTab /></TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
