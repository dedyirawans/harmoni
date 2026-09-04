import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Star, Coffee, Loader2, SearchX, SlidersHorizontal, Info, FilePlus2, CalendarCheck, Globe2 } from "lucide-react";
import { ROOM_OPTIONS } from "@/pages/hotel/hotelConstants";
import AddToQuotationDialog from "@/pages/hotel/AddToQuotationDialog";
import BookingDialog from "@/pages/hotel/BookingDialog";
import CityCombobox from "@/pages/hotel/CityCombobox";
import HotelPicker from "@/pages/hotel/HotelPicker";

const todayPlus = (d) => { const t = new Date(); t.setDate(t.getDate() + d); return t.toISOString().slice(0, 10); };
const today = () => new Date().toISOString().slice(0, 10);
const rupiah = (n, cur) => {
  if (n == null || isNaN(Number(n))) return "-";
  try { return new Intl.NumberFormat("id-ID", { style: "currency", currency: cur || "IDR", maximumFractionDigits: 0 }).format(Number(n)); }
  catch { return `${cur || ""} ${Number(n).toLocaleString("id-ID")}`; }
};

function StarRow({ n }) {
  const c = Math.round(Number(n) || 0);
  if (!c) return null;
  return <span className="inline-flex text-amber-500">{Array.from({ length: c }).map((_, i) => <Star key={i} className="h-3.5 w-3.5 fill-amber-400" />)}</span>;
}

