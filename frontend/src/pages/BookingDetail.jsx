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
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { ArrowLeft, Loader2, Plus, Trash2, Upload, FileText, Users, CreditCard, Ban, GitBranch, Eye, AlertTriangle, Pencil, RefreshCw } from "lucide-react";
import { expiryTone, daysUntil } from "@/components/ExpiringDocsWidget";
import { toast } from "sonner";

const BOOKING_STATUSES = ["DRAFT", "PENDING", "CONFIRMED", "PARTIAL_PAID", "PAID", "READY", "COMPLETED", "CANCELLED", "REFUNDED"];
const SCHED_COLORS = { PENDING: "bg-slate-100 text-slate-600", PARTIAL: "bg-amber-50 text-amber-700 border-amber-200", PAID: "bg-emerald-50 text-emerald-700 border-emerald-200", OVERDUE: "bg-red-50 text-red-700 border-red-200", CANCELLED: "bg-slate-100 text-slate-400" };

export default function BookingDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasPerm, user } = useAuth();
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
  const [editInv, setEditInv] = useState(null);

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
  const isSA = user?.role === "super_admin";
  const regenerateInvoice = async (iid) => {
    if (!window.confirm("Perbarui nominal invoice sesuai jumlah peserta terbaru?")) return;
    try { await api.post(`/invoices/${iid}/regenerate`); toast.success("Invoice diperbarui sesuai peserta"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const deleteInvoice = async (iid) => {
    if (!window.confirm("Hapus invoice ini? Tindakan tidak dapat dibatalkan.")) return;
    try { await api.delete(`/invoices/${iid}`); toast.success("Invoice dihapus"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const changeStatus = async (v) => {
    if (v === b.status) return;
    const reason = window.prompt(`Alasan perubahan status ke ${v} (opsional):`) || "";
    try { await api.patch(`/bookings/${id}/status`, { status: v, reason }); toast.success(`Status → ${v}`); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const sched = b?.payment_schedule || [];
  const schedTotals = { total: sched.reduce((a, s) => a + Number(s.amount || 0), 0), paid: sched.reduce((a, s) => a + Number(s.paid_amount || 0), 0) };
  schedTotals.out = Math.max(schedTotals.total - schedTotals.paid, 0);
  const genPlan = async () => {
    const plan = (window.prompt("Plan type: FULL / DP / INSTALLMENT", "DP") || "").toUpperCase();
    if (!["FULL", "DP", "INSTALLMENT"].includes(plan)) return;
    const body = { plan_type: plan, first_due: new Date().toISOString().slice(0, 10) };
    if (plan === "DP") body.dp_amount = Number(window.prompt("DP amount (Rp):", "5000000") || 0);
    if (plan === "INSTALLMENT") body.installments = Number(window.prompt("Jumlah cicilan:", "3") || 3);
    try { await api.post(`/bookings/${id}/payment-plan`, body); toast.success("Payment plan dibuat"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const recSched = async (s) => {
    const amt = Number(window.prompt(`Bayar untuk #${s.payment_number} (sisa Rp ${s.outstanding}):`, s.outstanding) || 0);
    if (amt <= 0) return;
    try {
      const r = await api.patch(`/bookings/${id}/schedule/${s.payment_number}/record`, { amount: amt });
      toast.success("Pembayaran dicatat");
      if (r.data?.last_receipt_id) openReceipt(r.data.last_receipt_id);
      load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const openReceipt = async (rid) => {
    try { const res = await api.get(`/receipts/${rid}/pdf`, { responseType: "blob" }); window.open(URL.createObjectURL(res.data), "_blank"); }
    catch { toast.error("Gagal membuka kwitansi"); }
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
          <TabsTrigger value="travelers" data-testid="tab-travelers"><Users className="h-4 w-4 mr-1" />Peserta</TabsTrigger>
          <TabsTrigger value="payments" data-testid="tab-payments"><CreditCard className="h-4 w-4 mr-1" />Invoice & Payment</TabsTrigger>
          <TabsTrigger value="timeline" data-testid="tab-timeline"><GitBranch className="h-4 w-4 mr-1" />Timeline</TabsTrigger>
          <TabsTrigger value="schedule" data-testid="tab-schedule"><CreditCard className="h-4 w-4 mr-1" />Payment Schedule</TabsTrigger>
        </TabsList>

        <TabsContent value="travelers">
          <Card className="border-slate-200"><CardContent className="p-4 space-y-3" data-testid="travelers-list">
            <div className="flex items-center justify-between flex-wrap gap-2">
              {canTravel && <Button size="sm" onClick={() => setTravOpen(true)} className="bg-blue-600 hover:bg-blue-700" data-testid="add-traveler-button"><Plus className="h-4 w-4 mr-1" />Tambah Peserta</Button>}
              <PaxCountBadge registered={data.travelers.length} pax={b.pax} />
            </div>
            {data.travelers.length === 0 ? <p className="text-sm text-slate-400 text-center py-4">Belum ada peserta.</p>
              : data.travelers.map((t) => (
                <TravelerCard key={t._id} t={t} docs={data.documents.filter((d) => d.traveler_id === t._id)} canDoc={canDoc} canTravel={canTravel} onChange={load} />
              ))}
          </CardContent></Card>
        </TabsContent>

        <TabsContent value="payments">
          <Card className="border-slate-200 mb-4"><CardContent className="p-4">
            {data.travelers.length !== (b.pax || 0) && (
              <div className="mb-3 flex items-center gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2" data-testid="invoice-pax-warning">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>Jumlah peserta terdaftar (<b>{data.travelers.length}</b>) berbeda dari pax booking (<b>{b.pax || 0}</b>). Invoice dihitung sesuai jumlah peserta terdaftar.</span>
              </div>
            )}
            {canInvoice && <Button size="sm" onClick={createInvoice} className="bg-blue-600 hover:bg-blue-700" data-testid="create-invoice-button"><Plus className="h-4 w-4 mr-1" />Generate Invoice</Button>}
            {data.invoices.length === 0 && <p className="text-sm text-slate-400 text-center py-4">Belum ada invoice.</p>}
            <div className="space-y-3 mt-3">
              {data.invoices.map((inv) => (
                <div key={inv._id} className="border border-slate-200 rounded-md p-3" data-testid={`invoice-row-${inv._id}`}>
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div><p className="font-mono text-[11px] text-slate-400">{inv.invoice_number}</p><p className="font-medium text-slate-900">{fmtIDR(inv.total)}</p>
                      <p className="text-xs text-slate-500">{inv.pax || 0} peserta · Terbayar {fmtIDR(inv.paid_amount)} · Sisa {fmtIDR(inv.outstanding)}</p></div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline" className={INVOICE_STATUS_COLORS[inv.status]} data-testid={`invoice-status-${inv._id}`}>{inv.status}</Badge>
                      <Button size="sm" variant="outline" onClick={() => openPdf(inv._id)} data-testid={`invoice-pdf-${inv._id}`}><FileText className="h-4 w-4 mr-1" />PDF</Button>
                      {canInvoice && <Button size="sm" variant="outline" onClick={() => regenerateInvoice(inv._id)} data-testid={`invoice-regenerate-${inv._id}`} title="Perbarui nominal sesuai jumlah peserta"><RefreshCw className="h-4 w-4 mr-1" />Regenerate</Button>}
                      {isSA && <Button size="sm" variant="outline" onClick={() => setEditInv(inv)} data-testid={`invoice-edit-${inv._id}`}><Pencil className="h-4 w-4 mr-1" />Edit</Button>}
                      {isSA && <Button size="sm" variant="outline" className="text-red-600 border-red-200 hover:bg-red-50" onClick={() => deleteInvoice(inv._id)} data-testid={`invoice-delete-${inv._id}`}><Trash2 className="h-4 w-4" /></Button>}
                      {canPay && inv.status !== "Paid" && <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => setPayFor(inv)} data-testid={`record-payment-${inv._id}`}>Record Payment</Button>}
                    </div>
                  </div>
                  <InvoicePayments invoiceId={inv._id} canVoid={user?.role === "super_admin"} onChange={load} />
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

        <TabsContent value="schedule">
          <Card className="border-slate-200"><CardContent className="p-5" data-testid="payment-schedule">
            <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
              <div className="text-sm text-slate-600">Plan: <b>{b.payment_plan || "—"}</b> · Total <b>{fmtIDR(schedTotals.total)}</b> · Terbayar <b className="text-emerald-600">{fmtIDR(schedTotals.paid)}</b> · Outstanding <b className="text-red-600">{fmtIDR(schedTotals.out)}</b></div>
              {canPay && <Button size="sm" onClick={genPlan} data-testid="generate-plan-btn">Generate / Reset Plan</Button>}
            </div>
            {sched.length === 0 ? <p className="text-sm text-slate-400 text-center py-6">Belum ada jadwal pembayaran.{canPay ? " Klik Generate Plan." : ""}</p> : (
              <table className="w-full text-sm" data-testid="schedule-table">
                <thead><tr className="text-left text-slate-400 border-b border-slate-100"><th className="py-2">#</th><th>Label</th><th>Due</th><th>Amount</th><th>Paid</th><th>Outstanding</th><th>Status</th><th></th></tr></thead>
                <tbody>{sched.map((s) => (
                  <tr key={s.payment_number} className="border-b border-slate-50" data-testid={`schedule-row-${s.payment_number}`}>
                    <td className="py-2">{s.payment_number}</td><td>{s.label}</td><td>{(s.due_date || "").slice(0, 10)}</td>
                    <td>{fmtIDR(s.amount)}</td><td>{fmtIDR(s.paid_amount)}</td><td>{fmtIDR(s.outstanding)}</td>
                    <td><Badge variant="outline" className={SCHED_COLORS[s.status]}>{s.status}</Badge></td>
                    <td className="text-right space-x-1">
                      {s.last_receipt_id && <Button size="sm" variant="ghost" className="text-blue-600" onClick={() => openReceipt(s.last_receipt_id)} data-testid={`receipt-${s.payment_number}`}>Kwitansi</Button>}
                      {canPay && !["PAID", "CANCELLED"].includes(s.status) && <Button size="sm" variant="outline" onClick={() => recSched(s)} data-testid={`record-schedule-${s.payment_number}`}>Record</Button>}
                    </td>
                  </tr>))}
                </tbody>
              </table>
            )}
          </CardContent></Card>
        </TabsContent>
      </Tabs>

      {travOpen && <TravelerDialog bookingId={id} onClose={() => setTravOpen(false)} onSaved={() => { setTravOpen(false); load(); }} />}
      {payFor && <PaymentDialog invoice={payFor} onClose={() => setPayFor(null)} onSaved={() => { setPayFor(null); load(); }} />}
      {editInv && <EditInvoiceDialog invoice={editInv} onClose={() => setEditInv(null)} onSaved={() => { setEditInv(null); load(); }} />}
      {cancelOpen && <CancellationDialog booking={b} travelers={data.travelers} onClose={() => setCancelOpen(false)} onSaved={() => { setCancelOpen(false); load(); }} />}
    </div>
  );
}

const META_DOC_TYPES = ["PASSPORT", "VISA"];

function TravelerCard({ t, docs, canDoc, canTravel, onChange }) {
  const [metaFor, setMetaFor] = useState(null);
  const uploaded = {};
  docs.forEach((d) => { uploaded[d.doc_type] = d; });
  const upload = async (docType, file, meta) => {
    const existing = uploaded[docType];
    const fd = new FormData();
    if (!existing) fd.append("doc_type", docType);
    fd.append("file", file);
    if (meta) { fd.append("document_number", meta.document_number || ""); fd.append("issue_date", meta.issue_date || ""); fd.append("expiry_date", meta.expiry_date || ""); }
    const url = existing ? `/documents/${existing.id || existing._id}/replace` : `/travelers/${t._id}/documents`;
    try { await api.post(url, fd, { headers: { "Content-Type": "multipart/form-data" } }); toast.success(`${docType} ${existing ? "diganti" : "diupload"}`); onChange(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const viewDoc = (d) => window.open(`${API}/documents/${d.id || d._id}/download?auth=${localStorage.getItem("token")}`, "_blank");
  const delDoc = async (d) => { if (!window.confirm(`Hapus dokumen ${d.doc_type}?`)) return; try { await api.delete(`/documents/${d.id || d._id}`); toast.success("Dokumen dihapus"); onChange(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  const setStatus = async (docId, status) => { try { await api.patch(`/documents/${docId}/status`, { status }); onChange(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  const del = async () => { if (!window.confirm(`Hapus peserta ${t.full_name}?`)) return; try { await api.delete(`/travelers/${t._id}`); toast.success("Peserta dihapus"); onChange(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  return (
    <div className="border border-slate-200 rounded-md p-3" data-testid={`traveler-${t._id}`}>
      <div className="flex items-center justify-between">
        <div><p className="font-medium text-slate-900">{t.full_name}</p><p className="text-xs text-slate-500">{t.passport_number || "No passport"} · {t.room_type} · {t.gender}</p></div>
        {canTravel && <Button size="icon" variant="ghost" className="text-red-600" onClick={del}><Trash2 className="h-4 w-4" /></Button>}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-3">
        {DOCUMENT_TYPES.map((dt) => {
          const d = uploaded[dt];
          const isMeta = META_DOC_TYPES.includes(dt);
          const tone = isMeta && d ? expiryTone(daysUntil(d.expiry_date)) : null;
          return (
            <div key={dt} className="border border-slate-100 rounded p-2 flex items-center justify-between" data-testid={`doc-${t._id}-${dt}`}>
              <div className="min-w-0">
                <p className="text-xs font-medium text-slate-700">{dt}</p>
                <Badge variant="outline" className={`${DOC_STATUS_COLORS[d ? d.status : "Missing"]} text-[10px]`}>{d ? d.status : "Missing"}</Badge>
                {isMeta && d?.document_number && <p className="text-[10px] text-slate-400 mt-0.5 truncate">No. {d.document_number}</p>}
                {isMeta && d?.expiry_date && <p className="text-[10px] text-slate-400">Exp {(d.expiry_date || "").slice(0, 10)}</p>}
                {tone && <Badge variant="outline" className={`${tone.cls} text-[10px] mt-0.5`} data-testid={`doc-expiry-${t._id}-${dt}`}>{tone.label}</Badge>}
              </div>
              {canDoc && (
                <div className="flex items-center gap-1">
                  {d && <button type="button" className="text-slate-600 hover:text-slate-900" title="Lihat" onClick={() => viewDoc(d)} data-testid={`doc-view-${t._id}-${dt}`}><Eye className="h-4 w-4" /></button>}
                  {d && <Select value={d.status} onValueChange={(v) => setStatus(d.id, v)}><SelectTrigger className="h-7 w-7 p-0 border-0" data-testid={`doc-status-${t._id}-${dt}`}><span className="sr-only">status</span></SelectTrigger><SelectContent className="bg-white"><SelectItem value="Verified">Verify</SelectItem><SelectItem value="Rejected">Reject</SelectItem><SelectItem value="Uploaded">Reset</SelectItem></SelectContent></Select>}
                  {isMeta ? (
                    <button type="button" className="cursor-pointer text-blue-600" title={d ? "Ganti" : "Upload"} data-testid={`doc-upload-${t._id}-${dt}`} onClick={() => setMetaFor(dt)}>
                      <Upload className="h-4 w-4" />
                    </button>
                  ) : (
                    <label className="cursor-pointer text-blue-600" title={d ? "Ganti" : "Upload"} data-testid={`doc-upload-${t._id}-${dt}`}>
                      <Upload className="h-4 w-4" />
                      <input type="file" className="hidden" onChange={(e) => e.target.files[0] && upload(dt, e.target.files[0])} />
                    </label>
                  )}
                  {d && <button type="button" className="text-red-600 hover:text-red-700" title="Hapus" onClick={() => delDoc(d)} data-testid={`doc-delete-${t._id}-${dt}`}><Trash2 className="h-4 w-4" /></button>}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {metaFor && <DocMetaDialog docType={metaFor} existing={uploaded[metaFor]} onClose={() => setMetaFor(null)}
        onUpload={async (file, meta) => { await upload(metaFor, file, meta); setMetaFor(null); }} />}
    </div>
  );
}

function DocMetaDialog({ docType, existing, onClose, onUpload }) {
  const [f, setF] = useState({ document_number: existing?.document_number || "", issue_date: (existing?.issue_date || "").slice(0, 10), expiry_date: (existing?.expiry_date || "").slice(0, 10) });
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const set = (k) => (e) => setF((o) => ({ ...o, [k]: e.target.value }));
  const submit = async () => {
    if (!file) return toast.error("Pilih file dokumen dulu");
    if (!f.expiry_date) return toast.error("Tanggal kedaluwarsa wajib diisi");
    setSaving(true);
    try { await onUpload(file, f); } finally { setSaving(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-white max-w-md" data-testid="doc-meta-dialog">
        <DialogHeader><DialogTitle className="font-display">Upload {docType}</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div className="space-y-1"><Label className="text-xs">Nomor Dokumen</Label><Input value={f.document_number} onChange={set("document_number")} data-testid="doc-meta-number" placeholder={docType === "PASSPORT" ? "No. Paspor" : "No. Visa"} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1"><Label className="text-xs">Tanggal Terbit</Label><Input type="date" value={f.issue_date} onChange={set("issue_date")} data-testid="doc-meta-issue" /></div>
            <div className="space-y-1"><Label className="text-xs">Tanggal Kedaluwarsa</Label><Input type="date" value={f.expiry_date} onChange={set("expiry_date")} data-testid="doc-meta-expiry" /></div>
          </div>
          <div className="space-y-1"><Label className="text-xs">File Dokumen</Label><Input type="file" onChange={(e) => setFile(e.target.files[0] || null)} data-testid="doc-meta-file" /></div>
        </div>
        <DialogFooter><Button onClick={submit} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="doc-meta-save">{saving ? "Uploading..." : "Upload"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function TravelerDialog({ bookingId, onClose, onSaved }) {
  const [f, setF] = useState({ full_name: "", passport_name: "", nik: "", passport_number: "", passport_expiry: "", dob: "", gender: "Male", nationality: "Indonesia", phone: "", emergency_contact: "", room_type: "QUAD", special_request: "" });
  const [saving, setSaving] = useState(false);
  const set = (k) => (v) => setF((o) => ({ ...o, [k]: v }));
  const save = async () => {
    if (!f.full_name.trim()) return toast.error("Nama wajib diisi");
    setSaving(true);
    try { await api.post(`/bookings/${bookingId}/travelers`, f); toast.success("Peserta ditambahkan"); onSaved(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setSaving(false); }
  };
  const F = ({ label, k, type }) => <div className="space-y-1"><Label className="text-xs">{label}</Label><Input type={type} value={f[k]} onChange={(e) => set(k)(e.target.value)} data-testid={`traveler-${k}`} /></div>;
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-white max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="traveler-dialog">
        <DialogHeader><DialogTitle className="font-display">Tambah Peserta</DialogTitle></DialogHeader>
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

function InvoicePayments({ invoiceId, canVoid, onChange }) {
  const [pays, setPays] = useState(null);
  const load = useCallback(() => {
    api.get(`/invoices/${invoiceId}/payments`).then((r) => setPays(r.data || [])).catch(() => setPays([]));
  }, [invoiceId]);
  useEffect(() => { load(); }, [load]);
  const voidPay = async (p) => {
    const reason = window.prompt(`Alasan VOID pembayaran Rp ${p.amount} (wajib):`, "");
    if (reason === null) return;
    if (!reason.trim()) return toast.error("Alasan wajib diisi");
    try { await api.post(`/payments/${p._id}/void`, { reason }); toast.success("Pembayaran di-VOID"); load(); onChange && onChange(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  if (!pays || pays.length === 0) return null;
  return (
    <div className="mt-3 border-t border-slate-100 pt-2 space-y-1" data-testid={`payments-list-${invoiceId}`}>
      {pays.map((p) => {
        const isVoid = p.status === "VOID";
        return (
          <div key={p._id} className="flex items-center justify-between text-xs" data-testid={`payment-item-${p._id}`}>
            <div className={isVoid ? "line-through text-slate-400" : "text-slate-600"}>
              {(p.payment_date || "").slice(0, 10)} · {fmtIDR(p.amount)} · {p.payment_method || "—"}
              {isVoid && <span className="ml-2 text-red-500 no-underline">VOID{p.void_reason ? ` · ${p.void_reason}` : ""}</span>}
            </div>
            {canVoid && !isVoid && (
              <Button size="sm" variant="ghost" className="h-6 px-2 text-red-600" onClick={() => voidPay(p)} data-testid={`void-payment-${p._id}`}><Ban className="h-3 w-3 mr-1" />Void</Button>
            )}
          </div>
        );
      })}
    </div>
  );
}

function PaymentDialog({ invoice, onClose, onSaved }) {  const [f, setF] = useState({ payment_date: new Date().toISOString().slice(0, 10), amount: invoice.outstanding, payment_type: "DP", payment_method: "Bank Transfer", bank: "", reference_number: "", notes: "" });
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
        <DialogHeader><DialogTitle className="font-display">Record Payment — {invoice.invoice_number}</DialogTitle><DialogDescription>Pembayaran tidak boleh melebihi outstanding invoice.</DialogDescription></DialogHeader>
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
    if (!full && selected.length === 0) return toast.error("Pilih minimal 1 peserta");
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
            <label className="flex items-center gap-2"><input type="radio" checked={!full} onChange={() => setFull(false)} data-testid="cancel-partial" /> Partial (pilih peserta)</label>
          </div>
          {!full && (
            <div className="border border-slate-200 rounded p-2 max-h-40 overflow-y-auto space-y-1">
              {travelers.length === 0 ? <p className="text-slate-400">Belum ada peserta.</p> : travelers.map((t) => (
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


function PaxCountBadge({ registered, pax }) {
  const p = pax || 0;
  const match = registered === p;
  return (
    <Badge variant="outline" className={match ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-700 border-amber-200"} data-testid="pax-count-badge">
      {!match && <AlertTriangle className="h-3.5 w-3.5 mr-1" />}
      {registered} peserta terdaftar / {p} pax booking
    </Badge>
  );
}

function EditInvoiceDialog({ invoice, onClose, onSaved }) {
  const [f, setF] = useState({
    due_date: (invoice.due_date || "").slice(0, 10),
    pax: invoice.pax || 1,
    per_pax_price: invoice.per_pax_price || 0,
    discount_amount: invoice.discount_amount || 0,
    tax_amount: invoice.tax_amount || 0,
  });
  const [saving, setSaving] = useState(false);
  const set = (k) => (v) => setF((o) => ({ ...o, [k]: v }));
  const addonComp = Math.max(Number(invoice.subtotal || invoice.amount || 0) - Number(invoice.per_pax_price || 0) * Number(invoice.pax || 1), 0);
  const subtotal = Number(f.per_pax_price || 0) * Number(f.pax || 0) + addonComp;
  const total = subtotal - Number(f.discount_amount || 0) + Number(f.tax_amount || 0);
  const save = async () => {
    setSaving(true);
    try {
      await api.put(`/invoices/${invoice._id}`, {
        due_date: f.due_date, pax: Number(f.pax), per_pax_price: Number(f.per_pax_price),
        discount_amount: Number(f.discount_amount), tax_amount: Number(f.tax_amount),
      });
      toast.success("Invoice diperbarui"); onSaved();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-white max-w-md" data-testid="edit-invoice-dialog">
        <DialogHeader><DialogTitle>Edit Invoice — {invoice.invoice_number}</DialogTitle>
          <DialogDescription>Ubah nominal invoice secara manual (khusus Super Admin).</DialogDescription></DialogHeader>
        <div className="grid grid-cols-2 gap-3 py-2 text-sm">
          <div className="space-y-1"><Label className="text-xs">Jumlah Peserta</Label><Input type="number" value={f.pax} onChange={(e) => set("pax")(e.target.value)} data-testid="edit-inv-pax" /></div>
          <div className="space-y-1"><Label className="text-xs">Harga / Peserta</Label><Input type="number" value={f.per_pax_price} onChange={(e) => set("per_pax_price")(e.target.value)} data-testid="edit-inv-perpax" /></div>
          <div className="space-y-1"><Label className="text-xs">Diskon (Rp)</Label><Input type="number" value={f.discount_amount} onChange={(e) => set("discount_amount")(e.target.value)} data-testid="edit-inv-discount" /></div>
          <div className="space-y-1"><Label className="text-xs">Pajak (Rp)</Label><Input type="number" value={f.tax_amount} onChange={(e) => set("tax_amount")(e.target.value)} data-testid="edit-inv-tax" /></div>
          <div className="space-y-1 col-span-2"><Label className="text-xs">Jatuh Tempo</Label><Input type="date" value={f.due_date} onChange={(e) => set("due_date")(e.target.value)} data-testid="edit-inv-due" /></div>
        </div>
        <div className="rounded-md bg-slate-50 border border-slate-100 p-3 text-sm space-y-1" data-testid="edit-inv-preview">
          <div className="flex justify-between text-slate-500"><span>Subtotal</span><span>{fmtIDR(subtotal)}</span></div>
          <div className="flex justify-between text-slate-500"><span>Diskon</span><span>- {fmtIDR(f.discount_amount || 0)}</span></div>
          <div className="flex justify-between text-slate-500"><span>Pajak</span><span>+ {fmtIDR(f.tax_amount || 0)}</span></div>
          <div className="flex justify-between font-semibold text-slate-900 border-t border-slate-200 pt-1"><span>Total</span><span data-testid="edit-inv-total">{fmtIDR(total)}</span></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Batal</Button>
          <Button className="bg-blue-600 hover:bg-blue-700" onClick={save} disabled={saving} data-testid="edit-inv-save">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Simpan"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}