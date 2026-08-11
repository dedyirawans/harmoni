import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { fmtIDR } from "@/config/crm";
import { PRODUCT_TYPES, PACKAGE_STATUSES, ROOM_TYPES, PKG_STATUS_COLORS, UMRAH_FIELDS, subLabel, SUB_FILTER } from "@/config/product";
import { ProductAdvancedFields } from "@/components/ProductAdvancedFields";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Search, Loader2, Package as PackageIcon, MapPin, Clock, Tag } from "lucide-react";
import { toast } from "sonner";

const EMPTY = {
  package_name: "", product_type: "TOUR", category: "", destination: "", country: "", duration: "",
  description: "", cover_image: "", min_pax: 1, max_pax: 40, selling_price: 0, child_price: 0,
  infant_price: 0, single_supplement: 0, currency: "IDR", tax_treatment: "Non-PPN",
  commission_eligibility: true, status: "DRAFT", promo_text: "", terms: "", umrah: {},
};

export default function Products() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { hasPerm } = useAuth();
  const canManage = hasPerm("product.manage");
  const canHpp = hasPerm("hpp.view");
  const base = pathname.startsWith("/packages") ? "/packages" : "/products";

  const [rows, setRows] = useState(null);
  const [q, setQ] = useState("");
  const [type, setType] = useState("all");
  const [sub, setSub] = useState("all");
  const [status, setStatus] = useState("all");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = () => {
    setRows(null);
    api.get("/packages", { params: { q: q || undefined, product_type: type, sub_category: sub, status } })
      .then((r) => setRows(r.data)).catch(() => setRows([]));
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [type, sub, status]);

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));
  const setU = (k) => (v) => setForm((f) => ({ ...f, umrah: { ...f.umrah, [k]: v } }));

  const save = async () => {
    if (!form.package_name.trim()) return toast.error("Package name is required");
    setSaving(true);
    try {
      const p = { ...form, min_pax: Number(form.min_pax), max_pax: Number(form.max_pax),
        selling_price: Number(form.selling_price), child_price: Number(form.child_price),
        infant_price: Number(form.infant_price), single_supplement: Number(form.single_supplement),
        min_quota_pax: Number(form.min_quota_pax || 0), tour_price_portion: Number(form.tour_price_portion || 0),
        pricing_tiers: (form.pricing_tiers || []).map((t) => ({ min_pax: Number(t.min_pax || 0), max_pax: Number(t.max_pax || 0), price: Number(t.price || 0) })) };
      await api.post("/packages", p);
      toast.success("Package created"); setOpen(false); setForm(EMPTY); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-6" data-testid="products-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">{canManage ? "Product Management" : "Packages"}</h1>
          <p className="text-slate-500 mt-1">{canManage ? "Manage tour & umrah packages, pricing, itinerary and departures." : "Browse active packages available to sell."}</p>
        </div>
        {canManage && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button className="bg-blue-600 hover:bg-blue-700" data-testid="add-package-button"><Plus className="h-4 w-4 mr-2" aria-hidden="true" />New Package</Button></DialogTrigger>
            <DialogContent className="bg-white max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="package-dialog">
              <DialogHeader><DialogTitle className="font-display">New Package</DialogTitle><DialogDescription>Create a tour or umrah package.</DialogDescription></DialogHeader>
              <div className="grid grid-cols-2 gap-4 py-2">
                <F label="Package Name *" full><Input value={form.package_name} onChange={(e) => set("package_name")(e.target.value)} data-testid="package-name-input" /></F>
                <F label="Product Type"><Select value={form.product_type} onValueChange={set("product_type")}><SelectTrigger data-testid="package-type-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white">{PRODUCT_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}</SelectContent></Select></F>
                <F label="Category"><Input value={form.category} onChange={(e) => set("category")(e.target.value)} placeholder="e.g. Umrah VIP / Japan" /></F>
                <F label="Destination"><Input value={form.destination} onChange={(e) => set("destination")(e.target.value)} /></F>
                <F label="Country"><Input value={form.country} onChange={(e) => set("country")(e.target.value)} /></F>
                <F label="Duration"><Input value={form.duration} onChange={(e) => set("duration")(e.target.value)} placeholder="e.g. 9 Days" /></F>
                <F label="Status"><Select value={form.status} onValueChange={set("status")}><SelectTrigger data-testid="package-status-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white">{PACKAGE_STATUSES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></F>
                <ProductAdvancedFields f={form} set={set} />
                <F label="Selling Price"><Input type="number" value={form.selling_price} onChange={(e) => set("selling_price")(e.target.value)} data-testid="package-price-input" /></F>
                <F label="Child Price"><Input type="number" value={form.child_price} onChange={(e) => set("child_price")(e.target.value)} /></F>
                <F label="Infant Price"><Input type="number" value={form.infant_price} onChange={(e) => set("infant_price")(e.target.value)} /></F>
                <F label="Single Supplement"><Input type="number" value={form.single_supplement} onChange={(e) => set("single_supplement")(e.target.value)} /></F>
                <F label="Min Pax"><Input type="number" value={form.min_pax} onChange={(e) => set("min_pax")(e.target.value)} /></F>
                <F label="Max Pax"><Input type="number" value={form.max_pax} onChange={(e) => set("max_pax")(e.target.value)} /></F>
                <F label="Cover Image URL" full><Input value={form.cover_image} onChange={(e) => set("cover_image")(e.target.value)} /></F>
                <F label="Description" full><Textarea value={form.description} onChange={(e) => set("description")(e.target.value)} /></F>
                <F label="Promo Text" full><Input value={form.promo_text} onChange={(e) => set("promo_text")(e.target.value)} /></F>
                {form.product_type === "UMROH" && (
                  <div className="col-span-2 border-t pt-3">
                    <p className="text-xs font-semibold uppercase text-slate-500 mb-2">Umrah Details</p>
                    <div className="grid grid-cols-2 gap-3">
                      {UMRAH_FIELDS.map(([k, l]) => k === "room_type" ? (
                        <F key={k} label={l}><Select value={form.umrah[k] || ""} onValueChange={setU(k)}><SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger><SelectContent className="bg-white">{ROOM_TYPES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent></Select></F>
                      ) : (
                        <F key={k} label={l}><Input value={form.umrah[k] || ""} onChange={(e) => setU(k)(e.target.value)} /></F>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <DialogFooter><Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="package-save-button">{saving ? "Saving..." : "Create package"}</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <Input className="pl-9" placeholder="Search package, destination..." value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} data-testid="package-search-input" />
        </div>
        <Select value={type} onValueChange={setType}><SelectTrigger className="w-40" data-testid="package-type-filter"><SelectValue placeholder="Kategori" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Semua Kategori</SelectItem>{PRODUCT_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}</SelectContent></Select>
        <Select value={sub} onValueChange={setSub}><SelectTrigger className="w-40" data-testid="package-sub-filter"><SelectValue placeholder="Sub Kategori" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Semua Sub Kategori</SelectItem>{SUB_FILTER.map((s) => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}</SelectContent></Select>
        {canManage && <Select value={status} onValueChange={setStatus}><SelectTrigger className="w-40" data-testid="package-status-filter"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">All status</SelectItem>{PACKAGE_STATUSES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select>}
        <Button variant="outline" onClick={load}>Search</Button>
      </div>

      {rows === null ? (
        <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
      ) : rows.length === 0 ? (
        <Card className="border-slate-200"><CardContent className="p-12 text-center text-slate-500"><PackageIcon className="h-8 w-8 mx-auto text-slate-300" aria-hidden="true" /><p className="mt-2">No packages found.</p></CardContent></Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="packages-grid">
          {rows.map((p) => (
            <Card key={p._id} onClick={() => navigate(`${base}/${p._id}`)} className="border-slate-200 shadow-sm hover:shadow-md transition-shadow duration-200 cursor-pointer overflow-hidden" data-testid={`package-card-${p._id}`}>
              <div className="h-28 bg-slate-100 relative">
                {p.cover_image ? <img src={p.cover_image} alt="" className="h-full w-full object-cover" /> : <div className="h-full w-full flex items-center justify-center"><PackageIcon className="h-8 w-8 text-slate-300" aria-hidden="true" /></div>}
                <Badge variant="outline" className={`absolute top-2 right-2 ${PKG_STATUS_COLORS[p.status]}`}>{p.status}</Badge>
                <Badge variant="outline" className="absolute top-2 left-2 bg-white/90 text-slate-700">{subLabel(p.product_type, p.sub_category) || p.product_type}</Badge>
              </div>
              <CardContent className="p-4">
                <p className="text-[10px] font-mono text-slate-400">{p.package_code}</p>
                <h3 className="font-display font-semibold text-slate-900 mt-0.5">{p.package_name}</h3>
                <div className="flex items-center gap-3 text-xs text-slate-500 mt-2">
                  <span className="flex items-center gap-1"><MapPin className="h-3 w-3" aria-hidden="true" />{p.destination || "—"}</span>
                  <span className="flex items-center gap-1"><Clock className="h-3 w-3" aria-hidden="true" />{p.duration || "—"}</span>
                </div>
                {p.promo_text && <p className="mt-2 text-xs text-blue-700 flex items-center gap-1"><Tag className="h-3 w-3" aria-hidden="true" />{p.promo_text}</p>}
                <div className="flex items-center justify-between mt-3">
                  <span className="font-display text-lg font-bold text-slate-900">{fmtIDR(p.selling_price)}</span>
                  {canHpp && p.gross_margin != null && <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">GM {p.gross_margin}%</Badge>}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function F({ label, children, full }) {
  return <div className={`space-y-2 ${full ? "col-span-2" : "col-span-2 sm:col-span-1"}`}><Label>{label}</Label>{children}</div>;
}
