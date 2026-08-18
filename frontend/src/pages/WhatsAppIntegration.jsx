import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { Navigate } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import {
  MessageCircle, PlugZap, MessagesSquare, Bot, BookOpen, Palette, ShieldAlert,
  UserCog, ScrollText, Activity, Loader2, RefreshCw, Send, CheckCircle2, PlayCircle, Save,
  FileText, Megaphone, HeartPulse, Plus, UploadCloud,
} from "lucide-react";

const fmt = (t) => (t || "—").toString().replace("T", " ").slice(0, 19);
const connColor = (s) =>
  s === "CONNECTED" ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : s === "ERROR" ? "bg-red-50 text-red-700 border-red-200"
      : "bg-slate-100 text-slate-600 border-slate-200";
const statusColor = (s) =>
  s === "AI ACTIVE" ? "bg-blue-50 text-blue-700 border-blue-200"
    : s === "HUMAN HANDOVER" ? "bg-red-50 text-red-700 border-red-200"
      : s === "WAITING CUSTOMER" ? "bg-amber-50 text-amber-700 border-amber-200"
        : "bg-slate-100 text-slate-600 border-slate-200";
const err = (e) => toast.error(formatApiErrorDetail(e?.response?.data?.detail) || "Terjadi kesalahan");

// ============================================================ Provider (Api.co.id)
function ProviderTab() {
  const [cfg, setCfg] = useState(null);
  const [form, setForm] = useState({ base_url: "", api_key: "", phone_number_id: "" });
  const [phones, setPhones] = useState([]);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => api.get("/whatsapp/provider").then((r) => {
    setCfg(r.data); setForm((f) => ({ ...f, base_url: r.data.base_url || "", phone_number_id: r.data.phone_number_id || "" }));
  }).catch(() => setCfg({})), []);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setBusy("save");
    try {
      const body = { base_url: form.base_url, phone_number_id: form.phone_number_id };
      if (form.api_key) body.api_key = form.api_key;
      const sel = phones.find((p) => (p.id || p.phone_number_id) === form.phone_number_id);
      if (sel) { body.phone_number = sel.phone_number || sel.display_phone_number; body.phone_display_name = sel.display_name || sel.verified_name; }
      const r = await api.put("/whatsapp/provider", body);
      setCfg(r.data); setForm((f) => ({ ...f, api_key: "" }));
      toast.success("Konfigurasi disimpan");
    } catch (e) { err(e); } finally { setBusy(""); }
  };
  const test = async () => {
    setBusy("test");
    try { const r = await api.post("/whatsapp/provider/test-connection"); setCfg((c) => ({ ...c, connection_status: r.data.connection_status }));
      r.data.ok ? toast.success(r.data.message) : toast.error(r.data.message || "Koneksi gagal"); }
    catch (e) { err(e); } finally { setBusy(""); }
  };
  const loadPhones = async () => {
    setBusy("phones");
    try { const r = await api.get("/whatsapp/provider/phone-numbers"); setPhones(r.data.phone_numbers || []);
      toast.success(`${(r.data.phone_numbers || []).length} nomor ditemukan`); }
    catch (e) { err(e); } finally { setBusy(""); }
  };

  if (!cfg) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  return (
    <div className="space-y-4 max-w-2xl" data-testid="wa-provider-tab">
      <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100 text-sm text-emerald-800">
        Provider WhatsApp: <b>API.CO.ID</b> (Chat Gateway resmi). API Key disimpan server-side terenkripsi & tidak pernah ditampilkan ke browser.
      </div>
      <Card><CardContent className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <span className="font-medium text-slate-700">Status Koneksi</span>
          <Badge variant="outline" className={connColor(cfg.connection_status)} data-testid="wa-conn-status">{cfg.connection_status || "UNKNOWN"}</Badge>
        </div>
        <div><Label>Provider</Label><Input value="API.CO.ID" disabled data-testid="wa-provider-name" /></div>
        <div><Label>Base URL</Label><Input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://chat.api.co.id" data-testid="wa-base-url" /></div>
        <div><Label>API Key {cfg.has_key && <span className="text-xs text-slate-400">(tersimpan: {cfg.api_key_mask} — kosongkan bila tak diubah)</span>}</Label>
          <Input type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder="Bearer API Key" data-testid="wa-api-key" /></div>
        <div><Label>WhatsApp Phone Number ID</Label>
          {phones.length > 0 ? (
            <Select value={form.phone_number_id} onValueChange={(v) => setForm({ ...form, phone_number_id: v })}>
              <SelectTrigger data-testid="wa-phone-select"><SelectValue placeholder="Pilih nomor" /></SelectTrigger>
              <SelectContent>{phones.map((p) => {
                const id = p.id || p.phone_number_id;
                return <SelectItem key={id} value={id}>{(p.display_name || p.verified_name || "WA")} · {p.phone_number || p.display_phone_number || id}{p.is_primary ? " (Primary)" : ""}</SelectItem>;
              })}</SelectContent>
            </Select>
          ) : (
            <Input value={form.phone_number_id} onChange={(e) => setForm({ ...form, phone_number_id: e.target.value })} placeholder="Klik 'Load Phone Numbers' atau isi manual" data-testid="wa-phone-id" />
          )}
          {cfg.phone_number && <p className="text-xs text-slate-400 mt-1">Aktif: {cfg.phone_display_name || ""} {cfg.phone_number}</p>}
        </div>
        {phones.length > 0 && (
          <Card><CardContent className="p-0"><Table>
            <TableHeader><TableRow><TableHead>ID</TableHead><TableHead>Nama</TableHead><TableHead>Nomor</TableHead><TableHead>Primary</TableHead></TableRow></TableHeader>
            <TableBody>{phones.map((p) => { const id = p.id || p.phone_number_id; return (
              <TableRow key={id} data-testid={`wa-phone-row-${id}`}>
                <TableCell className="font-mono text-xs">{id}</TableCell>
                <TableCell>{p.display_name || p.verified_name || "—"}</TableCell>
                <TableCell>{p.phone_number || p.display_phone_number || "—"}</TableCell>
                <TableCell>{p.is_primary ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : "—"}</TableCell>
              </TableRow>); })}</TableBody>
          </Table></CardContent></Card>
        )}
        <div className="flex flex-wrap gap-2 pt-1">
          <Button variant="outline" onClick={test} disabled={!!busy} data-testid="wa-test-connection-btn">{busy === "test" ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <PlugZap className="h-4 w-4 mr-1" />}Test Connection</Button>
          <Button variant="outline" onClick={loadPhones} disabled={!!busy} data-testid="wa-load-phones-btn">{busy === "phones" ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />}Load Phone Numbers</Button>
          <Button onClick={save} disabled={!!busy} data-testid="wa-save-config-btn">{busy === "save" ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}Save Configuration</Button>
        </div>
      </CardContent></Card>
    </div>
  );
}

