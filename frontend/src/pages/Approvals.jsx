import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Loader2, ShieldCheck, XCircle, RotateCcw, Wallet, Ban, Eye, Percent } from "lucide-react";

const rp = (v) => "Rp " + (Number(v || 0)).toLocaleString("id-ID");
const CX_COLORS = { REQUESTED: "bg-amber-50 text-amber-700 border-amber-200", ACCOUNTING_REVIEWED: "bg-sky-50 text-sky-700 border-sky-200", APPROVED: "bg-emerald-50 text-emerald-700 border-emerald-200", REJECTED: "bg-red-50 text-red-700 border-red-200" };
const RF_COLORS = { CALCULATED: "bg-slate-100 text-slate-600 border-slate-200", ACCOUNTING_REVIEWED: "bg-sky-50 text-sky-700 border-sky-200", APPROVED: "bg-indigo-50 text-indigo-700 border-indigo-200", REJECTED: "bg-red-50 text-red-700 border-red-200", PROCESSING: "bg-amber-50 text-amber-700 border-amber-200", PARTIALLY_REFUNDED: "bg-amber-50 text-amber-700 border-amber-200", REFUNDED: "bg-emerald-600 text-white border-emerald-600" };

export default function Approvals() {
  const { user } = useAuth();
  const p = user.permissions || [];
  const has = (x) => p.includes(x);

  return (
    <div className="space-y-6" data-testid="approvals-page">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-blue-600 flex items-center justify-center"><ShieldCheck className="h-6 w-6 text-white" /></div>
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">Approval — Cancellation & Refund</h1>
          <p className="text-slate-500 mt-0.5">Semua pembatalan & refund wajib melalui persetujuan Super Admin.</p>
        </div>
      </div>
      <Tabs defaultValue="cancellation">
        <TabsList data-testid="approval-tabs">
          <TabsTrigger value="cancellation" data-testid="tab-cancellation">Cancellation</TabsTrigger>
          <TabsTrigger value="refund" data-testid="tab-refund">Refund</TabsTrigger>
          {user.role === "super_admin" && <TabsTrigger value="commission" data-testid="tab-commission-approval">Sales Commission</TabsTrigger>}
        </TabsList>
        <TabsContent value="cancellation"><CancellationList has={has} role={user.role} /></TabsContent>
        <TabsContent value="refund"><RefundList has={has} role={user.role} /></TabsContent>
        {user.role === "super_admin" && <TabsContent value="commission"><CommissionApprovalTab /></TabsContent>}
      </Tabs>
    </div>
  );
}

/* ---------------- CANCELLATION ---------------- */
function CancellationList({ has, role }) {
  const [rows, setRows] = useState([]);
  const [sel, setSel] = useState(null);
  const load = () => api.get("/cancellations").then((r) => setRows(r.data || [])).catch(() => {});
  useEffect(() => { load(); }, []);
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="border-b border-slate-100"><CardTitle className="font-display text-lg flex items-center gap-2"><Ban className="h-5 w-5 text-red-500" /> Cancellation Requests</CardTitle></CardHeader>
      <CardContent className="p-0">
        <table className="w-full text-sm" data-testid="cancellation-table">
          <thead><tr className="bg-blue-600 text-white text-left">
            <th className="px-3 py-2.5">No</th><th className="px-3 py-2.5 border-l border-blue-500">Booking</th><th className="px-3 py-2.5 border-l border-blue-500">Customer</th>
            <th className="px-3 py-2.5 border-l border-blue-500">Pax Batal</th><th className="px-3 py-2.5 border-l border-blue-500">Est. Refund</th><th className="px-3 py-2.5 border-l border-blue-500">Status</th><th className="px-3 py-2.5 border-l border-blue-500"></th>
          </tr></thead>
          <tbody>
            {rows.length === 0 ? <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Belum ada pengajuan.</td></tr> :
              rows.map((c, i) => (
                <tr key={c._id} className={i % 2 ? "bg-slate-50" : "bg-white"} data-testid={`cx-row-${c._id}`}>
                  <td className="px-3 py-2.5 font-medium">{c.cancellation_number}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{c.booking_number}{c.is_partial && <Badge className="ml-1 bg-orange-50 text-orange-600 border-orange-200">Partial</Badge>}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{c.customer_name}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{c.cancelled_pax}/{c.total_pax}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{rp(c.accounting_review?.estimated_refund)}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100"><Badge className={CX_COLORS[c.status]}>{c.status}</Badge></td>
                  <td className="px-3 py-2.5 border-l border-slate-100"><Button size="sm" variant="ghost" onClick={() => setSel(c._id)} data-testid={`cx-open-${c._id}`}><Eye className="h-4 w-4" /></Button></td>
                </tr>
              ))}
          </tbody>
        </table>
      </CardContent>
      {sel && <CancellationDetail id={sel} has={has} role={role} onClose={() => setSel(null)} onChanged={() => { load(); }} />}
    </Card>
  );
}

