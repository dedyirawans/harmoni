import { PageHeader } from "@/components/PageHeader";
import { useEffect, useState } from "react";
import api, { API, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { fmtIDR } from "@/config/crm";
import { QUOT_STATUS_COLORS, DISCOUNT_STATUS_COLORS, P4_ROOM_TYPES } from "@/config/phase4";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plus, Loader2, FileText, Check, X, ArrowRightCircle, Trash2, Pencil, Hotel, ExternalLink } from "lucide-react";
import { toast } from "sonner";

const HEAD = "bg-blue-600 text-white font-semibold text-xs uppercase tracking-wide border-r border-blue-500/40 last:border-r-0";
const CELL = "border-r border-slate-100 last:border-r-0 align-middle";
const ROW = "odd:bg-white even:bg-slate-50 hover:bg-blue-50/60 border-b border-slate-200";

export default function Quotations() {
  const { hasPerm } = useAuth();
  const canManage = hasPerm("quotation.manage");
  const canApprove = hasPerm("quotation.approve");
  const canBook = hasPerm("booking.manage");
  const [rows, setRows] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [packages, setPackages] = useState([]);
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [hotelView, setHotelView] = useState(null);
  const empty = { customer_id: "", package_id: "", pax: 1, room_type: "QUAD", discount_type: "PERCENT", discount_value: 0, addons: [], departure_id: null, notes: "", terms: "" };
  const [form, setForm] = useState(empty);

  const load = () => {
    setRows(null);
    api.get("/quotations").then((r) => setRows(r.data)).catch(() => setRows([]));
  };
  useEffect(() => {
    load();
    api.get("/customers").then((r) => setCustomers(r.data)).catch(() => {});
    api.get("/packages", { params: { status: "ACTIVE" } }).then((r) => setPackages(r.data)).catch(() => {});
  }, []);

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));
  const openPdf = (id) => window.open(`${API}/quotations/${id}/pdf?auth=${localStorage.getItem("token")}`, "_blank");

  const openCreate = () => { setEditId(null); setForm(empty); setOpen(true); };
  const openEdit = (q) => {
    setEditId(q._id);
    setForm({ customer_id: q.customer_id, package_id: q.package_id, pax: q.pax, room_type: q.room_type || "QUAD",
      discount_type: q.discount_type || "PERCENT", discount_value: q.discount_value != null ? q.discount_value : (q.discount_percent || 0),
      addons: q.addons || [], departure_id: q.departure_id || null, notes: q.notes || "", terms: q.terms || "" });
    setOpen(true);
  };
  const onDialogChange = (v) => { setOpen(v); if (!v) { setEditId(null); setForm(empty); } };

  const save = async () => {
    if (!form.customer_id || !form.package_id) return toast.error("Pilih customer & package");
    setSaving(true);
    const body = {
      ...form, pax: Number(form.pax), discount_value: Number(form.discount_value),
      addons: (form.addons || []).filter((a) => a.name).map((a) => ({ name: a.name, amount: Number(a.amount || 0) })),
    };
    try {
      if (editId) { await api.put(`/quotations/${editId}`, body); toast.success("Quotation diperbarui"); }
      else { await api.post("/quotations", body); toast.success("Quotation dibuat"); }
      onDialogChange(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  const act = async (fn, ok) => { try { await fn(); toast.success(ok); load(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };

  const addAddon = () => set("addons")([...(form.addons || []), { name: "", amount: 0 }]);
  const updAddon = (i, k, v) => set("addons")(form.addons.map((a, idx) => (idx === i ? { ...a, [k]: v } : a)));

  return (
    <div className="space-y-6" data-testid="quotations-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <PageHeader title="Quotations" subtitle="Buat penawaran, kelola approval diskon, dan konversi ke booking." />
        </div>
        {canManage && (
          <Dialog open={open} onOpenChange={onDialogChange}>
            <DialogTrigger asChild><Button className="bg-blue-600 hover:bg-blue-700" onClick={openCreate} data-testid="add-quotation-button"><Plus className="h-4 w-4 mr-2" aria-hidden="true" />New Quotation</Button></DialogTrigger>
            <DialogContent className="bg-white max-w-xl max-h-[90vh] overflow-y-auto" data-testid="quotation-dialog">
              <DialogHeader><DialogTitle className="font-display">{editId ? "Edit Quotation" : "New Quotation"}</DialogTitle><DialogDescription>Harga dasar otomatis dari Package Master.</DialogDescription></DialogHeader>
              <div className="grid grid-cols-2 gap-4 py-2">
                <Field label="Customer" full><Select value={form.customer_id} onValueChange={set("customer_id")}><SelectTrigger data-testid="quot-customer-select"><SelectValue placeholder="Pilih customer" /></SelectTrigger><SelectContent className="bg-white">{customers.map((c) => <SelectItem key={c._id} value={c._id}>{c.full_name}</SelectItem>)}</SelectContent></Select></Field>
                <Field label="Package" full><Select value={form.package_id} onValueChange={set("package_id")}><SelectTrigger data-testid="quot-package-select"><SelectValue placeholder="Pilih package" /></SelectTrigger><SelectContent className="bg-white">{packages.map((p) => <SelectItem key={p._id} value={p._id}>{p.package_name} — {fmtIDR(p.selling_price)}</SelectItem>)}</SelectContent></Select></Field>
                <Field label="Pax"><Input type="number" value={form.pax} onChange={(e) => set("pax")(e.target.value)} data-testid="quot-pax-input" /></Field>
                <Field label="Room Type"><Select value={form.room_type} onValueChange={set("room_type")}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent className="bg-white">{P4_ROOM_TYPES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent></Select></Field>
                <Field label="Tipe Diskon"><Select value={form.discount_type} onValueChange={set("discount_type")}><SelectTrigger data-testid="quot-discount-type"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="PERCENT">Persen (%)</SelectItem><SelectItem value="AMOUNT">Nominal (Rp)</SelectItem></SelectContent></Select></Field>
                <Field label={form.discount_type === "AMOUNT" ? "Nilai Diskon (Rp)" : "Nilai Diskon (%)"}><Input type="number" value={form.discount_value} onChange={(e) => set("discount_value")(e.target.value)} data-testid="quot-discount-input" /></Field>
                <div className="col-span-2 space-y-2">
                  <div className="flex items-center justify-between"><Label>Add-ons</Label><Button type="button" size="sm" variant="outline" onClick={addAddon} data-testid="add-addon-button"><Plus className="h-3 w-3 mr-1" />Add-on</Button></div>
                  {(form.addons || []).map((a, i) => (
                    <div key={i} className="grid grid-cols-12 gap-2">
                      <Input className="col-span-7" placeholder="Nama add-on" value={a.name} onChange={(e) => updAddon(i, "name", e.target.value)} data-testid={`addon-name-${i}`} />
                      <Input className="col-span-4" type="number" placeholder="Harga" value={a.amount} onChange={(e) => updAddon(i, "amount", e.target.value)} data-testid={`addon-amount-${i}`} />
                      <Button type="button" size="icon" variant="ghost" className="col-span-1 text-red-600" onClick={() => set("addons")(form.addons.filter((_, idx) => idx !== i))}><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  ))}
                </div>
              </div>
              <DialogFooter><Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="quotation-save-button">{saving ? "Saving..." : editId ? "Update quotation" : "Create quotation"}</Button></DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {rows === null ? <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
        : rows.length === 0 ? <Card className="border-slate-200"><CardContent className="p-12 text-center text-slate-500">Belum ada quotation.</CardContent></Card>
        : (
          <Card className="border-slate-200 shadow-sm overflow-hidden">
            <Table data-testid="quotations-list">
              <TableHeader><TableRow className="hover:bg-transparent">
                <TableHead className={HEAD}>Quotation</TableHead><TableHead className={HEAD}>Customer</TableHead>
                <TableHead className={HEAD}>Package</TableHead><TableHead className={`${HEAD} text-right`}>Total</TableHead>
                <TableHead className={HEAD}>Status</TableHead><TableHead className={HEAD}>Diskon</TableHead>
                <TableHead className={`${HEAD} text-right`}>Aksi</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {rows.map((q) => (
                  <TableRow key={q._id} className={ROW} data-testid={`quotation-row-${q._id}`}>
                    <TableCell className={`${CELL} font-mono text-xs`}>{q.quotation_number}</TableCell>
                    <TableCell className={`${CELL} font-medium text-slate-900`}>{q.customer_name}</TableCell>
                    <TableCell className={`${CELL} text-slate-500`}>
                      {q.package_name}<span className="block text-xs text-slate-400">{q.pax} pax</span>
                      {q.hotel_items?.length > 0 && (
                        <button onClick={() => setHotelView(q)} className="mt-1 inline-flex" data-testid={`quot-hotel-badge-${q._id}`}>
                          <Badge variant="outline" className="rounded-full bg-blue-50 text-blue-700 border-blue-200 cursor-pointer"><Hotel className="h-3 w-3 mr-1" />Hotel ({q.hotel_items.length})</Badge>
                        </button>
                      )}
                    </TableCell>
                    <TableCell className={`${CELL} text-right font-semibold`}>
                      {fmtIDR(q.total)}
                      <span className="block text-xs text-slate-400 font-normal">diskon {q.discount_type === "AMOUNT" ? fmtIDR(q.discount_amount) : `${q.discount_percent}%`}</span>
                      {q.hotel_total > 0 && (
                        <span className="block text-xs text-blue-600 font-normal mt-0.5" data-testid={`quot-hotel-total-${q._id}`}>+ Hotel {fmtIDR(q.hotel_total)}<span className="block text-slate-500">Estimasi {fmtIDR(q.grand_total_with_hotel ?? (Number(q.total || 0) + Number(q.hotel_total || 0)))}</span></span>
                      )}
                    </TableCell>
                    <TableCell className={CELL}><Badge variant="outline" className={QUOT_STATUS_COLORS[q.status]}>{q.status}</Badge>{(() => { try { const d = new Date(q.created_at); d.setDate(d.getDate() + 7); return (d < new Date() && !q.converted_booking_id && !["ACCEPTED", "EXPIRED", "REJECTED"].includes(String(q.status || "").toUpperCase())); } catch { return false; } })() && <Badge variant="outline" className="ml-1 rounded-full bg-red-50 text-red-700 border-red-200" data-testid={`quot-expired-${q._id}`}>Kedaluwarsa</Badge>}</TableCell>
                    <TableCell className={CELL}><Badge variant="outline" className={DISCOUNT_STATUS_COLORS[q.discount_status]} data-testid={`quot-discount-status-${q._id}`}>{q.discount_status}</Badge></TableCell>
                    <TableCell className={`${CELL} text-right`}>
                      <div className="flex items-center gap-1 justify-end flex-wrap">
                        <Button size="sm" variant="outline" onClick={() => openPdf(q._id)} data-testid={`quot-pdf-${q._id}`}><FileText className="h-4 w-4" /></Button>
                        {canManage && ["DRAFT", "SENT"].includes(q.status) && !q.converted_booking_id && (
                          <Button size="sm" variant="outline" onClick={() => openEdit(q)} data-testid={`quot-edit-${q._id}`}><Pencil className="h-4 w-4" /></Button>
                        )}
                        {canApprove && q.discount_status === "PENDING" && (
                          <>
                            <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => act(() => api.patch(`/quotations/${q._id}/discount-approval`, { action: "approve" }), "Diskon disetujui")} data-testid={`quot-approve-${q._id}`}><Check className="h-4 w-4" /></Button>
                            <Button size="sm" variant="outline" className="text-red-600" onClick={() => act(() => api.patch(`/quotations/${q._id}/discount-approval`, { action: "reject" }), "Diskon ditolak")} data-testid={`quot-reject-${q._id}`}><X className="h-4 w-4" /></Button>
                          </>
                        )}
                        {canApprove && ["DRAFT", "SENT"].includes(q.status) && q.discount_status === "APPROVED" && (
                          <Button size="sm" variant="outline" onClick={() => act(() => api.patch(`/quotations/${q._id}/status`, { status: "ACCEPTED" }), "Quotation accepted")} data-testid={`quot-accept-${q._id}`}>Accept</Button>
                        )}
                        {canBook && q.status === "ACCEPTED" && !q.converted_booking_id && (
                          <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={() => act(() => api.post(`/quotations/${q._id}/convert`, { booking_source: "SALES" }), "Dikonversi ke booking")} data-testid={`quot-convert-${q._id}`}><ArrowRightCircle className="h-4 w-4 mr-1" />Convert</Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}

      <Dialog open={!!hotelView} onOpenChange={(o) => !o && setHotelView(null)}>
        <DialogContent className="bg-white max-w-2xl" data-testid="quot-hotel-dialog">
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Hotel className="h-4 w-4 text-blue-600" />Hotel di {hotelView?.quotation_number}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            {(hotelView?.hotel_items || []).map((hi, i) => (
              <div key={i} className="rounded-lg border border-slate-200 p-3 flex items-center justify-between gap-3" data-testid={`quot-hotel-item-${i}`}>
                <div className="text-sm">
                  <p className="font-semibold text-slate-800">{hi.hotelName}</p>
                  {hi.roomtypeName && <p className="text-xs text-slate-500">{hi.roomtypeName}</p>}
                  <p className="text-xs text-slate-500">{hi.checkInDate} → {hi.checkOutDate} · {hi.nights} malam × {hi.numberOfRooms} kamar · {hi.numberOfAdults}D/{hi.numberOfChildren}A</p>
                  {(hi.includeBreakfast || hi.specialRequest) && <p className="text-xs text-slate-500">{hi.includeBreakfast ? "Termasuk sarapan" : "Tanpa sarapan"}{hi.specialRequest ? ` · Permintaan: ${hi.specialRequest}` : ""}</p>}
                  <p className="text-xs text-slate-400">Sumber: {hi.source || "AGODA_API"} · Rate {fmtIDR(hi.agoda_daily_rate)}/malam</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-bold text-blue-700">{fmtIDR(hi.total)}</p>
                  {hi.landingURL && <a href={hi.landingURL} target="_blank" rel="noreferrer"><Button size="sm" variant="outline" className="mt-1"><ExternalLink className="h-3.5 w-3.5 mr-1" />Agoda</Button></a>}
                </div>
              </div>
            ))}
            <div className="flex items-center justify-between border-t border-slate-200 pt-3 text-sm">
              <span className="font-semibold">Total Hotel</span>
              <span className="font-bold text-blue-700">{fmtIDR(hotelView?.hotel_total)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="font-semibold">Total Estimasi (termasuk hotel)</span>
              <span className="font-bold text-slate-900">{fmtIDR(hotelView?.grand_total_with_hotel ?? (Number(hotelView?.total || 0) + Number(hotelView?.hotel_total || 0)))}</span>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Field({ label, children, full }) {
  return <div className={`space-y-2 ${full ? "col-span-2" : "col-span-2 sm:col-span-1"}`}><Label>{label}</Label>{children}</div>;
}
