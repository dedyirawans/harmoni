import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
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
  Briefcase, Clock, User as UserIcon,
} from "lucide-react";
import { toast } from "sonner";

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
              <p className="flex items-center gap-2"><UserIcon className="h-4 w-4 text-slate-400" aria-hidden="true" />PIC: {c.sales_pic_name}</p>
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
              <Rows testid="c360-documents" items={data.documents} empty="No documents." row={(d) => (
                <>
                  <div><p className="font-medium text-slate-900">{d.doc_type}</p>
                    <p className="text-xs text-slate-500">{bmap[d.booking_id] || d.booking_id || "—"}</p></div>
                  <Badge variant="outline" className="bg-slate-100 text-slate-700">{d.status}</Badge>
                </>
              )} />
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

function ChatHistory({ customerId }) {
  const [msgs, setMsgs] = useState(null);
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
