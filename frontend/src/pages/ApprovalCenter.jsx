import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";
import { ShieldCheck, Plus, Loader2, ExternalLink } from "lucide-react";

const idr = (n) => "Rp " + Number(n || 0).toLocaleString("id-ID");
const dt = (s) => (s || "—").toString().replace("T", " ").slice(0, 16);
const TYPES = ["ALL", "REFUND", "CANCELLATION", "COMMISSION", "PRICE_ADJUSTMENT", "PAYMENT_ADJUSTMENT", "ACCOUNTING_ADJUSTMENT", "OTHER"];
const ADJ = ["PRICE_ADJUSTMENT", "PAYMENT_ADJUSTMENT", "ACCOUNTING_ADJUSTMENT", "OTHER"];
const STC = { PENDING: "bg-amber-50 text-amber-700 border-amber-200", APPROVED: "bg-emerald-50 text-emerald-700 border-emerald-200", REJECTED: "bg-red-50 text-red-700 border-red-200", REVISION: "bg-blue-50 text-blue-700 border-blue-200" };

export default function ApprovalCenter() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState({ pending: 0, approved_today: 0, rejected_today: 0, total_this_month: 0 });
  const [type, setType] = useState("ALL");
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [act, setAct] = useState(null); // {row, action}
  const [reason, setReason] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    const params = {};
    if (type !== "ALL") params.type = type;
    if (status !== "all") params.status = status;
    Promise.all([api.get("/approval-center", { params }), api.get("/approval-center/stats")])
      .then(([r, s]) => { setRows(r.data || []); setStats(s.data || {}); })
      .catch(() => toast.error("Gagal memuat approval"))
      .finally(() => setLoading(false));
  }, [type, status]);
  useEffect(() => { load(); }, [load]);

  const openDetail = async (r) => {
    try { const res = await api.get(`/approval-center/detail/${r.source}/${r.id}`); setDetail({ meta: r, doc: res.data }); }
    catch { toast.error("Gagal memuat detail"); }
  };
  const doAction = async () => {
    const { row, action } = act;
    if ((action === "REJECT" || action === "REQUEST_REVISION") && !reason.trim()) { toast.error("Reason wajib diisi"); return; }
    try {
      await api.post(`/approval-center/adjustments/${row.id}/action`, { action, reason });
      toast.success(`Approval ${action}`); setAct(null); setReason(""); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Gagal memproses"); }
  };

  const cards = [["Pending", stats.pending, "text-amber-600"], ["Approved Today", stats.approved_today, "text-emerald-600"],
    ["Rejected Today", stats.rejected_today, "text-red-600"], ["Total This Month", stats.total_this_month, "text-slate-900"]];

  return (
    <div className="space-y-5" data-testid="approval-center-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-slate-900 flex items-center justify-center"><ShieldCheck className="h-6 w-6 text-white" /></div>
          <div><h1 className="font-display text-3xl font-bold text-slate-900">Approval Center</h1>
            <p className="text-slate-500 mt-0.5">Pusat persetujuan terpusat • {user.role === "super_admin" ? "Full access" : "Finance"}.</p></div>
        </div>
        <NewAdjustment onDone={load} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="approval-stats">
        {cards.map(([l, v, c]) => (
          <Card key={l} className="border-slate-200 shadow-sm"><CardContent className="p-4">
            <p className="text-xs uppercase tracking-wide font-semibold text-slate-400">{l}</p>
            <p className={`font-display text-3xl font-bold mt-1 ${c}`}>{v}</p>
          </CardContent></Card>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Select value={type} onValueChange={setType}><SelectTrigger className="w-52" data-testid="approval-type-filter"><SelectValue /></SelectTrigger>
          <SelectContent>{TYPES.map((t) => <SelectItem key={t} value={t}>{t.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select>
        <Select value={status} onValueChange={setStatus}><SelectTrigger className="w-40" data-testid="approval-status-filter"><SelectValue /></SelectTrigger>
          <SelectContent>{["all", "PENDING", "APPROVED", "REJECTED", "REVISION"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select>
      </div>

      <Card className="border-slate-200 shadow-sm"><CardContent className="p-0 overflow-x-auto">
        {loading ? <div className="p-10 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
          : rows.length === 0 ? <p className="p-10 text-center text-slate-400 text-sm">Tidak ada approval.</p> : (
            <table className="w-full text-sm" data-testid="approval-table">
              <thead><tr className="bg-slate-900 text-white text-left">
                {["Approval #", "Type", "Reference", "Customer", "Amount", "Requested By", "Date", "Status", "Action"].map((h) =>
                  <th key={h} className="px-3 py-2.5 border-l border-slate-700 first:border-l-0">{h}</th>)}
              </tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={`${r.source}-${r.id}`} className="border-b border-slate-100 hover:bg-slate-50" data-testid={`approval-row-${r.id}`}>
                    <td className="px-3 py-2.5 font-medium text-slate-900">{r.approval_number}</td>
                    <td className="px-3 py-2.5"><Badge variant="outline" className="text-[10px]">{(r.type || "").replace(/_/g, " ")}</Badge></td>
                    <td className="px-3 py-2.5 text-slate-600">{r.reference || "—"}</td>
                    <td className="px-3 py-2.5 text-slate-600">{r.customer || "—"}</td>
                    <td className="px-3 py-2.5">{idr(r.amount)}</td>
                    <td className="px-3 py-2.5 text-slate-600">{r.requested_by || "—"}</td>
                    <td className="px-3 py-2.5 text-slate-500">{dt(r.requested_date)}</td>
                    <td className="px-3 py-2.5"><Badge variant="outline" className={STC[r.status]}>{r.status}</Badge></td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1.5">
                        <Button size="sm" variant="outline" onClick={() => openDetail(r)} data-testid={`approval-detail-${r.id}`}>Detail</Button>
                        {r.source === "adjustment" && r.actionable && r.status === "PENDING" ? (
                          <>
                            <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => { setAct({ row: r, action: "APPROVE" }); setReason(""); }} data-testid={`approval-approve-${r.id}`}>Approve</Button>
                            <Button size="sm" variant="outline" className="text-blue-600" onClick={() => { setAct({ row: r, action: "REQUEST_REVISION" }); setReason(""); }} data-testid={`approval-revision-${r.id}`}>Revise</Button>
                            <Button size="sm" variant="outline" className="text-red-600" onClick={() => { setAct({ row: r, action: "REJECT" }); setReason(""); }} data-testid={`approval-reject-${r.id}`}>Reject</Button>
                          </>
                        ) : r.link ? (
                          <Button size="sm" variant="outline" onClick={() => navigate(r.link)} data-testid={`approval-open-${r.id}`}><ExternalLink className="h-3.5 w-3.5 mr-1" />Open</Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </CardContent></Card>

      {/* Detail dialog */}
      <Dialog open={!!detail} onOpenChange={(v) => !v && setDetail(null)}>
        <DialogContent className="bg-white max-w-lg max-h-[85vh] overflow-y-auto" data-testid="approval-detail-dialog">
          <DialogHeader><DialogTitle>{detail?.meta?.approval_number} • {(detail?.meta?.type || "").replace(/_/g, " ")}</DialogTitle></DialogHeader>
          {detail && (
            <div className="space-y-2 text-sm">
              <Row l="Reference" v={detail.meta.reference} /><Row l="Customer" v={detail.meta.customer} />
              <Row l="Amount" v={idr(detail.meta.amount)} /><Row l="Requested By" v={detail.meta.requested_by} />
              <Row l="Reason" v={detail.doc.reason || detail.doc.notes} />
              {detail.doc.evidence_url && <Row l="Evidence" v={<a className="text-blue-600 underline" href={detail.doc.evidence_url} target="_blank" rel="noreferrer">Lihat</a>} />}
              <div className="pt-2"><p className="font-semibold text-slate-800 mb-1">History</p>
                <ol className="space-y-1.5" data-testid="approval-history">
                  {(detail.doc.history || []).length === 0 ? <p className="text-slate-400">Belum ada history.</p> :
                    detail.doc.history.map((h, i) => (
                      <li key={i} className="flex items-start gap-2 border-l-2 border-slate-200 pl-2">
                        <div><p className="text-slate-800"><b>{h.action}</b> — {h.by || h.user || "—"} <span className="text-slate-400">({h.role})</span></p>
                          {(h.comment || h.reason) && <p className="text-slate-500">{h.comment || h.reason}</p>}
                          <p className="text-[11px] text-slate-400">{dt(h.at)}</p></div>
                      </li>
                    ))}
                </ol>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Action dialog */}
      <Dialog open={!!act} onOpenChange={(v) => !v && setAct(null)}>
        <DialogContent className="bg-white" data-testid="approval-action-dialog">
          <DialogHeader><DialogTitle>{act?.action?.replace("_", " ")} — {act?.row?.approval_number}</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <Label>Reason / Comment {(act?.action === "REJECT" || act?.action === "REQUEST_REVISION") && <span className="text-red-500">*</span>}</Label>
            <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="approval-reason-input"
              placeholder={act?.action === "APPROVE" ? "Opsional" : "Wajib diisi"} />
          </div>
          <DialogFooter><Button onClick={doAction} data-testid="approval-action-confirm">Confirm {act?.action?.replace("_", " ")}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Row({ l, v }) {
  return <div className="flex gap-2"><span className="text-slate-400 w-28 shrink-0">{l}</span><span className="text-slate-800 break-words">{v || "—"}</span></div>;
}

function NewAdjustment({ onDone }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [f, setF] = useState({ atype: "PRICE_ADJUSTMENT", reference: "", customer_name: "", amount: "", reason: "", evidence_url: "" });
  const submit = async () => {
    if (!f.reason.trim()) { toast.error("Reason wajib diisi"); return; }
    setSaving(true);
    try { await api.post("/approval-center/adjustments", { ...f, amount: Number(f.amount || 0) });
      toast.success("Pengajuan approval dibuat"); setOpen(false);
      setF({ atype: "PRICE_ADJUSTMENT", reference: "", customer_name: "", amount: "", reason: "", evidence_url: "" }); onDone();
    } catch { toast.error("Gagal membuat pengajuan"); } finally { setSaving(false); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button data-testid="new-adjustment-btn"><Plus className="h-4 w-4 mr-1" />New Approval Request</Button></DialogTrigger>
      <DialogContent className="bg-white">
        <DialogHeader><DialogTitle>New Approval Request</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div><Label>Type</Label>
            <Select value={f.atype} onValueChange={(v) => setF({ ...f, atype: v })}><SelectTrigger data-testid="adj-type-select"><SelectValue /></SelectTrigger>
              <SelectContent>{ADJ.map((t) => <SelectItem key={t} value={t}>{t.replace(/_/g, " ")}</SelectItem>)}</SelectContent></Select></div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Reference</Label><Input value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} data-testid="adj-ref-input" placeholder="Booking/Invoice #" /></div>
            <div><Label>Amount</Label><Input type="number" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} data-testid="adj-amount-input" /></div>
          </div>
          <div><Label>Customer (name)</Label><Input value={f.customer_name} onChange={(e) => setF({ ...f, customer_name: e.target.value })} data-testid="adj-customer-input" /></div>
          <div><Label>Reason <span className="text-red-500">*</span></Label><Textarea rows={2} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} data-testid="adj-reason-input" /></div>
          <div><Label>Supporting Evidence (URL)</Label><Input value={f.evidence_url} onChange={(e) => setF({ ...f, evidence_url: e.target.value })} data-testid="adj-evidence-input" /></div>
        </div>
        <DialogFooter><Button onClick={submit} disabled={saving} data-testid="adj-save-btn">{saving ? "Saving..." : "Submit"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