// ============================================================ Conversation Monitor
function MediaBubble({ m }) {
  if (!m.media_url) return null;
  const t = m.media_type || m.type;
  if (t === "image") return <img src={m.media_url} alt={m.media_filename || "image"} className="rounded max-w-full max-h-48 mb-1" data-testid="wa-media-image" />;
  if (t === "video") return <video src={m.media_url} controls className="rounded max-w-full max-h-48 mb-1" data-testid="wa-media-video" />;
  if (t === "audio") return <audio src={m.media_url} controls className="w-full mb-1" data-testid="wa-media-audio" />;
  return <a href={m.media_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 underline mb-1" data-testid="wa-media-doc"><FileText className="h-4 w-4" />{m.media_filename || "Dokumen"}</a>;
}

function MediaFilePreview({ file, type }) {
  const [url, setUrl] = useState("");
  useEffect(() => { const u = URL.createObjectURL(file); setUrl(u); return () => URL.revokeObjectURL(u); }, [file]);
  if (type === "image") return <img src={url} alt="preview" className="h-12 w-12 object-cover rounded" />;
  if (type === "video") return <video src={url} className="h-12 w-12 object-cover rounded" />;
  return <span className="flex items-center gap-1 text-slate-600 truncate"><FileText className="h-4 w-4" />{file.name}</span>;
}

function MonitorTab() {
  const [convs, setConvs] = useState(null);
  const [sel, setSel] = useState(null);
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [mediaType, setMediaType] = useState("image");
  const [mediaFile, setMediaFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const load = useCallback(() => api.get("/whatsapp/conversations").then((r) => setConvs(r.data)).catch(() => setConvs([])), []);
  useEffect(() => { load(); }, [load]);
  const openConv = async (c) => {
    setSel(c);
    try { const r = await api.get(`/whatsapp/conversations/${c.id}/messages`); setMsgs(r.data); } catch (e) { err(e); }
  };
  const send = async () => {
    if (!text.trim() || !sel) return;
    setSending(true);
    try { await api.post(`/whatsapp/conversations/${sel.id}/send`, { type: "text", content: text }); setText(""); await openConv(sel); }
    catch (e) { err(e); } finally { setSending(false); }
  };
  const sendMedia = async () => {
    if (!mediaFile || !sel) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("media_type", mediaType);
      fd.append("file", mediaFile);
      fd.append("caption", text || "");
      await api.post(`/whatsapp/conversations/${sel.id}/send-media`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Media terkirim");
      setMediaFile(null); setText(""); await openConv(sel);
    } catch (e) { err(e); } finally { setUploading(false); }
  };
  const accept = { image: "image/*", document: ".pdf,.doc,.docx,.xls,.xlsx,.txt,.csv", audio: "audio/*", video: "video/*" }[mediaType];
  if (convs === null) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  return (
    <div className="grid md:grid-cols-3 gap-4 h-[560px]" data-testid="wa-monitor-tab">
      <Card className="md:col-span-1 overflow-hidden"><CardContent className="p-0 h-full overflow-y-auto">
        {convs.length === 0 ? <div className="p-6 text-sm text-slate-400 text-center">Belum ada percakapan.</div>
          : convs.map((c) => (
            <button key={c.id} onClick={() => openConv(c)} className={`w-full text-left px-4 py-3 border-b hover:bg-slate-50 ${sel?.id === c.id ? "bg-blue-50" : ""}`} data-testid={`wa-conv-item-${c.id}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-slate-800 truncate">{c.customer_name || c.wa_number}</span>
                <Badge variant="outline" className={statusColor(c.status)}>{c.status}</Badge>
              </div>
              <div className="text-xs text-slate-500 truncate mt-0.5">{c.last_message || "—"}</div>
              <div className="text-[10px] text-slate-400 mt-0.5">{fmt(c.last_activity)}</div>
            </button>
          ))}
      </CardContent></Card>
      <Card className="md:col-span-2 flex flex-col"><CardContent className="p-0 flex flex-col h-full">
        {!sel ? <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">Pilih percakapan.</div>
          : (<>
            <div className="px-4 py-3 border-b flex items-center justify-between">
              <span className="font-medium text-slate-800">{sel.customer_name || sel.wa_number}</span>
              <Badge variant="outline" className={statusColor(sel.status)}>{sel.status}</Badge>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-2 bg-slate-50">
              {msgs.map((m) => (
                <div key={m.id} className={`flex ${m.sender === "CUSTOMER" ? "justify-start" : "justify-end"}`}>
                  <div className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${m.sender === "CUSTOMER" ? "bg-white border" : m.sender === "AI" ? "bg-blue-100 text-blue-900" : "bg-emerald-100 text-emerald-900"}`} data-testid={`wa-msg-${m.id}`}>
                    <div className="text-[10px] opacity-60 mb-0.5">{m.sender}{m.ai_generated ? " · AI" : ""}</div>
                    <MediaBubble m={m} />
                    {m.content && <div className="whitespace-pre-wrap">{m.content}</div>}
                    <div className="text-[10px] opacity-50 mt-0.5">{fmt(m.timestamp)}</div>
                  </div>
                </div>
              ))}
              {msgs.length === 0 && <div className="text-center text-slate-400 text-sm py-6">Belum ada pesan.</div>}
            </div>
            {mediaFile && (
              <div className="px-3 pt-2 bg-white">
                <div className="flex items-center gap-2 text-xs bg-slate-50 border rounded p-2" data-testid="wa-media-preview">
                  <MediaFilePreview file={mediaFile} type={mediaType} />
                  <button className="ml-auto text-slate-400 hover:text-red-500 px-1" onClick={() => setMediaFile(null)} data-testid="wa-media-clear">✕</button>
                </div>
              </div>
            )}
            <div className="p-3 border-t flex gap-2 items-center bg-white">
              <Select value={mediaType} onValueChange={setMediaType}>
                <SelectTrigger className="w-[110px]" data-testid="wa-media-type"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="image">Gambar</SelectItem>
                  <SelectItem value="document">Dokumen</SelectItem>
                  <SelectItem value="audio">Audio</SelectItem>
                  <SelectItem value="video">Video</SelectItem>
                </SelectContent>
              </Select>
              <label className="cursor-pointer inline-flex items-center justify-center h-9 w-9 rounded-md border hover:bg-slate-50 shrink-0" data-testid="wa-media-attach">
                <UploadCloud className="h-4 w-4 text-slate-600" />
                <input type="file" accept={accept} className="hidden" onChange={(e) => setMediaFile(e.target.files?.[0] || null)} />
              </label>
              <Input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && !mediaFile && send()} placeholder={mediaFile ? "Caption (opsional)..." : "Ketik pesan manual..."} data-testid="wa-msg-input" />
              {mediaFile
                ? <Button onClick={sendMedia} disabled={uploading} data-testid="wa-media-send">{uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}</Button>
                : <Button onClick={send} disabled={sending} data-testid="wa-msg-send">{sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}</Button>}
            </div>
          </>)}
      </CardContent></Card>
    </div>
  );
}

