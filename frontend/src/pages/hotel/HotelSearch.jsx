import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Star, Wifi, Coffee, ExternalLink, Loader2, SearchX, SlidersHorizontal, Info, FilePlus2 } from "lucide-react";
import { CURRENCIES, LANGUAGES, SORT_OPTIONS } from "@/pages/hotel/hotelConstants";
import AddToQuotationDialog from "@/pages/hotel/AddToQuotationDialog";
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
  const isAdmin = user?.role === "super_admin";

  const [searchType, setSearchType] = useState("city");
  const [common, setCommon] = useState({
    checkInDate: todayPlus(14), checkOutDate: todayPlus(15),
    currency: "IDR", language: "id-id", adults: 2, children: 0, childrenAges: [],
  });
  const [city, setCity] = useState({
    cityId: 9395, sortBy: "Recommended", maxResult: 30, discountOnly: false,
    minimumStarRating: "", minimumReviewScore: "", dailyRateMin: "", dailyRateMax: "",
  });
  const [hotelIds, setHotelIds] = useState("");

  const [customers, setCustomers] = useState([]);
  const [customerCtx, setCustomerCtx] = useState("none");

  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [meta, setMeta] = useState(null);
  const inFlight = useRef(false);

  const [showFilters, setShowFilters] = useState(false);
  const [cf, setCf] = useState({ minStar: 0, minReview: 0, priceMin: "", priceMax: "", discountOnly: false, breakfast: false, wifi: false });
  const [detail, setDetail] = useState(null);
  const [addHotel, setAddHotel] = useState(null);

  useEffect(() => { if (canQuote) api.get("/customers").then((r) => setCustomers(r.data || [])).catch(() => {}); }, [canQuote]);

  const setC = (k, v) => setCommon((f) => ({ ...f, [k]: v }));
  const setCt = (k, v) => setCity((f) => ({ ...f, [k]: v }));

  const setChildren = (n) => {
    const num = Math.max(0, Number(n) || 0);
    setCommon((f) => {
      const ages = [...f.childrenAges];
      while (ages.length < num) ages.push(7);
      ages.length = num;
      return { ...f, children: num, childrenAges: ages };
    });
  };
  const setAge = (i, v) => setCommon((f) => { const ages = [...f.childrenAges]; ages[i] = Number(v) || 0; return { ...f, childrenAges: ages }; });

  const validate = () => {
    if (!common.checkInDate || !common.checkOutDate) return "Tanggal check-in & check-out wajib diisi.";
    if (common.checkInDate < today()) return "Tanggal check-in tidak boleh di masa lalu.";
    if (common.checkOutDate <= common.checkInDate) return "Check-out harus setelah check-in.";
    if (common.childrenAges.length !== Number(common.children)) return "Jumlah usia anak harus sama dengan jumlah anak.";
    if (searchType === "city" && !city.cityId) return "City ID wajib diisi untuk City Search.";
    if (searchType === "hotel" && hotelIds.split(/[\s,]+/).filter(Boolean).length === 0) return "Minimal satu Hotel ID untuk Hotel List Search.";
    return null;
  };

  const buildPayload = () => {
    const p = {
      searchType,
      checkInDate: common.checkInDate, checkOutDate: common.checkOutDate,
      currency: common.currency, language: common.language,
      numberOfAdult: Number(common.adults) || 1,
      numberOfChildren: Number(common.children) || 0,
      childrenAges: common.childrenAges.map(Number),
    };
    if (customerCtx && customerCtx !== "none") p.customer_id = customerCtx;
    if (searchType === "city") {
      p.cityId = Number(city.cityId);
      p.sortBy = city.sortBy;
      p.maxResult = Number(city.maxResult) || 30;
      p.discountOnly = !!city.discountOnly;
      if (city.minimumStarRating !== "") p.minimumStarRating = Number(city.minimumStarRating);
      if (city.minimumReviewScore !== "") p.minimumReviewScore = Number(city.minimumReviewScore);
      if (city.dailyRateMin !== "") p.dailyRateMin = Number(city.dailyRateMin);
      if (city.dailyRateMax !== "") p.dailyRateMax = Number(city.dailyRateMax);
    } else {
      p.hotelId = hotelIds.split(/[\s,]+/).filter(Boolean).map(Number);
      p.discountOnly = !!city.discountOnly;
    }
    return p;
  };

  const search = async () => {
    if (inFlight.current) return;
    const err = validate();
    if (err) return toast.error(err);
    inFlight.current = true;
    setLoading(true);
    setResults(null);
    setMeta(null);
    try {
      const { data } = await api.post("/hotel/search", buildPayload());
      setResults(data.results || []);
      setMeta({ status: data.status, partial: data.partial, message: data.message, cached: data.cached, error: data.error });
      if (data.error && data.message) toast.error(data.message);
      else if (data.partial) toast.warning(data.message || "Sebagian hasil mungkin belum lengkap.");
    } catch (e) {
      const d = formatApiErrorDetail(e?.response?.data?.detail);
      setResults([]);
      setMeta({ status: 0, error: true, message: d });
      toast.error(d);
    } finally {
      setLoading(false);
      inFlight.current = false;
    }
  };

  const filtered = useMemo(() => {
    if (!results) return [];
    return results.filter((h) => {
      if (cf.minStar && (Number(h.starRating) || 0) < cf.minStar) return false;
      if (cf.minReview && (Number(h.reviewScore) || 0) < cf.minReview) return false;
      if (cf.priceMin !== "" && (Number(h.dailyRate) || 0) < Number(cf.priceMin)) return false;
      if (cf.priceMax !== "" && (Number(h.dailyRate) || 0) > Number(cf.priceMax)) return false;
      if (cf.discountOnly && !(Number(h.discountPercentage) > 0)) return false;
      if (cf.breakfast && !h.includeBreakfast) return false;
      if (cf.wifi && !h.freeWifi) return false;
      return true;
    });
  }, [results, cf]);

  const searchCtx = {
    checkInDate: common.checkInDate, checkOutDate: common.checkOutDate,
    adults: common.adults, children: common.children, currency: common.currency,
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
            {searchType === "city" ? (
              <div className="space-y-1 lg:col-span-2">
                <Label>Destinasi (Kota)</Label>
                <CityCombobox value={city.cityId} onChange={(v) => setCt("cityId", v)} />
                <p className="text-[11px] text-slate-400">Cari kota berdasarkan nama, atau ketik City ID Agoda manual.</p>
              </div>
            ) : (
              <>
                <div className="space-y-1 lg:col-span-2">
                  <Label>Kota (untuk memfilter hotel)</Label>
                  <CityCombobox value={city.cityId} onChange={(v) => setCt("cityId", v)} />
                </div>
                <div className="space-y-1 lg:col-span-2">
                  <Label>Hotel (cari by nama)</Label>
                  <HotelPicker cityId={Number(city.cityId) || undefined} onChange={(ids) => setHotelIds(ids.join(", "))} />
                  <p className="text-[11px] text-slate-400">Hasil dibatasi ke kota terpilih. Ketik nama hotel, atau Hotel ID manual.</p>
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
              <Label>Dewasa</Label>
              <Input type="number" min="1" value={common.adults} data-testid="hotel-search-adults"
                onChange={(e) => setC("adults", e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Anak</Label>
              <Input type="number" min="0" value={common.children} data-testid="hotel-search-children"
                onChange={(e) => setChildren(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Mata Uang</Label>
              <Select value={common.currency} onValueChange={(v) => setC("currency", v)}>
                <SelectTrigger data-testid="hotel-search-currency"><SelectValue /></SelectTrigger>
                <SelectContent>{CURRENCIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Bahasa</Label>
              <Select value={common.language} onValueChange={(v) => setC("language", v)}>
                <SelectTrigger data-testid="hotel-search-language"><SelectValue /></SelectTrigger>
                <SelectContent>{LANGUAGES.map((l) => <SelectItem key={l.code} value={l.code}>{l.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>

          {Number(common.children) > 0 && (
            <div className="flex flex-wrap gap-3 items-end" data-testid="hotel-search-children-ages">
              {common.childrenAges.map((a, i) => (
                <div key={i} className="space-y-1 w-24">
                  <Label className="text-xs">Usia Anak {i + 1}</Label>
                  <Input type="number" min="0" max="17" value={a} data-testid={`hotel-search-childage-${i}`}
                    onChange={(e) => setAge(i, e.target.value)} />
                </div>
              ))}
            </div>
          )}

          {searchType === "city" && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 pt-2 border-t border-slate-100">
              <div className="space-y-1">
                <Label className="text-xs">Urutkan</Label>
                <Select value={city.sortBy} onValueChange={(v) => setCt("sortBy", v)}>
                  <SelectTrigger data-testid="hotel-search-sortby"><SelectValue /></SelectTrigger>
                  <SelectContent>{SORT_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Min Bintang</Label>
                <Input type="number" min="0" max="5" step="0.5" value={city.minimumStarRating} data-testid="hotel-search-minstar"
                  onChange={(e) => setCt("minimumStarRating", e.target.value)} placeholder="0-5" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Min Skor Ulasan</Label>
                <Input type="number" min="0" max="10" step="0.1" value={city.minimumReviewScore} data-testid="hotel-search-minreview"
                  onChange={(e) => setCt("minimumReviewScore", e.target.value)} placeholder="0-10" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Harga Min</Label>
                <Input type="number" min="0" value={city.dailyRateMin} data-testid="hotel-search-ratemin"
                  onChange={(e) => setCt("dailyRateMin", e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Harga Maks</Label>
                <Input type="number" min="0" value={city.dailyRateMax} data-testid="hotel-search-ratemax"
                  onChange={(e) => setCt("dailyRateMax", e.target.value)} />
              </div>
              <div className="flex items-center gap-2 pt-5">
                <Switch checked={city.discountOnly} onCheckedChange={(v) => setCt("discountOnly", v)} data-testid="hotel-search-discountonly" />
                <Label className="text-xs cursor-pointer">Diskon Saja</Label>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between pt-2">
            <p className="text-[11px] text-slate-400 flex items-center gap-1"><Info className="h-3 w-3" />Hasil & harga langsung dari Agoda. Pemesanan diselesaikan di Agoda.</p>
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
              <p className="text-sm text-slate-600">{filtered.length} dari {results.length} hotel</p>
              {meta?.partial && <Badge variant="secondary" data-testid="hotel-partial-badge">Sebagian hasil</Badge>}
              {meta?.cached && <Badge variant="outline" data-testid="hotel-cached-badge">Dari cache</Badge>}
            </div>
            <Button size="sm" variant="outline" onClick={() => setShowFilters((v) => !v)} data-testid="hotel-toggle-filters">
              <SlidersHorizontal className="h-3.5 w-3.5 mr-1" /> Filter
            </Button>
          </div>

          {showFilters && (
            <Card className="border-slate-200" data-testid="hotel-client-filters">
              <CardContent className="p-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                <div className="space-y-1">
                  <Label className="text-xs">Min Bintang</Label>
                  <Input type="number" min="0" max="5" value={cf.minStar} onChange={(e) => setCf((f) => ({ ...f, minStar: Number(e.target.value) || 0 }))} data-testid="hotel-cf-minstar" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Min Skor</Label>
                  <Input type="number" min="0" max="10" value={cf.minReview} onChange={(e) => setCf((f) => ({ ...f, minReview: Number(e.target.value) || 0 }))} data-testid="hotel-cf-minreview" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Harga Min</Label>
                  <Input type="number" value={cf.priceMin} onChange={(e) => setCf((f) => ({ ...f, priceMin: e.target.value }))} data-testid="hotel-cf-pricemin" />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Harga Maks</Label>
                  <Input type="number" value={cf.priceMax} onChange={(e) => setCf((f) => ({ ...f, priceMax: e.target.value }))} data-testid="hotel-cf-pricemax" />
                </div>
                <label className="flex items-center gap-2 pt-5 cursor-pointer text-xs" data-testid="hotel-cf-breakfast">
                  <Checkbox checked={cf.breakfast} onCheckedChange={(v) => setCf((f) => ({ ...f, breakfast: !!v }))} /> Sarapan
                </label>
                <label className="flex items-center gap-2 pt-5 cursor-pointer text-xs" data-testid="hotel-cf-wifi">
                  <Checkbox checked={cf.wifi} onCheckedChange={(v) => setCf((f) => ({ ...f, wifi: !!v }))} /> WiFi
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-xs col-span-2" data-testid="hotel-cf-discount">
                  <Checkbox checked={cf.discountOnly} onCheckedChange={(v) => setCf((f) => ({ ...f, discountOnly: !!v }))} /> Hanya yang diskon
                </label>
              </CardContent>
            </Card>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((h, i) => (
              <Card key={h.hotelId || i} className="border-slate-200 shadow-sm overflow-hidden flex flex-col" data-testid={`hotel-result-${h.hotelId || i}`}>
                <div className="aspect-video bg-slate-100 relative">
                  {h.imageURL ? <img src={h.imageURL} alt={h.hotelName} className="w-full h-full object-cover" />
                    : <div className="w-full h-full flex items-center justify-center text-slate-300 text-xs">Tanpa gambar</div>}
                  {Number(h.discountPercentage) > 0 && (
                    <span className="absolute top-2 left-2 bg-red-500 text-white text-[11px] font-semibold px-2 py-0.5 rounded-full">{Math.round(h.discountPercentage)}% OFF</span>
                  )}
                </div>
                <CardContent className="p-4 space-y-2 flex flex-col flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-semibold text-slate-800 text-sm leading-snug">{h.hotelName || "Hotel"}</h3>
                    <StarRow n={h.starRating} />
                  </div>
                  {h.roomtypeName && <p className="text-xs text-slate-500">{h.roomtypeName}</p>}
                  <div className="flex items-center gap-2 flex-wrap">
                    {h.reviewScore ? <Badge variant="outline" className="text-[10px]">{h.reviewScore}/10 · {h.reviewCount || 0} ulasan</Badge> : null}
                    {h.includeBreakfast && <Badge variant="secondary" className="text-[10px]"><Coffee className="h-3 w-3 mr-1" />Sarapan</Badge>}
                    {h.freeWifi && <Badge variant="secondary" className="text-[10px]"><Wifi className="h-3 w-3 mr-1" />WiFi</Badge>}
                  </div>
                  <div className="mt-auto flex items-end justify-between pt-2">
                    <div>
                      {Number(h.crossedOutRate) > 0 && Number(h.crossedOutRate) !== Number(h.dailyRate) ? <p className="text-xs text-slate-400 line-through">{rupiah(h.crossedOutRate, h.currency)}</p> : null}
                      <p className="text-base font-bold text-blue-600">{rupiah(h.dailyRate, h.currency)}<span className="text-xs font-normal text-slate-400">/malam</span></p>
                    </div>
                    <div className="flex gap-1">
                      {canQuote && (
                        <Button size="sm" variant="outline" onClick={() => setAddHotel(h)} data-testid={`hotel-addquote-${h.hotelId || i}`}><FilePlus2 className="h-3.5 w-3.5" /></Button>
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
        <DialogContent className="max-w-lg" data-testid="hotel-detail-dialog">
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
                  {detail.reviewScore ? <Badge variant="outline">{detail.reviewScore}/10 · {detail.reviewCount || 0} ulasan</Badge> : null}
                  {detail.includeBreakfast && <Badge variant="secondary"><Coffee className="h-3 w-3 mr-1" />Sarapan</Badge>}
                  {detail.freeWifi && <Badge variant="secondary"><Wifi className="h-3 w-3 mr-1" />WiFi</Badge>}
                </div>
                {detail.roomtypeName && <p className="text-sm text-slate-600">Tipe kamar: <span className="font-medium">{detail.roomtypeName}</span></p>}
                <div className="flex items-end gap-3">
                  {Number(detail.crossedOutRate) > 0 && Number(detail.crossedOutRate) !== Number(detail.dailyRate) ? <span className="text-sm text-slate-400 line-through">{rupiah(detail.crossedOutRate, detail.currency)}</span> : null}
                  <span className="text-2xl font-bold text-blue-600">{rupiah(detail.dailyRate, detail.currency)}</span>
                  <span className="text-sm text-slate-400">/malam</span>
                  {Number(detail.discountPercentage) > 0 && <Badge className="bg-red-500 hover:bg-red-500">{Math.round(detail.discountPercentage)}% OFF</Badge>}
                </div>
                <div className="flex gap-2">
                  {isAdmin && detail.landingURL ? (
                    <a href={detail.landingURL} target="_blank" rel="noreferrer" className="flex-1" data-testid="hotel-detail-book">
                      <Button className="w-full"><ExternalLink className="h-4 w-4 mr-2" />Book on Agoda</Button>
                    </a>
                  ) : <p className="text-xs text-slate-400 flex-1 self-center">{isAdmin ? "Tautan pemesanan tidak tersedia." : "Booking ke Agoda hanya oleh Super Admin."}</p>}
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
    </div>
  );
}
