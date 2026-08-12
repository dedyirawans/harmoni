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
            <div className="mt-5 grid grid-cols-2 gap-2 text-xs text-slate-500">
              <Info label="NIK" value={c.nik} /><Info label="Passport" value={c.passport_number} />
              <Info label="DOB" value={fmtDate(c.date_of_birth)} /><Info label="Passport Exp" value={fmtDate(c.passport_expiry)} />
              <Info label="Source" value={c.customer_source} /><Info label="Since" value={fmtDate(c.created_at)} />
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
          <div className="grid grid-cols-3 gap-3">
            <Kpi label="Leads" value={data.totals.leads} icon={Briefcase} />
            <Kpi label="Follow Ups" value={data.totals.follow_ups} icon={CalendarClock} />
            <Kpi label="Pipeline Value" value={fmtIDR(data.totals.total_value)} icon={Clock} />
          </div>

          <Tabs defaultValue="timeline">
            <TabsList data-testid="c360-tabs">
              <TabsTrigger value="timeline" data-testid="tab-timeline">Timeline</TabsTrigger>
              <TabsTrigger value="leads">Leads</TabsTrigger>
              <TabsTrigger value="followups">Follow Ups</TabsTrigger>
              <TabsTrigger value="comms">Communication</TabsTrigger>
              <TabsTrigger value="chat" data-testid="tab-chat">WhatsApp Chat</TabsTrigger>
            </TabsList>

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

            <TabsContent value="leads">
              <Card className="border-slate-200 shadow-sm"><CardContent className="p-4 space-y-2">
                {data.leads.length === 0 ? <p className="text-sm text-slate-400 text-center py-6">No leads.</p> :
                  data.leads.map((l) => (
                    <div key={l._id} className="flex items-center justify-between border border-slate-100 rounded-md p-3">
                      <div><p className="font-medium text-slate-900">{l.interested_package || "Lead"}</p>
                        <p className="text-xs text-slate-500">{l.destination} · {l.pax} pax · {fmtIDR(l.budget)}</p></div>
                      <Badge variant="outline" className={STAGE_COLORS[l.status]}>{l.status}</Badge>
                    </div>
                  ))}
              </CardContent></Card>
            </TabsContent>

            <TabsContent value="followups">
              <Card className="border-slate-200 shadow-sm"><CardContent className="p-4 space-y-2">
                {data.follow_ups.length === 0 ? <p className="text-sm text-slate-400 text-center py-6">No follow ups.</p> :
                  data.follow_ups.map((f) => (
                    <div key={f._id} className="flex items-center justify-between border border-slate-100 rounded-md p-3">
                      <div><p className="font-medium text-slate-900">{f.activity_type}</p><p className="text-xs text-slate-500">{f.notes}</p></div>
                      <div className="text-right"><p className="text-xs text-slate-500">{fmtDate(f.due_date)}</p>
                        <Badge variant="outline" className={f.status === "completed" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-700 border-amber-200"}>{f.status}</Badge></div>
                    </div>
                  ))}
              </CardContent></Card>
            </TabsContent>

            <TabsContent value="comms">
              <Card className="border-slate-200 shadow-sm"><CardContent className="p-4 space-y-2">
                {data.communications.length === 0 ? <p className="text-sm text-slate-400 text-center py-6">No communication logged.</p> :
                  data.communications.map((m) => (
                    <div key={m._id} className="border border-slate-100 rounded-md p-3">
                      <div className="flex items-center justify-between"><p className="text-sm font-medium text-slate-900">{m.channel} · {m.direction}</p>
                        <span className="text-xs text-slate-400">{fmtDateTime(m.timestamp)}</span></div>
                      <p className="text-sm text-slate-500 mt-0.5">{m.message}</p>
                    </div>
                  ))}
              </CardContent></Card>
            </TabsContent>
            <TabsContent value="chat">
              <ChatHistory customerId={id} />
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