// ============================================================ AI config (Agent/Knowledge/Style/Rules)
function AiConfigTab({ cfg, setCfg, section }) {
  const [saving, setSaving] = useState(false);
  const [kw, setKw] = useState((cfg.handover_keywords || []).join(", "));
  useEffect(() => { setKw((cfg.handover_keywords || []).join(", ")); }, [cfg.handover_keywords]);
  const save = async (payload) => {
    setSaving(true);
    try { const r = await api.put("/whatsapp/ai-config", payload); setCfg(r.data); toast.success("Konfigurasi AI disimpan"); }
    catch (e) { err(e); } finally { setSaving(false); }
  };
  if (section === "agent") return (
    <div className="space-y-4 max-w-2xl" data-testid="wa-ai-agent-tab">
      <div className="flex items-center justify-between p-4 rounded-lg border bg-slate-50">
        <div><div className="font-medium text-slate-800">AI Agent Aktif</div><div className="text-sm text-slate-500">Balas otomatis pesan customer memakai Gemini + Knowledge Base.</div></div>
        <Switch checked={!!cfg.enabled} onCheckedChange={(v) => setCfg({ ...cfg, enabled: v })} data-testid="wa-ai-enabled-switch" />
      </div>
      <div><Label>Pesan Sambutan (Greeting)</Label><Textarea rows={2} value={cfg.greeting || ""} onChange={(e) => setCfg({ ...cfg, greeting: e.target.value })} data-testid="wa-ai-greeting" /></div>
      <div><Label>Kata Kunci Handover (pisahkan koma)</Label>
        <Textarea rows={2} value={kw} onChange={(e) => setKw(e.target.value)} data-testid="wa-ai-keywords" /></div>
      <Button onClick={() => save({ enabled: cfg.enabled, greeting: cfg.greeting, handover_keywords: kw.split(",").map((s) => s.trim()).filter(Boolean) })} disabled={saving} data-testid="wa-ai-agent-save">{saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}Simpan Agent</Button>
    </div>
  );
  const map = { knowledge: ["Basis Pengetahuan Tambahan", "wa-ai-knowledge"], style: ["Gaya Bahasa", "wa-ai-style"], rules: ["Aturan & Batasan", "wa-ai-rules"] };
  const [label, tid] = map[section];
  return (
    <div className="space-y-4 max-w-2xl" data-testid={`wa-ai-${section}-tab`}>
      <div><Label>{label}</Label><Textarea rows={section === "knowledge" ? 10 : 6} value={cfg[section] || ""} onChange={(e) => setCfg({ ...cfg, [section]: e.target.value })} data-testid={tid} /></div>
      <Button onClick={() => save({ [section]: cfg[section] })} disabled={saving} data-testid={`${tid}-save`}>{saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}Simpan</Button>
    </div>
  );
}

