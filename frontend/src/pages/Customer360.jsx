import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api, { API, formatApiErrorDetail } from "@/lib/api";
import { fmtIDR, fmtDate, fmtDateTime, STAGE_COLORS, FOLLOWUP_ACTIVITIES } from "@/config/crm";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import {
  ArrowLeft, Loader2, Phone, Mail, MapPin, StickyNote, MessageSquare, CalendarClock,
  Briefcase, Clock, User as UserIcon, Upload, Eye, Trash2, RefreshCw, UserCog,
  Sparkles, Copy, ShieldCheck, FileText, Send, Lightbulb, Pencil, History,
} from "lucide-react";
import { toast } from "sonner";
import { expiryTone, daysUntil } from "@/components/ExpiringDocsWidget";

export default function Customer360() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(undefined);
  const [dialog, setDialog] = useState(null); // 'note' | 'follow' | 'comm'

  const load = useCallback(() => {
    api.get(`/customers/${id}/360`).then((r) => setData(r.data)).catch((e) => {
      setData(null);
      if (e.response?.status === 403) toast.error("You cannot view this customer");
    });
  }, [id]);
  useEffect(() => { load(); }, [load]);

  if (data === undefined) return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  if (data === null) return (
    <div className="p-12 text-center" data-testid="customer360-forbidden">
      <p className="text-red-600 font-medium">Customer not available (403 / not found).</p>
      <Button variant="outline" className="mt-4" onClick={() => navigate("/crm")}>Back to customers</Button>
    </div>
  );

  const c = data.customer;
  const T = data.totals || {};
  const lastActivity = (data.timeline && data.timeline[0]) ? data.timeline[0].timestamp : null;
  const bmap = {};
  (data.bookings || []).forEach((b) => { bmap[b._id || b.id] = b.booking_number; });
  const stats = [
    ["Total Leads", T.leads ?? 0], ["Total Quotations", T.quotations ?? 0], ["Total Bookings", T.bookings ?? 0],
    ["Total Pax", T.total_pax ?? 0], ["Total Sales", fmtIDR(T.total_sales || 0)], ["Total Paid", fmtIDR(T.total_paid || 0)],
    ["Outstanding", fmtIDR(T.outstanding || 0)], ["Total Refund", fmtIDR(T.total_refund || 0)],
    ["Last Booking", T.last_booking ? fmtDate(T.last_booking) : "—"],
  ];

  return (
    <div className="space-y-6" data-testid="customer360-page">
      <button onClick={() => navigate("/crm")} className="flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900 transition-colors duration-200" data-testid="back-to-customers">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to customers
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Profile */}
        <Card className="border-slate-200 shadow-sm lg:col-span-1 h-fit">
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="h-14 w-14 rounded-full bg-blue-600 text-white flex items-center justify-center text-lg font-semibold">
                {(c.full_name || "?").slice(0, 2).toUpperCase()}
              </div>
              <div>
                <h2 className="font-display text-xl font-bold text-slate-900">{c.full_name}</h2>
                <p className="text-xs font-mono text-slate-400">{c.customer_code}</p>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-1">
              <Badge variant="outline" className="bg-slate-100 text-slate-700">{c.customer_type}</Badge>
              {(c.tags || []).map((t) => <Badge key={t} variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">{t}</Badge>)}
            </div>
            <div className="mt-5 space-y-2 text-sm text-slate-600">
              {c.whatsapp && <p className="flex items-center gap-2"><Phone className="h-4 w-4 text-slate-400" aria-hidden="true" />{c.whatsapp}</p>}
              {c.email && <p className="flex items-center gap-2"><Mail className="h-4 w-4 text-slate-400" aria-hidden="true" />{c.email}</p>}
              {(c.city || c.country) && <p className="flex items-center gap-2"><MapPin className="h-4 w-4 text-slate-400" aria-hidden="true" />{[c.city, c.country].filter(Boolean).join(", ")}</p>}
              <p className="flex items-center gap-2"><UserIcon className="h-4 w-4 text-slate-400" aria-hidden="true" />PIC: {c.sales_pic_name}<ChangePicButton customerId={id} currentPicId={c.sales_pic_id} onDone={load} /></p>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-2 text-xs text-slate-500" data-testid="c360-profile">
              <Info label="Customer ID" value={c.customer_code} /><Info label="Type" value={c.customer_type} />
              <Info label="Phone" value={c.phone || c.whatsapp} /><Info label="WhatsApp" value={c.whatsapp} />
              <Info label="Email" value={c.email} /><Info label="Gender" value={c.gender} />
              <Info label="DOB" value={fmtDate(c.date_of_birth)} /><Info label="Lead Source" value={c.customer_source} />
              <Info label="Assigned Sales" value={c.sales_pic_name} /><Info label="Since" value={fmtDate(c.created_at)} />
              <Info label="Last Activity" value={lastActivity ? fmtDate(lastActivity) : "—"} /><Info label="NIK" value={c.nik} />
              <div className="col-span-2"><Info label="Address" value={[c.address, c.city, c.country].filter(Boolean).join(", ")} /></div>
            </div>
            {c.notes && <p className="mt-4 text-sm text-slate-500 bg-slate-50 rounded-md p-3 border border-slate-100">{c.notes}</p>}
            <div className="mt-5 grid grid-cols-2 gap-2">
              <Button size="sm" variant="outline" onClick={() => setDialog("note")} data-testid="qa-note"><StickyNote className="h-4 w-4 mr-1" aria-hidden="true" />Note</Button>
              <Button size="sm" variant="outline" onClick={() => setDialog("comm")} data-testid="qa-comm"><MessageSquare className="h-4 w-4 mr-1" aria-hidden="true" />Log Msg</Button>
              <EditCustomerButton customer={c} onDone={load} />
              <Button size="sm" className="col-span-2 bg-blue-600 hover:bg-blue-700" onClick={() => setDialog("follow")} data-testid="qa-follow"><CalendarClock className="h-4 w-4 mr-1" aria-hidden="true" />Schedule Follow Up</Button>
            </div>
          </CardContent>
        </Card>

        {/* Right column */}
        <div className="lg:col-span-2 space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3" data-testid="c360-stats">
            {stats.map(([l, v], i) => (
              <Card key={i} className="border-slate-200 shadow-sm"><CardContent className="p-3.5">
                <p className="text-[11px] uppercase tracking-wide font-semibold text-slate-400">{l}</p>
                <p className="font-display text-lg font-bold text-slate-900 mt-0.5">{v}</p>
              </CardContent></Card>
            ))}
          </div>

          <Tabs defaultValue="overview">
            <TabsList className="flex flex-wrap h-auto gap-1" data-testid="c360-tabs">
              <TabsTrigger value="overview" data-testid="tab-overview">Overview</TabsTrigger>
              <TabsTrigger value="leads" data-testid="tab-leads">Leads</TabsTrigger>
              <TabsTrigger value="quotations" data-testid="tab-quotations">Quotations</TabsTrigger>
              <TabsTrigger value="bookings" data-testid="tab-bookings">Bookings</TabsTrigger>
              <TabsTrigger value="payments" data-testid="tab-payments">Payments</TabsTrigger>
              <TabsTrigger value="refunds" data-testid="tab-refunds">Refunds</TabsTrigger>
              <TabsTrigger value="commissions" data-testid="tab-commissions">Commissions</TabsTrigger>
              <TabsTrigger value="conversations" data-testid="tab-conversations">Conversations</TabsTrigger>
              <TabsTrigger value="followups" data-testid="tab-followups">Follow Ups</TabsTrigger>
              <TabsTrigger value="documents" data-testid="tab-documents">Documents</TabsTrigger>
              <TabsTrigger value="timeline" data-testid="tab-timeline">Activity Timeline</TabsTrigger>
              <TabsTrigger value="audit" data-testid="tab-audit"><History className="h-3.5 w-3.5 mr-1 text-slate-500" aria-hidden="true" />Riwayat Perubahan</TabsTrigger>
              <TabsTrigger value="ai-assistant" data-testid="tab-ai-assistant"><Sparkles className="h-3.5 w-3.5 mr-1 text-purple-500" aria-hidden="true" />AI Assistant</TabsTrigger>
            </TabsList>

            <TabsContent value="overview">
              <Card className="border-slate-200 shadow-sm"><CardContent className="p-5 grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm" data-testid="c360-overview">
                <Info label="Assigned Sales" value={c.sales_pic_name} />
                <Info label="Customer Since" value={fmtDate(c.created_at)} />
                <Info label="Last Activity" value={lastActivity ? fmtDateTime(lastActivity) : "—"} />
                <Info label="Last Booking" value={T.last_booking ? fmtDate(T.last_booking) : "—"} />
                <Info label="Total Bookings / Pax" value={`${T.bookings ?? 0} / ${T.total_pax ?? 0}`} />
                <Info label="Total Sales" value={fmtIDR(T.total_sales || 0)} />
                <Info label="Total Paid" value={fmtIDR(T.total_paid || 0)} />
                <Info label="Outstanding" value={fmtIDR(T.outstanding || 0)} />
              </CardContent></Card>
            </TabsContent>

            <TabsContent value="leads">
              <Rows testid="c360-leads" items={data.leads} empty="No leads." row={(l) => (
                <>
                  <div><p className="font-medium text-slate-900">{l.interested_package || l.lead_code}</p>
                    <p className="text-xs text-slate-500">{l.destination} · {l.pax || 0} pax · {fmtIDR(l.budget || 0)}</p></div>
                  <Badge variant="outline" className={STAGE_COLORS[l.status]}>{l.status}</Badge>
                </>
              )} />
            </TabsContent>

            <TabsContent value="quotations">
              <Rows testid="c360-quotations" items={data.quotations} empty="No quotations." row={(q) => (
                <>
                  <div><p className="font-medium text-slate-900">{q.quotation_number}</p>
                    <p className="text-xs text-slate-500">{q.package_name} · {q.pax || 0} pax · {fmtIDR(q.total || 0)}</p></div>
                  <Badge variant="outline" className="bg-slate-100 text-slate-700">{q.status}</Badge>
                </>
              )} />
            </TabsContent>

            <TabsContent value="bookings">
              <Rows testid="c360-bookings" items={data.bookings} empty="No bookings." row={(b) => (
                <>
                  <div><p className="font-medium text-slate-900">{b.booking_number}</p>
                    <p className="text-xs text-slate-500">{b.package_name} · {b.pax || 0} pax · {fmtIDR(b.total || 0)}</p></div>
                  <div className="text-right"><Badge variant="outline" className="bg-slate-100 text-slate-700">{b.status}</Badge>
                    {b.booking_source === "AUTO SALES" && <Badge className="ml-1 bg-purple-100 text-purple-700 border-purple-200">AUTO</Badge>}</div>
                </>
              )} />
            </TabsContent>

            <TabsContent value="payments">
              <Rows testid="c360-payments" items={data.payments} empty="No payments." row={(p) => (
                <>
                  <div><p className="font-medium text-slate-900">{fmtIDR(p.amount || 0)}</p>
                    <p className="text-xs text-slate-500">{p.invoice_number} · {p.payment_method || "—"} · {p.reference_number || ""}</p></div>
                  <span className="text-xs text-slate-500">{fmtDate(p.payment_date || p.created_at)}</span>
                </>
              )} />
            </TabsContent>

            <TabsContent value="refunds">
              <Rows testid="c360-refunds" items={data.refunds} empty="No refunds." row={(r) => (
                <>
                  <div><p className="font-medium text-slate-900">{r.refund_number}</p>
                    <p className="text-xs text-slate-500">{fmtIDR(r.approved_refund || r.proposed_refund || 0)}</p></div>
                  <Badge variant="outline" className="bg-slate-100 text-slate-700">{r.status}</Badge>
                </>
              )} />
            </TabsContent>

            <TabsContent value="commissions">
              <Rows testid="c360-commissions" items={data.commissions} empty="No commissions." row={(cm) => (
                <>
                  <div><p className="font-medium text-slate-900">{bmap[cm.booking_id] || cm.booking_number || "Commission"}</p>
                    <p className="text-xs text-slate-500">Period {cm.period || "—"} · {cm.pax || 0} pax</p></div>
                  <span className="text-sm font-medium text-slate-700">{fmtIDR(cm.final_commission ?? cm.total_commission ?? cm.commission ?? cm.rate_per_pax ?? 0)}</span>
                </>
              )} />
            </TabsContent>

            <TabsContent value="conversations">
              <Card className="border-slate-200 shadow-sm"><CardContent className="p-4" data-testid="c360-conversations">
                {(data.conversations || []).length === 0 ? <p className="text-sm text-slate-400 text-center py-6">Belum ada percakapan.</p> : (
                  <div className="space-y-3">
                    {data.conversations.map((m, i) => {
                      const inbound = m.direction === "INBOUND";
                      return (
                        <div key={m.id || m.conversation_id || i} className={`flex ${inbound ? "justify-start" : "justify-end"}`} data-testid={`c360-chat-${m.direction}`}>
                          <div className={`max-w-[75%] rounded-2xl px-4 py-2 ${inbound ? "bg-slate-100 text-slate-800 rounded-tl-sm" : "bg-blue-600 text-white rounded-tr-sm"}`}>
                            <div className="flex items-center gap-2 mb-0.5">
                              <span className={`text-[10px] font-semibold ${inbound ? "text-slate-500" : "text-blue-100"}`}>
                                {m.sender_name || m.sender_type}{m.ai_or_human === "AI" ? " · AI" : ""} · {m.channel || "WHATSAPP"}
                              </span>
                              {m.status === "REQUIRES_HUMAN" && <Badge className="bg-amber-500 text-white text-[9px] px-1.5 py-0">HANDOVER</Badge>}
                            </div>
                            <p className="text-sm whitespace-pre-wrap">{m.message}</p>
                            <p className={`text-[10px] mt-1 ${inbound ? "text-slate-400" : "text-blue-100"}`}>
                              {fmtDateTime(m.timestamp)}{m.n8n_workflow_id ? ` · WF ${m.n8n_workflow_id}` : ""}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent></Card>
            </TabsContent>

            <TabsContent value="followups">
              <Rows testid="c360-followups" items={data.follow_ups} empty="No follow ups." row={(f) => (
                <>
                  <div><p className="font-medium text-slate-900">{f.activity_type}</p><p className="text-xs text-slate-500">{f.notes}</p></div>
                  <div className="text-right"><p className="text-xs text-slate-500">{fmtDate(f.due_date)}</p>
                    <Badge variant="outline" className={f.status === "completed" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-700 border-amber-200"}>{f.status}</Badge></div>
                </>
              )} />
            </TabsContent>

            <TabsContent value="documents">
              <DocumentsTab customerId={id} docs={data.documents} bmap={bmap} onChange={load} />
            </TabsContent>

            <TabsContent value="timeline">
              <Card className="border-slate-200 shadow-sm"><CardContent className="p-6" data-testid="customer-timeline">
                {data.timeline.length === 0 ? <p className="text-sm text-slate-400 text-center py-6">No activity yet.</p> : (
                  <ol className="relative border-l border-slate-200 ml-2 space-y-5">
                    {data.timeline.map((t, i) => (
                      <li key={i} className="ml-5">
                        <span className="absolute -left-1.5 h-3 w-3 rounded-full bg-blue-600 border-2 border-white" />
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-medium text-slate-900">{t.title}</p>
                          <span className="text-xs text-slate-400">{fmtDateTime(t.timestamp)}</span>
                        </div>
                        {t.detail && <p className="text-sm text-slate-500 mt-0.5">{t.detail}</p>}
                        <p className="text-[11px] text-slate-400 mt-0.5">by {t.user_name || "—"} · {t.kind}</p>
                      </li>
                    ))}
                  </ol>
                )}
              </CardContent></Card>
            </TabsContent>

            <TabsContent value="ai-assistant">
              <AIAssistantTab customerId={id} customerName={c.full_name} />
            </TabsContent>

            <TabsContent value="audit">
              <AuditTab customerId={id} />
            </TabsContent>
          </Tabs>
        </div>
      </div>

      <QuickDialog dialog={dialog} setDialog={setDialog} customer={c} onDone={load} />
    </div>
  );
}

function Info({ label, value }) {
  return <div><span className="text-slate-400">{label}: </span><span className="text-slate-700">{value || "—"}</span></div>;
}

function ChangePicButton({ customerId, currentPicId, onDone }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [users, setUsers] = useState([]);
  const [sel, setSel] = useState(currentPicId || "");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (open && users.length === 0) {
      api.get("/users").then((r) => setUsers((r.data || []).filter((u) => ["sales", "super_admin"].includes(u.role) && u.status !== "ARCHIVED"))).catch(() => {});
    }
  }, [open, users.length]);
  if (user?.role !== "super_admin") return null;
  const save = async () => {
    if (!sel) return toast.error("Pilih PIC sales");
    setSaving(true);
    try { await api.put(`/customers/${customerId}`, { sales_pic_id: sel }); toast.success("PIC sales diperbarui"); setOpen(false); onDone(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };
  return (
    <>
      <button onClick={() => setOpen(true)} className="ml-1 text-blue-600 hover:text-blue-800 transition-colors" data-testid="change-pic-btn" title="Ganti PIC Sales"><UserCog className="h-3.5 w-3.5" /></button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-white" data-testid="change-pic-dialog">
          <DialogHeader><DialogTitle className="font-display">Ganti PIC Sales</DialogTitle><DialogDescription>Pindahkan kepemilikan customer ini ke sales lain.</DialogDescription></DialogHeader>
          <div className="space-y-2 py-2">
            <Label className="text-xs">PIC Sales</Label>
            <Select value={sel} onValueChange={setSel}>
              <SelectTrigger data-testid="pic-select"><SelectValue placeholder="Pilih sales" /></SelectTrigger>
              <SelectContent className="bg-white">
                {users.map((u) => <SelectItem key={u._id} value={u._id} data-testid={`pic-option-${u._id}`}>{u.name} ({u.role})</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Batal</Button>
            <Button className="bg-blue-600 hover:bg-blue-700" onClick={save} disabled={saving} data-testid="pic-save-btn">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Simpan"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function EditCustomerButton({ customer, onDone }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({});
  const openDialog = () => {
    setForm({
      full_name: customer.full_name || "", whatsapp: customer.whatsapp || "", phone: customer.phone || "",
      email: customer.email || "", gender: customer.gender || "", date_of_birth: customer.date_of_birth || "",
      nik: customer.nik || "", passport_number: customer.passport_number || "", passport_expiry: customer.passport_expiry || "",
      address: customer.address || "", city: customer.city || "", province: customer.province || "",
      postal_code: customer.postal_code || "", country: customer.country || "",
      customer_type: customer.customer_type || "", customer_source: customer.customer_source || "", notes: customer.notes || "",
    });
    setOpen(true);
  };
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e?.target ? e.target.value : e }));
  const save = async () => {
    if (!(form.full_name || "").trim()) return toast.error("Nama wajib diisi");
    setSaving(true);
    try {
      await api.put(`/customers/${customer._id || customer.id}`, form);
      toast.success("Data customer diperbarui");
      setOpen(false);
      onDone();
    } catch (e) {
      const st = e.response?.status;
      const d = e.response?.data?.detail;
      if (st === 409) toast.error(typeof d === "string" ? d : "Nomor HP/WhatsApp sudah terdaftar pada customer lain.");
      else toast.error(formatApiErrorDetail(d));
    } finally { setSaving(false); }
  };
  const Field = ({ k, label, type = "text" }) => (
    <div className="space-y-1">
      <Label className="text-xs">{label}</Label>
      <Input type={type} value={form[k] || ""} onChange={set(k)} data-testid={`edit-cust-${k}`} />
    </div>
  );
  return (
    <>
      <Button size="sm" variant="outline" className="col-span-2 border-blue-200 text-blue-700 hover:bg-blue-50" onClick={openDialog} data-testid="edit-customer-btn">
        <Pencil className="h-4 w-4 mr-1" aria-hidden="true" />Edit Customer
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-white max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="edit-customer-dialog">
          <DialogHeader>
            <DialogTitle className="font-display">Edit Data Customer</DialogTitle>
            <DialogDescription>Perbarui data customer. Perubahan akan tercatat di Riwayat Perubahan.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-2">
            <div className="sm:col-span-2"><Field k="full_name" label="Nama Lengkap" /></div>
            <Field k="whatsapp" label="WhatsApp" />
            <Field k="phone" label="No. HP" />
            <Field k="email" label="Email" type="email" />
            <div className="space-y-1">
              <Label className="text-xs">Gender</Label>
              <Select value={form.gender || ""} onValueChange={set("gender")}>
                <SelectTrigger data-testid="edit-cust-gender"><SelectValue placeholder="Pilih" /></SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="Male">Laki-laki</SelectItem>
                  <SelectItem value="Female">Perempuan</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Field k="date_of_birth" label="Tanggal Lahir" type="date" />
            <Field k="nik" label="NIK" />
            <Field k="passport_number" label="No. Paspor" />
            <Field k="passport_expiry" label="Masa Berlaku Paspor" type="date" />
            <div className="sm:col-span-2"><Field k="address" label="Alamat" /></div>
            <Field k="city" label="Kota" />
            <Field k="province" label="Provinsi" />
            <Field k="postal_code" label="Kode Pos" />
            <Field k="country" label="Negara" />
            <div className="space-y-1">
              <Label className="text-xs">Tipe Customer</Label>
              <Select value={form.customer_type || ""} onValueChange={set("customer_type")}>
                <SelectTrigger data-testid="edit-cust-customer_type"><SelectValue placeholder="Pilih" /></SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="Prospect">Prospect</SelectItem>
                  <SelectItem value="Customer">Customer</SelectItem>
                  <SelectItem value="VIP">VIP</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Field k="customer_source" label="Sumber" />
            <div className="sm:col-span-2 space-y-1">
              <Label className="text-xs">Catatan</Label>
              <Textarea value={form.notes || ""} onChange={set("notes")} data-testid="edit-cust-notes" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Batal</Button>
            <Button className="bg-blue-600 hover:bg-blue-700" onClick={save} disabled={saving} data-testid="edit-customer-save-btn">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Simpan Perubahan"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function AuditTab({ customerId }) {
  const [logs, setLogs] = useState(null);
  useEffect(() => {
    api.get(`/customers/${customerId}/audit`).then((r) => setLogs(r.data || [])).catch(() => setLogs([]));
  }, [customerId]);
  if (logs === null) return <div className="p-8 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>;
  return (
    <Card className="border-slate-200 shadow-sm"><CardContent className="p-6" data-testid="customer-audit">
      {logs.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-6">Belum ada riwayat perubahan.</p>
      ) : (
        <ol className="relative border-l border-slate-200 ml-2 space-y-5">
          {logs.map((l, i) => (
            <li key={i} className="ml-5" data-testid={`audit-row-${i}`}>
              <span className="absolute -left-1.5 h-3 w-3 rounded-full bg-amber-500 border-2 border-white" />
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-slate-900">Ubah <span className="font-mono text-amber-700">{l.field}</span></p>
                <span className="text-xs text-slate-400">{fmtDateTime(l.timestamp)}</span>
              </div>
              <p className="text-sm text-slate-500 mt-0.5">
                <span className="line-through text-slate-400">{String(l.old_value ?? "—")}</span>
                {" → "}
                <span className="text-slate-800 font-medium">{String(l.new_value ?? "—")}</span>
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">oleh {l.changed_by || "—"} · {l.changed_by_role || ""}</p>
            </li>
          ))}
        </ol>
      )}
    </CardContent></Card>
  );
}

const AI_ACTIONS = [
  { mode: "summary", label: "Ringkas Customer", desc: "Ringkasan profil, minat, percakapan, quotation/booking & follow-up terakhir.", icon: FileText, color: "text-blue-600", bg: "bg-blue-50 border-blue-200 hover:bg-blue-100" },
  { mode: "followup", label: "Draft Follow-Up", desc: "Draft pesan WhatsApp follow-up yang personal & persuasif.", icon: Send, color: "text-emerald-600", bg: "bg-emerald-50 border-emerald-200 hover:bg-emerald-100" },
  { mode: "suggestion", label: "Saran Respons & Paket", desc: "Rekomendasi paket, saran balasan, dan strategi follow-up.", icon: Lightbulb, color: "text-amber-600", bg: "bg-amber-50 border-amber-200 hover:bg-amber-100" },
];

function AIAssistantTab({ customerId, customerName }) {
  const [loading, setLoading] = useState(null); // mode currently loading
  const [result, setResult] = useState(null); // { mode, draft }

  const run = async (mode) => {
    setLoading(mode);
    setResult(null);
    try {
      const r = await api.post(`/sales/ai-assist/${customerId}`, { mode });
      setResult({ mode, draft: r.data.draft || "" });
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "AI gagal merespons");
    } finally {
      setLoading(null);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(result.draft);
      toast.success("Disalin ke clipboard");
    } catch { toast.error("Gagal menyalin"); }
  };

  const activeAction = result ? AI_ACTIONS.find((a) => a.mode === result.mode) : null;

  return (
    <div className="space-y-4" data-testid="c360-ai-assistant">
      <Card className="border-purple-200 bg-purple-50/40 shadow-sm">
        <CardContent className="p-4 flex items-start gap-3">
          <div className="h-9 w-9 rounded-lg bg-purple-600 text-white flex items-center justify-center shrink-0">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <p className="font-display text-base font-bold text-slate-900">AI Sales Assistant</p>
            <p className="text-sm text-slate-500">Bantuan AI internal untuk {customerName}. Semua output hanya draft &mdash; wajib disetujui sales sebelum dikirim.</p>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {AI_ACTIONS.map((a) => {
          const Icon = a.icon;
          const isLoading = loading === a.mode;
          return (
            <button
              key={a.mode}
              onClick={() => run(a.mode)}
              disabled={!!loading}
              className={`text-left rounded-xl border p-4 transition-colors duration-200 disabled:opacity-60 disabled:cursor-not-allowed ${a.bg}`}
              data-testid={`ai-action-${a.mode}`}
            >
              <div className="flex items-center gap-2 mb-1.5">
                {isLoading ? <Loader2 className={`h-5 w-5 animate-spin ${a.color}`} /> : <Icon className={`h-5 w-5 ${a.color}`} aria-hidden="true" />}
                <span className="font-semibold text-slate-900 text-sm">{a.label}</span>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">{a.desc}</p>
            </button>
          );
        })}
      </div>

      {loading && !result && (
        <Card className="border-slate-200 shadow-sm"><CardContent className="p-8 flex flex-col items-center gap-3 text-slate-400" data-testid="ai-loading">
          <Loader2 className="h-6 w-6 animate-spin text-purple-600" />
          <p className="text-sm">AI sedang menyusun jawaban&hellip;</p>
        </CardContent></Card>
      )}

      {result && (
        <Card className="border-slate-200 shadow-sm" data-testid="ai-result">
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                {activeAction && <activeAction.icon className={`h-4 w-4 ${activeAction.color}`} aria-hidden="true" />}
                <span className="font-semibold text-slate-900 text-sm">{activeAction?.label}</span>
              </div>
              <Button size="sm" variant="outline" onClick={copy} data-testid="ai-copy-btn">
                <Copy className="h-4 w-4 mr-1" aria-hidden="true" />Salin
              </Button>
            </div>
            <div className="rounded-lg bg-slate-50 border border-slate-100 p-4 text-sm text-slate-700 whitespace-pre-wrap leading-relaxed" data-testid="ai-result-text">
              {result.draft}
            </div>
            <div className="mt-3 flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2" data-testid="ai-approval-notice">
              <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>Draft ini perlu ditinjau &amp; disetujui sales sebelum dikirim ke customer. AI tidak mengirim pesan secara otomatis.</span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
function Rows({ items, row, empty, testid }) {
  return (
    <Card className="border-slate-200 shadow-sm"><CardContent className="p-4 space-y-2" data-testid={testid}>
      {(!items || items.length === 0) ? <p className="text-sm text-slate-400 text-center py-6">{empty}</p> :
        items.map((it, i) => (
          <div key={it._id || it.id || i} className="flex items-center justify-between border border-slate-100 rounded-md p-3">
            {row(it)}
          </div>
        ))}
    </CardContent></Card>
  );
}
function Kpi({ label, value, icon: Icon }) {
  return (
    <Card className="border-slate-200 shadow-sm"><CardContent className="p-4">
      <div className="flex items-center justify-between"><p className="text-xs uppercase tracking-wide font-semibold text-slate-500">{label}</p>
        <Icon className="h-4 w-4 text-blue-500" aria-hidden="true" /></div>
      <p className="font-display text-2xl font-bold text-slate-900 mt-1">{value}</p>
    </CardContent></Card>
  );
}

function QuickDialog({ dialog, setDialog, customer, onDone }) {
  const [val, setVal] = useState({ note: "", message: "", channel: "whatsapp", direction: "outbound", activity_type: "Call", due_date: "", notes: "" });
  const [saving, setSaving] = useState(false);
  const s = (k) => (v) => setVal((o) => ({ ...o, [k]: v }));

  const submit = async () => {
    setSaving(true);
    try {
      if (dialog === "note") await api.post(`/customers/${customer._id}/notes`, { note: val.note });
      else if (dialog === "comm") await api.post(`/communications`, { customer_id: customer._id, phone: customer.whatsapp, message: val.message, channel: val.channel, direction: val.direction });
      else if (dialog === "follow") await api.post(`/follow-ups`, { customer_id: customer._id, activity_type: val.activity_type, due_date: val.due_date, notes: val.notes });
      toast.success("Saved");
      setDialog(null); onDone();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  return (
    <Dialog open={!!dialog} onOpenChange={(o) => !o && setDialog(null)}>
      <DialogContent className="bg-white" data-testid="quick-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">
            {dialog === "note" ? "Add Note" : dialog === "comm" ? "Log Communication" : "Schedule Follow Up"}
          </DialogTitle>
          <DialogDescription>For {customer.full_name}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          {dialog === "note" && <Textarea placeholder="Write a note..." value={val.note} onChange={(e) => s("note")(e.target.value)} data-testid="note-input" />}
          {dialog === "comm" && (<>
            <div className="grid grid-cols-2 gap-3">
              <Select value={val.channel} onValueChange={s("channel")}><SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white"><SelectItem value="whatsapp">WhatsApp</SelectItem><SelectItem value="email">Email</SelectItem><SelectItem value="phone">Phone</SelectItem></SelectContent></Select>
              <Select value={val.direction} onValueChange={s("direction")}><SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white"><SelectItem value="outbound">Outbound</SelectItem><SelectItem value="inbound">Inbound</SelectItem></SelectContent></Select>
            </div>
            <Textarea placeholder="Message content..." value={val.message} onChange={(e) => s("message")(e.target.value)} data-testid="comm-input" />
          </>)}
          {dialog === "follow" && (<>
            <div className="space-y-2"><Label>Activity</Label>
              <Select value={val.activity_type} onValueChange={s("activity_type")}><SelectTrigger data-testid="follow-activity-select"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white">{FOLLOWUP_ACTIVITIES.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}</SelectContent></Select></div>
            <div className="space-y-2"><Label>Due date</Label><Input type="date" value={val.due_date} onChange={(e) => s("due_date")(e.target.value)} data-testid="follow-date-input" /></div>
            <Textarea placeholder="Notes..." value={val.notes} onChange={(e) => s("notes")(e.target.value)} />
          </>)}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="quick-save-button">{saving ? "Saving..." : "Save"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ChatHistory({ customerId }) {  const [msgs, setMsgs] = useState(null);
  useEffect(() => {
    api.get(`/customers/${customerId}/conversations`).then((r) => setMsgs(r.data || [])).catch(() => setMsgs([]));
  }, [customerId]);
  if (msgs === null) return <Card className="border-slate-200 shadow-sm"><CardContent className="p-8 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></CardContent></Card>;
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardContent className="p-4" data-testid="chat-history">
        {msgs.length === 0 ? <p className="text-sm text-slate-400 text-center py-6">Belum ada percakapan WhatsApp.</p> : (
          <div className="space-y-3">
            {msgs.map((m) => {
              const inbound = m.direction === "INBOUND";
              return (
                <div key={m.id || m.conversation_id} className={`flex ${inbound ? "justify-start" : "justify-end"}`} data-testid={`chat-msg-${m.direction}`}>
                  <div className={`max-w-[75%] rounded-2xl px-4 py-2 ${inbound ? "bg-slate-100 text-slate-800 rounded-tl-sm" : "bg-blue-600 text-white rounded-tr-sm"}`}>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className={`text-[10px] font-semibold ${inbound ? "text-slate-500" : "text-blue-100"}`}>{m.sender_type}{m.ai_or_human === "AI" && !inbound ? " · AI" : ""}</span>
                      {m.status === "REQUIRES_HUMAN" && <Badge className="bg-amber-500 text-white text-[9px] px-1.5 py-0">HANDOVER</Badge>}
                    </div>
                    <p className="text-sm whitespace-pre-wrap">{m.message}</p>
                    <p className={`text-[10px] mt-1 ${inbound ? "text-slate-400" : "text-blue-100"}`}>{fmtDateTime(m.timestamp)}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}


const DOC_TYPES = ["KTP", "PASSPORT", "PHOTO", "VISA", "MARRIAGE_BOOK", "OTHER"];
const META_TYPES = ["PASSPORT", "VISA"];

function DocumentsTab({ customerId, docs, bmap, onChange }) {
  const [upOpen, setUpOpen] = useState(false);
  const [replaceDoc, setReplaceDoc] = useState(null);
  const view = (d) => window.open(`${API}/documents/${d.id || d._id}/download?auth=${localStorage.getItem("token")}`, "_blank");
  const del = async (d) => {
    if (!window.confirm(`Hapus dokumen ${d.doc_type}?`)) return;
    try { await api.delete(`/documents/${d.id || d._id}`); toast.success("Dokumen dihapus"); onChange(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  return (
    <Card className="border-slate-200 shadow-sm"><CardContent className="p-4 space-y-2" data-testid="c360-documents">
      <div className="flex justify-end">
        <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={() => setUpOpen(true)} data-testid="c360-upload-doc-btn"><Upload className="h-4 w-4 mr-1" aria-hidden="true" />Upload Dokumen</Button>
      </div>
      {(!docs || docs.length === 0) ? <p className="text-sm text-slate-400 text-center py-6">No documents.</p> :
        docs.map((d) => {
          const tone = META_TYPES.includes(d.doc_type) ? expiryTone(daysUntil(d.expiry_date)) : null;
          return (
            <div key={d.id || d._id} className="flex items-center justify-between border border-slate-100 rounded-md p-3" data-testid={`c360-doc-${d.id || d._id}`}>
              <div className="min-w-0">
                <p className="font-medium text-slate-900 truncate">{d.doc_type}{d.document_number ? ` · ${d.document_number}` : ""}</p>
                <p className="text-xs text-slate-500">{d.customer_id ? "Customer" : (bmap[d.booking_id] || d.booking_id || "—")}{d.expiry_date ? ` · Exp ${(d.expiry_date || "").slice(0, 10)}` : ""}</p>
              </div>
              <div className="flex items-center gap-2">
                {tone && <Badge variant="outline" className={`${tone.cls} text-[10px]`}>{tone.label}</Badge>}
                <Badge variant="outline" className="bg-slate-100 text-slate-700">{d.status}</Badge>
                <Button size="icon" variant="ghost" className="h-7 w-7 text-slate-600" title="Lihat" onClick={() => view(d)} data-testid={`c360-doc-view-${d.id || d._id}`}><Eye className="h-4 w-4" /></Button>
                <Button size="icon" variant="ghost" className="h-7 w-7 text-blue-600" title="Ganti" onClick={() => setReplaceDoc(d)} data-testid={`c360-doc-replace-${d.id || d._id}`}><RefreshCw className="h-4 w-4" /></Button>
                <Button size="icon" variant="ghost" className="h-7 w-7 text-red-600" title="Hapus" onClick={() => del(d)} data-testid={`c360-doc-delete-${d.id || d._id}`}><Trash2 className="h-4 w-4" /></Button>
              </div>
            </div>
          );
        })}
      {upOpen && <DocUploadDialog customerId={customerId} onClose={() => setUpOpen(false)} onDone={() => { setUpOpen(false); onChange(); }} />}
      {replaceDoc && <DocReplaceDialog doc={replaceDoc} onClose={() => setReplaceDoc(null)} onDone={() => { setReplaceDoc(null); onChange(); }} />}
    </CardContent></Card>
  );
}

function DocUploadDialog({ customerId, onClose, onDone }) {
  const [f, setF] = useState({ doc_type: "KTP", document_number: "", issue_date: "", expiry_date: "" });
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const isMeta = META_TYPES.includes(f.doc_type);
  const submit = async () => {
    if (!file) return toast.error("Pilih file dokumen dulu");
    if (isMeta && !f.expiry_date) return toast.error("Tanggal kedaluwarsa wajib untuk Passport/Visa");
    setSaving(true);
    const fd = new FormData();
    fd.append("doc_type", f.doc_type); fd.append("file", file);
    fd.append("document_number", f.document_number); fd.append("issue_date", f.issue_date); fd.append("expiry_date", f.expiry_date);
    try { await api.post(`/customers/${customerId}/documents`, fd, { headers: { "Content-Type": "multipart/form-data" } }); toast.success("Dokumen diupload"); onDone(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setSaving(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-white max-w-md" data-testid="c360-doc-upload-dialog">
        <DialogHeader><DialogTitle className="font-display">Upload Dokumen Customer</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div className="space-y-1"><Label className="text-xs">Jenis Dokumen</Label>
            <Select value={f.doc_type} onValueChange={(v) => setF({ ...f, doc_type: v })}><SelectTrigger data-testid="c360-doc-type"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-white">{DOC_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent></Select></div>
          {isMeta && (<>
            <div className="space-y-1"><Label className="text-xs">Nomor Dokumen</Label><Input value={f.document_number} onChange={(e) => setF({ ...f, document_number: e.target.value })} data-testid="c360-doc-number" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1"><Label className="text-xs">Tanggal Terbit</Label><Input type="date" value={f.issue_date} onChange={(e) => setF({ ...f, issue_date: e.target.value })} data-testid="c360-doc-issue" /></div>
              <div className="space-y-1"><Label className="text-xs">Tanggal Kedaluwarsa</Label><Input type="date" value={f.expiry_date} onChange={(e) => setF({ ...f, expiry_date: e.target.value })} data-testid="c360-doc-expiry" /></div>
            </div>
          </>)}
          <div className="space-y-1"><Label className="text-xs">File Dokumen</Label><Input type="file" onChange={(e) => setFile(e.target.files[0] || null)} data-testid="c360-doc-file" /></div>
        </div>
        <DialogFooter><Button onClick={submit} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="c360-doc-upload-save">{saving ? "Uploading..." : "Upload"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DocReplaceDialog({ doc, onClose, onDone }) {
  const isMeta = META_TYPES.includes(doc.doc_type);
  const [f, setF] = useState({ document_number: doc.document_number || "", issue_date: (doc.issue_date || "").slice(0, 10), expiry_date: (doc.expiry_date || "").slice(0, 10) });
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const submit = async () => {
    if (!file) return toast.error("Pilih file pengganti dulu");
    setSaving(true);
    const fd = new FormData(); fd.append("file", file);
    if (isMeta) { fd.append("document_number", f.document_number); fd.append("issue_date", f.issue_date); fd.append("expiry_date", f.expiry_date); }
    try { await api.post(`/documents/${doc.id || doc._id}/replace`, fd, { headers: { "Content-Type": "multipart/form-data" } }); toast.success("Dokumen diganti"); onDone(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); } finally { setSaving(false); }
  };
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-white max-w-md" data-testid="c360-doc-replace-dialog">
        <DialogHeader><DialogTitle className="font-display">Ganti Dokumen — {doc.doc_type}</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          {isMeta && (<>
            <div className="space-y-1"><Label className="text-xs">Nomor Dokumen</Label><Input value={f.document_number} onChange={(e) => setF({ ...f, document_number: e.target.value })} data-testid="c360-replace-number" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1"><Label className="text-xs">Tanggal Terbit</Label><Input type="date" value={f.issue_date} onChange={(e) => setF({ ...f, issue_date: e.target.value })} data-testid="c360-replace-issue" /></div>
              <div className="space-y-1"><Label className="text-xs">Tanggal Kedaluwarsa</Label><Input type="date" value={f.expiry_date} onChange={(e) => setF({ ...f, expiry_date: e.target.value })} data-testid="c360-replace-expiry" /></div>
            </div>
          </>)}
          <div className="space-y-1"><Label className="text-xs">File Pengganti</Label><Input type="file" onChange={(e) => setFile(e.target.files[0] || null)} data-testid="c360-doc-replace-file" /></div>
        </div>
        <DialogFooter><Button onClick={submit} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="c360-doc-replace-save">{saving ? "Uploading..." : "Ganti"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
