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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  MessageSquareHeart, Sparkles, Loader2, Plus, Pencil, Trash2, History,
  CheckCircle2, Star, Send, X,
} from "lucide-react";

const err = (e) => toast.error(formatApiErrorDetail(e?.response?.data?.detail) || "Terjadi kesalahan");
const fmt = (t) => (t || "—").toString().replace("T", " ").slice(0, 16);
const stColor = (s) =>
  s === "ACTIVE" ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : s === "DRAFT" ? "bg-amber-50 text-amber-700 border-amber-200"
      : "bg-slate-100 text-slate-600 border-slate-200";

const emptyProfile = (meta) => ({
  profile_name: "", language: "AUTO", tone: ["Friendly", "Professional", "Helpful"],
  formality: "", personality: "", greeting_style: "", closing_style: "",
  emoji_usage: "LIMITED", response_length: "MEDIUM", sales_style: "", brand_voice: "",
  examples: [], do_list: "", dont_list: "", status: "DRAFT",
});

// ============================================================ Profile editor
function ProfileDialog({ open, setOpen, meta, edit, onSaved }) {
  const [f, setF] = useState(emptyProfile(meta));
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (open) {
      if (edit) setF({ ...edit, do_list: (edit.do_list || []).join("\n"), dont_list: (edit.dont_list || []).join("\n"), examples: edit.examples || [] });
      else setF(emptyProfile(meta));
    }
  }, [open, edit, meta]);

  const toggleTone = (t) => setF((p) => ({ ...p, tone: p.tone.includes(t) ? p.tone.filter((x) => x !== t) : [...p.tone, t] }));
  const addEx = () => setF((p) => ({ ...p, examples: [...(p.examples || []), { customer: "", ideal_ai: "" }] }));
  const setEx = (i, k, v) => setF((p) => ({ ...p, examples: p.examples.map((e, idx) => idx === i ? { ...e, [k]: v } : e) }));
  const delEx = (i) => setF((p) => ({ ...p, examples: p.examples.filter((_, idx) => idx !== i) }));

  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...f };
      if (edit) await api.put(`/communication/profiles/${edit.id}`, payload);
      else await api.post("/communication/profiles", payload);
      toast.success(edit ? "Profil diperbarui" : "Profil dibuat");
      setOpen(false); onSaved();
    } catch (e) { err(e); } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-3xl" data-testid="comm-profile-dialog">
        <DialogHeader><DialogTitle>{edit ? "Edit Communication Profile" : "Profil Komunikasi Baru"}</DialogTitle>
          <DialogDescription>Atur gaya bicara, brand voice, contoh, dan aturan AI. Profil ACTIVE dipakai di WhatsApp & Test AI.</DialogDescription></DialogHeader>
        <div className="space-y-4 max-h-[68vh] overflow-y-auto pr-1">
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Nama Profil</Label><Input value={f.profile_name} onChange={(e) => setF({ ...f, profile_name: e.target.value })} data-testid="comm-name" /></div>
            <div><Label>Bahasa</Label>
              <Select value={f.language} onValueChange={(v) => setF({ ...f, language: v })}><SelectTrigger data-testid="comm-language"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="AUTO">Auto-detect (ID/EN)</SelectItem><SelectItem value="ID">Bahasa Indonesia</SelectItem><SelectItem value="EN">English</SelectItem></SelectContent></Select></div>
          </div>
          <div>
            <Label>Tone (pilih kombinasi)</Label>
            <div className="flex flex-wrap gap-2 mt-1" data-testid="comm-tones">
              {(meta.tones || []).map((t) => (
                <button key={t} type="button" onClick={() => toggleTone(t)} data-testid={`comm-tone-${t}`}
                  className={`px-3 py-1 rounded-full text-sm border transition-colors ${f.tone.includes(t) ? "bg-purple-600 text-white border-purple-600" : "bg-white text-slate-600 border-slate-200 hover:border-purple-300"}`}>{t}</button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div><Label>Emoji</Label>
              <Select value={f.emoji_usage} onValueChange={(v) => setF({ ...f, emoji_usage: v })}><SelectTrigger data-testid="comm-emoji"><SelectValue /></SelectTrigger>
                <SelectContent>{(meta.emoji || []).map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>Panjang Jawaban</Label>
              <Select value={f.response_length} onValueChange={(v) => setF({ ...f, response_length: v })}><SelectTrigger data-testid="comm-length"><SelectValue /></SelectTrigger>
                <SelectContent>{(meta.lengths || []).map((x) => <SelectItem key={x} value={x}>{x}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>Formality</Label><Input value={f.formality} onChange={(e) => setF({ ...f, formality: e.target.value })} placeholder="tidak terlalu formal" /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Personality</Label><Input value={f.personality} onChange={(e) => setF({ ...f, personality: e.target.value })} placeholder="ramah & membantu" /></div>
            <div><Label>Sales Style</Label><Input value={f.sales_style} onChange={(e) => setF({ ...f, sales_style: e.target.value })} placeholder="consultative, tidak memaksa" /></div>
          </div>
          <div><Label>Brand Voice — bagaimana perusahaan berbicara ke customer?</Label>
            <Textarea rows={3} value={f.brand_voice} onChange={(e) => setF({ ...f, brand_voice: e.target.value })} placeholder="Ramah, tidak kaku, profesional, tidak terlalu formal, mengutamakan pelayanan, tidak memaksa membeli." data-testid="comm-brandvoice" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Greeting Style</Label><Textarea rows={2} value={f.greeting_style} onChange={(e) => setF({ ...f, greeting_style: e.target.value })} placeholder="Halo Kak, terima kasih sudah menghubungi kami. Ada yang bisa dibantu?" data-testid="comm-greeting" /></div>
            <div><Label>Closing Style</Label><Textarea rows={2} value={f.closing_style} onChange={(e) => setF({ ...f, closing_style: e.target.value })} placeholder="Silakan Kak, kami siap membantu 🙏" /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>DO (satu per baris)</Label><Textarea rows={5} value={f.do_list} onChange={(e) => setF({ ...f, do_list: e.target.value })} placeholder={"gunakan \"Kak\"\njawab langsung\ntawarkan bantuan\nkonfirmasi sebelum booking"} data-testid="comm-do" /></div>
            <div><Label>DON'T (satu per baris)</Label><Textarea rows={5} value={f.dont_list} onChange={(e) => setF({ ...f, dont_list: e.target.value })} placeholder={"jangan terlalu formal\njangan pakai istilah teknis\njangan memaksa closing\njangan mengaku manusia"} data-testid="comm-dont" /></div>
          </div>
          <div>
            <div className="flex items-center justify-between mb-1"><Label>Contoh Komunikasi Ideal</Label>
              <Button size="sm" variant="outline" onClick={addEx} data-testid="comm-add-example"><Plus className="h-3.5 w-3.5 mr-1" />Tambah Contoh</Button></div>
            <div className="space-y-2">
              {(f.examples || []).map((e, i) => (
                <div key={i} className="p-3 rounded-lg border bg-slate-50 space-y-2" data-testid={`comm-example-${i}`}>
                  <div className="flex items-center justify-between"><span className="text-xs font-medium text-slate-500">Contoh #{i + 1}</span>
                    <button onClick={() => delEx(i)} className="text-red-500"><X className="h-4 w-4" /></button></div>
                  <Input value={e.customer} onChange={(ev) => setEx(i, "customer", ev.target.value)} placeholder="CUSTOMER: Pak, ada paket Jepang Oktober?" />
                  <Textarea rows={2} value={e.ideal_ai} onChange={(ev) => setEx(i, "ideal_ai", ev.target.value)} placeholder="IDEAL AI: Ada Kak. Untuk Oktober kami punya beberapa pilihan..." />
                </div>
              ))}
              {(f.examples || []).length === 0 && <p className="text-xs text-slate-400">Belum ada contoh.</p>}
            </div>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <input type="checkbox" id="comm-set-active" checked={f.status === "ACTIVE"} onChange={(e) => setF({ ...f, status: e.target.checked ? "ACTIVE" : "DRAFT" })} data-testid="comm-set-active" />
            <Label htmlFor="comm-set-active" className="cursor-pointer">Jadikan profil AKTIF (dipakai AI)</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>Batal</Button>
          <Button onClick={save} disabled={saving} data-testid="comm-save">{saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}Simpan</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================ Profiles tab
function ProfilesTab({ meta }) {
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState(null);
  const [verFor, setVerFor] = useState(null);
  const [versions, setVersions] = useState(null);
  const load = useCallback(() => api.get("/communication/profiles").then((r) => setRows(r.data)).catch(() => setRows([])), []);
  useEffect(() => { load(); }, [load]);

  const activate = async (p) => {
    try { await api.post(`/communication/profiles/${p.id}/activate`); toast.success(`"${p.profile_name}" diaktifkan`); load(); } catch (e) { err(e); }
  };
  const archive = async (p) => {
    if (!window.confirm(`Arsipkan profil "${p.profile_name}"?`)) return;
    try { await api.delete(`/communication/profiles/${p.id}`); toast.success("Diarsipkan"); load(); } catch (e) { err(e); }
  };
  const showVersions = async (p) => {
    setVerFor(p); setVersions(null);
    try { const r = await api.get(`/communication/profiles/${p.id}/versions`); setVersions(r.data); } catch (e) { err(e); }
  };

  return (
    <div className="space-y-4" data-testid="comm-profiles-tab">
      <div className="flex items-center justify-between">
        <div><h3 className="text-lg font-semibold text-slate-800">Communication Profiles</h3>
          <p className="text-sm text-slate-500">Profil ACTIVE dipakai AI di WhatsApp & Test AI. Perubahan menyimpan riwayat versi.</p></div>
        <Button onClick={() => { setEdit(null); setOpen(true); }} data-testid="comm-add-btn"><Plus className="h-4 w-4 mr-1" />Profil</Button>
      </div>
      {rows === null ? <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
        : rows.length === 0 ? <p className="text-slate-400 text-center py-8">Belum ada profil komunikasi.</p>
          : <div className="grid md:grid-cols-2 gap-3">
            {rows.map((p) => (
              <Card key={p.id} data-testid={`comm-card-${p.id}`} className={p.status === "ACTIVE" ? "border-emerald-300 shadow-sm" : ""}>
                <CardContent className="p-4 space-y-2">
                  <div className="flex items-start justify-between">
                    <div><div className="font-semibold text-slate-800 flex items-center gap-2">{p.profile_name}
                      {p.status === "ACTIVE" && <Star className="h-4 w-4 text-emerald-500 fill-emerald-500" />}</div>
                      <div className="text-xs text-slate-500 mt-0.5">v{p.version} · {p.updated_by || "—"} · {fmt(p.updated_at)}</div></div>
                    <Badge variant="outline" className={stColor(p.status)}>{p.status}</Badge>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    <Badge variant="outline" className="text-[10px]">{p.language}</Badge>
                    {(p.tone || []).map((t) => <Badge key={t} variant="outline" className="text-[10px] bg-purple-50 text-purple-700 border-purple-200">{t}</Badge>)}
                    <Badge variant="outline" className="text-[10px]">emoji {p.emoji_usage}</Badge>
                    <Badge variant="outline" className="text-[10px]">{p.response_length}</Badge>
                  </div>
                  {p.brand_voice && <p className="text-xs text-slate-500 line-clamp-2">{p.brand_voice}</p>}
                  <div className="flex flex-wrap gap-1 pt-1">
                    {p.status !== "ACTIVE" && <Button size="sm" onClick={() => activate(p)} data-testid={`comm-activate-${p.id}`}><CheckCircle2 className="h-3.5 w-3.5 mr-1" />Aktifkan</Button>}
                    <Button size="sm" variant="outline" onClick={() => { setEdit(p); setOpen(true); }} data-testid={`comm-edit-${p.id}`}><Pencil className="h-3.5 w-3.5 mr-1" />Edit</Button>
                    <Button size="sm" variant="outline" onClick={() => showVersions(p)} data-testid={`comm-versions-${p.id}`}><History className="h-3.5 w-3.5 mr-1" />Versi</Button>
                    <Button size="sm" variant="ghost" onClick={() => archive(p)} data-testid={`comm-archive-${p.id}`}><Trash2 className="h-3.5 w-3.5 text-red-500" /></Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>}

      <ProfileDialog open={open} setOpen={setOpen} meta={meta} edit={edit} onSaved={load} />

      <Dialog open={!!verFor} onOpenChange={(o) => !o && setVerFor(null)}>
        <DialogContent className="max-w-lg" data-testid="comm-versions-dialog">
          <DialogHeader><DialogTitle>Riwayat Versi — {verFor?.profile_name}</DialogTitle>
            <DialogDescription>Versi saat ini v{versions?.current_version}. Riwayat tidak pernah dihapus.</DialogDescription></DialogHeader>
          <div className="space-y-2 max-h-[60vh] overflow-y-auto">
            {versions === null ? <Loader2 className="h-5 w-5 animate-spin mx-auto text-blue-600" />
              : (versions.history || []).length === 0 ? <p className="text-sm text-slate-400 text-center py-4">Belum ada riwayat.</p>
                : versions.history.map((h, i) => (
                  <div key={i} className="p-3 rounded-lg border bg-slate-50 text-sm">
                    <div className="flex items-center justify-between mb-1"><Badge variant="outline">v{h.version}</Badge>
                      <span className="text-xs text-slate-500">{h.updated_by || "—"} · {fmt(h.updated_at)}</span></div>
                    <div className="text-slate-700">Tone: {(h.tone || []).join(", ") || "—"} · Bahasa {h.language} · emoji {h.emoji_usage}</div>
                    {h.brand_voice && <div className="text-slate-500 line-clamp-2 mt-1">{h.brand_voice}</div>}
                  </div>
                ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ============================================================ Preview tab
function PreviewTab({ meta }) {
  const [profiles, setProfiles] = useState([]);
  const [pid, setPid] = useState("active");
  const [msg, setMsg] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState(null);
  useEffect(() => { api.get("/communication/profiles").then((r) => setProfiles(r.data)).catch(() => setProfiles([])); }, []);

  const ask = async () => {
    if (!msg.trim()) return;
    setLoading(true); setRes(null);
    try {
      const body = { customer_message: msg, customer_name: name };
      if (pid !== "active") body.profile_id = pid;
      const r = await api.post("/communication/preview", body); setRes(r.data);
    } catch (e) { err(e); } finally { setLoading(false); }
  };
  const samples = ["Pak, ada paket Jepang Oktober?", "Halo, mau tanya paket Umrah dong", "Is there any tour package for December?"];
  return (
    <div className="grid md:grid-cols-2 gap-4" data-testid="comm-preview-tab">
      <Card><CardContent className="p-5 space-y-3">
        <div className="flex items-center gap-2 text-slate-800 font-medium"><Sparkles className="h-4 w-4 text-purple-600" />Communication Preview</div>
        <div><Label>Profil</Label>
          <Select value={pid} onValueChange={setPid}><SelectTrigger data-testid="comm-preview-profile"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="active">Profil AKTIF saat ini</SelectItem>{profiles.map((p) => <SelectItem key={p.id} value={p.id}>{p.profile_name} ({p.status})</SelectItem>)}</SelectContent></Select></div>
        <div><Label>Nama Customer (opsional)</Label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Budi" data-testid="comm-preview-name" /></div>
        <div><Label>Pesan Customer</Label><Textarea rows={4} value={msg} onChange={(e) => setMsg(e.target.value)} placeholder="Pak, ada paket Jepang Oktober?" data-testid="comm-preview-input" /></div>
        <div className="flex flex-wrap gap-1">{samples.map((s) => <button key={s} onClick={() => setMsg(s)} className="text-xs px-2 py-1 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-600">{s}</button>)}</div>
        <Button onClick={ask} disabled={loading} data-testid="comm-preview-ask">{loading ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Send className="h-4 w-4 mr-1" />}Tes Respons AI</Button>
      </CardContent></Card>
      <Card><CardContent className="p-5 space-y-3 min-h-[300px]">
        <div className="font-medium text-slate-800">Respons AI</div>
        {loading ? <div className="flex items-center justify-center h-40"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
          : !res ? <p className="text-sm text-slate-400">Respons AI dengan gaya komunikasi terpilih akan tampil di sini.</p>
            : (<div className="space-y-3">
              <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100" data-testid="comm-preview-answer">
                <div className="text-xs text-emerald-700 font-medium mb-1">AI Response{res.profile_used ? ` · gaya: ${res.profile_used}` : ""}</div>
                <div className="text-sm text-slate-800 whitespace-pre-wrap">{res.answer}</div>
              </div>
              <div className="text-xs text-slate-500">Paket dipakai: {res.package_used?.length || 0} · Knowledge dipakai: {res.knowledge_used?.length || 0}</div>
            </div>)}
      </CardContent></Card>
    </div>
  );
}

// ============================================================ Main
export default function CommunicationStyle() {
  const { user } = useAuth();
  const [tab, setTab] = useState("profiles");
  const [meta, setMeta] = useState({ tones: [], emoji: [], lengths: [], languages: [] });
  useEffect(() => {
    if (user?.role !== "super_admin") return;
    api.get("/communication/meta").then((r) => setMeta(r.data)).catch(() => {});
  }, [user]);
  if (user?.role !== "super_admin") return <Navigate to="/dashboard" replace />;

  return (
    <div className="space-y-5" data-testid="communication-style-page">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-purple-500/10 flex items-center justify-center"><MessageSquareHeart className="h-6 w-6 text-purple-600" /></div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">AI Communication Style</h1>
          <p className="text-sm text-slate-500">Atur kepribadian & brand voice agar AI berbicara sesuai gaya perusahaan.</p>
        </div>
      </div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList data-testid="comm-tabs-list">
          <TabsTrigger value="profiles" data-testid="comm-tab-profiles"><MessageSquareHeart className="h-4 w-4 mr-1.5" />Profiles</TabsTrigger>
          <TabsTrigger value="preview" data-testid="comm-tab-preview"><Sparkles className="h-4 w-4 mr-1.5" />Preview</TabsTrigger>
        </TabsList>
        <div className="mt-4">
          <TabsContent value="profiles"><ProfilesTab meta={meta} /></TabsContent>
          <TabsContent value="preview"><PreviewTab meta={meta} /></TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