// ============================================================ Human Handover
function HandoverTab() {
  const [convs, setConvs] = useState(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => api.get("/whatsapp/conversations", { params: { status: "HUMAN HANDOVER" } }).then((r) => setConvs(r.data)).catch(() => setConvs([])), []);
  useEffect(() => { load(); }, [load]);
  const resume = async (c) => {
    setBusy(c.id);
    try { await api.post(`/whatsapp/conversations/${c.id}/resume-ai`); toast.success("AI diaktifkan kembali"); await load(); }
    catch (e) { err(e); } finally { setBusy(""); }
  };
  if (convs === null) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  return (
    <div className="space-y-4" data-testid="wa-handover-tab">
      <div className="flex items-center justify-between">
        <div><h3 className="text-lg font-semibold text-slate-800">Human Handover</h3>
          <p className="text-sm text-slate-500">Percakapan yang dieskalasi ke sales. Aktifkan AI kembali setelah selesai.</p></div>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4 mr-1" />Muat Ulang</Button>
      </div>
      <Card><CardContent className="p-0">
        <Table>
          <TableHeader><TableRow><TableHead>Customer</TableHead><TableHead>Nomor</TableHead><TableHead>Sales</TableHead><TableHead>Aktivitas</TableHead><TableHead>Aksi</TableHead></TableRow></TableHeader>
          <TableBody>
            {convs.length === 0 ? (<TableRow><TableCell colSpan={5} className="text-center py-8 text-slate-400">Tidak ada handover aktif.</TableCell></TableRow>)
              : convs.map((c) => (
                <TableRow key={c.id} data-testid={`wa-handover-row-${c.id}`}>
                  <TableCell className="font-medium">{c.customer_name || "—"}</TableCell>
                  <TableCell>{c.wa_number}</TableCell>
                  <TableCell>{c.assigned_sales_id ? <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">Ditugaskan</Badge> : <span className="text-slate-400 text-xs">Belum</span>}</TableCell>
                  <TableCell className="text-slate-500 text-xs">{fmt(c.last_activity)}</TableCell>
                  <TableCell><Button size="sm" onClick={() => resume(c)} disabled={busy === c.id} data-testid={`wa-resume-ai-${c.id}`}>{busy === c.id ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <PlayCircle className="h-4 w-4 mr-1" />}Aktifkan AI</Button></TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </CardContent></Card>
    </div>
  );
}

// ============================================================ Logs
function WaLogsTab() {
  const [logs, setLogs] = useState(null);
  const load = useCallback(() => api.get("/whatsapp/logs", { params: { kind: "wa" } }).then((r) => setLogs(r.data)).catch(() => setLogs([])), []);
  useEffect(() => { load(); }, [load]);
  if (logs === null) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  return (
    <div className="space-y-3" data-testid="wa-wa-logs-tab">
      <div className="flex justify-end"><Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4 mr-1" />Muat Ulang</Button></div>
      <Card><CardContent className="p-0"><Table>
        <TableHeader><TableRow><TableHead>Waktu</TableHead><TableHead>Jenis</TableHead><TableHead>Arah</TableHead><TableHead>Ref</TableHead><TableHead>Status</TableHead><TableHead>Error</TableHead></TableRow></TableHeader>
        <TableBody>
          {logs.length === 0 ? (<TableRow><TableCell colSpan={6} className="text-center py-8 text-slate-400">Belum ada log.</TableCell></TableRow>)
            : logs.map((l) => (
              <TableRow key={l.id} data-testid={`wa-log-row-${l.id}`}>
                <TableCell className="text-xs text-slate-500">{fmt(l.created_at)}</TableCell>
                <TableCell><Badge variant="outline">{l.kind}</Badge></TableCell>
                <TableCell className="text-xs">{l.direction}</TableCell>
                <TableCell className="font-mono text-xs truncate max-w-[160px]" title={l.ref}>{l.ref}</TableCell>
                <TableCell>{l.ok ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">FAILED</Badge>}</TableCell>
                <TableCell className="text-xs text-red-500 truncate max-w-[200px]" title={l.error}>{l.error || "—"}</TableCell>
              </TableRow>
            ))}
        </TableBody>
      </Table></CardContent></Card>
    </div>
  );
}

function ApiLogsTab() {
  const [logs, setLogs] = useState(null);
  const load = useCallback(() => api.get("/whatsapp/api-logs").then((r) => setLogs(r.data)).catch(() => setLogs([])), []);
  useEffect(() => { load(); }, [load]);
  if (logs === null) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  return (
    <div className="space-y-3" data-testid="wa-api-logs-tab">
      <div className="flex justify-end"><Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4 mr-1" />Muat Ulang</Button></div>
      <Card><CardContent className="p-0"><Table>
        <TableHeader><TableRow><TableHead>Waktu</TableHead><TableHead>Endpoint</TableHead><TableHead>Method</TableHead><TableHead>Status</TableHead><TableHead>Durasi</TableHead><TableHead>Kategori Error</TableHead></TableRow></TableHeader>
        <TableBody>
          {logs.length === 0 ? (<TableRow><TableCell colSpan={6} className="text-center py-8 text-slate-400">Belum ada API call.</TableCell></TableRow>)
            : logs.map((l) => (
              <TableRow key={l.id} data-testid={`wa-apilog-row-${l.id}`}>
                <TableCell className="text-xs text-slate-500">{fmt(l.created_at)}</TableCell>
                <TableCell className="font-mono text-xs truncate max-w-[220px]" title={l.endpoint}>{l.endpoint}</TableCell>
                <TableCell className="text-xs">{l.method}</TableCell>
                <TableCell>{l.ok ? <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">{l.status_code}</Badge> : <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">{l.status_code}</Badge>}</TableCell>
                <TableCell className="text-xs">{l.duration_ms}ms</TableCell>
                <TableCell className="text-xs text-red-500">{l.error_category || "—"}</TableCell>
              </TableRow>
            ))}
        </TableBody>
      </Table></CardContent></Card>
    </div>
  );
}

// ============================================================ Templates
function TemplatesTab() {
  const [rows, setRows] = useState(null);
  const [busy, setBusy] = useState("");
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ template_name: "", category: "UTILITY", language: "id", body: "" });
  const load = useCallback((sync) => { setBusy("load"); api.get("/whatsapp/templates", { params: sync ? { sync: 1 } : {} }).then((r) => setRows(r.data)).catch(() => setRows([])).finally(() => setBusy("")); }, []);
  useEffect(() => { load(false); }, [load]);
  const create = async () => {
    setBusy("save");
    try { await api.post("/whatsapp/templates", f); toast.success("Template dibuat (PENDING)"); setOpen(false); load(false); }
    catch (e) { err(e); } finally { setBusy(""); }
  };
  const submit = async (t) => { try { await api.post(`/whatsapp/templates/${t.provider_template_id}/submit`); toast.success("Disubmit ke Meta"); load(true); } catch (e) { err(e); } };
  const stc = (s) => s === "APPROVED" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : s === "REJECTED" ? "bg-red-50 text-red-700 border-red-200" : "bg-amber-50 text-amber-700 border-amber-200";
  return (
    <div className="space-y-4" data-testid="wa-templates-tab">
      <div className="flex items-center justify-between">
        <div><h3 className="text-lg font-semibold text-slate-800">WhatsApp Templates</h3><p className="text-sm text-slate-500">Hanya template APPROVED yang boleh dikirim. Sync dengan Api.co.id.</p></div>
        <div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => load(true)} disabled={!!busy} data-testid="wa-tpl-sync"><RefreshCw className="h-4 w-4 mr-1" />Sync</Button>
          <Button size="sm" onClick={() => setOpen(true)} data-testid="wa-tpl-add"><Plus className="h-4 w-4 mr-1" />Template</Button></div>
      </div>
      <Card><CardContent className="p-0"><Table>
        <TableHeader><TableRow><TableHead>Nama</TableHead><TableHead>Kategori</TableHead><TableHead>Bahasa</TableHead><TableHead>Status</TableHead><TableHead>Meta ID</TableHead><TableHead>Aksi</TableHead></TableRow></TableHeader>
        <TableBody>
          {rows === null ? (<TableRow><TableCell colSpan={6} className="text-center py-8"><Loader2 className="h-5 w-5 animate-spin mx-auto text-blue-600" /></TableCell></TableRow>)
            : rows.length === 0 ? (<TableRow><TableCell colSpan={6} className="text-center py-8 text-slate-400">Belum ada template. Klik Sync/Template.</TableCell></TableRow>)
              : rows.map((t) => (<TableRow key={t.id} data-testid={`wa-tpl-row-${t.id}`}>
                <TableCell className="font-medium">{t.template_name}</TableCell><TableCell><Badge variant="outline">{t.category}</Badge></TableCell>
                <TableCell>{t.language}</TableCell><TableCell><Badge variant="outline" className={stc(t.status)}>{t.status}</Badge></TableCell>
                <TableCell className="font-mono text-xs">{t.meta_template_id || "—"}</TableCell>
                <TableCell>{t.status !== "APPROVED" && t.provider_template_id && <Button size="sm" variant="outline" onClick={() => submit(t)} data-testid={`wa-tpl-submit-${t.id}`}>Submit</Button>}</TableCell>
              </TableRow>))}
        </TableBody></Table></CardContent></Card>
      <Dialog open={open} onOpenChange={setOpen}><DialogContent data-testid="wa-tpl-dialog">
        <DialogHeader><DialogTitle>Template Baru</DialogTitle><DialogDescription>Buat template lalu Submit ke Meta untuk approval.</DialogDescription></DialogHeader>
        <div className="space-y-3">
          <div><Label>Nama (huruf kecil/underscore)</Label><Input value={f.template_name} onChange={(e) => setF({ ...f, template_name: e.target.value })} data-testid="wa-tpl-name" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Kategori</Label><Select value={f.category} onValueChange={(v) => setF({ ...f, category: v })}><SelectTrigger data-testid="wa-tpl-category"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="MARKETING">MARKETING</SelectItem><SelectItem value="UTILITY">UTILITY</SelectItem><SelectItem value="AUTHENTICATION">AUTHENTICATION</SelectItem></SelectContent></Select></div>
            <div><Label>Bahasa</Label><Input value={f.language} onChange={(e) => setF({ ...f, language: e.target.value })} /></div>
          </div>
          <div><Label>Body (pakai {"{{1}}"} untuk variabel)</Label><Textarea rows={4} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} data-testid="wa-tpl-body" /></div>
        </div>
        <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Batal</Button><Button onClick={create} disabled={busy === "save"} data-testid="wa-tpl-save">{busy === "save" && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}Simpan</Button></DialogFooter>
      </DialogContent></Dialog>
    </div>
  );
}

// ============================================================ Broadcast
function BroadcastTab() {
  const [tpls, setTpls] = useState([]);
  const [name, setName] = useState("");
  const [phones, setPhones] = useState("");
  const [jobs, setJobs] = useState([]);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    api.get("/whatsapp/templates", { params: { status: "APPROVED" } }).then((r) => setTpls(r.data)).catch(() => {});
    api.get("/whatsapp/broadcast/jobs").then((r) => setJobs(r.data.local || [])).catch(() => {});
  }, []);
  useEffect(() => { load(); }, [load]);
  const send = async () => {
    if (!name) { toast.error("Pilih template APPROVED"); return; }
    setBusy(true);
    try { const r = await api.post("/whatsapp/broadcast", { template_name: name, phone_numbers: phones.split(",").map((s) => s.trim()).filter(Boolean) });
      toast.success(`Terkirim ke ${r.data.recipients} (skip ${r.data.skipped})`); setPhones(""); load(); }
    catch (e) { err(e); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4 max-w-2xl" data-testid="wa-broadcast-tab">
      <div className="p-3 rounded-lg bg-amber-50 border border-amber-100 text-sm text-amber-800">Broadcast hanya Super Admin, wajib template <b>APPROVED</b>. Customer blacklist/opt-out otomatis difilter.</div>
      <Card><CardContent className="p-5 space-y-3">
        <div><Label>Template APPROVED</Label><Select value={name} onValueChange={setName}><SelectTrigger data-testid="wa-bc-template"><SelectValue placeholder={tpls.length ? "Pilih template" : "Belum ada template APPROVED"} /></SelectTrigger><SelectContent>{tpls.map((t) => <SelectItem key={t.id} value={t.template_name}>{t.template_name} ({t.language})</SelectItem>)}</SelectContent></Select></div>
        <div><Label>Nomor Telepon (+62…, pisahkan koma)</Label><Textarea rows={3} value={phones} onChange={(e) => setPhones(e.target.value)} placeholder="+628123..., +628987..." data-testid="wa-bc-phones" /></div>
        <Button onClick={send} disabled={busy} data-testid="wa-bc-send">{busy ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Megaphone className="h-4 w-4 mr-1" />}Kirim Broadcast</Button>
      </CardContent></Card>
      <Card><CardContent className="p-0"><Table>
        <TableHeader><TableRow><TableHead>Waktu</TableHead><TableHead>Template</TableHead><TableHead>Penerima</TableHead><TableHead>Skip</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
        <TableBody>{jobs.length === 0 ? (<TableRow><TableCell colSpan={5} className="text-center py-6 text-slate-400">Belum ada broadcast.</TableCell></TableRow>)
          : jobs.map((j) => (<TableRow key={j.id}><TableCell className="text-xs text-slate-500">{fmt(j.created_at)}</TableCell><TableCell>{j.template_name}</TableCell><TableCell>{j.recipients}</TableCell><TableCell>{j.skipped}</TableCell><TableCell><Badge variant="outline">{j.status}</Badge></TableCell></TableRow>))}
        </TableBody></Table></CardContent></Card>
    </div>
  );
}

