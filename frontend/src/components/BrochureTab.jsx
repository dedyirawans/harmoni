import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Upload, Download, Trash2, Sparkles, FileText } from "lucide-react";
import { toast } from "sonner";

export function BrochureTab({ pkgId, canManage }) {
  const [items, setItems] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [gen, setGen] = useState({ theme: "", highlights: "", promo: "", cta: "", extra: "" });
  const [generating, setGenerating] = useState(false);

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
      toast.success("Brosur berhasil diunggah");
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal mengunggah brosur");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const download = async (b) => {
    try {
      const r = await api.get(`/brochures/${b.id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = b.filename || "brosur";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Gagal mengunduh brosur");
    }
  };

  const remove = async (b) => {
    if (!window.confirm("Hapus brosur ini?")) return;
    try {
      await api.delete(`/brochures/${b.id}`);
      toast.success("Brosur dihapus");
      await load();
    } catch {
      toast.error("Gagal menghapus brosur");
    }
  };

  const generate = async () => {
    setGenerating(true);
    try {
      await api.post(`/packages/${pkgId}/brochures/generate-infographic`, gen);
      toast.success("Brosur infografis berhasil dibuat AI");
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Gagal generate brosur AI");
    } finally {
      setGenerating(false);
    }
  };

  if (items === null) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;

  return (
    <div className="space-y-4" data-testid="brochure-tab">
      {canManage && (
        <Card className="border-slate-200"><CardContent className="p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-800"><Sparkles className="h-4 w-4 text-indigo-600" /> Generate Brosur Infografis (AI · Nano Banana)</div>
          <p className="text-xs text-slate-500">Data paket (nama, harga, durasi, destinasi, itinerary) dipakai otomatis. Isi field opsional di bawah agar hasil lebih tajam.</p>
          <div className="grid sm:grid-cols-2 gap-3">
            <div><Label className="text-xs">Tema / Nuansa Warna</Label><Input value={gen.theme} onChange={(e) => setGen({ ...gen, theme: e.target.value })} placeholder="mis. hijau elegan aksen emas" data-testid="gen-theme" /></div>
            <div><Label className="text-xs">Promo / Diskon</Label><Input value={gen.promo} onChange={(e) => setGen({ ...gen, promo: e.target.value })} placeholder="mis. Early bird diskon 10%" data-testid="gen-promo" /></div>
            <div className="sm:col-span-2"><Label className="text-xs">Highlight Fasilitas</Label><Textarea rows={2} value={gen.highlights} onChange={(e) => setGen({ ...gen, highlights: e.target.value })} placeholder="mis. Hotel bintang 5 dekat Masjidil Haram, maskapai Saudia, bimbingan ustadz" data-testid="gen-highlights" /></div>
            <div><Label className="text-xs">Ajakan (CTA)</Label><Input value={gen.cta} onChange={(e) => setGen({ ...gen, cta: e.target.value })} placeholder="mis. Booking sekarang: WA 0812-xxxx" data-testid="gen-cta" /></div>
            <div><Label className="text-xs">Catatan Tambahan</Label><Input value={gen.extra} onChange={(e) => setGen({ ...gen, extra: e.target.value })} placeholder="opsional" data-testid="gen-extra" /></div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={generate} disabled={generating} data-testid="gen-brochure-btn">
              {generating ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Membuat brosur…</> : <><Sparkles className="h-4 w-4 mr-2" /> Generate Brosur AI</>}
            </Button>
            <label className="cursor-pointer inline-flex items-center gap-2 h-10 px-4 rounded-md border text-sm hover:bg-slate-50" data-testid="upload-brochure-label">
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} Upload Brosur (PDF/Gambar)
              <input type="file" accept="image/*,application/pdf" className="hidden" onChange={upload} data-testid="upload-brochure-input" />
            </label>
          </div>
          {generating && <p className="text-xs text-indigo-600">AI sedang menyusun infografis, mohon tunggu ~20–40 detik…</p>}
        </CardContent></Card>
      )}

      {items.length === 0 ? (
        <div className="text-center text-slate-400 text-sm py-10 border rounded-md">Belum ada brosur untuk paket ini.</div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((b) => (
            <Card key={b.id} className="border-slate-200 overflow-hidden" data-testid={`brochure-card-${b.id}`}>
              <div className="h-44 bg-slate-100 flex items-center justify-center overflow-hidden">
                {b.is_image && b.public_url
                  ? <img src={b.public_url} alt={b.filename} className="w-full h-full object-cover" />
                  : <FileText className="h-12 w-12 text-slate-300" />}
              </div>
              <CardContent className="p-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-slate-700 truncate">{b.filename}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${b.kind === "AI" ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-600"}`}>{b.kind === "AI" ? "AI" : "Upload"}</span>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" className="h-8 flex-1" onClick={() => download(b)} data-testid={`download-brochure-${b.id}`}><Download className="h-3.5 w-3.5 mr-1" /> Unduh</Button>
                  {canManage && <Button size="sm" variant="outline" className="h-8 text-red-600 hover:text-red-700" onClick={() => remove(b)} data-testid={`delete-brochure-${b.id}`}><Trash2 className="h-3.5 w-3.5" /></Button>}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