export default function HotelSearch() {
  const { user } = useAuth();
  const canQuote = ["super_admin", "sales", "accounting"].includes(user?.role);

  const [searchType, setSearchType] = useState("city");
  const [countries, setCountries] = useState([]);
  const [iso, setIso] = useState("");
  const [city, setCity] = useState(null);           // full city object
  const [hotels, setHotels] = useState([]);          // array of hotel objects
  const [common, setCommon] = useState({
    checkInDate: todayPlus(14), checkOutDate: todayPlus(15),
    rooms: 1, adults: 2, children: 0,
  });

  const [customers, setCustomers] = useState([]);
  const [customerCtx, setCustomerCtx] = useState("none");

  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [meta, setMeta] = useState(null);
  const inFlight = useRef(false);

  const [showFilters, setShowFilters] = useState(false);
  const [cf, setCf] = useState({ minStar: 0, priceMin: "", priceMax: "", breakfast: false });
  const [detail, setDetail] = useState(null);
  const [addHotel, setAddHotel] = useState(null);
  const [bookHotel, setBookHotel] = useState(null);

  useEffect(() => {
    api.get("/hotel/countries").then((r) => setCountries(r.data || [])).catch(() => {});
    if (canQuote) api.get("/customers").then((r) => setCustomers(r.data || [])).catch(() => {});
  }, [canQuote]);

  const setC = (k, v) => setCommon((f) => ({ ...f, [k]: v }));
  const onCountryChange = (v) => { setIso(v); setCity(null); setHotels([]); };

  const validate = () => {
    if (!common.checkInDate || !common.checkOutDate) return "Tanggal check-in & check-out wajib diisi.";
    if (common.checkInDate < today()) return "Tanggal check-in tidak boleh di masa lalu.";
    if (common.checkOutDate <= common.checkInDate) return "Check-out harus setelah check-in.";
    if (!iso) return "Pilih negara terlebih dahulu.";
    if (searchType === "city" && !city) return "Pilih kota untuk City Search.";
    if (searchType === "hotel" && hotels.length === 0) return "Pilih minimal satu hotel untuk Hotel List Search.";
    return null;
  };

  const buildPayload = () => {
    const p = {
      searchType,
      checkInDate: common.checkInDate, checkOutDate: common.checkOutDate,
      numberOfRooms: Number(common.rooms) || 1,
      numberOfAdult: Number(common.adults) || 1,
      numberOfChildren: Number(common.children) || 0,
    };
    if (customerCtx && customerCtx !== "none") p.customer_id = customerCtx;
    if (searchType === "city") {
      p.countryCode = String(city.countryCode);
      p.cityId = String(city.cityId);
    } else {
      p.hotels = hotels.map((h) => ({ hotelId: String(h.hotelId), cityId: String(h.cityId), countryCode: String(h.countryCode) }));
    }
    return p;
  };

  const search = async () => {
    if (inFlight.current) return;
    const err = validate();
    if (err) return toast.error(err);
    inFlight.current = true;
    setLoading(true); setResults(null); setMeta(null);
    try {
      const { data } = await api.post("/hotel/search", buildPayload());
      setResults(data.results || []);
      setMeta({ status: data.status, message: data.message, cached: data.cached, error: data.error });
      if (data.error && data.message) toast.error(data.message);
    } catch (e) {
      const d = formatApiErrorDetail(e?.response?.data?.detail);
      setResults([]); setMeta({ status: 0, error: true, message: d });
      toast.error(d);
    } finally {
      setLoading(false); inFlight.current = false;
    }
  };

  const filtered = useMemo(() => {
    if (!results) return [];
    return results.filter((h) => {
      if (cf.minStar && (Number(h.starRating) || 0) < cf.minStar) return false;
      if (cf.priceMin !== "" && (Number(h.dailyRate) || 0) < Number(cf.priceMin)) return false;
      if (cf.priceMax !== "" && (Number(h.dailyRate) || 0) > Number(cf.priceMax)) return false;
      if (cf.breakfast && !h.includeBreakfast) return false;
      return true;
    });
  }, [results, cf]);

  const searchCtx = {
    checkInDate: common.checkInDate, checkOutDate: common.checkOutDate,
    adults: common.adults, children: common.children, rooms: common.rooms, currency: "IDR",
  };

  return (
    <div className="space-y-5" data-testid="hotel-search">
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <Tabs value={searchType} onValueChange={setSearchType}>
              <TabsList data-testid="hotel-searchtype-tabs">
                <TabsTrigger value="city" data-testid="hotel-searchtype-city">City Search</TabsTrigger>
                <TabsTrigger value="hotel" data-testid="hotel-searchtype-hotel">Hotel List Search</TabsTrigger>
              </TabsList>
            </Tabs>
            {canQuote && (
              <div className="flex items-center gap-2">
                <Label className="text-xs text-slate-500">Untuk Customer</Label>
                <Select value={customerCtx} onValueChange={setCustomerCtx}>
                  <SelectTrigger className="w-56" data-testid="hotel-customer-ctx"><SelectValue placeholder="Tanpa customer" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Tanpa customer</SelectItem>
                    {customers.map((c) => <SelectItem key={c._id} value={c._id}>{c.full_name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="space-y-1">
              <Label className="flex items-center gap-1"><Globe2 className="h-3.5 w-3.5 text-slate-400" />Negara</Label>
              <Select value={iso} onValueChange={onCountryChange}>
                <SelectTrigger data-testid="hotel-country-select"><SelectValue placeholder="Pilih negara" /></SelectTrigger>
                <SelectContent>
                  {countries.length === 0 && <SelectItem value="__none" disabled>Belum ada data — sinkronkan di API Settings</SelectItem>}
                  {countries.map((c) => (
                    <SelectItem key={c.country_code} value={c.country_code}>
                      {c.country_name}{c.active_hotels ? ` (${Number(c.active_hotels).toLocaleString("id-ID")})` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {searchType === "city" ? (
              <div className="space-y-1 lg:col-span-3">
                <Label>Destinasi (Kota)</Label>
                <CityCombobox value={city} iso={iso} onChange={setCity} />
              </div>
            ) : (
              <>
                <div className="space-y-1">
                  <Label>Kota (opsional, untuk memfilter)</Label>
                  <CityCombobox value={city} iso={iso} onChange={setCity} />
                </div>
                <div className="space-y-1 lg:col-span-2">
                  <Label>Hotel (cari by nama)</Label>
                  <HotelPicker iso={iso} cityId={city?.cityId} onChange={setHotels} />
                </div>
              </>
            )}

            <div className="space-y-1">
              <Label>Check-in</Label>
              <Input type="date" min={today()} value={common.checkInDate} data-testid="hotel-search-checkin"
                onChange={(e) => setC("checkInDate", e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Check-out</Label>
              <Input type="date" min={common.checkInDate} value={common.checkOutDate} data-testid="hotel-search-checkout"
                onChange={(e) => setC("checkOutDate", e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Jumlah Kamar</Label>
              <Select value={String(common.rooms)} onValueChange={(v) => setC("rooms", Number(v))}>
                <SelectTrigger data-testid="hotel-search-rooms"><SelectValue /></SelectTrigger>
                <SelectContent>{ROOM_OPTIONS.map((r) => <SelectItem key={r} value={String(r)}>{r} kamar</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Dewasa</Label>
                <Input type="number" min="1" value={common.adults} data-testid="hotel-search-adults"
                  onChange={(e) => setC("adults", e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>Anak</Label>
                <Input type="number" min="0" value={common.children} data-testid="hotel-search-children"
                  onChange={(e) => setC("children", e.target.value)} />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <p className="text-[11px] text-slate-400 flex items-center gap-1"><Info className="h-3 w-3" />Hasil & harga live dari MMBC. Harga sudah termasuk markup agen.</p>
            <Button onClick={search} disabled={loading} className="min-w-[140px]" data-testid="hotel-search-submit">
              {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              {loading ? "Mencari…" : "Cari Hotel"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading && (
        <div className="flex items-center justify-center py-16 text-slate-500" data-testid="hotel-search-loading">
          <Loader2 className="h-5 w-5 mr-2 animate-spin" /> Mencari hotel yang tersedia…
        </div>
      )}

      {!loading && meta?.error && (
        <div className="flex flex-col items-center justify-center py-16 text-slate-500" data-testid="hotel-search-error">
          <SearchX className="h-10 w-10 mb-3 text-slate-300" />
          <p className="text-sm max-w-md text-center">{meta.message || "Terjadi kesalahan."}</p>
        </div>
      )}

      {!loading && results && !meta?.error && results.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-slate-500" data-testid="hotel-search-empty">
          <SearchX className="h-10 w-10 mb-3 text-slate-300" />
          <p className="text-sm">{meta?.message || "Tidak ada hotel untuk kriteria yang dipilih."}</p>
        </div>
      )}

      {!loading && results && !meta?.error && results.length > 0 && (
        <div className="space-y-4" data-testid="hotel-search-results">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <p className="text-sm text-slate-600">{filtered.length} dari {results.length} pilihan kamar</p>
              {meta?.cached && <Badge variant="outline" data-testid="hotel-cached-badge">Dari cache</Badge>}
            </div>
            <Button size="sm" variant="outline" onClick={() => setShowFilters((v) => !v)} data-testid="hotel-toggle-filters">
              <SlidersHorizontal className="h-3.5 w-3.5 mr-1" /> Filter
            </Button>
          </div>

          {showFilters && (
            <Card className="border-slate-200" data-testid="hotel-client-filters">
              <CardContent className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="space-y-1">
                  <Label className="text-xs">Min Bintang</Label>
                  <Input type="number" min="0" max="5" value={cf.minStar} onChange={(e) => setCf((f) => ({ ...f, minStar: Number(e.target.value) || 0 }))} data-testid="hotel-cf-minstar" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Harga Min /malam</Label>
                  <Input type="number" value={cf.priceMin} onChange={(e) => setCf((f) => ({ ...f, priceMin: e.target.value }))} data-testid="hotel-cf-pricemin" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Harga Maks /malam</Label>
                  <Input type="number" value={cf.priceMax} onChange={(e) => setCf((f) => ({ ...f, priceMax: e.target.value }))} data-testid="hotel-cf-pricemax" />
                </div>
                <label className="flex items-center gap-2 pt-5 cursor-pointer text-xs" data-testid="hotel-cf-breakfast">
                  <Checkbox checked={cf.breakfast} onCheckedChange={(v) => setCf((f) => ({ ...f, breakfast: !!v }))} /> Termasuk Sarapan
                </label>
              </CardContent>
            </Card>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((h, i) => (
              <Card key={`${h.hotelId}-${h.roomRateKey || i}`} className="border-slate-200 shadow-sm overflow-hidden flex flex-col" data-testid={`hotel-result-${h.hotelId || i}`}>
                <div className="aspect-video bg-slate-100 relative">
                  {h.imageURL ? <img src={h.imageURL} alt={h.hotelName} className="w-full h-full object-cover" />
                    : <div className="w-full h-full flex items-center justify-center text-slate-300 text-xs">Tanpa gambar</div>}
                </div>
                <CardContent className="p-4 space-y-2 flex flex-col flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-semibold text-slate-800 text-sm leading-snug">{h.hotelName || "Hotel"}</h3>
                    <StarRow n={h.starRating} />
                  </div>
                  {h.city && <p className="text-[11px] text-slate-400">{h.city}{h.country ? `, ${h.country}` : ""}</p>}
                  {h.roomtypeName && <p className="text-xs text-slate-500">{h.roomtypeName}</p>}
                  <div className="flex items-center gap-2 flex-wrap">
                    {h.includeBreakfast && <Badge variant="secondary" className="text-[10px]"><Coffee className="h-3 w-3 mr-1" />Sarapan</Badge>}
                    {h.boardName && !h.includeBreakfast && <Badge variant="outline" className="text-[10px]">{h.boardName}</Badge>}
                  </div>
                  <div className="mt-auto flex items-end justify-between pt-2">
                    <div>
                      <p className="text-base font-bold text-blue-600">{rupiah(h.dailyRate, h.currency)}<span className="text-xs font-normal text-slate-400">/malam</span></p>
                      <p className="text-[11px] text-slate-400">Total {rupiah(h.sellTotal, h.currency)} · {h.nights || 1} mlm</p>
                    </div>
                    <div className="flex gap-1">
                      {canQuote && (
                        <Button size="sm" variant="outline" onClick={() => setAddHotel(h)} title="Tambah ke Quotation" data-testid={`hotel-addquote-${h.hotelId || i}`}><FilePlus2 className="h-3.5 w-3.5" /></Button>
                      )}
                      {canQuote && (
                        <Button size="sm" variant="outline" onClick={() => setBookHotel(h)} title="Booking" data-testid={`hotel-book-${h.hotelId || i}`}><CalendarCheck className="h-3.5 w-3.5" /></Button>
                      )}
                      <Button size="sm" variant="outline" onClick={() => setDetail(h)} data-testid={`hotel-view-${h.hotelId || i}`}>Lihat</Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="hotel-detail-dialog">
          {detail && (
            <>
              <DialogHeader>
                <DialogTitle className="pr-6">{detail.hotelName}</DialogTitle>
              </DialogHeader>
              <div className="space-y-3">
                <div className="aspect-video bg-slate-100 rounded-lg overflow-hidden">
                  {detail.imageURL ? <img src={detail.imageURL} alt={detail.hotelName} className="w-full h-full object-cover" />
                    : <div className="w-full h-full flex items-center justify-center text-slate-300 text-xs">Tanpa gambar</div>}
                </div>
                <div className="flex items-center gap-3 flex-wrap">
                  <StarRow n={detail.starRating} />
                  {detail.boardName && <Badge variant="outline">{detail.boardName}</Badge>}
                </div>
                {detail.address && <p className="text-xs text-slate-500">{detail.address}{detail.city ? `, ${detail.city}` : ""}{detail.country ? `, ${detail.country}` : ""}</p>}
                {detail.roomtypeName && <p className="text-sm text-slate-600">Tipe kamar: <span className="font-medium">{detail.roomtypeName}</span></p>}
                <div className="flex items-end gap-3">
                  <span className="text-2xl font-bold text-blue-600">{rupiah(detail.dailyRate, detail.currency)}</span>
                  <span className="text-sm text-slate-400">/malam · Total {rupiah(detail.sellTotal, detail.currency)}</span>
                </div>
                {detail.cancellation && <p className="text-[11px] text-slate-500 border-l-2 border-slate-200 pl-2">{detail.cancellation}</p>}
                <div className="flex gap-2">
                  {canQuote && (
                    <Button className="flex-1" onClick={() => { setBookHotel(detail); setDetail(null); }} data-testid="hotel-detail-book">
                      <CalendarCheck className="h-4 w-4 mr-2" />Booking
                    </Button>
                  )}
                  {canQuote && (
                    <Button variant="outline" onClick={() => { setAddHotel(detail); setDetail(null); }} data-testid="hotel-detail-addquote">
                      <FilePlus2 className="h-4 w-4 mr-2" />Ke Quotation
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {canQuote && (
        <AddToQuotationDialog
          open={!!addHotel}
          onClose={() => setAddHotel(null)}
          hotel={addHotel || {}}
          searchCtx={searchCtx}
          customers={customers}
          defaultCustomerId={customerCtx !== "none" ? customerCtx : ""}
          onDone={() => api.get("/customers").then((r) => setCustomers(r.data || [])).catch(() => {})}
        />
      )}

      {canQuote && (
        <BookingDialog
          open={!!bookHotel}
          onClose={() => setBookHotel(null)}
          hotel={bookHotel || {}}
          customers={customers}
          defaultCustomerId={customerCtx !== "none" ? customerCtx : ""}
        />
      )}
    </div>
  );
}