// ============================================================ Webhook Health
function WebhookHealthTab() {
  const [h, setH] = useState(null);
  const [wh, setWh] = useState(null);
  const [hooks, setHooks] = useState([]);
  const load = useCallback(() => {
    api.get("/whatsapp/health").then((r) => setH(r.data)).catch(() => setH({}));
    api.get("/whatsapp/webhook-health").then((r) => setWh(r.data)).catch(() => setWh({}));
    api.get("/whatsapp/webhooks").then((r) => setHooks(r.data.webhooks || [])).catch(() => setHooks([]));
  }, []);
  useEffect(() => { load(); }, [load]);
  const enable = async (id) => { try { await api.post(`/whatsapp/webhooks/${id}/enable`); toast.success("Webhook di-enable"); load(); } catch (e) { err(e); } };
  const oc = (s) => s === "CONNECTED" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : s === "DEGRADED" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-red-50 text-red-700 border-red-200";
  return (
    <div className="space-y-4" data-testid="wa-webhook-health-tab">
      <div className="flex justify-end"><Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4 mr-1" />Muat Ulang</Button></div>
      <div className="grid md:grid-cols-2 gap-4">
        <Card><CardContent className="p-5 space-y-2">
          <div className="flex items-center justify-between"><span className="font-medium text-slate-700 flex items-center gap-1.5"><HeartPulse className="h-4 w-4" />Health</span>
            <Badge variant="outline" className={oc(h?.overall)} data-testid="wa-health-overall">{h?.overall || "—"}</Badge></div>
          <div className="text-sm text-slate-500">API auth: {h?.api_ok ? "OK" : "gagal"}</div>
          <div className="text-sm text-slate-500">Phone number: {h?.has_phone_number ? "terpilih" : "belum"}</div>
          <div className="text-sm text-slate-500">Webhook error events: {h?.webhook_error_events ?? "—"}</div>
        </CardContent></Card>
        <Card><CardContent className="p-5 space-y-2">
          <span className="font-medium text-slate-700">Webhook Events</span>
          <div className="text-sm text-slate-500">Total: {wh?.total_events ?? "—"} · Error: {wh?.error_events ?? "—"}</div>
          <div className="text-sm text-slate-500">Terakhir: {fmt(wh?.last_event_at)}</div>
          <div className="text-sm text-slate-500">Sukses terakhir: {fmt(wh?.last_success_at)}</div>
        </CardContent></Card>
      </div>
      <Card><CardContent className="p-0"><Table>
        <TableHeader><TableRow><TableHead>Webhook</TableHead><TableHead>Status</TableHead><TableHead>Failure</TableHead><TableHead>Disabled At</TableHead><TableHead>Aksi</TableHead></TableRow></TableHeader>
        <TableBody>{hooks.length === 0 ? (<TableRow><TableCell colSpan={5} className="text-center py-6 text-slate-400">Tidak ada data webhook (butuh API Key aktif).</TableCell></TableRow>)
          : hooks.map((w) => (<TableRow key={w.id}><TableCell className="font-mono text-xs">{w.url || w.id}</TableCell>
            <TableCell><Badge variant="outline">{w.is_active === false ? "DISABLED" : (w.status || "ACTIVE")}</Badge></TableCell>
            <TableCell>{w.failure_count ?? 0}</TableCell><TableCell className="text-xs">{fmt(w.disabled_at)}</TableCell>
            <TableCell>{(w.is_active === false || w.disabled_at) && <Button size="sm" variant="outline" onClick={() => enable(w.id)} data-testid={`wa-hook-enable-${w.id}`}>Enable</Button>}</TableCell></TableRow>))}
        </TableBody></Table></CardContent></Card>
    </div>
  );
}

