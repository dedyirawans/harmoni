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
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  BrainCircuit, FileText, HelpCircle, Package, Sparkles, Loader2, Plus, Pencil,
  Trash2, History, RefreshCw, Send, CheckCircle2, ChevronDown, ChevronRight,
} from "lucide-react";

const err = (e) => toast.error(formatApiErrorDetail(e?.response?.data?.detail) || "Terjadi kesalahan");
const fmt = (t) => (t || "—").toString().replace("T", " ").slice(0, 16);
const rupiah = (n) => "Rp" + (Number(n) || 0).toLocaleString("id-ID");
const stColor = (s) =>
  s === "ACTIVE" ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : s === "DRAFT" ? "bg-amber-50 text-amber-700 border-amber-200"
      : s === "INACTIVE" ? "bg-slate-100 text-slate-600 border-slate-200"
        : "bg-red-50 text-red-700 border-red-200";

// ============================================================ Articles
function ArticlesTab({ categories, statuses }) {
  const [rows, setRows] = useState(null);
  const [fCat, setFCat] = useState("all");
  const [fStatus, setFStatus] = useState("all");
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [verFor, setVerFor] = useState(null);
  const [versions, setVersions] = useState(null);

  const load = useCallback(() => {
    const params = {};
    if (fCat !== "all") params.category = fCat;
    if (fStatus !== "all") params.status = fStatus;
    api.get("/knowledge/articles", { params }).then((r) => setRows(r.data)).catch(() => setRows([]));
  }, [fCat, fStatus]);
  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEdit(null); setForm({ category: "PRODUCT", status: "DRAFT", priority: 0 }); setOpen(true); };
  const openEdit = (a) => { setEdit(a); setForm({ title: a.title, category: a.category, content: a.content, status: a.status, priority: a.priority || 0, effective_from: a.effective_from || "", effective_until: a.effective_until || "" }); setOpen(true); };
  const save = async () => {
    setSaving(true);
    try {
      if (edit) await api.put(`/knowledge/articles/${edit.id}`, form);
      else await api.post("/knowledge/articles", form);
      toast.success(edit ? "Artikel diperbarui" : "Artikel dibuat");
      setOpen(false); load();
    } catch (e) { err(e); } finally { setSaving(false); }
  };
  const archive = async (a) => {
    if (!window.confirm(`Arsipkan artikel "${a.title}"?`)) return;
    try { await api.delete(`/knowledge/articles/${a.id}`, { params: { reason: "archived from UI" } }); toast.success("Diarsipkan"); load(); }
    catch (e) { err(e); }
  };
  const showVersions = async (a) => {
    setVerFor(a); setVersions(null);
    try { const r = await api.get(`/knowledge/articles/${a.id}/versions`); setVersions(r.data); } catch (e) { err(e); }
  };

  return (
    <div className="space-y-4" data-testid="kb-articles-tab">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-800">Knowledge Articles</h3>
          <p className="text-sm text-slate-500">Kelola artikel pengetahuan untuk AI. Perubahan menyimpan riwayat versi.</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={fCat} onValueChange={setFCat}><SelectTrigger className="w-44" data-testid="kb-filter-category"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">Semua Kategori</SelectItem>{categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select>
          <Select value={fStatus} onValueChange={setFStatus}><SelectTrigger className="w-36" data-testid="kb-filter-status"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">Semua Status</SelectItem>{statuses.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select>
          <Button onClick={openNew} data-testid="kb-add-article-btn"><Plus className="h-4 w-4 mr-1" />Artikel</Button>
        </div>
      </div>
      <Card><CardContent className="p-0">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Judul</TableHead><TableHead>Kategori</TableHead><TableHead>Prioritas</TableHead>
            <TableHead>Status</TableHead><TableHead>Efektif</TableHead><TableHead>Versi</TableHead><TableHead>Aksi</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {rows === null ? (<TableRow><TableCell colSpan={7} className="text-center py-8"><Loader2 className="h-5 w-5 animate-spin mx-auto text-blue-600" /></TableCell></TableRow>)
              : rows.length === 0 ? (<TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-400">Belum ada artikel.</TableCell></TableRow>)
                : rows.map((a) => (
                  <TableRow key={a.id} data-testid={`kb-article-row-${a.id}`}>
                    <TableCell className="font-medium max-w-[240px] truncate" title={a.title}>{a.title}</TableCell>
                    <TableCell><Badge variant="outline">{a.category}</Badge></TableCell>
                    <TableCell>{a.priority || 0}</TableCell>
                    <TableCell><Badge variant="outline" className={stColor(a.status)}>{a.status}</Badge>{a.status === "ACTIVE" && !a.is_effective_now && <span className="ml-1 text-[10px] text-amber-600">(di luar tanggal)</span>}</TableCell>
                    <TableCell className="text-xs text-slate-500">{a.effective_from || "—"} → {a.effective_until || "∞"}</TableCell>
                    <TableCell>v{a.version || 1}</TableCell>
                    <TableCell className="flex gap-1">
                      <Button size="icon" variant="ghost" onClick={() => openEdit(a)} data-testid={`kb-edit-article-${a.id}`}><Pencil className="h-4 w-4" /></Button>
                      <Button size="icon" variant="ghost" onClick={() => showVersions(a)} data-testid={`kb-versions-${a.id}`}><History className="h-4 w-4 text-blue-600" /></Button>
                      <Button size="icon" variant="ghost" onClick={() => archive(a)} data-testid={`kb-archive-article-${a.id}`}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </CardContent></Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl" data-testid="kb-article-dialog">
          <DialogHeader><DialogTitle>{edit ? "Edit Artikel" : "Artikel Baru"}</DialogTitle>
            <DialogDescription>AI hanya memakai artikel berstatus ACTIVE yang berada dalam rentang tanggal efektif.</DialogDescription></DialogHeader>
          <div className="space-y-3 max-h-[65vh] overflow-y-auto pr-1">
            <div><Label>Judul</Label><Input value={form.title || ""} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="kb-article-title" /></div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label>Kategori</Label>
                <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}><SelectTrigger data-testid="kb-article-category"><SelectValue /></SelectTrigger>
                  <SelectContent>{categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select></div>
              <div><Label>Status</Label>
                <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}><SelectTrigger data-testid="kb-article-status"><SelectValue /></SelectTrigger>
                  <SelectContent>{statuses.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
              <div><Label>Prioritas</Label><Input type="number" value={form.priority ?? 0} onChange={(e) => setForm({ ...form, priority: e.target.value })} data-testid="kb-article-priority" /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Efektif Dari</Label><Input type="date" value={form.effective_from || ""} onChange={(e) => setForm({ ...form, effective_from: e.target.value })} data-testid="kb-article-from" /></div>
              <div><Label>Efektif Sampai</Label><Input type="date" value={form.effective_until || ""} onChange={(e) => setForm({ ...form, effective_until: e.target.value })} data-testid="kb-article-until" /></div>
            </div>
            <div><Label>Konten</Label><Textarea rows={8} value={form.content || ""} onChange={(e) => setForm({ ...form, content: e.target.value })} data-testid="kb-article-content" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Batal</Button>
            <Button onClick={save} disabled={saving} data-testid="kb-article-save">{saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}Simpan</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!verFor} onOpenChange={(o) => !o && setVerFor(null)}>
        <DialogContent className="max-w-lg" data-testid="kb-versions-dialog">
          <DialogHeader><DialogTitle>Riwayat Versi — {verFor?.title}</DialogTitle>
            <DialogDescription>Versi saat ini: v{versions?.current_version}. Riwayat tidak pernah dihapus.</DialogDescription></DialogHeader>
          <div className="space-y-2 max-h-[60vh] overflow-y-auto">
            {versions === null ? <Loader2 className="h-5 w-5 animate-spin mx-auto text-blue-600" />
              : (versions.history || []).length === 0 ? <p className="text-sm text-slate-400 text-center py-4">Belum ada riwayat perubahan.</p>
                : versions.history.map((h, i) => (
                  <div key={i} className="p-3 rounded-lg border bg-slate-50 text-sm">
                    <div className="flex items-center justify-between mb-1">
                      <Badge variant="outline">v{h.version}</Badge>
                      <span className="text-xs text-slate-500">{h.updated_by || "—"} · {fmt(h.updated_at)}</span>
                    </div>
                    <div className="text-slate-700 line-clamp-3 whitespace-pre-wrap">{h.content}</div>
                  </div>
                ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ============================================================ FAQ
function FaqTab({ categories }) {
  const [rows, setRows] = useState(null);
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const load = useCallback(() => api.get("/knowledge/faqs").then((r) => setRows(r.data)).catch(() => setRows([])), []);
  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEdit(null); setForm({ category: "FAQ", status: "ACTIVE", keywords: "" }); setOpen(true); };
  const openEdit = (f) => { setEdit(f); setForm({ question: f.question, answer: f.answer, category: f.category, status: f.status, keywords: (f.keywords || []).join(", ") }); setOpen(true); };
  const save = async () => {
    setSaving(true);
    try {
      if (edit) await api.put(`/knowledge/faqs/${edit.id}`, form);
      else await api.post("/knowledge/faqs", form);
      toast.success(edit ? "FAQ diperbarui" : "FAQ dibuat"); setOpen(false); load();
    } catch (e) { err(e); } finally { setSaving(false); }
  };
  const remove = async (f) => {
    if (!window.confirm("Hapus FAQ ini?")) return;
    try { await api.delete(`/knowledge/faqs/${f.id}`); toast.success("Dihapus"); load(); } catch (e) { err(e); }
  };

  return (
    <div className="space-y-4" data-testid="kb-faq-tab">
      <div className="flex items-center justify-between">
        <div><h3 className="text-lg font-semibold text-slate-800">FAQ</h3>
          <p className="text-sm text-slate-500">Pertanyaan umum. AI menjawab berdasarkan data paket aktual + FAQ aktif.</p></div>
        <Button onClick={openNew} data-testid="kb-add-faq-btn"><Plus className="h-4 w-4 mr-1" />FAQ</Button>
      </div>
      <Card><CardContent className="p-0">
        <Table>
          <TableHeader><TableRow><TableHead>Pertanyaan</TableHead><TableHead>Kategori</TableHead><TableHead>Keywords</TableHead><TableHead>Status</TableHead><TableHead>Aksi</TableHead></TableRow></TableHeader>
          <TableBody>
            {rows === null ? (<TableRow><TableCell colSpan={5} className="text-center py-8"><Loader2 className="h-5 w-5 animate-spin mx-auto text-blue-600" /></TableCell></TableRow>)
              : rows.length === 0 ? (<TableRow><TableCell colSpan={5} className="text-center py-8 text-slate-400">Belum ada FAQ.</TableCell></TableRow>)
                : rows.map((f) => (
                  <TableRow key={f.id} data-testid={`kb-faq-row-${f.id}`}>
                    <TableCell className="font-medium max-w-[280px] truncate" title={f.question}>{f.question}</TableCell>
                    <TableCell><Badge variant="outline">{f.category}</Badge></TableCell>
                    <TableCell className="text-xs text-slate-500 max-w-[160px] truncate">{(f.keywords || []).join(", ") || "—"}</TableCell>
                    <TableCell><Badge variant="outline" className={stColor(f.status)}>{f.status}</Badge></TableCell>
                    <TableCell className="flex gap-1">
                      <Button size="icon" variant="ghost" onClick={() => openEdit(f)} data-testid={`kb-edit-faq-${f.id}`}><Pencil className="h-4 w-4" /></Button>
                      <Button size="icon" variant="ghost" onClick={() => remove(f)} data-testid={`kb-delete-faq-${f.id}`}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </CardContent></Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-xl" data-testid="kb-faq-dialog">
          <DialogHeader><DialogTitle>{edit ? "Edit FAQ" : "FAQ Baru"}</DialogTitle>
            <DialogDescription>Contoh: "Apakah harga sudah termasuk visa?"</DialogDescription></DialogHeader>
          <div className="space-y-3">
            <div><Label>Pertanyaan</Label><Input value={form.question || ""} onChange={(e) => setForm({ ...form, question: e.target.value })} data-testid="kb-faq-question" /></div>
            <div><Label>Jawaban</Label><Textarea rows={4} value={form.answer || ""} onChange={(e) => setForm({ ...form, answer: e.target.value })} data-testid="kb-faq-answer" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Kategori</Label>
                <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}><SelectTrigger data-testid="kb-faq-category"><SelectValue /></SelectTrigger>
                  <SelectContent>{categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select></div>
              <div><Label>Status</Label>
                <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}><SelectTrigger data-testid="kb-faq-status"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="ACTIVE">ACTIVE</SelectItem><SelectItem value="INACTIVE">INACTIVE</SelectItem></SelectContent></Select></div>
            </div>
            <div><Label>Keywords (pisahkan koma)</Label><Input value={form.keywords || ""} onChange={(e) => setForm({ ...form, keywords: e.target.value })} placeholder="visa, harga, termasuk" data-testid="kb-faq-keywords" /></div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Batal</Button>
            <Button onClick={save} disabled={saving} data-testid="kb-faq-save">{saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}Simpan</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ============================================================ Package Knowledge
function PackagesTab() {
  const [rows, setRows] = useState(null);
  const [openId, setOpenId] = useState(null);
  useEffect(() => { api.get("/knowledge/packages").then((r) => setRows(r.data)).catch(() => setRows([])); }, []);
  if (rows === null) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  return (
    <div className="space-y-3" data-testid="kb-packages-tab">
      <div className="p-3 rounded-lg bg-blue-50 border border-blue-100 text-sm text-blue-800">
        Data ini dibaca langsung dari <b>Package Master CRM</b> (single source of truth). AI selalu memakai data terkini di sini — tidak ada database paket terpisah.
      </div>
      {rows.length === 0 ? <p className="text-slate-400 text-center py-8">Belum ada paket aktif.</p>
        : rows.map((p) => (
          <Card key={p.id} data-testid={`kb-package-${p.id}`}>
            <CardContent className="p-4">
              <button className="w-full flex items-center justify-between text-left" onClick={() => setOpenId(openId === p.id ? null : p.id)}>
                <div>
                  <div className="font-semibold text-slate-800">{p.package_name} <span className="text-xs text-slate-400">[{p.package_code}]</span></div>
                  <div className="text-xs text-slate-500 mt-0.5">{p.package_type || "—"} · {p.destination || "—"} · {p.duration || "—"} · dasar {rupiah(p.selling_price)}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className={stColor(p.status === "ACTIVE" ? "ACTIVE" : "INACTIVE")}>{p.status}</Badge>
                  {openId === p.id ? <ChevronDown className="h-4 w-4 text-slate-400" /> : <ChevronRight className="h-4 w-4 text-slate-400" />}
                </div>
              </button>
              {openId === p.id && (
                <div className="mt-3 pt-3 border-t space-y-2 text-sm">
                  {p.description && <div><span className="text-slate-500">Deskripsi: </span>{p.description}</div>}
                  {p.terms && <div><span className="text-slate-500">Terms: </span><span className="whitespace-pre-wrap">{p.terms}</span></div>}
                  <div className="font-medium text-slate-700 mt-1">Jadwal Keberangkatan</div>
                  {(p.departures || []).length === 0 ? <p className="text-slate-400 text-xs">Belum ada jadwal.</p>
                    : <Table><TableHeader><TableRow><TableHead>Berangkat</TableHead><TableHead>Kembali</TableHead><TableHead>Harga</TableHead><TableHead>Sisa Kursi</TableHead><TableHead>Hotel</TableHead><TableHead>Maskapai</TableHead></TableRow></TableHeader>
                      <TableBody>{p.departures.map((d, i) => (
                        <TableRow key={i}><TableCell>{d.departure_date || "—"}</TableCell><TableCell>{d.return_date || "—"}</TableCell><TableCell>{rupiah(d.price)}</TableCell>
                          <TableCell>{d.available_seat ?? "—"}</TableCell><TableCell>{d.hotel || "—"}</TableCell><TableCell>{d.airline || "—"}</TableCell></TableRow>
                      ))}</TableBody></Table>}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
    </div>
  );
}

// ============================================================ Test AI
function TestAiTab() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState(null);
  const ask = async () => {
    if (!q.trim()) return;
    setLoading(true); setRes(null);
    try { const r = await api.post("/knowledge/test-ai", { question: q }); setRes(r.data); }
    catch (e) { err(e); } finally { setLoading(false); }
  };
  const samples = ["Apakah paket Umrah masih tersedia?", "Apakah harga sudah termasuk visa?", "Berapa harga paket termurah?"];
  return (
    <div className="grid md:grid-cols-2 gap-4" data-testid="kb-testai-tab">
      <Card><CardContent className="p-5 space-y-3">
        <div className="flex items-center gap-2 text-slate-800 font-medium"><Sparkles className="h-4 w-4 text-purple-600" />Test AI Knowledge</div>
        <p className="text-sm text-slate-500">Ketik pertanyaan seperti customer. AI menjawab HANYA dari data paket & knowledge aktif.</p>
        <Textarea rows={4} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Apakah paket Umrah Desember masih tersedia?" data-testid="kb-testai-input" />
        <div className="flex flex-wrap gap-1">{samples.map((s) => <button key={s} onClick={() => setQ(s)} className="text-xs px-2 py-1 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-600">{s}</button>)}</div>
        <Button onClick={ask} disabled={loading} data-testid="kb-testai-ask">{loading ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Send className="h-4 w-4 mr-1" />}Tanya AI</Button>
      </CardContent></Card>
      <Card><CardContent className="p-5 space-y-3 min-h-[300px]">
        <div className="font-medium text-slate-800">Hasil</div>
        {loading ? <div className="flex items-center justify-center h-40"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
          : !res ? <p className="text-sm text-slate-400">Jawaban AI akan tampil di sini.</p>
            : (<div className="space-y-3">
              <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100" data-testid="kb-testai-answer">
                <div className="text-xs text-emerald-700 font-medium mb-1 flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5" />Answer</div>
                <div className="text-sm text-slate-800 whitespace-pre-wrap">{res.answer}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-slate-600 mb-1">Package Used ({res.package_used?.length || 0})</div>
                <div className="flex flex-wrap gap-1">{(res.package_used || []).slice(0, 20).map((p) => <Badge key={p.id} variant="outline" className="text-[10px]">{p.package_code || p.package_name}</Badge>)}
                  {(res.package_used || []).length === 0 && <span className="text-xs text-slate-400">—</span>}</div>
              </div>
              <div>
                <div className="text-xs font-medium text-slate-600 mb-1">Knowledge Used ({res.knowledge_used?.length || 0})</div>
                <div className="flex flex-wrap gap-1">{(res.knowledge_used || []).slice(0, 30).map((k) => <Badge key={k.id} variant="outline" className="text-[10px] bg-blue-50 text-blue-700 border-blue-200">{k.type}: {k.title?.slice(0, 30)}</Badge>)}
                  {(res.knowledge_used || []).length === 0 && <span className="text-xs text-slate-400">—</span>}</div>
              </div>
            </div>)}
      </CardContent></Card>
    </div>
  );
}

// ============================================================ Main
const TABS = [
  ["articles", "Articles", FileText],
  ["faq", "FAQ", HelpCircle],
  ["packages", "Package Knowledge", Package],
  ["testai", "Test AI", Sparkles],
];

export default function KnowledgeBase() {
  const { user } = useAuth();
  const [tab, setTab] = useState("articles");
  const [cats, setCats] = useState([]);
  const [statuses, setStatuses] = useState(["DRAFT", "ACTIVE", "INACTIVE", "ARCHIVED"]);

  useEffect(() => {
    if (user?.role !== "super_admin") return;
    api.get("/knowledge/categories").then((r) => { setCats(r.data.categories || []); setStatuses(r.data.article_statuses || statuses); }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  if (user?.role !== "super_admin") return <Navigate to="/dashboard" replace />;

  return (
    <div className="space-y-5" data-testid="knowledge-base-page">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-purple-500/10 flex items-center justify-center"><BrainCircuit className="h-6 w-6 text-purple-600" /></div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">AI Knowledge Base</h1>
          <p className="text-sm text-slate-500">Ajarkan AI tentang produk, paket, kebijakan, dan FAQ perusahaan.</p>
        </div>
      </div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList data-testid="kb-tabs-list">
          {TABS.map(([k, label, Icon]) => (
            <TabsTrigger key={k} value={k} data-testid={`kb-tab-${k}`}><Icon className="h-4 w-4 mr-1.5" />{label}</TabsTrigger>
          ))}
        </TabsList>
        <div className="mt-4">
          <TabsContent value="articles"><ArticlesTab categories={cats} statuses={statuses} /></TabsContent>
          <TabsContent value="faq"><FaqTab categories={cats} /></TabsContent>
          <TabsContent value="packages"><PackagesTab /></TabsContent>
          <TabsContent value="testai"><TestAiTab /></TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
