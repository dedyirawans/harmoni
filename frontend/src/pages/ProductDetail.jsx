import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { fmtIDR, fmtDate } from "@/config/crm";
import { PACKAGE_STATUSES, ROOM_TYPES, PKG_STATUS_COLORS, DEP_STATUS_COLORS, UMRAH_FIELDS, COST_COMPONENTS, PRODUCT_TYPES, subLabel } from "@/config/product";
import { ProductAdvancedFields } from "@/components/ProductAdvancedFields";
import { BrochureTab } from "@/components/BrochureTab";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { ArrowLeft, Loader2, Plus, Pencil, Trash2, Copy, GripVertical, Calendar } from "lucide-react";
import { toast } from "sonner";

export default function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { hasPerm } = useAuth();
  const canManage = hasPerm("product.manage");
  const canHpp = hasPerm("hpp.view");
  const backBase = pathname.startsWith("/packages") ? "/packages" : "/products";

  const [data, setData] = useState(undefined);
  const [editOpen, setEditOpen] = useState(false);
  const [depOpen, setDepOpen] = useState(false);
  const [itinOpen, setItinOpen] = useState(null); // null | {} | itinerary

  const load = useCallback(() => {
    api.get(`/packages/${id}`).then((r) => setData(r.data)).catch((e) => {
      setData(null); if (e.response?.status === 403) toast.error("Package not available");
    });
  }, [id]);
  useEffect(() => { load(); }, [load]);

  if (data === undefined) return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  if (data === null) return <div className="p-12 text-center" data-testid="product-forbidden"><p className="text-red-600 font-medium">Package not available (403 / not found).</p><Button variant="outline" className="mt-4" onClick={() => navigate(backBase)}>Back</Button></div>;

  const p = data.package;
  const isUmrah = p.product_type === "UMROH";

  const setStatus = async (s) => {
    try { await api.patch(`/packages/${id}/status`, { stage: s }); toast.success(`Status: ${s}`); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const delItin = async (iid) => { try { await api.delete(`/itineraries/${iid}`); load(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  const dupItin = async (iid) => { try { await api.post(`/itineraries/${iid}/duplicate`); load(); toast.success("Day duplicated"); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };

  return (
    <div className="space-y-6" data-testid="product-detail-page">
      <button onClick={() => navigate(backBase)} className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900" data-testid="product-back"><ArrowLeft className="h-4 w-4" aria-hidden="true" />Back to packages</button>

      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-3xl font-bold text-slate-900">{p.package_name}</h1>
            <Badge variant="outline" className={PKG_STATUS_COLORS[p.status]}>{p.status}</Badge>
            <Badge variant="outline" className="bg-slate-100 text-slate-700">{p.product_type}</Badge>
          </div>
          <p className="text-slate-500 mt-1 font-mono text-xs">{p.package_code} · v{p.version} · {p.destination}</p>
        </div>
        {canManage && (
          <div className="flex items-center gap-2">
            <Select value={p.status} onValueChange={setStatus}><SelectTrigger className="w-36" data-testid="detail-status-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white">{PACKAGE_STATUSES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select>
            <Button onClick={() => setEditOpen(true)} className="bg-blue-600 hover:bg-blue-700" data-testid="edit-package-button"><Pencil className="h-4 w-4 mr-2" aria-hidden="true" />Edit</Button>
          </div>
        )}
      </div>

      <Tabs defaultValue="overview">
        <TabsList data-testid="detail-tabs">
          <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
          <TabsTrigger value="itinerary" data-testid="tab-itinerary">Itinerary</TabsTrigger>
          <TabsTrigger value="departures" data-testid="tab-departures">Departures</TabsTrigger>
          <TabsTrigger value="brochures" data-testid="tab-brochures">Brosur</TabsTrigger>
          {isUmrah && <TabsTrigger value="umrah" data-testid="tab-umrah">Umrah</TabsTrigger>}
          {canHpp && <TabsTrigger value="costing" data-testid="tab-costing">Costing / HPP</TabsTrigger>}
          {canManage && <TabsTrigger value="versions" data-testid="tab-versions">Versions</TabsTrigger>}
        </TabsList>

        <TabsContent value="overview">
          <GalleryManager pkg={p} canManage={canManage} onChange={load} />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card className="border-slate-200 lg:col-span-2"><CardContent className="p-6">
              <p className="text-slate-600 leading-relaxed">{p.description || "No description."}</p>
              {p.promo_text && <p className="mt-3 text-sm text-blue-700 bg-blue-50 border border-blue-200 rounded-md px-3 py-2">Promo: {p.promo_text}</p>}
              {p.terms && <div className="mt-4"><p className="text-xs font-semibold uppercase text-slate-500 mb-1">Terms & Conditions</p><p className="text-sm text-slate-600">{p.terms}</p></div>}
              {p.include && <div className="mt-4"><p className="text-xs font-semibold uppercase text-emerald-600 mb-1">Include (Harga Sudah Termasuk)</p><p className="text-sm text-slate-600 whitespace-pre-line" data-testid="detail-include">{p.include}</p></div>}
              {p.exclude && <div className="mt-4"><p className="text-xs font-semibold uppercase text-rose-600 mb-1">Exclude (Tidak Termasuk)</p><p className="text-sm text-slate-600 whitespace-pre-line" data-testid="detail-exclude">{p.exclude}</p></div>}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-5 text-sm">
                <Info label="Country" v={p.country} /><Info label="Duration" v={p.duration} /><Info label="Category" v={p.category} />
                <Info label="Sub Category" v={subLabel(p.product_type, p.sub_category)} />
                <Info label="Min / Max Pax" v={`${p.min_pax} - ${p.max_pax}`} /><Info label="Currency" v={p.currency} />
                <Info label="Pajak Kategori" v={`${p.tax_percent || 0}%${p.tax_amount ? " · " + fmtIDR(p.tax_amount) : ""}`} />
                <Info label="Tax Treatment" v={p.tax_treatment} />
              </div>
            </CardContent></Card>
            <Card className="border-slate-200"><CardContent className="p-6 space-y-3">
              <Price label="Selling Price" v={p.selling_price} big />
              <Price label="Child Price" v={p.child_price} />
              <Price label="Infant Price" v={p.infant_price} />
              <Price label="Single Supplement" v={p.single_supplement} />
              {p.sub_category === "PRIVATE" && (p.pricing_tiers || []).length > 0 && (
                <div className="pt-3 border-t space-y-1" data-testid="detail-tiers">
                  <p className="text-xs font-semibold uppercase text-slate-500">Harga Berjenjang</p>
                  {p.pricing_tiers.map((t, i) => (
                    <div key={i} className="flex justify-between text-sm"><span className="text-slate-500">{t.min_pax}–{t.max_pax} pax</span><span className="font-medium text-slate-800">{fmtIDR(t.price)}</span></div>
                  ))}
                </div>
              )}
              {["OPEN_TRIP", "SEAT_IN_COACH"].includes(p.sub_category) && p.min_quota_pax > 0 && (
                <div className="flex justify-between text-sm pt-2 border-t"><span className="text-slate-500">Min. Kuota Pax</span><span className="font-medium text-slate-800">{p.min_quota_pax}</span></div>
              )}
              {canHpp && p.gross_margin != null && (
                <div className="pt-3 border-t space-y-1">
                  <Price label="HPP (Cost/Pax)" v={p.cost_per_pax} />
                  <div className="flex justify-between text-sm"><span className="text-slate-500">Gross Profit</span><span className="font-medium text-emerald-700">{fmtIDR(p.gross_profit)}</span></div>
                  <div className="flex justify-between text-sm"><span className="text-slate-500">Gross Margin</span><Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">{p.gross_margin}%</Badge></div>
                </div>
              )}
            </CardContent></Card>
          </div>
        </TabsContent>

        <TabsContent value="itinerary">
          <ItineraryTab pkgId={id} items={data.itineraries} canManage={canManage} onChange={load} onEdit={setItinOpen} onDelete={delItin} onDup={dupItin} />
        </TabsContent>

        <TabsContent value="departures">
          <DeparturesTab items={data.departures} canManage={canManage} onAdd={() => setDepOpen(true)} pkgId={id} onChange={load} />
        </TabsContent>

        <TabsContent value="brochures">
          <BrochureTab pkgId={id} canManage={canManage} />
        </TabsContent>

        {isUmrah && (
          <TabsContent value="umrah">
            <Card className="border-slate-200"><CardContent className="p-6 grid grid-cols-2 sm:grid-cols-3 gap-4">
              {UMRAH_FIELDS.map(([k, l]) => <Info key={k} label={l} v={p.umrah?.[k]} />)}
            </CardContent></Card>
          </TabsContent>
        )}

        {canHpp && (
          <TabsContent value="costing">
            <CostingTab pkgId={id} sellingPrice={p.selling_price} costing={data.costing} canManage={canManage} onChange={load} />
          </TabsContent>
        )}

        {canManage && (
          <TabsContent value="versions">
            <Card className="border-slate-200"><CardContent className="p-4 space-y-2">
              <div className="flex items-center justify-between border border-blue-100 bg-blue-50/40 rounded-md p-3">
                <span className="text-sm font-medium text-slate-900">Current — v{p.version}</span><span className="font-medium">{fmtIDR(p.selling_price)}</span>
              </div>
              {(data.versions || []).length === 0 ? <p className="text-sm text-slate-400 text-center py-4">No previous versions. New versions are created automatically when selling price changes.</p> :
                data.versions.map((v) => (
                  <div key={v._id} className="flex items-center justify-between border border-slate-100 rounded-md p-3">
                    <span className="text-sm text-slate-700">Version {v.version}</span>
                    <div className="flex items-center gap-3"><span className="text-slate-600">{fmtIDR(v.selling_price)}</span><span className="text-xs text-slate-400">{fmtDate(v.created_at)}</span></div>
                  </div>
                ))}
            </CardContent></Card>
          </TabsContent>
        )}
      </Tabs>

      {canManage && editOpen && <PackageEditDialog pkg={p} onClose={() => setEditOpen(false)} onSaved={() => { setEditOpen(false); load(); }} />}
      {canManage && depOpen && <DepartureDialog pkgId={id} onClose={() => setDepOpen(false)} onSaved={() => { setDepOpen(false); load(); }} />}
      {canManage && itinOpen !== null && <ItineraryDialog pkgId={id} itin={itinOpen} onClose={() => setItinOpen(null)} onSaved={() => { setItinOpen(null); load(); }} />}
    </div>
  );
}

const Info = ({ label, v }) => <div><p className="text-xs text-slate-400">{label}</p><p className="text-slate-800 font-medium">{v || "—"}</p></div>;
const Price = ({ label, v, big }) => <div className="flex justify-between items-center"><span className="text-slate-500 text-sm">{label}</span><span className={big ? "font-display text-2xl font-bold text-slate-900" : "font-medium text-slate-800"}>{fmtIDR(v)}</span></div>;

function ItineraryTab({ pkgId, items, canManage, onChange, onEdit, onDelete, onDup }) {
  const [order, setOrder] = useState(items);
  const [dragId, setDragId] = useState(null);
  useEffect(() => setOrder(items), [items]);

  const onDrop = async (targetId) => {
    if (!dragId || dragId === targetId) return;
    const arr = [...order];
    const from = arr.findIndex((x) => x._id === dragId);
    const to = arr.findIndex((x) => x._id === targetId);
    const [moved] = arr.splice(from, 1); arr.splice(to, 0, moved);
    setOrder(arr); setDragId(null);
    try { await api.put(`/packages/${pkgId}/itineraries/reorder`, { ids: arr.map((x) => x._id) }); toast.success("Reordered"); onChange(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <Card className="border-slate-200"><CardContent className="p-4 space-y-3" data-testid="itinerary-list">
      {canManage && <Button size="sm" onClick={() => onEdit({})} className="bg-blue-600 hover:bg-blue-700" data-testid="add-itinerary-button"><Plus className="h-4 w-4 mr-1" aria-hidden="true" />Add Day</Button>}
      {order.length === 0 ? <p className="text-sm text-slate-400 text-center py-6">No itinerary yet.</p> :
        order.map((it, i) => (
          <div key={it._id}
            draggable={canManage} onDragStart={() => canManage && setDragId(it._id)}
            onDragOver={(e) => canManage && e.preventDefault()} onDrop={() => onDrop(it._id)}
            className={`flex gap-3 border border-slate-200 rounded-md p-3 ${canManage ? "cursor-grab" : ""} ${dragId === it._id ? "opacity-50" : ""}`} data-testid={`itinerary-day-${it._id}`}>
            {canManage && <GripVertical className="h-4 w-4 text-slate-300 mt-1 shrink-0" aria-hidden="true" />}
            <div className="h-8 w-8 rounded-md bg-blue-600 text-white text-sm font-bold flex items-center justify-center shrink-0">{i + 1}</div>
            <div className="flex-1">
              <p className="font-medium text-slate-900">{it.location || "Day " + (i + 1)}</p>
              <p className="text-sm text-slate-600">{it.activity}</p>
              <div className="flex flex-wrap gap-2 mt-1 text-xs text-slate-400">
                {it.hotel && <span>🏨 {it.hotel}</span>}{it.meal && <span>🍽 {it.meal}</span>}{it.transport && <span>🚌 {it.transport}</span>}{it.flight && <span>✈ {it.flight}</span>}
              </div>
            </div>
            {canManage && (
              <div className="flex items-start gap-1">
                <Button size="icon" variant="ghost" onClick={() => onEdit(it)} data-testid={`edit-itin-${it._id}`}><Pencil className="h-4 w-4" aria-hidden="true" /></Button>
                <Button size="icon" variant="ghost" onClick={() => onDup(it._id)}><Copy className="h-4 w-4" aria-hidden="true" /></Button>
                <Button size="icon" variant="ghost" onClick={() => onDelete(it._id)} className="text-red-600"><Trash2 className="h-4 w-4" aria-hidden="true" /></Button>
              </div>
            )}
          </div>
        ))}
    </CardContent></Card>
  );
}

function DeparturesTab({ items, canManage, onAdd, pkgId, onChange }) {
  const del = async (did) => { try { await api.delete(`/departures/${did}`); onChange(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  return (
    <Card className="border-slate-200"><CardContent className="p-4 space-y-3" data-testid="departures-list">
      {canManage && <Button size="sm" onClick={onAdd} className="bg-blue-600 hover:bg-blue-700" data-testid="add-departure-button"><Plus className="h-4 w-4 mr-1" aria-hidden="true" />Add Departure</Button>}
      {items.length === 0 ? <p className="text-sm text-slate-400 text-center py-6">No departures.</p> :
        items.map((d) => (
          <div key={d._id} className="flex items-center justify-between border border-slate-200 rounded-md p-3" data-testid={`dep-row-${d._id}`}>
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-md bg-blue-50 flex items-center justify-center"><Calendar className="h-4 w-4 text-blue-600" aria-hidden="true" /></div>
              <div><p className="font-medium text-slate-900">{fmtDate(d.departure_date)} → {fmtDate(d.return_date)}</p>
                <p className="text-xs text-slate-500">{d.flight} · {d.available_seat}/{d.quota} seats · {fmtIDR(d.price)}</p></div>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className={DEP_STATUS_COLORS[d.status] || "bg-slate-100"}>{d.status}</Badge>
              {canManage && <Button size="icon" variant="ghost" onClick={() => del(d._id)} className="text-red-600"><Trash2 className="h-4 w-4" aria-hidden="true" /></Button>}
            </div>
          </div>
        ))}
    </CardContent></Card>
  );
}

function CostingTab({ pkgId, sellingPrice, costing, canManage, onChange }) {
  const init = {};
  COST_COMPONENTS.forEach(([k]) => { init[k] = costing?.components?.[k] || 0; });
  const [comp, setComp] = useState(init);
  const [saving, setSaving] = useState(false);
  const [supCosts, setSupCosts] = useState([]);
  useEffect(() => { api.get(`/supplier-costs?package_id=${pkgId}`).then((r) => setSupCosts(r.data || [])).catch(() => setSupCosts([])); }, [pkgId]);

  const total = Object.values(comp).reduce((a, b) => a + Number(b || 0), 0);
  const supTotal = supCosts.reduce((a, c) => a + Number(c.total_cost || 0), 0);
  const combined = total + supTotal;
  const gp = Number(sellingPrice || 0) - combined;
  const gm = sellingPrice ? ((gp / sellingPrice) * 100).toFixed(2) : 0;

  const save = async () => {
    setSaving(true);
    try { await api.put(`/packages/${pkgId}/costing`, { components: comp }); toast.success("Costing saved"); onChange(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4" data-testid="costing-tab">
      <div className="lg:col-span-2 space-y-4">
        <Card className="border-slate-200"><CardHeader><CardTitle className="font-display text-lg">Cost Components (per pax)</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-2 gap-3">
            {COST_COMPONENTS.map(([k, l]) => (
              <div key={k} className="space-y-1"><Label className="text-xs">{l}</Label>
                <Input type="number" value={comp[k]} disabled={!canManage} onChange={(e) => setComp({ ...comp, [k]: e.target.value })} data-testid={`cost-${k}`} /></div>
            ))}
            {canManage && <div className="col-span-2"><Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="save-costing-button">{saving ? "Saving..." : "Save costing"}</Button></div>}
          </CardContent>
        </Card>
        <Card className="border-slate-200" data-testid="linked-supplier-costs">
          <CardHeader><CardTitle className="font-display text-lg">Linked Supplier Costs</CardTitle></CardHeader>
          <CardContent>
            {supCosts.length === 0 ? <p className="text-sm text-slate-400" data-testid="no-supplier-costs">Belum ada biaya supplier tertaut. Tambahkan via menu Suppliers → Supplier Costs.</p>
              : <div className="space-y-2">
                  {supCosts.map((c) => (
                    <div key={c._id} className="flex justify-between text-sm border-b border-slate-100 pb-1" data-testid={`linked-cost-${c._id}`}>
                      <span className="text-slate-600">{c.supplier_name || "—"}<span className="text-slate-400"> · {c.service || "-"} ({c.quantity}×)</span></span>
                      <span className="font-medium text-slate-800">{fmtIDR(c.total_cost)}</span>
                    </div>
                  ))}
                  <div className="flex justify-between pt-1"><span className="text-slate-500 text-sm">Total Supplier Cost</span><span className="font-medium text-blue-700" data-testid="linked-supplier-total">{fmtIDR(supTotal)}</span></div>
                </div>}
          </CardContent>
        </Card>
      </div>
      <Card className="border-slate-200"><CardContent className="p-6 space-y-3">
        <Price label="Selling Price" v={sellingPrice} />
        <Price label="Component Cost (per pax)" v={total} />
        <Price label="Supplier Cost" v={supTotal} />
        <div className="flex justify-between items-center pt-2 border-t"><span className="text-slate-600 text-sm font-medium">Total Cost (HPP)</span><span className="font-medium text-slate-900" data-testid="combined-hpp-value">{fmtIDR(combined)}</span></div>
        <div className="flex justify-between items-center pt-2 border-t"><span className="text-slate-500 text-sm">Gross Profit</span><span className="font-medium text-emerald-700">{fmtIDR(gp)}</span></div>
        <div className="flex justify-between items-center"><span className="text-slate-500 text-sm">Gross Margin</span><Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200" data-testid="gross-margin-value">{gm}%</Badge></div>
      </CardContent></Card>
    </div>
  );
}

function GalleryManager({ pkg, canManage, onChange }) {
  const [box, setBox] = useState(null);
  const gallery = pkg.gallery || [];
  const put = async (patch) => {
    try { await api.put(`/packages/${pkg._id}`, { ...pkg, umrah: pkg.umrah || {}, ...patch }); onChange && onChange(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const addFiles = (files) => {
    const arr = Array.from(files || []); if (!arr.length) return;
    const reads = arr.map((f) => new Promise((res) => {
      if (f.size > 5 * 1024 * 1024) { toast.error(`${f.name} > 5MB`); return res(null); }
      const r = new FileReader(); r.onload = () => res(r.result); r.readAsDataURL(f);
    }));
    Promise.all(reads).then((urls) => { const clean = urls.filter(Boolean); if (clean.length) { put({ gallery: [...gallery, ...clean] }).then(() => toast.success("Foto ditambahkan")); } });
  };
  return (
    <div className="mb-4" data-testid="detail-cover-wrap">
      {pkg.cover_image && (
        <div className="aspect-video max-h-72 w-full overflow-hidden rounded-lg bg-slate-100 border border-slate-200">
          <img src={pkg.cover_image} alt={pkg.package_name} onClick={() => setBox(pkg.cover_image)} className="h-full w-full object-cover cursor-zoom-in" data-testid="detail-cover-img" />
        </div>
      )}
      <div className="mt-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase text-slate-500">Galeri Foto</p>
        {canManage && (
          <label className="text-xs text-blue-700 cursor-pointer hover:underline" data-testid="gallery-add">
            <input type="file" accept="image/*" multiple className="hidden" onChange={(e) => addFiles(e.target.files)} />+ Tambah Foto
          </label>
        )}
      </div>
      <div className="mt-2 grid grid-cols-3 sm:grid-cols-4 gap-2" data-testid="detail-gallery">
        {gallery.filter(Boolean).map((g, i) => (
          <div key={i} className="relative group aspect-video overflow-hidden rounded-md bg-slate-100 border border-slate-200">
            <img src={g} alt={`galeri ${i + 1}`} onClick={() => setBox(g)} className="h-full w-full object-cover cursor-zoom-in" data-testid={`detail-gallery-img-${i}`} />
            {canManage && (
              <div className="absolute inset-x-0 bottom-0 flex justify-between bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity px-1.5 py-1">
                <button onClick={() => put({ cover_image: g })} className="text-[10px] font-medium text-white hover:underline" data-testid={`gallery-setcover-${i}`}>Jadikan Cover</button>
                <button onClick={() => put({ gallery: gallery.filter((_, k) => k !== i) })} className="text-[10px] font-medium text-red-200 hover:underline" data-testid={`gallery-del-${i}`}>Hapus</button>
              </div>
            )}
          </div>
        ))}
        {gallery.filter(Boolean).length === 0 && <p className="text-xs text-slate-400 col-span-full">Belum ada foto galeri.</p>}
      </div>
      {box && (
        <div className="fixed inset-0 z-[80] bg-black/80 flex items-center justify-center p-6 cursor-zoom-out" onClick={() => setBox(null)} data-testid="gallery-lightbox">
          <img src={box} alt="preview" className="max-h-[90vh] max-w-[90vw] rounded-lg object-contain shadow-2xl" />
        </div>
      )}
    </div>
  );
}

function PackageEditDialog({ pkg, onClose, onSaved }) {
  const [f, setF] = useState({ ...pkg, umrah: pkg.umrah || {} });
  const [saving, setSaving] = useState(false);
  const set = (k) => (v) => setF((o) => ({ ...o, [k]: v }));
  const setU = (k) => (v) => setF((o) => ({ ...o, umrah: { ...o.umrah, [k]: v } }));
  const save = async () => {
    setSaving(true);
    try {
      const body = { package_name: f.package_name, product_type: f.product_type, sub_category: f.sub_category, category: f.category, destination: f.destination,
        country: f.country, duration: f.duration, description: f.description, cover_image: f.cover_image, gallery: f.gallery || [],
        min_pax: Number(f.min_pax), max_pax: Number(f.max_pax), selling_price: Number(f.selling_price), child_price: Number(f.child_price),
        infant_price: Number(f.infant_price), single_supplement: Number(f.single_supplement), currency: f.currency,
        min_quota_pax: Number(f.min_quota_pax || 0), tour_price_portion: Number(f.tour_price_portion || 0),
        pricing_tiers: (f.pricing_tiers || []).map((t) => ({ min_pax: Number(t.min_pax || 0), max_pax: Number(t.max_pax || 0), price: Number(t.price || 0) })),
        tax_treatment: f.tax_treatment, commission_eligibility: f.commission_eligibility, status: f.status,
        max_discount_type: f.max_discount_type || "PERCENT", max_discount_value: Number(f.max_discount_value || 0),
        promo_text: f.promo_text, terms: f.terms, include: f.include, exclude: f.exclude, umrah: f.umrah };
      await api.put(`/packages/${pkg._id}`, body); toast.success("Package updated"); onSaved();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-white max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="package-edit-dialog">
        <DialogHeader><DialogTitle className="font-display">Edit Package</DialogTitle><DialogDescription>Changing the selling price creates a new version automatically.</DialogDescription></DialogHeader>
        <div className="grid grid-cols-2 gap-4 py-2">
          <EF label="Package Name" full><Input value={f.package_name} onChange={(e) => set("package_name")(e.target.value)} data-testid="edit-name-input" /></EF>
          <EF label="Include (Harga Sudah Termasuk — satu per baris)" full><textarea value={f.include || ""} onChange={(e) => set("include")(e.target.value)} rows={3} className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" data-testid="edit-include" /></EF>
          <EF label="Exclude (Tidak Termasuk — satu per baris)" full><textarea value={f.exclude || ""} onChange={(e) => set("exclude")(e.target.value)} rows={3} className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm" data-testid="edit-exclude" /></EF>
          <EF label="Destination"><Input value={f.destination} onChange={(e) => set("destination")(e.target.value)} /></EF>
          <EF label="Duration"><Input value={f.duration} onChange={(e) => set("duration")(e.target.value)} /></EF>
          <EF label="Selling Price"><Input type="number" value={f.selling_price} onChange={(e) => set("selling_price")(e.target.value)} data-testid="edit-price-input" /></EF>
          <EF label="Maks Diskon (Tipe)"><Select value={f.max_discount_type || "PERCENT"} onValueChange={set("max_discount_type")}><SelectTrigger data-testid="edit-max-discount-type"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="PERCENT">Persen (%)</SelectItem><SelectItem value="NOMINAL">Nominal (Rp)</SelectItem></SelectContent></Select></EF>
          <EF label="Maks Diskon (Nilai)"><Input type="number" value={f.max_discount_value ?? 0} onChange={(e) => set("max_discount_value")(e.target.value)} data-testid="edit-max-discount-value" /></EF>
          <EF label="Child Price"><Input type="number" value={f.child_price} onChange={(e) => set("child_price")(e.target.value)} /></EF>
          <EF label="Status"><Select value={f.status} onValueChange={set("status")}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent className="bg-white">{PACKAGE_STATUSES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></EF>
          <EF label="Product Type"><Select value={f.product_type} onValueChange={set("product_type")}><SelectTrigger data-testid="edit-type-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white">{PRODUCT_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}</SelectContent></Select></EF>
          <ProductAdvancedFields f={f} set={set} />
          <EF label="Description" full><Textarea value={f.description} onChange={(e) => set("description")(e.target.value)} /></EF>
          <EF label="Promo Text" full><Input value={f.promo_text} onChange={(e) => set("promo_text")(e.target.value)} /></EF>
          <EF label="Terms" full><Textarea value={f.terms} onChange={(e) => set("terms")(e.target.value)} /></EF>
          {f.product_type === "UMRAH" && (
            <div className="col-span-2 border-t pt-3 grid grid-cols-2 gap-3">
              {UMRAH_FIELDS.map(([k, l]) => k === "room_type" ? (
                <EF key={k} label={l}><Select value={f.umrah?.[k] || ""} onValueChange={setU(k)}><SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger><SelectContent className="bg-white">{ROOM_TYPES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent></Select></EF>
              ) : <EF key={k} label={l}><Input value={f.umrah?.[k] || ""} onChange={(e) => setU(k)(e.target.value)} /></EF>)}
            </div>
          )}
        </div>
        <DialogFooter><Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="save-package-edit">{saving ? "Saving..." : "Save changes"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DepartureDialog({ pkgId, onClose, onSaved }) {
  const [f, setF] = useState({ departure_date: "", return_date: "", quota: 40, confirmed_pax: 0, flight: "", hotel: "", price: 0, status: "" });
  const [saving, setSaving] = useState(false);
  const set = (k) => (v) => setF((o) => ({ ...o, [k]: v }));
  const save = async () => {
    if (!f.departure_date) return toast.error("Departure date required");
    setSaving(true);
    try { await api.post(`/packages/${pkgId}/departures`, { ...f, quota: Number(f.quota), confirmed_pax: Number(f.confirmed_pax), price: Number(f.price) }); toast.success("Departure added"); onSaved(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-white" data-testid="departure-dialog">
        <DialogHeader><DialogTitle className="font-display">Add Departure</DialogTitle><DialogDescription>Available seat = quota − confirmed pax.</DialogDescription></DialogHeader>
        <div className="grid grid-cols-2 gap-4 py-2">
          <EF label="Departure Date"><Input type="date" value={f.departure_date} onChange={(e) => set("departure_date")(e.target.value)} data-testid="dep-date-input" /></EF>
          <EF label="Return Date"><Input type="date" value={f.return_date} onChange={(e) => set("return_date")(e.target.value)} /></EF>
          <EF label="Quota"><Input type="number" value={f.quota} onChange={(e) => set("quota")(e.target.value)} data-testid="dep-quota-input" /></EF>
          <EF label="Confirmed Pax"><Input type="number" value={f.confirmed_pax} onChange={(e) => set("confirmed_pax")(e.target.value)} /></EF>
          <EF label="Flight"><Input value={f.flight} onChange={(e) => set("flight")(e.target.value)} /></EF>
          <EF label="Price"><Input type="number" value={f.price} onChange={(e) => set("price")(e.target.value)} data-testid="dep-price-input" /></EF>
        </div>
        <DialogFooter><Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="save-departure-button">{saving ? "Saving..." : "Add departure"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ItineraryDialog({ pkgId, itin, onClose, onSaved }) {
  const [f, setF] = useState({ location: "", activity: "", hotel: "", meal: "", transport: "", flight: "", description: "", notes: "", ...itin });
  const [saving, setSaving] = useState(false);
  const set = (k) => (v) => setF((o) => ({ ...o, [k]: v }));
  const save = async () => {
    setSaving(true);
    try {
      if (itin && itin._id) await api.put(`/itineraries/${itin._id}`, f);
      else await api.post(`/packages/${pkgId}/itineraries`, f);
      toast.success("Saved"); onSaved();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-white" data-testid="itinerary-dialog">
        <DialogHeader><DialogTitle className="font-display">{itin && itin._id ? "Edit Day" : "Add Day"}</DialogTitle><DialogDescription>Itinerary day details.</DialogDescription></DialogHeader>
        <div className="grid grid-cols-2 gap-4 py-2">
          <EF label="Location" full><Input value={f.location} onChange={(e) => set("location")(e.target.value)} data-testid="itin-location-input" /></EF>
          <EF label="Activity" full><Input value={f.activity} onChange={(e) => set("activity")(e.target.value)} data-testid="itin-activity-input" /></EF>
          <EF label="Hotel"><Input value={f.hotel} onChange={(e) => set("hotel")(e.target.value)} /></EF>
          <EF label="Meal"><Input value={f.meal} onChange={(e) => set("meal")(e.target.value)} /></EF>
          <EF label="Transport"><Input value={f.transport} onChange={(e) => set("transport")(e.target.value)} /></EF>
          <EF label="Flight"><Input value={f.flight} onChange={(e) => set("flight")(e.target.value)} /></EF>
          <EF label="Description" full><Textarea value={f.description} onChange={(e) => set("description")(e.target.value)} /></EF>
        </div>
        <DialogFooter><Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="save-itinerary-button">{saving ? "Saving..." : "Save day"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const EF = ({ label, children, full }) => <div className={`space-y-2 ${full ? "col-span-2" : "col-span-2 sm:col-span-1"}`}><Label>{label}</Label>{children}</div>;
