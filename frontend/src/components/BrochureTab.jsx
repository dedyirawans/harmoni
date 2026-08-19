import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Loader2, Upload, Download, Trash2, Sparkles, FileText, FileType2, ImagePlus, Eye, FileImage, RefreshCw, Star } from "lucide-react";
import { toast } from "sonner";

export function BrochureTab({ pkgId, canManage }) {
  const [items, setItems] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [gen, setGen] = useState({ theme: "", highlights: "", promo: "", cta: "", extra: "" });
  const [variants, setVariants] = useState("1");
  const [logoPos, setLogoPos] = useState("top-right");
  const [wm, setWm] = useState({ logo_scale: 0.12, logo_opacity: 180 });
  const [busyId, setBusyId] = useState(null);
  const [refIds, setRefIds] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [pdfGen, setPdfGen] = useState(false);
  const [preview, setPreview] = useState(null);

  const load = useCallback(() => api.get(`/packages/${pkgId}/brochures`).then((r) => setItems(r.data)).catch(() => setItems([])), [pkgId]);
  useEffect(() => { load(); }, [load]);

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api.post(`/packages/${pkgId}/brochures`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("File berhasil diunggah");
      await load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Gagal mengunggah"); }
    finally { setUploading(false); e.target.value = ""; }
  };

  const download = async (b, format) => {
    try {
      const q = format ? `?format=${format}` : "";
      const r = await api.get(`/brochures/${b.id}/download${q}`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      const base = (b.filename || "brosur").replace(/\.[^.]+$/, "");
      a.href = url;
      a.download = format === "pdf" ? `${base}.pdf` : (b.filename || "brosur");
      a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error("Gagal mengunduh"); }
  };

  const remove = async (b) => {
    if (!window.confirm("Hapus brosur ini?")) return;
    try { await api.delete(`/brochures/${b.id}`); toast.success("Brosur dihapus"); await load(); }
    catch { toast.error("Gagal menghapus"); }
  };

  const toggleRef = (id) => setRefIds((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));

  const generate = async () => {
    setGenerating(true);
    try {
      const res = await api.post(`/packages/${pkgId}/brochures/generate-infographic`, { ...gen, ...wm, variants: Number(variants), logo_position: logoPos, reference_ids: refIds });
      toast.success(`${res.data.length} varian brosur dibuat AI`);
      await load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Gagal generate brosur AI"); }
    finally { setGenerating(false); }
  };

  const generatePdf = async () => {
    setPdfGen(true);
    try {
      await api.post(`/packages/${pkgId}/brochures/generate-pdf`, { ...gen, ...wm, logo_position: logoPos, reference_ids: refIds });
      toast.success("Brosur PDF dibuat");
      await load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Gagal membuat PDF"); }
    finally { setPdfGen(false); }
  };

  const regenerate = async (b) => {
    setBusyId(b.id);
    try {
      await api.post(`/brochures/${b.id}/regenerate`, { ...wm, logo_position: logoPos });
      toast.success("Brosur diregenerate");
      await load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Gagal regenerate"); }
    finally { setBusyId(null); }
  };

  const setPrimary = async (b) => {
    setBusyId(b.id);
    try {
      await api.post(`/brochures/${b.id}/set-primary`);
      toast.success("Dijadikan brosur utama (cover & default WhatsApp)");
      await load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Gagal set utama"); }
    finally { setBusyId(null); }
  };

  if (items === null) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;

  const busy = generating || pdfGen;
  const imageItems = items.filter((b) => b.is_image);

  return (
    <div className="space-y-4" data-testid="brochure-tab">
      {canManage && (
        <Card className="border-slate-200"><CardContent className="p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-800"><Sparkles className="h-4 w-4 text-indigo-600" /> Generate Brosur (AI · Nano Banana)</div>
          <p className="text-xs text-slate-500">Data paket (nama, harga, durasi, destinasi) dipakai otomatis. Logo agency (dari Settings) ditempel di bagian atas gambar.</p>
          <div className="grid sm:grid-cols-2 gap-3">
            <div><Label className="text-xs">Tema / Nuansa Warna</Label><Input value={gen.theme} onChange={(e) => setGen({ ...gen, theme: e.target.value })} placeholder="mis. hijau elegan aksen emas" data-testid="gen-theme" /></div>
            <div><Label className="text-xs">Promo / Diskon</Label><Input value={gen.promo} onChange={(e) => setGen({ ...gen, promo: e.target.value })} placeholder="mis. Early bird diskon 10%" data-testid="gen-promo" /></div>
            <div className="sm:col-span-2"><Label className="text-xs">Highlight Fasilitas</Label><Textarea rows={2} value={gen.highlights} onChange={(e) => setGen({ ...gen, highlights: e.target.value })} placeholder="mis. Hotel bintang 5 dekat Masjidil Haram, maskapai Saudia" data-testid="gen-highlights" /></div>
            <div><Label className="text-xs">Ajakan (CTA)</Label><Input value={gen.cta} onChange={(e) => setGen({ ...gen, cta: e.target.value })} placeholder="mis. Booking sekarang: WA 0812-xxxx" data-testid="gen-cta" /></div>
            <div><Label className="text-xs">Catatan Tambahan</Label><Input value={gen.extra} onChange={(e) => setGen({ ...gen, extra: e.target.value })} placeholder="opsional" data-testid="gen-extra" /></div>
            <div><Label className="text-xs">Jumlah Varian</Label>
              <Select value={variants} onValueChange={setVariants}>
                <SelectTrigger data-testid="gen-variants"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="1">1 varian</SelectItem>
                  <SelectItem value="2">2 varian (beda gaya)</SelectItem>
                  <SelectItem value="3">3 varian (beda gaya)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div><Label className="text-xs">Posisi Logo</Label>
              <Select value={logoPos} onValueChange={setLogoPos}>
                <SelectTrigger data-testid="gen-logo-pos"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="top-left">Atas Kiri</SelectItem>
                  <SelectItem value="top-center">Atas Tengah</SelectItem>
                  <SelectItem value="top-right">Atas Kanan</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div><Label className="text-xs">Ukuran Logo (%)</Label><Input type="number" min="5" max="40" value={Math.round(wm.logo_scale * 100)} onChange={(e) => setWm({ ...wm, logo_scale: Math.min(0.4, Math.max(0.05, (Number(e.target.value) || 12) / 100)) })} data-testid="gen-logo-scale" /></div>
            <div><Label className="text-xs">Opasitas Logo (0–255)</Label><Input type="number" min="0" max="255" value={wm.logo_opacity} onChange={(e) => setWm({ ...wm, logo_opacity: Math.min(255, Math.max(0, Number(e.target.value) || 0)) })} data-testid="gen-logo-opacity" /></div>
          </div>

          {imageItems.length > 0 && (
            <div className="border rounded-md p-3 bg-slate-50/60">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-600 mb-2"><ImagePlus className="h-3.5 w-3.5" /> Foto referensi untuk AI (opsional — centang foto yang ingin dipakai)</div>
              <div className="flex gap-2 overflow-x-auto pb-1">
                {imageItems.map((b) => (
                  <button key={b.id} type="button" onClick={() => toggleRef(b.id)} data-testid={`ref-toggle-${b.id}`}
                    className={`shrink-0 rounded-md overflow-hidden border-2 ${refIds.includes(b.id) ? "border-indigo-500 ring-2 ring-indigo-200" : "border-transparent"}`}>
                    <img src={b.public_url} alt="ref" className="h-16 w-16 object-cover" />
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <Button onClick={generate} disabled={busy} data-testid="gen-brochure-btn">
              {generating ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Membuat…</> : <><Sparkles className="h-4 w-4 mr-2" /> Generate Infografis</>}
            </Button>
            <Button variant="outline" onClick={generatePdf} disabled={busy} data-testid="gen-pdf-btn">
              {pdfGen ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Menyusun PDF…</> : <><FileType2 className="h-4 w-4 mr-2" /> Generate PDF</>}
            </Button>
            <label className="cursor-pointer inline-flex items-center gap-2 h-10 px-4 rounded-md border text-sm hover:bg-slate-50" data-testid="upload-brochure-label">
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} Upload Brosur / Foto (PDF/Gambar)
              <input type="file" accept="image/*,application/pdf" className="hidden" onChange={upload} data-testid="upload-brochure-input" />
            </label>
          </div>
          {busy && <p className="text-xs text-indigo-600">AI sedang bekerja, mohon tunggu ~20–60 detik…</p>}
        </CardContent></Card>
      )}

      {items.length === 0 ? (
        <div className="text-center text-slate-400 text-sm py-10 border rounded-md">Belum ada brosur/foto untuk paket ini.</div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((b) => {
            const isPdf = (b.content_type || "").includes("pdf");
            return (
              <Card key={b.id} className="border-slate-200 overflow-hidden" data-testid={`brochure-card-${b.id}`}>
                <button type="button" onClick={() => setPreview(b)} className="block w-full h-44 bg-slate-100 overflow-hidden group relative" data-testid={`preview-brochure-${b.id}`}>
                  {b.is_image && b.public_url
                    ? <img src={b.public_url} alt={b.filename} className="w-full h-full object-cover" />
                    : <div className="flex flex-col items-center justify-center h-full text-slate-300"><FileText className="h-12 w-12" /><span className="text-[10px] mt-1 uppercase">{isPdf ? "PDF" : "FILE"}</span></div>}
                  <span className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center opacity-0 group-hover:opacity-100"><Eye className="h-6 w-6 text-white" /></span>
                </button>
                <CardContent className="p-3 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-slate-700 truncate">{b.filename}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${b.kind === "AI" ? "bg-indigo-100 text-indigo-700" : b.kind === "AI_PDF" ? "bg-rose-100 text-rose-700" : "bg-slate-100 text-slate-600"}`}>{b.kind === "AI" ? "AI" : b.kind === "AI_PDF" ? "AI PDF" : "Upload"}</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    <Button size="sm" variant="outline" className="h-8 flex-1 text-xs" onClick={() => setPreview(b)} data-testid={`preview-btn-${b.id}`}><Eye className="h-3.5 w-3.5 mr-1" /> Preview</Button>
                    {b.is_image
                      ? <>
                          <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => download(b, "image")} data-testid={`download-img-${b.id}`}><FileImage className="h-3.5 w-3.5 mr-1" /> Gambar</Button>
                          <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => download(b, "pdf")} data-testid={`download-pdf-${b.id}`}><FileType2 className="h-3.5 w-3.5 mr-1" /> PDF</Button>
                        </>
                      : <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => download(b)} data-testid={`download-brochure-${b.id}`}><Download className="h-3.5 w-3.5 mr-1" /> Unduh</Button>}
                    {canManage && b.kind === "AI" && <Button size="sm" variant="outline" className="h-8" title="Regenerate" disabled={busyId === b.id} onClick={() => regenerate(b)} data-testid={`regen-${b.id}`}>{busyId === b.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}</Button>}
                    {canManage && <Button size="sm" variant="outline" className={`h-8 ${b.is_primary ? "text-amber-600" : ""}`} title="Jadikan Utama (cover & WA)" disabled={busyId === b.id} onClick={() => setPrimary(b)} data-testid={`primary-${b.id}`}><Star className={`h-3.5 w-3.5 ${b.is_primary ? "fill-amber-400" : ""}`} /></Button>}
                    {canManage && <Button size="sm" variant="outline" className="h-8 text-xs text-red-600 hover:text-red-700 hover:bg-red-50" onClick={() => remove(b)} data-testid={`delete-brochure-${b.id}`}><Trash2 className="h-3.5 w-3.5 mr-1" /> Hapus</Button>}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <Dialog open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <DialogContent className="max-w-3xl bg-white" data-testid="brochure-preview-dialog">
          <DialogHeader><DialogTitle className="text-sm truncate">{preview?.filename}</DialogTitle></DialogHeader>
          {preview && (preview.is_image
            ? <img src={preview.public_url} alt={preview.filename} className="w-full max-h-[75vh] object-contain rounded" />
            : <iframe title="preview" src={`${api.defaults.baseURL}/brochures/${preview.id}/download?auth=${localStorage.getItem("token") || ""}`} className="w-full h-[75vh] rounded border" />)}
          {preview && (
            <div className="flex gap-2 justify-end pt-2">
              {preview.is_image
                ? <>
                    <Button variant="outline" onClick={() => download(preview, "image")}><FileImage className="h-4 w-4 mr-1" /> Unduh Gambar</Button>
                    <Button onClick={() => download(preview, "pdf")}><FileType2 className="h-4 w-4 mr-1" /> Unduh PDF</Button>
                  </>
                : <Button onClick={() => download(preview)}><Download className="h-4 w-4 mr-1" /> Unduh PDF</Button>}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