function CancellationDetail({ id, has, role, onClose, onChanged }) {
  const [d, setD] = useState(null);
  const [rev, setRev] = useState({ cancellation_fee: 0, non_refundable_cost: 0, supplier_cost: 0, other_deduction: 0, recommendation: "" });
  const [reason, setReason] = useState("");
  const load = () => api.get(`/cancellations/${id}`).then((r) => { setD(r.data); if (r.data.accounting_review) setRev(r.data.accounting_review); }).catch(() => {});
  useEffect(() => { load(); }, [id]);
  if (!d) return null;
  const paid = d.total_paid || 0;
  const est = Math.max(0, paid - (+rev.cancellation_fee || 0) - (+rev.non_refundable_cost || 0) - (+rev.other_deduction || 0));

  const doReview = async () => {
    try { await api.patch(`/cancellations/${id}/review`, rev); toast.success("Review terkirim ke Super Admin"); load(); onChanged(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const doApprove = async (action) => {
    if ((action === "REJECT" || action === "REQUEST_REVISION") && !reason) return toast.error("Isi alasan dulu");
    try { await api.patch(`/cancellations/${id}/approve`, { action, reason, ...rev }); toast.success(`Cancellation ${action}`); load(); onChanged(); if (action === "APPROVE") onClose(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const canReview = has("cancellation.review") && d.status === "REQUESTED";
  const canApprove = has("cancellation.approve") && d.status === "ACCOUNTING_REVIEWED";

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="cx-detail-dialog">
        <DialogHeader><DialogTitle className="flex items-center gap-2">{d.cancellation_number} <Badge className={CX_COLORS[d.status]}>{d.status}</Badge></DialogTitle></DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-2">
            <Info k="Booking" v={d.booking_number} /><Info k="Customer" v={d.customer_name} />
            <Info k="Sales" v={d.sales_name} /><Info k="Package" v={d.package_name} />
            <Info k="Departure" v={d.departure_date || "-"} /><Info k="Pax Batal" v={`${d.cancelled_pax} / ${d.total_pax}`} />
            <Info k="Total Booking" v={rp(d.total_booking_value)} /><Info k="Total Paid" v={rp(d.total_paid)} />
            <Info k="Outstanding" v={rp(d.outstanding)} /><Info k="Reason" v={d.reason} />
          </div>
          {d.detail && <p className="text-slate-500"><b>Detail:</b> {d.detail}</p>}
          {d.approval?.action === "REJECT" && <p className="text-red-600"><b>Ditolak:</b> {d.approval.reason}</p>}

          {(canReview || canApprove || d.accounting_review) && (
            <div className="rounded-lg border border-slate-200 p-3 space-y-2 bg-slate-50">
              <p className="font-semibold text-slate-700">Accounting Review {has("cancellation.approve") && "(Super Admin dapat mengubah)"}</p>
              <div className="grid grid-cols-2 gap-2">
                {[["Cancellation Fee", "cancellation_fee"], ["Non-refundable Cost", "non_refundable_cost"], ["Supplier Cost", "supplier_cost"], ["Other Deduction", "other_deduction"]].map(([lb, k]) => (
                  <div key={k}><Label className="text-xs">{lb}</Label><Input type="number" value={rev[k] ?? 0} disabled={!(canReview || canApprove)} onChange={(e) => setRev({ ...rev, [k]: e.target.value })} data-testid={`cx-${k}`} /></div>
                ))}
              </div>
              <div><Label className="text-xs">Accounting Recommendation</Label><Textarea rows={2} value={rev.recommendation || ""} disabled={!(canReview || canApprove)} onChange={(e) => setRev({ ...rev, recommendation: e.target.value })} data-testid="cx-recommendation" /></div>
              <p className="text-sm font-semibold text-emerald-700">Estimated Refund: {rp(est)}</p>
            </div>
          )}
          {canApprove && <div><Label className="text-xs">Reason (untuk Reject / Revision)</Label><Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="cx-reject-reason" /></div>}
        </div>
        <DialogFooter className="gap-2">
          {canReview && <Button onClick={doReview} data-testid="cx-submit-review">Submit Review</Button>}
          {canApprove && <>
            <Button variant="outline" onClick={() => doApprove("REQUEST_REVISION")} data-testid="cx-revision"><RotateCcw className="h-4 w-4 mr-1" />Revisi</Button>
            <Button variant="outline" className="text-red-600 border-red-200" onClick={() => doApprove("REJECT")} data-testid="cx-reject"><XCircle className="h-4 w-4 mr-1" />Reject</Button>
            <Button className="bg-emerald-600 hover:bg-emerald-700" onClick={() => doApprove("APPROVE")} data-testid="cx-approve"><ShieldCheck className="h-4 w-4 mr-1" />Approve</Button>
          </>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ---------------- REFUND ---------------- */
function RefundList({ has, role }) {
  const [rows, setRows] = useState([]);
  const [sel, setSel] = useState(null);
  const load = () => api.get("/refund-requests").then((r) => setRows(r.data || [])).catch(() => {});
  useEffect(() => { load(); }, []);
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="border-b border-slate-100"><CardTitle className="font-display text-lg flex items-center gap-2"><Wallet className="h-5 w-5 text-indigo-600" /> Refund Requests</CardTitle></CardHeader>
      <CardContent className="p-0">
        <table className="w-full text-sm" data-testid="refund-table">
          <thead><tr className="bg-indigo-600 text-white text-left">
            <th className="px-3 py-2.5">No</th><th className="px-3 py-2.5 border-l border-indigo-500">Booking</th><th className="px-3 py-2.5 border-l border-indigo-500">Customer</th>
            <th className="px-3 py-2.5 border-l border-indigo-500">Proposed</th><th className="px-3 py-2.5 border-l border-indigo-500">Refunded</th><th className="px-3 py-2.5 border-l border-indigo-500">Status</th><th className="px-3 py-2.5 border-l border-indigo-500"></th>
          </tr></thead>
          <tbody>
            {rows.length === 0 ? <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Belum ada refund.</td></tr> :
              rows.map((c, i) => (
                <tr key={c._id} className={i % 2 ? "bg-slate-50" : "bg-white"} data-testid={`rf-row-${c._id}`}>
                  <td className="px-3 py-2.5 font-medium">{c.refund_number}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{c.booking_number}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{c.customer_name}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{rp(c.proposed_refund)}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{rp(c.refunded_amount)}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100"><Badge className={RF_COLORS[c.status]}>{c.status}</Badge></td>
                  <td className="px-3 py-2.5 border-l border-slate-100"><Button size="sm" variant="ghost" onClick={() => setSel(c._id)} data-testid={`rf-open-${c._id}`}><Eye className="h-4 w-4" /></Button></td>
                </tr>
              ))}
          </tbody>
        </table>
      </CardContent>
      {sel && <RefundDetail id={sel} has={has} onClose={() => setSel(null)} onChanged={load} />}
    </Card>
  );
}

function RefundDetail({ id, has, onClose, onChanged }) {
  const [d, setD] = useState(null);
  const [bank, setBank] = useState({ bank_name: "", account_number: "", account_holder: "" });
  const [rec, setRec] = useState("");
  const [reason, setReason] = useState("");
  const [pay, setPay] = useState({ payment_date: "", amount: "", bank: "", account: "", transaction_reference: "", notes: "" });
  const [ded, setDed] = useState({ type: "", method: "FIXED", source: "Manual Adjustment", qty: 1, unit_amount: "", non_refundable: false });
  const [adj, setAdj] = useState({ refund_adjustment: "", reason: "" });
  const [dtypes, setDtypes] = useState([]);
  const load = () => api.get(`/refund-requests/${id}`).then((r) => { setD(r.data); setBank(r.data.bank || bank); setRec(r.data.recommendation || ""); }).catch(() => {});
  useEffect(() => { load(); api.get("/deduction-types").then((r) => setDtypes(r.data || [])).catch(() => {}); }, [id]);
  if (!d) return null;

  const canReview = has("refund.review") && d.status === "CALCULATED";
  const canApprove = has("refund.approve") && d.status === "ACCOUNTING_REVIEWED";
  const canAdjust = has("refund.approve") && ["CALCULATED", "ACCOUNTING_REVIEWED"].includes(d.status);
  const canProcess = has("refund.process") && ["APPROVED", "PARTIALLY_REFUNDED", "PROCESSING"].includes(d.status);

  const doReview = async () => { try { await api.patch(`/refund-requests/${id}/review`, { bank, recommendation: rec }); toast.success("Refund disubmit ke Super Admin"); load(); onChanged(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  const doApprove = async (action) => { if ((action === "REJECT" || action === "REQUEST_REVISION") && !reason) return toast.error("Isi alasan dulu"); try { await api.patch(`/refund-requests/${id}/approve`, { action, reason, proposed_refund: d.proposed_refund }); toast.success(`Refund ${action}`); load(); onChanged(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  const doProcess = async () => { try { await api.post(`/refund-requests/${id}/process`, pay); toast.success("Pembayaran refund tercatat"); load(); onChanged(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  const editable = ["CALCULATED", "ACCOUNTING_REVIEWED"].includes(d.status);
  const addDeduction = async () => { if (!ded.type) return toast.error("Pilih type"); try { const r = await api.post(`/refund-requests/${id}/deductions`, ded); if (r.data.warning) toast.warning(r.data.warning); toast.success("Deduction ditambah"); setDed({ type: "", method: "FIXED", source: "Manual Adjustment", qty: 1, unit_amount: "", non_refundable: false }); load(); onChanged(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  const removeDeduction = async (itemId) => { try { await api.delete(`/refund-requests/${id}/deductions/${itemId}`); load(); onChanged(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };
  const doAdjust = async () => { if (!adj.reason) return toast.error("Reason wajib"); try { await api.patch(`/refund-requests/${id}/adjustment`, adj); toast.success("Adjustment tersimpan"); load(); onChanged(); } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="rf-detail-dialog">
        <DialogHeader><DialogTitle className="flex items-center gap-2">{d.refund_number} <Badge className={RF_COLORS[d.status]}>{d.status}</Badge></DialogTitle></DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-2">
            <Info k="Booking" v={d.booking_number} /><Info k="Customer" v={d.customer_name} />
            <Info k="Package" v={d.package_name} /><Info k="Sales" v={d.sales_name} />
            <Info k="Original Value" v={rp(d.original_booking_value)} /><Info k="Total Paid" v={rp(d.total_paid)} />
            <Info k="Cancellation Fee" v={rp(d.cancellation_fee)} /><Info k="Deduction" v={rp((d.non_refundable_cost || 0) + (d.other_deduction || 0))} />
            <Info k="Proposed Refund" v={rp(d.proposed_refund)} /><Info k="Refunded" v={rp(d.refunded_amount)} />
          </div>
          {d.recommendation && <p className="text-slate-500"><b>Rekomendasi:</b> {d.recommendation}</p>}
          {d.approval?.action === "REJECT" && <p className="text-red-600"><b>Ditolak:</b> {d.approval.reason}</p>}

          <div className="rounded-lg border border-slate-200 p-3 space-y-2">
            <p className="font-semibold text-slate-700">Deduction Breakdown</p>
            <table className="w-full text-xs" data-testid="rf-deduction-table">
              <thead><tr className="text-left text-slate-400"><th className="py-1">Type</th><th>Method</th><th>Qty</th><th>Source</th><th className="text-right">Amount</th><th></th></tr></thead>
              <tbody>
                {(d.deductions || []).length === 0 ? <tr><td colSpan={6} className="py-2 text-slate-400">Belum ada deduction.</td></tr> :
                  d.deductions.map((x) => (
                    <tr key={x.id} className="border-t border-slate-100">
                      <td className="py-1">{x.type}{x.non_refundable && <span className="ml-1 text-[10px] text-red-500">NR</span>}</td>
                      <td>{x.method}</td><td>{x.qty}</td><td>{x.source}</td>
                      <td className="text-right font-medium">{rp(x.amount)}</td>
                      <td className="text-right">{editable && canReview && <button onClick={() => removeDeduction(x.id)} data-testid={`rf-del-ded-${x.id}`} className="text-red-500"><XCircle className="h-3.5 w-3.5" /></button>}</td>
                    </tr>
                  ))}
              </tbody>
              <tfoot><tr className="border-t border-slate-200 font-semibold"><td colSpan={4} className="py-1">Total Deduction</td><td className="text-right">{rp(d.total_deduction)}</td><td></td></tr>
                {!!d.refund_adjustment && <tr><td colSpan={4} className="text-slate-500">Refund Adjustment</td><td className="text-right text-slate-500">{rp(d.refund_adjustment)}</td><td></td></tr>}
                <tr className="text-emerald-700 font-bold"><td colSpan={4} className="py-1">Final / Proposed Refund</td><td className="text-right">{rp(d.proposed_refund)}</td><td></td></tr>
              </tfoot>
            </table>
            {editable && canReview && (
              <div className="grid grid-cols-12 gap-2 items-end pt-2 border-t border-slate-100">
                <div className="col-span-3"><Label className="text-[10px]">Type</Label><Input list="ded-types" value={ded.type} onChange={(e) => setDed({ ...ded, type: e.target.value })} data-testid="rf-ded-type" /><datalist id="ded-types">{dtypes.map((t) => <option key={t.id} value={t.name} />)}</datalist></div>
                <div className="col-span-2"><Label className="text-[10px]">Method</Label>
                  <select className="w-full h-9 border rounded px-1 text-xs" value={ded.method} onChange={(e) => setDed({ ...ded, method: e.target.value })} data-testid="rf-ded-method">
                    {["FIXED", "PERCENTAGE", "PER_PAX", "PER_TRAVELER", "FULL_NON_REFUNDABLE"].map((m) => <option key={m}>{m}</option>)}
                  </select></div>
                <div className="col-span-2"><Label className="text-[10px]">Qty</Label><Input type="number" value={ded.qty} onChange={(e) => setDed({ ...ded, qty: e.target.value })} data-testid="rf-ded-qty" /></div>
                <div className="col-span-3"><Label className="text-[10px]">Unit / %</Label><Input type="number" value={ded.unit_amount} onChange={(e) => setDed({ ...ded, unit_amount: e.target.value })} data-testid="rf-ded-unit" /></div>
                <div className="col-span-2"><Button size="sm" className="w-full" onClick={addDeduction} data-testid="rf-add-ded">+ Add</Button></div>
              </div>
            )}
          </div>

          {canAdjust && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 grid grid-cols-12 gap-2 items-end">
              <div className="col-span-4"><Label className="text-xs">Refund Adjustment (+/-)</Label><Input type="number" value={adj.refund_adjustment} onChange={(e) => setAdj({ ...adj, refund_adjustment: e.target.value })} data-testid="rf-adj-amount" /></div>
              <div className="col-span-6"><Label className="text-xs">Adjustment Reason</Label><Input value={adj.reason} onChange={(e) => setAdj({ ...adj, reason: e.target.value })} data-testid="rf-adj-reason" /></div>
              <div className="col-span-2"><Button size="sm" className="w-full" onClick={doAdjust} data-testid="rf-adj-save">Apply</Button></div>
            </div>
          )}

          <div className="rounded-lg border border-slate-200 p-3 space-y-2 bg-slate-50">
            <p className="font-semibold text-slate-700">Bank Tujuan Refund</p>
            <div className="grid grid-cols-3 gap-2">
              <div><Label className="text-xs">Bank</Label><Input value={bank.bank_name || ""} disabled={!canReview} onChange={(e) => setBank({ ...bank, bank_name: e.target.value })} data-testid="rf-bank-name" /></div>
              <div><Label className="text-xs">No. Rekening</Label><Input value={bank.account_number || ""} disabled={!canReview} onChange={(e) => setBank({ ...bank, account_number: e.target.value })} data-testid="rf-bank-account" /></div>
              <div><Label className="text-xs">Atas Nama</Label><Input value={bank.account_holder || ""} disabled={!canReview} onChange={(e) => setBank({ ...bank, account_holder: e.target.value })} data-testid="rf-bank-holder" /></div>
            </div>
            {canReview && <div><Label className="text-xs">Recommendation</Label><Textarea rows={2} value={rec} onChange={(e) => setRec(e.target.value)} data-testid="rf-recommendation" /></div>}
          </div>

          {canProcess && (
            <div className="rounded-lg border border-emerald-200 p-3 space-y-2 bg-emerald-50">
              <p className="font-semibold text-emerald-700">Process Refund Payment</p>
              <div className="grid grid-cols-2 gap-2">
                <div><Label className="text-xs">Payment Date</Label><Input type="date" value={pay.payment_date} onChange={(e) => setPay({ ...pay, payment_date: e.target.value })} data-testid="rf-pay-date" /></div>
                <div><Label className="text-xs">Amount</Label><Input type="number" value={pay.amount} onChange={(e) => setPay({ ...pay, amount: e.target.value })} data-testid="rf-pay-amount" /></div>
                <div><Label className="text-xs">Bank</Label><Input value={pay.bank} onChange={(e) => setPay({ ...pay, bank: e.target.value })} data-testid="rf-pay-bank" /></div>
                <div><Label className="text-xs">Transaction Ref</Label><Input value={pay.transaction_reference} onChange={(e) => setPay({ ...pay, transaction_reference: e.target.value })} data-testid="rf-pay-ref" /></div>
              </div>
            </div>
          )}
          {canApprove && <div><Label className="text-xs">Reason (Reject / Revision)</Label><Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="rf-reject-reason" /></div>}
        </div>
        <DialogFooter className="gap-2 flex-wrap">
          {canReview && <Button onClick={doReview} data-testid="rf-submit-review">Submit for Approval</Button>}
          {canApprove && <>
            <Button variant="outline" onClick={() => doApprove("REQUEST_REVISION")} data-testid="rf-revision"><RotateCcw className="h-4 w-4 mr-1" />Revisi</Button>
            <Button variant="outline" className="text-red-600 border-red-200" onClick={() => doApprove("REJECT")} data-testid="rf-reject"><XCircle className="h-4 w-4 mr-1" />Reject</Button>
            <Button className="bg-emerald-600 hover:bg-emerald-700" onClick={() => doApprove("APPROVE")} data-testid="rf-approve"><ShieldCheck className="h-4 w-4 mr-1" />Approve Refund</Button>
          </>}
          {canProcess && <Button className="bg-emerald-600 hover:bg-emerald-700" onClick={doProcess} data-testid="rf-process">Process Refund</Button>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const Info = ({ k, v }) => (<div><p className="text-xs uppercase tracking-wide text-slate-400">{k}</p><p className="font-medium text-slate-800">{v || "-"}</p></div>);


/* ---------------- SALES COMMISSION APPROVAL (Super Admin) ---------------- */
function CommissionApprovalTab() {
  const [rows, setRows] = useState([]);
  const [sel, setSel] = useState(null);
  const [reason, setReason] = useState("");
  const load = () => api.get("/commissions/pending-approval").then((r) => setRows(r.data || [])).catch(() => {});
  useEffect(() => { load(); }, []);
  const decide = async (period, decision) => {
    if ((decision === "REJECTED" || decision === "REVISION") && !reason) return toast.error("Isi alasan dulu");
    try { await api.patch(`/commissions/closings/${period}/approval`, { decision, reason }); toast.success(`Commission ${decision}`); setReason(""); setSel(null); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const adjust = async (lineId, adjustment, adjReason) => {
    if (!adjReason) return toast.error("Adjustment reason wajib diisi");
    try { await api.patch(`/commissions/lines/${lineId}/adjustment`, { adjustment: Number(adjustment) || 0, notes: adjReason }); toast.success("Adjustment tersimpan"); load(); setSel(null); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="border-b border-slate-100"><CardTitle className="font-display text-lg flex items-center gap-2"><Percent className="h-5 w-5 text-blue-600" /> Sales Commission Approval</CardTitle></CardHeader>
      <CardContent className="p-0">
        <table className="w-full text-sm" data-testid="commission-approval-table">
          <thead><tr className="bg-blue-600 text-white text-left">
            <th className="px-3 py-2.5">Period</th><th className="px-3 py-2.5 border-l border-blue-500">Status</th><th className="px-3 py-2.5 border-l border-blue-500">Payout</th>
            <th className="px-3 py-2.5 border-l border-blue-500">Pax</th><th className="px-3 py-2.5 border-l border-blue-500">Total</th><th className="px-3 py-2.5 border-l border-blue-500">SA Approval</th><th className="px-3 py-2.5 border-l border-blue-500"></th>
          </tr></thead>
          <tbody>
            {rows.length === 0 ? <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Tidak ada commission menunggu approval.</td></tr> :
              rows.map((r) => { const c = r.closing; return (
                <tr key={c.period} className="border-t border-slate-100" data-testid={`comm-appr-row-${c.period}`}>
                  <td className="px-3 py-2.5 font-medium">{c.period}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100"><Badge className="bg-slate-100 text-slate-600 border-slate-200">{c.status}</Badge></td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{c.payout_month}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100">{c.total_pax}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100 font-semibold">{rp(c.total_commission)}</td>
                  <td className="px-3 py-2.5 border-l border-slate-100"><Badge className={c.sa_approval === "APPROVED" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : c.sa_approval === "REJECTED" ? "bg-red-50 text-red-700 border-red-200" : c.sa_approval === "REVISION" ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-slate-100 text-slate-500 border-slate-200"}>{c.sa_approval || "PENDING"}</Badge></td>
                  <td className="px-3 py-2.5 border-l border-slate-100"><Button size="sm" variant="ghost" onClick={() => setSel(r)} data-testid={`comm-appr-open-${c.period}`}><Eye className="h-4 w-4" /></Button></td>
                </tr>
              ); })}
          </tbody>
        </table>
      </CardContent>
      {sel && <CommissionApprovalDetail data={sel} reason={reason} setReason={setReason} onDecide={decide} onAdjust={adjust} onClose={() => { setSel(null); setReason(""); }} />}
    </Card>
  );
}

function CommissionApprovalDetail({ data, reason, setReason, onDecide, onAdjust, onClose }) {
  const c = data.closing;
  const [adj, setAdj] = useState({});
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="comm-appr-dialog">
        <DialogHeader><DialogTitle className="flex items-center gap-2">Commission {c.period} <Badge className="bg-slate-100 text-slate-600 border-slate-200">{c.status}</Badge> <span className="text-xs text-slate-400">Payout {c.payout_month}</span></DialogTitle></DialogHeader>
        <div className="space-y-3">
          <table className="w-full text-sm border border-slate-100">
            <thead><tr className="bg-slate-800 text-white text-left"><th className="px-3 py-2">Sales</th><th className="px-3 py-2 border-l border-slate-600">Pax</th><th className="px-3 py-2 border-l border-slate-600">Tier</th><th className="px-3 py-2 border-l border-slate-600">Commission</th><th className="px-3 py-2 border-l border-slate-600">Adjustment</th><th className="px-3 py-2 border-l border-slate-600">Final</th></tr></thead>
            <tbody>
              {data.lines.map((l) => (
                <tr key={l.id} className="border-t border-slate-100" data-testid={`comm-appr-line-${l.sales_pic_id}`}>
                  <td className="px-3 py-2 font-medium">{l.sales_pic_name}</td>
                  <td className="px-3 py-2 border-l border-slate-100">{l.total_pax}</td>
                  <td className="px-3 py-2 border-l border-slate-100">{l.tier}</td>
                  <td className="px-3 py-2 border-l border-slate-100">{rp(l.total_commission)}</td>
                  <td className="px-3 py-2 border-l border-slate-100">
                    <div className="flex items-center gap-1">
                      <Input type="number" className="w-24 h-8" defaultValue={l.adjustment || 0} onChange={(e) => setAdj({ ...adj, [l.id]: { ...(adj[l.id] || {}), value: e.target.value } })} data-testid={`comm-adj-val-${l.sales_pic_id}`} />
                      <Input className="w-32 h-8" placeholder="Reason" onChange={(e) => setAdj({ ...adj, [l.id]: { ...(adj[l.id] || {}), reason: e.target.value } })} data-testid={`comm-adj-reason-${l.sales_pic_id}`} />
                      <Button size="sm" variant="outline" onClick={() => onAdjust(l.id, adj[l.id]?.value ?? l.adjustment, adj[l.id]?.reason)} data-testid={`comm-adj-save-${l.sales_pic_id}`}>Adjust</Button>
                    </div>
                  </td>
                  <td className="px-3 py-2 border-l border-slate-100 font-semibold">{rp(l.final_commission)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div><Label className="text-xs">Reason (untuk Reject / Request Revision)</Label><Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="comm-appr-reason" /></div>
        </div>
        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onDecide(c.period, "REVISION")} data-testid="comm-appr-revision"><RotateCcw className="h-4 w-4 mr-1" />Request Revision</Button>
          <Button variant="outline" className="text-red-600 border-red-200" onClick={() => onDecide(c.period, "REJECTED")} data-testid="comm-appr-reject"><XCircle className="h-4 w-4 mr-1" />Reject</Button>
          <Button className="bg-emerald-600 hover:bg-emerald-700" onClick={() => onDecide(c.period, "APPROVED")} data-testid="comm-appr-approve"><ShieldCheck className="h-4 w-4 mr-1" />Approve</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
