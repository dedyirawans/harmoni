import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { API, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { fmtIDR, fmtDate } from "@/config/crm";
import { INVOICE_STATUS_COLORS, DOC_STATUS_COLORS, DOCUMENT_TYPES, P4_ROOM_TYPES, PAYMENT_TYPES } from "@/config/phase4";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { ArrowLeft, Loader2, Plus, Trash2, Upload, FileText, Users, CreditCard, Ban, GitBranch } from "lucide-react";
import { toast } from "sonner";

const BOOKING_STATUSES = ["DRAFT", "PENDING", "CONFIRMED", "PARTIAL_PAID", "PAID", "READY", "COMPLETED", "CANCELLED", "REFUNDED"];

export default function BookingDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasPerm } = useAuth();
  const canTravel = hasPerm("traveler.manage");
  const canDoc = hasPerm("document.manage");
  const canInvoice = hasPerm("invoice.manage");
  const canPay = hasPerm("payment.manage");
  const canSchedule = hasPerm("booking.manage");
  const canCancel = hasPerm("cancellation.request");
  const [data, setData] = useState(undefined);
  const [travOpen, setTravOpen] = useState(false);
  const [payFor, setPayFor] = useState(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [timeline, setTimeline] = useState({ steps: [] });

  const load = useCallback(() => {
    api.get(`/bookings/${id}`).then((r) => setData(r.data)).catch(() => setData(null));
    api.get(`/bookings/${id}/timeline`).then((r) => setTimeline(r.data || { steps: [] })).catch(() => {});
  }, [id]);
  useEffect(() => { load(); }, [load]);

  if (data === undefined) return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  if (data === null) return <div className="p-12 text-center"><p className="text-red-600">Booking tidak tersedia.</p><Button variant="outline" className="mt-4" onClick={() => navigate("/booking")}>Back</Button></div>;
  const b = data.booking;
  const openPdf = (iid) => window.open(`${API}/invoices/${iid}/pdf?auth=${localStorage.getItem("token")}`, "_blank");

  const createInvoice = async () => {
    try { await api.post(`/bookings/${id}/invoice`, { due_date: "" }); toast.success("Invoice dibuat"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const changeStatus = async (v) => {
    if (v === b.status) return;
    const reason = window.prompt(`Alasan perubahan status ke ${v} (opsional):`) || "";
    try { await api.patch(`/bookings/${id}/status`, { status: v, reason }); toast.success(`Status → ${v}`); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <div className="space-y-6" data-testid="booking-detail-page">
      <button onClick={() => navigate("/booking")} className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900"><ArrowLeft className="h-4 w-4" />Back to bookings</button>
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2"><h1 className="font-display text-3xl font-bold text-slate-900">{b.customer_name}</h1><Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">{b.status}</Badge></div>
          <p className="text-slate-500 mt-1 font-mono text-xs">{b.booking_number} · v{b.package_version} · {b.package_name} · Source: {b.booking_source}</p>
        </div>
        <div className="text-right"><p className="font-display text-2xl font-bold text-slate-900">{fmtIDR(b.total)}</p><p className="text-xs text-slate-400">{b.pax} pax · diskon {b.discount_percent}%</p>
          {canCancel && !["CANCELLED"].includes(b.status) && <Button size="sm" variant="outline" className="mt-2 text-red-600 border-red-200" onClick={() => setCancelOpen(true)} data-testid="request-cancellation-button"><Ban className="h-4 w-4 mr-1" />Request Cancellation</Button>}
          {canSchedule && !["COMPLETED", "REFUNDED"].includes(b.status) && (
            <div className="mt-2 flex justify-end" data-testid="booking-status-control">
              <Select value={b.status} onValueChange={changeStatus}>
                <SelectTrigger className="w-44 h-8" data-testid="booking-status-select"><SelectValue /></SelectTrigger>
                <SelectContent>{BOOKING_STATUSES.map((s) => <SelectItem key={s} value={s}>{s.replace("_", " ")}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          )}
        </div>
      </div>

      <Tabs defaultValue="travelers">
        <TabsList>
          <TabsTrigger value="travelers" data-testid="tab-travelers"><Users className="h-4 w-4 mr-1" />Jamaah</TabsTrigger>
          <TabsTrigger value="payments" data-testid="tab-payments"><CreditCard className="h-4 w-4 mr-1" />Invoice & Payment</TabsTrigger>
          <TabsTrigger value="timeline" data-testid="tab-timeline"><GitBranch className="h-4 w-4 mr-1" />Timeline</TabsTrigger>
        </TabsList>

        <TabsContent value="travelers">
          <Card className="border-slate-200"><CardContent className="p-4 space-y-3" data-testid="travelers-list">
            {canTravel && <Button size="sm" onClick={() => setTravOpen(true)} className="bg-blue-600 hover:bg-blue-700" data-testid="add-traveler-button"><Plus className="h-4 w-4 mr-1" />Tambah Jamaah</Button>}
            {data.travelers.length === 0 ? <p className="text-sm text-slate-400 text-center py-4">Belum ada jamaah.</p>
              : data.travelers.map((t) => (
                <TravelerCard key={t._id} t={t} docs={data.documents.filter((d) => d.traveler_id === t._id)} canDoc={canDoc} canTravel={canTravel} onChange={load} />
              ))}
          </CardContent></Card>
        </TabsContent>

        <TabsContent value="payments">
          <Card className="border-slate-200 mb-4"><CardContent className="p-4">
            {canInvoice && <Button size="sm" onClick={createInvoice} className="bg-blue-600 hover:bg-blue-700" data-testid="create-invoice-button"><Plus className="h-4 w-4 mr-1" />Generate Invoice</Button>}
            {data.invoices.length === 0 && <p className="text-sm text-slate-400 text-center py-4">Belum ada invoice.</p>}
            <div className="space-y-3 mt-3">
              {data.invoices.map((inv) => (
                <div key={inv._id} className="border border-slate-200 rounded-md p-3" data-testid={`invoice-row-${inv._id}`}>
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div><p className="font-mono text-[11px] text-slate-400">{inv.invoice_number}</p><p className="font-medium text-slate-900">{fmtIDR(inv.total)}</p>
                      <p className="text-xs text-slate-500">Terbayar {fmtIDR(inv.paid_amount)} · Sisa {fmtIDR(inv.outstanding)}</p></div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className={INVOICE_STATUS_COLORS[inv.status]} data-testid={`invoice-status-${inv._id}`}>{inv.status}</Badge>
                      <Button size="sm" variant="outline" onClick={() => openPdf(inv._id)} data-testid={`invoice-pdf-${inv._id}`}><FileText className="h-4 w-4 mr-1" />PDF</Button>
                      {canPay && inv.status !== "Paid" && <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => setPayFor(inv)} data-testid={`record-payment-${inv._id}`}>Record Payment</Button>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent></Card>
        </TabsContent>

        <TabsContent value="timeline">
          <Card className="border-slate-200"><CardContent className="p-5" data-testid="booking-timeline">
            {timeline.branch === "cancellation" && <p className="text-xs font-medium text-red-600 mb-3">Cancellation flow</p>}
            <ol className="relative border-l-2 border-slate-200 ml-2 space-y-4">
              {(timeline.steps || []).map((s, i) => (
                <li key={i} className="ml-5" data-testid={`timeline-step-${i}`}>
                  <span className={`absolute -left-[9px] h-4 w-4 rounded-full border-2 border-white ${s.done ? "bg-emerald-500" : "bg-slate-300"}`} />
                  <div className="flex items-center justify-between">
                    <p className={`text-sm font-medium ${s.done ? "text-slate-900" : "text-slate-400"}`}>{s.step}</p>
                    {s.at && <span className="text-xs text-slate-400">{(s.at || "").slice(0, 10)}</span>}
                  </div>
                  {s.detail && <p className="text-xs text-slate-500">{s.detail}</p>}
                </li>
              ))}
            </ol>
            <div className="mt-6"><p className="font-semibold text-sm text-slate-800 mb-1">Status Audit</p>
              {(b.status_history || []).length === 0 ? <p className="text-xs text-slate-400">Belum ada perubahan status.</p> : (
                <ul className="space-y-1 text-xs" data-testid="booking-status-audit">
                  {b.status_history.map((h, i) => (
                    <li key={i} className="text-slate-600"><b>{h.old_status} → {h.new_status}</b> · {h.user} ({h.role}) · {(h.at || "").replace("T", " ").slice(0, 16)}{h.reason ? ` · ${h.reason}` : ""}</li>
                  ))}
                </ul>
              )}
            </div>
          </CardContent></Card>
        </TabsContent>
      </Tabs>

      {travOpen && <TravelerDialog bookingId={id} onClose={() => setTravOpen(false)} onSaved={() => { setTravOpen(false); load(); }} />}
      {payFor && <PaymentDialog invoice={payFor} onClose={() => setPayFor(null)} onSaved={() => { setPayFor(null); load(); }} />}
      {cancelOpen && <CancellationDialog booking={b} travelers={data.travelers} onClose={() => setCancelOpen(false)} onSaved={() => { setCancelOpen(false); load(); }} />}
    </div>
  );
}

function TravelerCard({ t, docs, canDoc, canTravel, onChange }) {
  const uploaded = {};
  docs.forEach((d) => { uploaded[d.doc_type] = d; });
  const upload = async (docType, file) => {
    const fd = new FormData(); fd.append("doc_type", docType); fd.append("file", file);
    try { await api.post(`/travelers/${t._id}/documents`, fd, { headers: { "Content-Type": "multipart/form-data" } }); toast.success(`${docType} diupload`); onChange(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const setStatus = async (docId, status) => { try { await api.patch(`/documents/${docId}/status`, { status }); onChange(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  const del = async () => { if (!window.confirm(`Hapus jamaah ${t.full_name}?`)) return; try { await api.delete(`/travelers/${t._id}`); toast.success("Jamaah dihapus"); onChange(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  return (
    <div className="border border-slate-200 rounded-md p-3" data-testid={`traveler-${t._id}`}>
      <div className="flex items-center justify-between">
        <div><p className="font-medium text-slate-900">{t.full_name}</p><p className="text-xs text-slate-500">{t.passport_number || "No passport"} · {t.room_type} · {t.gender}</p></div>
        {canTravel && <Button size="icon" variant="ghost" className="text-red-600" onClick={del}><Trash2 className="h-4 w-4" /></Button>}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-3">
        {DOCUMENT_TYPES.map((dt) => {
          const d = uploaded[dt];
          return (
            <div key={dt} className="border border-slate-100 rounded p-2 flex items-center justify-between" data-testid={`doc-${t._id}-${dt}`}>
              <div className="min-w-0">
                <p className="text-xs font-medium text-slate-700">{dt}</p>
                <Badge variant="outline" className={`${DOC_STATUS_COLORS[d ? d.status : "Missing"]} text-[10px]`}>{d ? d.status : "Missing"}</Badge>
              </div>
              {canDoc && (
                <div className="flex items-center gap-1">
                  {d && <Select value={d.status} onValueChange={(v) => setStatus(d.id, v)}><SelectTrigger className="h-7 w-7 p-0 border-0" data-testid={`doc-status-${t._id}-${dt}`}><span className="sr-only">status</span></SelectTrigger><SelectContent className="bg-white"><SelectItem value="Verified">Verify</SelectItem><SelectItem value="Rejected">Reject</SelectItem><SelectItem value="Uploaded">Reset</SelectItem></SelectContent></Select>}
                  <label className="cursor-pointer text-blue-600" data-testid={`doc-upload-${t._id}-${dt}`}>
                    <Upload className="h-4 w-4" />
                    <input type="file" className="hidden" onChange={(e) => e.target.files[0] && upload(dt, e.target.files[0])} />
                  </label>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TravelerDialog({ bookingId, onClose, onSaved }) {
  const [f, setF] = useState({ full_name: "", passport_name: "", nik: "", passport_number: "", passport_expiry: "", dob: "", gender: "Male", nationality: "Indonesia", phone: "", emergency_contact: "", room_type: "QUAD", special_request: "" });
  const [saving, setSaving] = useState(false);
  const set = (k) => (v) => setF((o) => ({ ...o, [k]: v }));
  const save = async () => {
    if (!f.full_name.trim()) return toast.error("Nama wajib diisi");
    setSaving(true);
    try { await api.post(`/bookings/${bookingId}/travelers`, f); toast.success("Jamaah ditambahkan"); onSaved(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setSaving(false); }
  };
  const F = ({ label, k, type }) => <div className="space-y-1"><Label className="text-xs">{label}</Label><Input type={type} value={f[k]} onChange={(e) => set(k)(e.target.value)} data-testid={`traveler-${k}`} /></div>;
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-white max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="traveler-dialog">
        <DialogHeader><DialogTitle className="font-display">Tambah Jamaah</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-3 py-2">
          <F label="Full Name" k="full_name" /><F label="Passport Name" k="passport_name" />
          <F label="NIK" k="nik" /><F label="Passport" k="passport_number" />
          <F label="Passport Expiry" k="passport_expiry" type="date" /><F label="Date of Birth" k="dob" type="date" />
          <div className="space-y-1"><Label className="text-xs">Gender</Label><Select value={f.gender} onValueChange={set("gender")}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="Male">Male</SelectItem><SelectItem value="Female">Female</SelectItem></SelectContent></Select></div>
          <F label="Nationality" k="nationality" /><F label="Phone" k="phone" /><F label="Emergency Contact" k="emergency_contact" />
          <div className="space-y-1"><Label className="text-xs">Room Type</Label><Select value={f.room_type} onValueChange={set("room_type")}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent className="bg-white">{P4_ROOM_TYPES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent></Select></div>
          <F label="Special Request" k="special_request" />
        </div>
        <DialogFooter><Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="save-traveler-button">{saving ? "Saving..." : "Simpan"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PaymentDialog({ invoice, onClose, onSaved }) {
  const [f, setF] = useState({ payment_date: new Date().toISOString().slice(0, 10), amount: invoice.outstanding, payment_type: "DP", payment_method: "Bank Transfer", bank: "", reference_number: "", notes: "" });
  const [saving, setSaving] = useState(false);
  const set = (k) => (v) => setF((o) => ({ ...o, [k]: v }));
  const save = async () => {
    setSaving(true);
    try { await api.post(`/invoices/${invoice._id}/payments`, { ...f, amount: Number(f.amount) }); toast.success("Pembayaran dicatat"); onSaved(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setSaving(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-white" data-testid="payment-dialog">
        <DialogHeader><DialogTitle className="font-display">Record Payment — {invoice.invoice_number}</DialogTitle></DialogHeader>
        <div className="grid grid-cols-2 gap-3 py-2">
          <div className="space-y-1"><Label className="text-xs">Payment Date</Label><Input type="date" value={f.payment_date} onChange={(e) => set("payment_date")(e.target.value)} data-testid="pay-date" /></div>
          <div className="space-y-1"><Label className="text-xs">Amount</Label><Input type="number" value={f.amount} onChange={(e) => set("amount")(e.target.value)} data-testid="pay-amount" /></div>
          <div className="space-y-1"><Label className="text-xs">Type</Label><Select value={f.payment_type} onValueChange={set("payment_type")}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent className="bg-white">{PAYMENT_TYPES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent></Select></div>
          <div className="space-y-1"><Label className="text-xs">Method</Label><Input value={f.payment_method} onChange={(e) => set("payment_method")(e.target.value)} data-testid="pay-method" /></div>
          <div className="space-y-1"><Label className="text-xs">Bank</Label><Input value={f.bank} onChange={(e) => set("bank")(e.target.value)} /></div>
          <div className="space-y-1"><Label className="text-xs">Reference No.</Label><Input value={f.reference_number} onChange={(e) => set("reference_number")(e.target.value)} data-testid="pay-ref" /></div>
        </div>
        <DialogFooter><Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="save-payment-button">{saving ? "Saving..." : "Simpan pembayaran"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CancellationDialog({ booking, travelers, onClose, onSaved }) {
  const [selected, setSelected] = useState([]);
  const [reason, setReason] = useState("");
  const [detail, setDetail] = useState("");
  const [notes, setNotes] = useState("");
  const [full, setFull] = useState(true);
  const toggle = (id) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  const submit = async () => {
    if (!reason) return toast.error("Cancellation reason wajib diisi");
    const body = { booking_id: booking._id, reason, detail, notes,
      cancelled_traveler_ids: full ? [] : selected };
    if (!full && selected.length === 0) return toast.error("Pilih minimal 1 jamaah");
    try { await api.post("/cancellations", body); toast.success("Cancellation diajukan — menunggu review & approval"); onSaved(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-white max-w-lg" data-testid="cancellation-dialog">
        <DialogHeader><DialogTitle>Request Cancellation — {booking.booking_number}</DialogTitle></DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2"><input type="radio" checked={full} onChange={() => setFull(true)} data-testid="cancel-full" /> Full Cancellation</label>
            <label className="flex items-center gap-2"><input type="radio" checked={!full} onChange={() => setFull(false)} data-testid="cancel-partial" /> Partial (pilih jamaah)</label>
          </div>
          {!full && (
            <div className="border border-slate-200 rounded p-2 max-h-40 overflow-y-auto space-y-1">
              {travelers.length === 0 ? <p className="text-slate-400">Belum ada jamaah.</p> : travelers.map((t) => (
                <label key={t._id} className="flex items-center gap-2" data-testid={`cancel-trav-${t._id}`}>
                  <input type="checkbox" checked={selected.includes(t._id)} onChange={() => toggle(t._id)} /> {t.full_name}
                </label>
              ))}
            </div>
          )}
          <div><Label className="text-xs">Cancellation Reason</Label><Input value={reason} onChange={(e) => setReason(e.target.value)} data-testid="cancel-reason" /></div>
          <div><Label className="text-xs">Cancellation Detail</Label><Input value={detail} onChange={(e) => setDetail(e.target.value)} data-testid="cancel-detail" /></div>
          <div><Label className="text-xs">Notes</Label><Input value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="cancel-notes" /></div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose}>Batal</Button><Button className="bg-red-600 hover:bg-red-700" onClick={submit} data-testid="cancel-submit">Ajukan</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