// ============================================================ AI Journey Simulator
function JourneyTab() {
  const [msg, setMsg] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [log, setLog] = useState([]);
  const run = async (reset) => {
    if (!reset && !msg.trim()) return;
    setLoading(true);
    try {
      const r = await api.post("/whatsapp/ai/simulate", { message: reset ? "Halo" : msg, confirmed, reset });
      if (reset) { setLog([]); toast.success("Percakapan direset"); }
      else {
        const entry = { you: msg, res: r.data };
        setLog((l) => [...l, entry]); setMsg("");
      }
    } catch (e) { err(e); } finally { setLoading(false); }
  };
  return (
    <div className="grid md:grid-cols-2 gap-4" data-testid="wa-journey-tab">
      <Card><CardContent className="p-5 space-y-3">
        <div className="flex items-center gap-2 text-slate-800 font-medium"><Bot className="h-4 w-4 text-indigo-600" />AI Customer Journey (Simulator)</div>
        <p className="text-sm text-slate-500">Uji alur AI (customer baru → lead → rekomendasi → order/booking → pembayaran → handover) tanpa WhatsApp live.</p>
        <div><Label>Pesan sebagai Customer</Label><Textarea rows={3} value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="Halo, saya mau tanya paket umrah bulan depan" data-testid="wa-journey-input" /></div>
        <div className="flex items-center gap-2"><Switch checked={confirmed} onCheckedChange={setConfirmed} data-testid="wa-journey-confirmed" /><Label className="cursor-pointer text-sm">Customer sudah konfirmasi (untuk Order/Booking)</Label></div>
        <div className="flex gap-2">
          <Button onClick={() => run(false)} disabled={loading} data-testid="wa-journey-send">{loading ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Send className="h-4 w-4 mr-1" />}Kirim</Button>
          <Button variant="outline" onClick={() => run(true)} disabled={loading} data-testid="wa-journey-reset"><RefreshCw className="h-4 w-4 mr-1" />Reset</Button>
        </div>
      </CardContent></Card>
      <Card><CardContent className="p-5 space-y-3 min-h-[300px] max-h-[560px] overflow-y-auto" data-testid="wa-journey-result">
        <div className="font-medium text-slate-800">Percakapan</div>
        {log.length === 0 ? <p className="text-sm text-slate-400">Hasil akan tampil di sini.</p>
          : log.map((e, i) => (
            <div key={i} className="space-y-1">
              <div className="text-right"><span className="inline-block bg-emerald-100 text-emerald-900 rounded-lg px-3 py-1.5 text-sm">{e.you}</span></div>
              {e.res.handover ? <div><Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">HANDOVER</Badge> <span className="text-sm text-slate-600">{e.res.reason}</span></div>
                : <div><span className="inline-block bg-blue-100 text-blue-900 rounded-lg px-3 py-1.5 text-sm whitespace-pre-wrap">{e.res.reply}</span></div>}
              {(e.res.tools_used || []).length > 0 && <div className="flex flex-wrap gap-1">{e.res.tools_used.map((t, j) => <Badge key={j} variant="outline" className={`text-[10px] ${t.ok ? "bg-slate-50 text-slate-600" : "bg-red-50 text-red-700 border-red-200"}`}>{t.tool}</Badge>)}</div>}
            </div>
          ))}
      </CardContent></Card>
    </div>
  );
}

