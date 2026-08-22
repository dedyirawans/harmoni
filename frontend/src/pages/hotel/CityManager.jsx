import { useEffect, useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Trash2, MapPin, Plus } from "lucide-react";

export default function CityManager() {
  const [cities, setCities] = useState([]);
  const [form, setForm] = useState({ name: "", cityId: "", country: "" });

  const load = () => api.get("/hotel/cities").then((r) => setCities(r.data || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!form.name.trim() || !form.cityId) return toast.error("Nama & City ID wajib diisi.");
    try {
      await api.post("/hotel/cities", { name: form.name.trim(), cityId: Number(form.cityId), country: form.country.trim() });
      toast.success("Kota disimpan.");
      setForm({ name: "", cityId: "", country: "" });
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e?.response?.data?.detail)); }
  };
  const del = async (id) => { try { await api.delete(`/hotel/cities/${id}`); load(); } catch {} };

  return (
    <Card className="border-slate-200 shadow-sm" data-testid="hotel-city-manager">
      <CardContent className="p-5 space-y-4">
        <div className="flex items-center gap-2 text-slate-700"><MapPin className="h-4 w-4 text-blue-600" /><p className="text-sm font-medium">Daftar Kota (Autocomplete Hotel Search)</p></div>
        <p className="text-xs text-slate-400">Kelola pemetaan nama kota ↔ Agoda City ID. Sales memilih kota dari daftar ini tanpa hafal ID. Verifikasi City ID lewat uji pencarian; edit/hapus bila hasil tidak sesuai.</p>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <Input placeholder="Nama kota" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} data-testid="city-mgr-name" />
          <Input type="number" placeholder="Agoda City ID" value={form.cityId} onChange={(e) => setForm((f) => ({ ...f, cityId: e.target.value }))} data-testid="city-mgr-id" />
          <Input placeholder="Negara (opsional)" value={form.country} onChange={(e) => setForm((f) => ({ ...f, country: e.target.value }))} data-testid="city-mgr-country" />
          <Button onClick={add} data-testid="city-mgr-add"><Plus className="h-4 w-4 mr-1" />Tambah</Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {cities.map((c) => (
            <Badge key={c._id} variant="outline" className="text-xs py-1 pl-2 pr-1 flex items-center gap-1" data-testid={`city-mgr-item-${c.cityId}`}>
              {c.name} · {c.cityId}{c.country ? ` · ${c.country}` : ""}
              <button onClick={() => del(c._id)} className="ml-1 text-red-500 hover:text-red-700" data-testid={`city-mgr-del-${c.cityId}`}><Trash2 className="h-3 w-3" /></button>
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
