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
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import {
  MessageCircle, Smartphone, QrCode, Settings2, MessagesSquare, Bot, BookOpen,
  Palette, ShieldAlert, UserCog, ScrollText, Activity, Loader2, Plus, Trash2,
  Pencil, RefreshCw, PlugZap, Power, Send, CheckCircle2, PlayCircle,
} from "lucide-react";

const fmt = (t) => (t || "—").toString().replace("T", " ").slice(0, 19);
const connColor = (s) =>
  s === "CONNECTED" ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : s === "CONNECTING" ? "bg-amber-50 text-amber-700 border-amber-200"
      : s === "ERROR" ? "bg-red-50 text-red-700 border-red-200"
        : "bg-slate-100 text-slate-600 border-slate-200";
const statusColor = (s) =>
  s === "AI ACTIVE" ? "bg-blue-50 text-blue-700 border-blue-200"
    : s === "HUMAN HANDOVER" ? "bg-red-50 text-red-700 border-red-200"
      : s === "WAITING CUSTOMER" ? "bg-amber-50 text-amber-700 border-amber-200"
        : "bg-slate-100 text-slate-600 border-slate-200";

const err = (e) => toast.error(formatApiErrorDetail(e?.response?.data?.detail) || "Terjadi kesalahan");

// ============================================================ Accounts
function AccountsTab({ accounts, reload, loading }) {
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  const openNew = () => { setEdit(null); setForm({ engine: "WEBJS", session: "default" }); setOpen(true); };
  const openEdit = (a) => { setEdit(a); setForm({ name: a.name, base_url: a.base_url, session: a.session, engine: a.engine, display_name: a.display_name, wa_number: a.wa_number }); setOpen(true); };

  const save = async () => {
    setSaving(true);
    try {
      if (edit) await api.put(`/whatsapp/accounts/${edit.id}`, form);
      else await api.post("/whatsapp/accounts", form);
      toast.success(edit ? "Akun diperbarui" : "Akun dibuat");
      setOpen(false); await reload();
    } catch (e) { err(e); } finally { setSaving(false); }
  };
  const remove = async (a) => {
    if (!window.confirm(`Arsipkan akun "${a.name}"?`)) return;
    try { await api.delete(`/whatsapp/accounts/${a.id}`); toast.success("Akun diarsipkan"); await reload(); }
    catch (e) { err(e); }
  };

  return (
    <div className="space-y-4" data-testid="wa-accounts-tab">
      <div className="flex items-center justify-between">
        <div><h3 className="text-lg font-semibold text-slate-800">Akun WhatsApp (WAHA)</h3>
          <p className="text-sm text-slate-500">Kelola koneksi WhatsApp Business melalui engine WAHA.</p></div>
        <Button onClick={openNew} data-testid="wa-add-account-btn"><Plus className="h-4 w-4 mr-1" />Tambah Akun</Button>
      </div>
      <Card><CardContent className="p-0">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Nama</TableHead><TableHead>Base URL</TableHead><TableHead>Session</TableHead>
            <TableHead>Nomor</TableHead><TableHead>API Key</TableHead><TableHead>Koneksi</TableHead><TableHead>Aksi</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {loading ? (<TableRow><TableCell colSpan={7} className="text-center py-8"><Loader2 className="h-5 w-5 animate-spin mx-auto text-blue-600" /></TableCell></TableRow>)
              : accounts.length === 0 ? (<TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-400">Belum ada akun. Klik "Tambah Akun".</TableCell></TableRow>)
                : accounts.map((a) => (
                  <TableRow key={a.id} data-testid={`wa-account-row-${a.id}`}>
                    <TableCell className="font-medium">{a.name}</TableCell>
                    <TableCell className="text-slate-500 text-xs">{a.base_url || "—"}</TableCell>
                    <TableCell>{a.session}</TableCell>
                    <TableCell>{a.wa_number || "—"}</TableCell>
                    <TableCell className="font-mono text-xs">{a.api_key_mask || "—"}</TableCell>
                    <TableCell><Badge variant="outline" className={connColor(a.connection_status)}>{a.connection_status}</Badge></TableCell>
                    <TableCell className="flex gap-1">
                      <Button size="icon" variant="ghost" onClick={() => openEdit(a)} data-testid={`wa-edit-account-${a.id}`}><Pencil className="h-4 w-4" /></Button>
                      <Button size="icon" variant="ghost" onClick={() => remove(a)} data-testid={`wa-delete-account-${a.id}`}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </CardContent></Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="wa-account-dialog">
          <DialogHeader><DialogTitle>{edit ? "Edit Akun" : "Tambah Akun WhatsApp"}</DialogTitle>
            <DialogDescription>Isi konfigurasi WAHA. API Key & HMAC disimpan terenkripsi.</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div><Label>Nama Akun</Label><Input value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="WhatsApp Utama" data-testid="wa-account-name" /></div>
            <div><Label>WAHA Base URL</Label><Input value={form.base_url || ""} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://waha.example.com" data-testid="wa-account-baseurl" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Session</Label><Input value={form.session || ""} onChange={(e) => setForm({ ...form, session: e.target.value })} placeholder="default" /></div>
              <div><Label>Engine</Label><Input value={form.engine || ""} onChange={(e) => setForm({ ...form, engine: e.target.value })} placeholder="WEBJS" /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Display Name</Label><Input value={form.display_name || ""} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></div>
              <div><Label>Nomor WhatsApp</Label><Input value={form.wa_number || ""} onChange={(e) => setForm({ ...form, wa_number: e.target.value })} placeholder="+62..." /></div>
            </div>
            <div><Label>API Key {edit && <span className="text-xs text-slate-400">(kosongkan bila tidak diubah)</span>}</Label><Input type="password" value={form.api_key || ""} onChange={(e) => setForm({ ...form, api_key: e.target.value })} data-testid="wa-account-apikey" /></div>
            <div><Label>HMAC Secret (opsional)</Label><Input type="password" value={form.hmac_secret || ""} onChange={(e) => setForm({ ...form, hmac_secret: e.target.value })} /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Batal</Button>
            <Button onClick={save} disabled={saving} data-testid="wa-account-save">{saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}Simpan</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ============================================================ Connection + QR
function ConnectionTab({ accounts, reload }) {
  const [sel, setSel] = useState("");
  const [qr, setQr] = useState("");
  const [busy, setBusy] = useState("");
  const acc = accounts.find((a) => a.id === sel) || accounts[0];
  useEffect(() => { if (!sel && accounts[0]) setSel(accounts[0].id); }, [accounts, sel]);

  const act = async (kind) => {
    if (!acc) return;
    setBusy(kind); setQr("");
    try {
      if (kind === "connect") { const r = await api.post(`/whatsapp/accounts/${acc.id}/connect`); toast.success(r.data?.message || "Sesi dimulai"); await loadQr(); }
      else if (kind === "test") { const r = await api.post(`/whatsapp/accounts/${acc.id}/test`); toast.success(`Status: ${r.data?.connection_status}`); }
      else if (kind === "disconnect") { await api.post(`/whatsapp/accounts/${acc.id}/disconnect`); toast.success("Terputus"); }
      await reload();
    } catch (e) { err(e); } finally { setBusy(""); }
  };
  const loadQr = async () => {
    if (!acc) return;
    setBusy("qr"); setQr("");
    try { const r = await api.get(`/whatsapp/accounts/${acc.id}/qr`); setQr(r.data?.qr || ""); }
    catch (e) { err(e); } finally { setBusy(""); }
  };

  if (!acc) return <div className="text-slate-400 py-8 text-center" data-testid="wa-connection-tab">Tambahkan akun terlebih dahulu di tab Accounts.</div>;
  return (
    <div className="space-y-4" data-testid="wa-connection-tab">
      <div className="flex flex-wrap items-center gap-2">
        {accounts.map((a) => (
          <Button key={a.id} size="sm" variant={a.id === acc.id ? "default" : "outline"} onClick={() => { setSel(a.id); setQr(""); }} data-testid={`wa-conn-select-${a.id}`}>{a.name}</Button>
        ))}
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <Card><CardContent className="p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-medium text-slate-700">Status Koneksi</span>
            <Badge variant="outline" className={connColor(acc.connection_status)} data-testid="wa-conn-status">{acc.connection_status}</Badge>
          </div>
          <div className="text-sm text-slate-500">Webhook: <Badge variant="outline">{acc.webhook_status}</Badge></div>
          <div className="flex flex-wrap gap-2 pt-2">
            <Button size="sm" onClick={() => act("connect")} disabled={!!busy} data-testid="wa-connect-btn">{busy === "connect" ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <PlugZap className="h-4 w-4 mr-1" />}Connect</Button>
            <Button size="sm" variant="outline" onClick={() => act("test")} disabled={!!busy} data-testid="wa-test-btn">{busy === "test" ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />}Test</Button>
            <Button size="sm" variant="outline" onClick={loadQr} disabled={!!busy} data-testid="wa-refresh-qr-btn"><QrCode className="h-4 w-4 mr-1" />Muat QR</Button>
            <Button size="sm" variant="destructive" onClick={() => act("disconnect")} disabled={!!busy} data-testid="wa-disconnect-btn"><Power className="h-4 w-4 mr-1" />Disconnect</Button>
          </div>
        </CardContent></Card>
        <Card><CardContent className="p-5">
          <div className="font-medium text-slate-700 mb-3 flex items-center gap-2"><QrCode className="h-4 w-4" />Scan QR Code</div>
          <div className="flex items-center justify-center h-56 bg-slate-50 rounded-lg border border-dashed">
            {busy === "qr" ? <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
              : qr ? <img src={qr} alt="WhatsApp QR" className="h-52 w-52 object-contain" data-testid="wa-qr-img" />
                : <span className="text-sm text-slate-400 text-center px-4">Klik "Connect" lalu "Muat QR" untuk menyambungkan WhatsApp.</span>}
          </div>
        </CardContent></Card>
      </div>
    </div>
  );
}

// ============================================================ Configuration
function ConfigTab({ accounts }) {
  const [sel, setSel] = useState("");
  const acc = accounts.find((a) => a.id === sel) || accounts[0];
  useEffect(() => { if (!sel && accounts[0]) setSel(accounts[0].id); }, [accounts, sel]);
  if (!acc) return <div className="text-slate-400 py-8 text-center" data-testid="wa-config-tab">Tambahkan akun terlebih dahulu di tab Accounts.</div>;
  const base = `${process.env.REACT_APP_BACKEND_URL}/api/whatsapp/webhook/${acc.id}`;
  const rows = [
    ["Nama Akun", acc.name], ["Base URL WAHA", acc.base_url || "—"], ["Session", acc.session],
    ["Engine", acc.engine], ["Webhook URL", base], ["Verify Token", acc.verify_token || "—"],
    ["HMAC Aktif", acc.has_hmac ? "Ya" : "Tidak"], ["API Key", acc.api_key_mask || "—"],
  ];
  const copy = (t) => { navigator.clipboard?.writeText(t); toast.success("Disalin"); };
  return (
    <div className="space-y-4" data-testid="wa-config-tab">
      <div className="flex flex-wrap items-center gap-2">
        {accounts.map((a) => (<Button key={a.id} size="sm" variant={a.id === acc.id ? "default" : "outline"} onClick={() => setSel(a.id)}>{a.name}</Button>))}
      </div>
      <Card><CardContent className="p-5 space-y-1">
        <p className="text-sm text-slate-500 mb-3">Gunakan Webhook URL & Verify Token berikut untuk mengonfigurasi WAHA/Meta.</p>
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-center justify-between py-2 border-b last:border-0 gap-3">
            <span className="text-sm text-slate-500 shrink-0">{k}</span>
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm font-mono text-slate-700 truncate" title={v}>{v}</span>
              {(k === "Webhook URL" || k === "Verify Token") && <Button size="sm" variant="ghost" onClick={() => copy(v)}>Salin</Button>}
            </div>
          </div>
        ))}
      </CardContent></Card>
    </div>
  );
}

// ============================================================ Conversation Monitor
function MonitorTab() {
  const [convs, setConvs] = useState(null);
  const [sel, setSel] = useState(null);
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
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
                  <div className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${m.sender === "CUSTOMER" ? "bg-white border" : m.sender === "AI" ? "bg-blue-100 text-blue-900" : "bg-emerald-100 text-emerald-900"}`}>
                    <div className="text-[10px] opacity-60 mb-0.5">{m.sender}{m.ai_generated ? " · AI" : ""}</div>
                    {m.content}
                    <div className="text-[10px] opacity-50 mt-0.5">{fmt(m.timestamp)}</div>
                  </div>
                </div>
              ))}
              {msgs.length === 0 && <div className="text-center text-slate-400 text-sm py-6">Belum ada pesan.</div>}
            </div>
            <div className="p-3 border-t flex gap-2">
              <Input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} placeholder="Ketik pesan manual..." data-testid="wa-msg-input" />
              <Button onClick={send} disabled={sending} data-testid="wa-msg-send">{sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}</Button>
            </div>
          </>)}
      </CardContent></Card>
    </div>
  );
}

// ============================================================ AI config (shared: Agent/Knowledge/Style/Rules)
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
        <div><div className="font-medium text-slate-800">AI Agent Aktif</div><div className="text-sm text-slate-500">Balas otomatis pesan customer memakai Gemini.</div></div>
        <Switch checked={!!cfg.enabled} onCheckedChange={(v) => setCfg({ ...cfg, enabled: v })} data-testid="wa-ai-enabled-switch" />
      </div>
      <div><Label>Pesan Sambutan (Greeting)</Label><Textarea rows={2} value={cfg.greeting || ""} onChange={(e) => setCfg({ ...cfg, greeting: e.target.value })} placeholder="Assalamualaikum, ada yang bisa kami bantu?" data-testid="wa-ai-greeting" /></div>
      <div><Label>Kata Kunci Handover (pisahkan koma)</Label>
        <Textarea rows={2} value={kw} onChange={(e) => setKw(e.target.value)} placeholder="sales, bicara dengan, komplain" data-testid="wa-ai-keywords" />
        <p className="text-xs text-slate-400 mt-1">Jika customer mengetik salah satu kata, percakapan langsung dialihkan ke sales (Human Handover).</p></div>
      <Button onClick={() => save({ enabled: cfg.enabled, greeting: cfg.greeting, handover_keywords: kw.split(",").map((s) => s.trim()).filter(Boolean) })} disabled={saving} data-testid="wa-ai-agent-save">{saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}Simpan Agent</Button>
    </div>
  );
  if (section === "knowledge") return (
    <div className="space-y-4 max-w-2xl" data-testid="wa-ai-knowledge-tab">
      <div><Label>Basis Pengetahuan AI</Label>
        <Textarea rows={12} value={cfg.knowledge || ""} onChange={(e) => setCfg({ ...cfg, knowledge: e.target.value })} placeholder="Info perusahaan, FAQ, kebijakan pembayaran, dokumen umroh, dsb." data-testid="wa-ai-knowledge" />
        <p className="text-xs text-slate-400 mt-1">Digunakan AI sebagai konteks tambahan (selain data paket CRM yang otomatis disertakan).</p></div>
      <Button onClick={() => save({ knowledge: cfg.knowledge })} disabled={saving} data-testid="wa-ai-knowledge-save">{saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}Simpan Knowledge</Button>
    </div>
  );
  if (section === "style") return (
    <div className="space-y-4 max-w-2xl" data-testid="wa-ai-style-tab">
      <div><Label>Gaya Bahasa AI</Label>
        <Textarea rows={6} value={cfg.style || ""} onChange={(e) => setCfg({ ...cfg, style: e.target.value })} placeholder="Ramah, sopan, profesional, jawab singkat dalam Bahasa Indonesia." data-testid="wa-ai-style" /></div>
      <Button onClick={() => save({ style: cfg.style })} disabled={saving} data-testid="wa-ai-style-save">{saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}Simpan Style</Button>
    </div>
  );
  return (
    <div className="space-y-4 max-w-2xl" data-testid="wa-ai-rules-tab">
      <div><Label>Aturan & Batasan AI</Label>
        <Textarea rows={6} value={cfg.rules || ""} onChange={(e) => setCfg({ ...cfg, rules: e.target.value })} placeholder="Jangan mengarang harga di luar data. Jika tidak yakin, serahkan ke sales." data-testid="wa-ai-rules" /></div>
      <Button onClick={() => save({ rules: cfg.rules })} disabled={saving} data-testid="wa-ai-rules-save">{saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}Simpan Rules</Button>
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
          <p className="text-sm text-slate-500">Percakapan yang dieskalasi ke sales. Aktifkan AI kembali setelah selesai ditangani.</p></div>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4 mr-1" />Muat Ulang</Button>
      </div>
      <Card><CardContent className="p-0">
        <Table>
          <TableHeader><TableRow><TableHead>Customer</TableHead><TableHead>Nomor</TableHead><TableHead>Sales</TableHead><TableHead>Aktivitas Terakhir</TableHead><TableHead>Aksi</TableHead></TableRow></TableHeader>
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

// ============================================================ Logs (WhatsApp + API)
function LogsTab({ kind }) {
  const [logs, setLogs] = useState(null);
  const load = useCallback(() => api.get("/whatsapp/logs", { params: { kind: kind === "api" ? "API" : "wa" } }).then((r) => setLogs(r.data)).catch(() => setLogs([])), [kind]);
  useEffect(() => { load(); }, [load]);
  if (logs === null) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  return (
    <div className="space-y-3" data-testid={`wa-${kind}-logs-tab`}>
      <div className="flex justify-end"><Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4 mr-1" />Muat Ulang</Button></div>
      <Card><CardContent className="p-0">
        <Table>
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
        </Table>
      </CardContent></Card>
    </div>
  );
}

// ============================================================ Main
const TABS = [
  ["accounts", "Accounts", Smartphone],
  ["connection", "Connection + QR", QrCode],
  ["config", "Configuration", Settings2],
  ["monitor", "Conversation Monitor", MessagesSquare],
  ["ai-agent", "AI Agent", Bot],
  ["ai-knowledge", "AI Knowledge", BookOpen],
  ["ai-style", "AI Style", Palette],
  ["ai-rules", "AI Rules", ShieldAlert],
  ["handover", "Human Handover", UserCog],
  ["wa-logs", "WhatsApp Logs", ScrollText],
  ["api-logs", "API Logs", Activity],
];

export default function WhatsAppIntegration() {
  const { user } = useAuth();
  const [tab, setTab] = useState("accounts");
  const [accounts, setAccounts] = useState([]);
  const [loadingAcc, setLoadingAcc] = useState(true);
  const [cfg, setCfg] = useState(null);

  const reloadAcc = useCallback(async () => {
    setLoadingAcc(true);
    try { const r = await api.get("/whatsapp/accounts"); setAccounts(r.data); } catch { setAccounts([]); } finally { setLoadingAcc(false); }
  }, []);
  useEffect(() => {
    if (user?.role !== "super_admin") return;
    reloadAcc();
    api.get("/whatsapp/ai-config").then((r) => setCfg(r.data)).catch(() => setCfg({}));
  }, [reloadAcc, user]);

  if (user?.role !== "super_admin") return <Navigate to="/dashboard" replace />;

  return (
    <div className="space-y-5" data-testid="whatsapp-integration-page">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-emerald-500/10 flex items-center justify-center"><MessageCircle className="h-6 w-6 text-emerald-600" /></div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">WhatsApp Integration</h1>
          <p className="text-sm text-slate-500">Kelola koneksi WAHA, AI Agent, dan pantau seluruh aktivitas WhatsApp.</p>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex flex-wrap h-auto gap-1" data-testid="wa-tabs-list">
          {TABS.map(([k, label, Icon]) => (
            <TabsTrigger key={k} value={k} className="text-xs" data-testid={`wa-tab-${k}`}><Icon className="h-3.5 w-3.5 mr-1" />{label}</TabsTrigger>
          ))}
        </TabsList>

        <div className="mt-4">
          <TabsContent value="accounts"><AccountsTab accounts={accounts} reload={reloadAcc} loading={loadingAcc} /></TabsContent>
          <TabsContent value="connection"><ConnectionTab accounts={accounts} reload={reloadAcc} /></TabsContent>
          <TabsContent value="config"><ConfigTab accounts={accounts} /></TabsContent>
          <TabsContent value="monitor"><MonitorTab /></TabsContent>
          <TabsContent value="ai-agent">{cfg ? <AiConfigTab cfg={cfg} setCfg={setCfg} section="agent" /> : <Loader2 className="h-6 w-6 animate-spin text-blue-600 mx-auto my-8" />}</TabsContent>
          <TabsContent value="ai-knowledge">{cfg ? <AiConfigTab cfg={cfg} setCfg={setCfg} section="knowledge" /> : <Loader2 className="h-6 w-6 animate-spin text-blue-600 mx-auto my-8" />}</TabsContent>
          <TabsContent value="ai-style">{cfg ? <AiConfigTab cfg={cfg} setCfg={setCfg} section="style" /> : <Loader2 className="h-6 w-6 animate-spin text-blue-600 mx-auto my-8" />}</TabsContent>
          <TabsContent value="ai-rules">{cfg ? <AiConfigTab cfg={cfg} setCfg={setCfg} section="rules" /> : <Loader2 className="h-6 w-6 animate-spin text-blue-600 mx-auto my-8" />}</TabsContent>
          <TabsContent value="handover"><HandoverTab /></TabsContent>
          <TabsContent value="wa-logs"><LogsTab kind="wa" /></TabsContent>
          <TabsContent value="api-logs"><LogsTab kind="api" /></TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