// ============================================================ Safety & Messaging (Phase 10G)
function SafetyRow({ label, hint, children }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <div><div className="text-sm font-medium text-slate-700">{label}</div>{hint && <div className="text-xs text-slate-400">{hint}</div>}</div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function SafetyTab() {
  const [s, setS] = useState(null);
  const [mon, setMon] = useState(null);
  const [queue, setQueue] = useState(null);
  const [busy, setBusy] = useState(false);
  const upd = (k, v) => setS((p) => ({ ...p, [k]: v }));
  const num = (k, v) => upd(k, v === "" ? "" : Number(v));

  const loadMon = useCallback(() => {
    api.get("/whatsapp/messaging-monitor").then((r) => setMon(r.data)).catch(() => {});
    api.get("/whatsapp/outbound-queue").then((r) => setQueue(r.data)).catch(() => {});
  }, []);
  useEffect(() => {
    api.get("/whatsapp/safety").then((r) => setS(r.data)).catch(() => { setS({}); toast.error("Gagal memuat pengaturan keamanan"); });
    loadMon();
    const t = setInterval(loadMon, 8000);
    return () => clearInterval(t);
  }, [loadMon]);

  const save = async () => {
    setBusy(true);
    try { const r = await api.put("/whatsapp/safety", s); setS(r.data); toast.success("Pengaturan keamanan disimpan"); }
    catch (e) { err(e); } finally { setBusy(false); }
  };
  if (!s) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;

  const cards = mon ? [
    ["Pesan 24 jam", mon.messages_today, "text-slate-700"], ["Masuk", mon.inbound, "text-blue-600"],
    ["Keluar", mon.outbound, "text-emerald-600"], ["Balasan AI", mon.ai_responses, "text-indigo-600"],
    ["Balasan CS", mon.human_responses, "text-slate-700"], ["Gagal", mon.failed_messages, "text-red-600"],
    ["Kena Rate Limit", mon.rate_limit_events, "text-amber-600"], ["Follow-up dibatasi", mon.followup_capped, "text-amber-600"],
    ["Opt-out", mon.opt_out_customers, "text-slate-700"], ["Handover", mon.human_handover, "text-red-600"],
    ["Antrean pending", mon.queue_pending, "text-blue-600"],
  ] : [];

  return (
    <div className="space-y-4 max-w-4xl" data-testid="wa-safety-tab">
      <div className="p-3 rounded-lg bg-amber-50 border border-amber-100 text-sm text-amber-800">
        Kontrol keamanan & gaya pesan manusiawi (anti-spam). Delay & typing bersifat natural untuk UX — <b>bukan</b> untuk mengelabui WhatsApp.
      </div>

      {/* Monitor */}
      <Card><CardContent className="p-5 space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-slate-700 flex items-center gap-2"><Activity className="h-4 w-4 text-blue-600" />Messaging Monitor (24 jam)</span>
          <Button size="sm" variant="outline" onClick={loadMon} data-testid="wa-safety-refresh-monitor"><RefreshCw className="h-3.5 w-3.5 mr-1" />Muat ulang</Button>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
          {cards.map(([lbl, val, cls]) => (
            <div key={lbl} className="rounded-lg border border-slate-100 bg-slate-50/60 p-3" data-testid={`wa-mon-${lbl}`}>
              <div className={`text-xl font-bold ${cls}`}>{val ?? 0}</div>
              <div className="text-[11px] text-slate-500">{lbl}</div>
            </div>
          ))}
        </div>
        {queue && (
          <div className="flex flex-wrap gap-2 pt-1">
            {Object.entries(queue.counts || {}).map(([k, v]) => (
              <Badge key={k} variant="outline" className="text-[11px] bg-white" data-testid={`wa-queue-count-${k}`}>Antrean {k}: {v}</Badge>
            ))}
          </div>
        )}
      </CardContent></Card>

      {/* Messaging & AI */}
      <Card><CardContent className="p-5 space-y-1">
        <div className="font-semibold text-slate-700 mb-2">Messaging & AI</div>
        <SafetyRow label="Messaging aktif" hint="Master switch pengiriman WhatsApp"><Switch checked={!!s.messaging_enabled} onCheckedChange={(v) => upd("messaging_enabled", v)} data-testid="wa-safety-messaging-enabled" /></SafetyRow>
        <SafetyRow label="AI auto-reply" hint="AI membalas otomatis pesan masuk"><Switch checked={!!s.ai_auto_reply} onCheckedChange={(v) => upd("ai_auto_reply", v)} data-testid="wa-safety-ai-reply" /></SafetyRow>
        <SafetyRow label="Read receipt" hint="Tandai pesan customer sudah dibaca"><Switch checked={!!s.read_receipt} onCheckedChange={(v) => upd("read_receipt", v)} data-testid="wa-safety-read-receipt" /></SafetyRow>
        <SafetyRow label="Typing indicator" hint="Tampilkan 'sedang mengetik' sebelum membalas"><Switch checked={!!s.typing_indicator} onCheckedChange={(v) => upd("typing_indicator", v)} data-testid="wa-safety-typing" /></SafetyRow>
        <SafetyRow label="Marketing enabled" hint="Izinkan pesan marketing/broadcast promosi"><Switch checked={!!s.marketing_enabled} onCheckedChange={(v) => upd("marketing_enabled", v)} data-testid="wa-safety-marketing" /></SafetyRow>
      </CardContent></Card>

      {/* Human-like delay */}
      <Card><CardContent className="p-5 space-y-3">
        <div className="font-semibold text-slate-700">Human-like Delay</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div><Label>Delay min (detik)</Label><Input type="number" step="0.5" value={s.min_delay ?? ""} onChange={(e) => num("min_delay", e.target.value)} data-testid="wa-safety-min-delay" /></div>
          <div><Label>Delay maks (detik)</Label><Input type="number" step="0.5" value={s.max_delay ?? ""} onChange={(e) => num("max_delay", e.target.value)} data-testid="wa-safety-max-delay" /></div>
          <div><Label>Maks bubble (segmentasi)</Label><Input type="number" value={s.split_max_messages ?? ""} onChange={(e) => num("split_max_messages", e.target.value)} data-testid="wa-safety-split-max-msg" /></div>
          <div><Label>Kecepatan ketik min (char/dtk)</Label><Input type="number" value={s.typing_speed_min ?? ""} onChange={(e) => num("typing_speed_min", e.target.value)} data-testid="wa-safety-speed-min" /></div>
          <div><Label>Kecepatan ketik maks (char/dtk)</Label><Input type="number" value={s.typing_speed_max ?? ""} onChange={(e) => num("typing_speed_max", e.target.value)} data-testid="wa-safety-speed-max" /></div>
        </div>
        <div className="text-[11px] text-slate-400">Writing time dihitung dari panjang & kompleksitas pesan + variasi ringan, dengan batas aman keras (maks 12 dtk). Murni untuk UX — bukan untuk mengelabui WhatsApp.</div>
      </CardContent></Card>

      {/* Debounce & splitting */}
      <Card><CardContent className="p-5 space-y-3">
        <div className="font-semibold text-slate-700">Debounce & Message Splitting</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 items-end">
          <div><Label>Debounce window (detik)</Label><Input type="number" step="1" value={s.debounce_window ?? ""} onChange={(e) => num("debounce_window", e.target.value)} data-testid="wa-safety-debounce" /><div className="text-[11px] text-slate-400 mt-1">Gabungkan pesan beruntun sebelum AI membalas</div></div>
          <div><Label>Maks karakter per bubble</Label><Input type="number" value={s.split_max_chars ?? ""} onChange={(e) => num("split_max_chars", e.target.value)} data-testid="wa-safety-split-max" /></div>
          <SafetyRow label="Message splitting" hint="Pecah balasan panjang jadi beberapa bubble"><Switch checked={!!s.message_splitting} onCheckedChange={(v) => upd("message_splitting", v)} data-testid="wa-safety-splitting" /></SafetyRow>
        </div>
      </CardContent></Card>

      {/* Rate limits & follow-up */}
      <Card><CardContent className="p-5 space-y-3">
        <div className="font-semibold text-slate-700">Rate Limit & Follow-up Cap</div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div><Label>Per menit</Label><Input type="number" value={s.rate_per_minute ?? ""} onChange={(e) => num("rate_per_minute", e.target.value)} data-testid="wa-safety-rpm" /></div>
          <div><Label>Per jam</Label><Input type="number" value={s.rate_per_hour ?? ""} onChange={(e) => num("rate_per_hour", e.target.value)} data-testid="wa-safety-rph" /></div>
          <div><Label>Per hari</Label><Input type="number" value={s.rate_per_day ?? ""} onChange={(e) => num("rate_per_day", e.target.value)} data-testid="wa-safety-rpd" /></div>
          <div><Label>Maks follow-up</Label><Input type="number" value={s.max_followup ?? ""} onChange={(e) => num("max_followup", e.target.value)} data-testid="wa-safety-max-followup" /><div className="text-[11px] text-slate-400 mt-1">Tanpa balasan customer</div></div>
        </div>
      </CardContent></Card>

      {/* Business hours */}
      <Card><CardContent className="p-5 space-y-3">
        <div className="font-semibold text-slate-700">Business Hours / Out-of-Office</div>
        <SafetyRow label="Aktifkan jam kerja" hint="Batasi auto-reply hanya pada jam operasional (UTC)"><Switch checked={!!s.business_hours_enabled} onCheckedChange={(v) => upd("business_hours_enabled", v)} data-testid="wa-safety-bh-enabled" /></SafetyRow>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div><Label>Jam buka</Label><Input type="time" value={s.opening_time || ""} onChange={(e) => upd("opening_time", e.target.value)} data-testid="wa-safety-open" /></div>
          <div><Label>Jam tutup</Label><Input type="time" value={s.closing_time || ""} onChange={(e) => upd("closing_time", e.target.value)} data-testid="wa-safety-close" /></div>
          <div><Label>Perilaku di luar jam</Label>
            <Select value={s.off_hours_behavior || "AUTO_RESPONSE"} onValueChange={(v) => upd("off_hours_behavior", v)}>
              <SelectTrigger data-testid="wa-safety-offhours"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="AUTO_RESPONSE">Tetap balas AI</SelectItem>
                <SelectItem value="WAIT_UNTIL_BUSINESS_HOURS">Kirim pesan away</SelectItem>
                <SelectItem value="HUMAN_HANDOVER">Handover ke manusia</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <div><Label>Pesan away (di luar jam)</Label><Textarea rows={2} value={s.away_message || ""} onChange={(e) => upd("away_message", e.target.value)} data-testid="wa-safety-away-msg" /></div>
      </CardContent></Card>

      <div className="flex justify-end">
        <Button onClick={save} disabled={busy} data-testid="wa-safety-save">{busy ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}Simpan Pengaturan</Button>
      </div>
    </div>
  );
}

// ============================================================ Main
const TABS = [
  ["provider", "Provider", PlugZap],
  ["monitor", "Conversation Monitor", MessagesSquare],
  ["ai-agent", "AI Agent", Bot],
  ["ai-knowledge", "AI Knowledge", BookOpen],
  ["ai-style", "AI Style", Palette],
  ["ai-rules", "AI Rules", ShieldAlert],
  ["handover", "Human Handover", UserCog],
  ["safety", "Safety & Messaging", ShieldAlert],
  ["journey", "AI Journey", Bot],
  ["templates", "Templates", FileText],
  ["broadcast", "Broadcast", Megaphone],
  ["webhook-health", "Webhook Health", HeartPulse],
  ["wa-logs", "WhatsApp Logs", ScrollText],
  ["api-logs", "API Logs", Activity],
];

export default function WhatsAppIntegration() {
  const { user } = useAuth();
  const [tab, setTab] = useState("provider");
  const [cfg, setCfg] = useState(null);
  useEffect(() => {
    if (user?.role !== "super_admin") return;
    api.get("/whatsapp/ai-config").then((r) => setCfg(r.data)).catch(() => setCfg({}));
  }, [user]);
  if (user?.role !== "super_admin") return <Navigate to="/dashboard" replace />;

  const aiPending = <Loader2 className="h-6 w-6 animate-spin text-blue-600 mx-auto my-8" />;
  return (
    <div className="space-y-5" data-testid="whatsapp-integration-page">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-emerald-500/10 flex items-center justify-center"><MessageCircle className="h-6 w-6 text-emerald-600" /></div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">WhatsApp Integration</h1>
          <p className="text-sm text-slate-500">Provider <b>API.CO.ID</b> — kelola koneksi, AI Agent, dan pantau aktivitas WhatsApp.</p>
        </div>
      </div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex flex-wrap h-auto gap-1" data-testid="wa-tabs-list">
          {TABS.map(([k, label, Icon]) => (
            <TabsTrigger key={k} value={k} className="text-xs" data-testid={`wa-tab-${k}`}><Icon className="h-3.5 w-3.5 mr-1" />{label}</TabsTrigger>
          ))}
        </TabsList>
        <div className="mt-4">
          <TabsContent value="provider"><ProviderTab /></TabsContent>
          <TabsContent value="monitor"><MonitorTab /></TabsContent>
          <TabsContent value="ai-agent">{cfg ? <AiConfigTab cfg={cfg} setCfg={setCfg} section="agent" /> : aiPending}</TabsContent>
          <TabsContent value="ai-knowledge">{cfg ? <AiConfigTab cfg={cfg} setCfg={setCfg} section="knowledge" /> : aiPending}</TabsContent>
          <TabsContent value="ai-style">{cfg ? <AiConfigTab cfg={cfg} setCfg={setCfg} section="style" /> : aiPending}</TabsContent>
          <TabsContent value="ai-rules">{cfg ? <AiConfigTab cfg={cfg} setCfg={setCfg} section="rules" /> : aiPending}</TabsContent>
          <TabsContent value="handover"><HandoverTab /></TabsContent>
          <TabsContent value="safety"><SafetyTab /></TabsContent>
          <TabsContent value="journey"><JourneyTab /></TabsContent>
          <TabsContent value="templates"><TemplatesTab /></TabsContent>
          <TabsContent value="broadcast"><BroadcastTab /></TabsContent>
          <TabsContent value="webhook-health"><WebhookHealthTab /></TabsContent>
          <TabsContent value="wa-logs"><WaLogsTab /></TabsContent>
          <TabsContent value="api-logs"><ApiLogsTab /></TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
