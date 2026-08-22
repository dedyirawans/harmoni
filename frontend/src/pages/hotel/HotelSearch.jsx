import { useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Star, Wifi, Coffee, ExternalLink, Loader2, SearchX } from "lucide-react";

const todayPlus = (d) => {
  const t = new Date();
  t.setDate(t.getDate() + d);
  return t.toISOString().slice(0, 10);
};

const rupiah = (n, cur) => {
  if (n == null || isNaN(Number(n))) return "-";
  try {
    return new Intl.NumberFormat("id-ID", { style: "currency", currency: cur || "IDR", maximumFractionDigits: 0 }).format(Number(n));
  } catch {
    return `${cur || ""} ${Number(n).toLocaleString("id-ID")}`;
  }
};

export default function HotelSearch() {
  const [form, setForm] = useState({
    cityId: 9395,
    checkIn: todayPlus(14),
    checkOut: todayPlus(15),
    adults: 2,
    children: 0,
    rooms: 1,
    maxResult: 20,
  });
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [msg, setMsg] = useState("");

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const search = async () => {
    if (!form.cityId) return toast.error("City ID wajib diisi.");
    if (!form.checkIn || !form.checkOut) return toast.error("Tanggal check-in & check-out wajib diisi.");
    if (form.checkOut <= form.checkIn) return toast.error("Check-out harus setelah check-in.");
    setLoading(true);
    setMsg("");
    setResults(null);
    try {
      const criteria = {
        cityId: Number(form.cityId),
        checkIn: form.checkIn,
        checkOut: form.checkOut,
        additional: {
          maxResult: Number(form.maxResult) || 20,
          occupancy: {
            numberOfAdult: Number(form.adults) || 1,
            numberOfChildren: Number(form.children) || 0,
          },
          numberOfRoom: Number(form.rooms) || 1,
        },
      };
      const { data } = await api.post("/hotel/search", criteria);
      setResults(data.results || []);
      if (!data.results || data.results.length === 0) {
        setMsg(data.message || "Tidak ada hasil untuk kriteria ini.");
      }
    } catch (e) {
      const detail = formatApiErrorDetail(e?.response?.data?.detail);
      setMsg(detail);
      toast.error(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5" data-testid="hotel-search">
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-1">
              <Label>City ID (Agoda)</Label>
              <Input type="number" value={form.cityId} data-testid="hotel-search-cityid"
                onChange={(e) => set("cityId", e.target.value)} placeholder="mis. 9395 (Jakarta)" />
            </div>
            <div className="space-y-1">
              <Label>Check-in</Label>
              <Input type="date" value={form.checkIn} data-testid="hotel-search-checkin"
                onChange={(e) => set("checkIn", e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Check-out</Label>
              <Input type="date" value={form.checkOut} data-testid="hotel-search-checkout"
                onChange={(e) => set("checkOut", e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Jumlah Kamar</Label>
              <Input type="number" min="1" value={form.rooms} data-testid="hotel-search-rooms"
                onChange={(e) => set("rooms", e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Dewasa</Label>
              <Input type="number" min="1" value={form.adults} data-testid="hotel-search-adults"
                onChange={(e) => set("adults", e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Anak</Label>
              <Input type="number" min="0" value={form.children} data-testid="hotel-search-children"
                onChange={(e) => set("children", e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Maks Hasil</Label>
              <Input type="number" min="1" max="100" value={form.maxResult} data-testid="hotel-search-max"
                onChange={(e) => set("maxResult", e.target.value)} />
            </div>
            <div className="flex items-end">
              <Button onClick={search} disabled={loading} className="w-full" data-testid="hotel-search-submit">
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Cari Hotel
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {loading && (
        <div className="flex items-center justify-center py-16 text-slate-500" data-testid="hotel-search-loading">
          <Loader2 className="h-5 w-5 mr-2 animate-spin" /> Mencari hotel…
        </div>
      )}

      {!loading && results && results.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-slate-500" data-testid="hotel-search-empty">
          <SearchX className="h-10 w-10 mb-3 text-slate-300" />
          <p className="text-sm">{msg || "Tidak ada hasil."}</p>
        </div>
      )}

      {!loading && !results && msg && (
        <div className="flex flex-col items-center justify-center py-16 text-slate-500" data-testid="hotel-search-error">
          <SearchX className="h-10 w-10 mb-3 text-slate-300" />
          <p className="text-sm max-w-md text-center">{msg}</p>
        </div>
      )}

      {!loading && results && results.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="hotel-search-results">
          {results.map((h, i) => (
            <Card key={h.hotelId || i} className="border-slate-200 shadow-sm overflow-hidden" data-testid={`hotel-result-${h.hotelId || i}`}>
              <div className="aspect-video bg-slate-100">
                {h.imageURL ? (
                  <img src={h.imageURL} alt={h.hotelName} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-300 text-xs">No image</div>
                )}
              </div>
              <CardContent className="p-4 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-semibold text-slate-800 text-sm leading-snug">{h.hotelName || "Hotel"}</h3>
                  {h.starRating ? (
                    <span className="flex items-center gap-0.5 text-amber-500 shrink-0">
                      <Star className="h-3.5 w-3.5 fill-amber-400" />
                      <span className="text-xs font-medium">{h.starRating}</span>
                    </span>
                  ) : null}
                </div>
                {h.roomtypeName && <p className="text-xs text-slate-500">{h.roomtypeName}</p>}
                <div className="flex items-center gap-2 flex-wrap">
                  {h.includeBreakfast && <Badge variant="secondary" className="text-[10px]"><Coffee className="h-3 w-3 mr-1" />Sarapan</Badge>}
                  {h.freeWifi && <Badge variant="secondary" className="text-[10px]"><Wifi className="h-3 w-3 mr-1" />WiFi</Badge>}
                  {h.reviewScore ? <Badge variant="outline" className="text-[10px]">{h.reviewScore} ({h.reviewCount || 0})</Badge> : null}
                </div>
                <div className="flex items-end justify-between pt-1">
                  <div>
                    {h.crossedOutRate ? <p className="text-xs text-slate-400 line-through">{rupiah(h.crossedOutRate, h.currency)}</p> : null}
                    <p className="text-base font-bold text-blue-600">{rupiah(h.dailyRate, h.currency)}<span className="text-xs font-normal text-slate-400">/malam</span></p>
                  </div>
                  {h.landingURL ? (
                    <a href={h.landingURL} target="_blank" rel="noreferrer" data-testid={`hotel-book-${h.hotelId || i}`}>
                      <Button size="sm" variant="outline"><ExternalLink className="h-3.5 w-3.5 mr-1" />Book</Button>
                    </a>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
