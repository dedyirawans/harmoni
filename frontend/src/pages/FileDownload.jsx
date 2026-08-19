import { useEffect, useMemo, useState } from "react";
import api, { API, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { FolderDown, Loader2, Upload, Download, Pencil, Trash2, History, ClipboardList, FileText, Eye, Search, X } from "lucide-react";
import { toast } from "sonner";

const CATEGORIES = ["Price List", "Sales Material", "Product Information", "SOP", "Company Document", "Accounting Document", "Tax Document", "Training", "Other"];
const ACCESS_LABELS = {
  ALL_STAFF: "Semua Staff", SALES: "Sales", ACCOUNTING: "Accounting",
  SALES_ACCOUNTING: "Sales + Accounting", SPECIFIC: "User Tertentu",
};
const fmtDate = (s) => (s ? String(s).slice(0, 16).replace("T", " ") : "—");
const fmtSize = (n) => { const b = Number(n || 0); return b >= 1e6 ? (b / 1e6).toFixed(1) + " MB" : (b / 1e3).toFixed(0) + " KB"; };
const EMPTY = { file_name: "", description: "", category: "Other", version: "v1", access_type: "ALL_STAFF", allowed_user_ids: [] };
const isImg = (ct) => (ct || "").startsWith("image/");
const isPdf = (ct) => (ct || "").includes("pdf");

export default function FileDownload() {
  const { user } = useAuth();
  const isSA = user?.role === "super_admin";
  const [files, setFiles] = useState(null);
  const [meta, setMeta] = useState({ categories: [], access_types: [], users: [] });
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [toDelete, setToDelete] = useState(null);
  const [logs, setLogs] = useState(null);
  const [preview, setPreview] = useState(null);
  const [search, setSearch] = useState("");
  const [catFilter, setCatFilter] = useState("all");

  const load = () => api.get("/files").then((r) => setFiles(r.data)).catch(() => setFiles([]));
  useEffect(() => {
    load();
    if (isSA) api.get("/files/meta").then((r) => setMeta(r.data)).catch(() => {});
  }, [isSA]);

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));
  const toggleUser = (id) => setForm((f) => ({ ...f, allowed_user_ids: f.allowed_user_ids.includes(id) ? f.allowed_user_ids.filter((x) => x !== id) : [...f.allowed_user_ids, id] }));

  const filtered = useMemo(() => {
    let list = files || [];
    if (catFilter !== "all") list = list.filter((f) => f.category === catFilter);
    const s = search.trim().toLowerCase();
    if (s) list = list.filter((f) => (f.file_name || "").toLowerCase().includes(s) || (f.original_filename || "").toLowerCase().includes(s) || (f.description || "").toLowerCase().includes(s));
    return list;
  }, [files, catFilter, search]);

  const openCreate = () => { setEditing(null); setForm(EMPTY); setFile(null); setOpen(true); };
  const openEdit = (f) => { setEditing(f); setForm({ file_name: f.file_name, description: f.description || "", category: f.category, version: f.version, access_type: f.access_type, allowed_user_ids: f.allowed_user_ids || [] }); setFile(null); setOpen(true); };

  const save = async () => {
    if (!editing && !file) return toast.error("Pilih file untuk diunggah");
    if (!form.file_name.trim() && file) form.file_name = file.name;
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/files/${editing.id}`, { ...form, allowed_user_ids: form.allowed_user_ids });
        if (file) { const fd = new FormData(); fd.append("file", file); fd.append("version", form.version); await api.post(`/files/${editing.id}/replace`, fd); }
        toast.success("File diperbarui");
      } else {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("file_name", form.file_name || file.name);
        fd.append("description", form.description);
        fd.append("category", form.category);
        fd.append("version", form.version);
        fd.append("access_type", form.access_type);
        fd.append("allowed_user_ids", JSON.stringify(form.allowed_user_ids));
        await api.post("/files", fd);
        toast.success("File diunggah");
      }
      setOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  const fileUrl = (f, inline) => `${API}/files/${f.id}/download?auth=${localStorage.getItem("token")}${inline ? "&inline=1" : ""}`;
  const doDownload = (f) => { window.open(fileUrl(f, false), "_blank"); };
  const doDelete = async () => {
    try { await api.delete(`/files/${toDelete.id}`, { params: { reason: "Dihapus dari UI" } }); toast.success("File dihapus"); setToDelete(null); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const openLogs = () => { setLogs("loading"); api.get("/files/download-logs").then((r) => setLogs(r.data)).catch(() => setLogs([])); };

  if (files === null) return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;

  return (
    <div className="space-y-6" data-testid="documents-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900 flex items-center gap-2"><FolderDown className="h-7 w-7 text-blue-600" />Documents · File Download</h1>
          <p className="text-slate-500 mt-1">File internal perusahaan. Akses terbatas sesuai izin — bukan file publik.</p>
        </div>
        {isSA && (
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={openLogs} data-testid="view-logs-btn"><History className="h-4 w-4 mr-1" />Log Unduhan</Button>
            <Button className="bg-blue-600 hover:bg-blue-700" onClick={openCreate} data-testid="upload-file-btn"><Upload className="h-4 w-4 mr-1" />Upload File</Button>
          </div>
        )}
      </div>

      {/* Search + Category filter */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" aria-hidden="true" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari nama file atau deskripsi..." className="pl-9 pr-9" data-testid="file-search-input" />
          {search && <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600" data-testid="file-search-clear"><X className="h-4 w-4" /></button>}
        </div>
        <Select value={catFilter} onValueChange={setCatFilter}>
          <SelectTrigger className="w-full sm:w-56" data-testid="file-category-filter"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-white">
            <SelectItem value="all">Semua Kategori</SelectItem>
            {CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <Card className="border-slate-200 shadow-sm overflow-hidden">
        {filtered.length === 0 ? (
          <div className="p-12 text-center text-slate-500" data-testid="files-empty"><FileText className="h-8 w-8 mx-auto text-slate-300" /><p className="mt-2">{(files.length && (search || catFilter !== "all")) ? "Tidak ada file yang cocok dengan pencarian/filter." : "Belum ada file yang tersedia untuk Anda."}</p></div>
        ) : (
          <Table data-testid="files-table">
            <TableHeader><TableRow className="bg-slate-50">
              <TableHead>File</TableHead><TableHead>Kategori</TableHead><TableHead>Versi</TableHead>
              <TableHead>Diunggah Oleh</TableHead><TableHead>Tanggal</TableHead><TableHead>Akses</TableHead>
              <TableHead>Status</TableHead><TableHead className="text-right">Aksi</TableHead>
            </TableRow></TableHeader>
            <TableBody>{filtered.map((f) => (
              <TableRow key={f.id} data-testid={`file-row-${f.id}`}>
                <TableCell><div className="font-medium text-slate-900">{f.file_name}</div><div className="text-xs text-slate-400">{f.original_filename} · {fmtSize(f.size)}</div></TableCell>
                <TableCell><Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">{f.category}</Badge></TableCell>
                <TableCell className="font-mono text-slate-600">{f.version}</TableCell>
                <TableCell className="text-slate-600 text-sm">{f.uploaded_by}</TableCell>
                <TableCell className="text-slate-500 text-sm">{fmtDate(f.created_at)}</TableCell>
                <TableCell className="text-slate-600 text-sm">{ACCESS_LABELS[f.access_type] || f.access_type}{f.access_type === "SPECIFIC" && <span className="text-xs text-slate-400"> ({(f.allowed_user_ids || []).length})</span>}</TableCell>
                <TableCell><Badge variant="outline" className={f.status === "ACTIVE" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-500"}>{f.status}</Badge></TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  {(isImg(f.content_type) || isPdf(f.content_type)) && <Button size="icon" variant="ghost" onClick={() => setPreview(f)} data-testid={`preview-file-${f.id}`} title="Pratinjau"><Eye className="h-4 w-4 text-slate-600" /></Button>}
                  <Button size="icon" variant="ghost" onClick={() => doDownload(f)} data-testid={`download-file-${f.id}`} title="Unduh"><Download className="h-4 w-4 text-blue-600" /></Button>
                  {isSA && <Button size="icon" variant="ghost" onClick={() => openEdit(f)} data-testid={`edit-file-${f.id}`} title="Edit"><Pencil className="h-4 w-4 text-slate-600" /></Button>}
                  {isSA && <Button size="icon" variant="ghost" className="text-red-600" onClick={() => setToDelete(f)} data-testid={`delete-file-${f.id}`} title="Hapus"><Trash2 className="h-4 w-4" /></Button>}
                </TableCell>
              </TableRow>
            ))}</TableBody>
          </Table>
        )}
      </Card>

      {/* Preview dialog */}
      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="bg-white max-w-4xl" data-testid="file-preview-dialog">
          <DialogHeader><DialogTitle className="font-display truncate">{preview?.file_name}</DialogTitle><DialogDescription>Pratinjau — {preview?.category} · {preview?.version}</DialogDescription></DialogHeader>
          {preview && (
            <div className="w-full h-[70vh] bg-slate-50 rounded-md overflow-hidden flex items-center justify-center">
              {isImg(preview.content_type) ? (
                <img src={fileUrl(preview, true)} alt={preview.file_name} className="max-w-full max-h-full object-contain" data-testid="preview-image" />
              ) : isPdf(preview.content_type) ? (
                <iframe src={fileUrl(preview, true)} title="preview" className="w-full h-full border-0" data-testid="preview-pdf" />
              ) : (
                <p className="text-sm text-slate-500">Tipe file ini tidak dapat dipratinjau. Silakan unduh.</p>
              )}
            </div>
          )}
          <DialogFooter><Button variant="outline" onClick={() => doDownload(preview)} data-testid="preview-download-btn"><Download className="h-4 w-4 mr-1" />Unduh</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Upload / Edit dialog */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-white max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="file-dialog">
          <DialogHeader><DialogTitle className="font-display">{editing ? "Edit File" : "Upload File"}</DialogTitle><DialogDescription>File internal — atur nama, kategori, versi, dan izin akses.</DialogDescription></DialogHeader>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-2">
            <div className="space-y-1 sm:col-span-2">
              <Label className="text-xs">{editing ? "Ganti File (opsional — buat versi baru)" : "File *"}</Label>
              <Input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} data-testid="file-input"
                accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.ppt,.pptx,.jpg,.jpeg,.png,.zip" />
            </div>
            <div className="space-y-1 sm:col-span-2"><Label className="text-xs">Nama File</Label><Input value={form.file_name} onChange={(e) => set("file_name")(e.target.value)} placeholder="Price List Agustus 2026" data-testid="file-name-input" /></div>
            <div className="space-y-1 sm:col-span-2"><Label className="text-xs">Deskripsi</Label><Textarea value={form.description} onChange={(e) => set("description")(e.target.value)} data-testid="file-desc-input" /></div>
            <div className="space-y-1">
              <Label className="text-xs">Kategori</Label>
              <Select value={form.category} onValueChange={set("category")}>
                <SelectTrigger data-testid="file-category"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white">{(meta.categories || []).map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1"><Label className="text-xs">Versi</Label><Input value={form.version} onChange={(e) => set("version")(e.target.value)} data-testid="file-version-input" /></div>
            <div className="space-y-1 sm:col-span-2">
              <Label className="text-xs">Izin Akses</Label>
              <Select value={form.access_type} onValueChange={set("access_type")}>
                <SelectTrigger data-testid="file-access"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white">{(meta.access_types || []).map((a) => <SelectItem key={a} value={a}>{ACCESS_LABELS[a] || a}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            {form.access_type === "SPECIFIC" && (
              <div className="sm:col-span-2 border border-slate-200 rounded-md p-3 max-h-48 overflow-y-auto" data-testid="specific-users">
                <p className="text-xs text-slate-500 mb-2">Pilih user yang boleh mengunduh:</p>
                {(meta.users || []).map((u) => (
                  <label key={u.id} className="flex items-center gap-2 text-sm py-0.5">
                    <input type="checkbox" checked={form.allowed_user_ids.includes(u.id)} onChange={() => toggleUser(u.id)} data-testid={`user-opt-${u.id}`} />
                    {u.name} <span className="text-xs text-slate-400">({u.role})</span>
                  </label>
                ))}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Batal</Button>
            <Button className="bg-blue-600 hover:bg-blue-700" onClick={save} disabled={saving} data-testid="file-save-btn">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : editing ? "Simpan" : "Upload"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Download logs dialog */}
      <Dialog open={logs !== null} onOpenChange={(o) => !o && setLogs(null)}>
        <DialogContent className="bg-white max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="logs-dialog">
          <DialogHeader><DialogTitle className="font-display flex items-center gap-2"><ClipboardList className="h-5 w-5 text-blue-600" />Log Unduhan File</DialogTitle><DialogDescription>Riwayat siapa mengunduh/pratinjau file apa dan kapan.</DialogDescription></DialogHeader>
          {logs === "loading" ? <div className="p-8 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
            : (logs || []).length === 0 ? <p className="text-sm text-slate-400 text-center py-6">Belum ada log unduhan.</p>
            : (
            <Table data-testid="logs-table">
              <TableHeader><TableRow className="bg-slate-50"><TableHead>File</TableHead><TableHead>User</TableHead><TableHead>Role</TableHead><TableHead>Aksi</TableHead><TableHead>Waktu</TableHead><TableHead>IP</TableHead></TableRow></TableHeader>
              <TableBody>{(logs || []).map((l, i) => (
                <TableRow key={i}><TableCell className="font-medium">{l.file_name} <span className="text-xs text-slate-400">{l.version}</span></TableCell><TableCell>{l.user_name}</TableCell><TableCell><Badge variant="outline">{l.user_role}</Badge></TableCell><TableCell className="text-xs text-slate-500">{l.action}</TableCell><TableCell className="text-slate-500 text-sm">{fmtDate(l.timestamp)}</TableCell><TableCell className="text-xs text-slate-400">{l.ip || "—"}</TableCell></TableRow>
              ))}</TableBody>
            </Table>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <AlertDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <AlertDialogContent className="bg-white" data-testid="file-delete-dialog">
          <AlertDialogHeader><AlertDialogTitle>Hapus File</AlertDialogTitle><AlertDialogDescription>Apakah Anda yakin ingin menghapus file "{toDelete?.file_name}"?</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel>Batal</AlertDialogCancel><AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={doDelete} data-testid="file-delete-confirm">Hapus</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
