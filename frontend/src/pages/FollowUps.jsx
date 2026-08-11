import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import { FOLLOWUP_ACTIVITIES, fmtDate } from "@/config/crm";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Loader2, CheckCircle2, CalendarClock } from "lucide-react";
import { toast } from "sonner";

const SCOPES = [["today", "Today"], ["overdue", "Overdue"], ["upcoming", "Upcoming"], ["completed", "Completed"]];

export default function FollowUps() {
  const navigate = useNavigate();
  const [scope, setScope] = useState("today");
  const [rows, setRows] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ customer_id: "", activity_type: "Call", due_date: "", notes: "" });
  const [saving, setSaving] = useState(false);

  const load = () => { setRows(null); api.get("/follow-ups", { params: { scope } }).then((r) => setRows(r.data)).catch(() => setRows([])); };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [scope]);
  useEffect(() => { api.get("/customers").then((r) => setCustomers(r.data)).catch(() => {}); }, []);

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  const create = async () => {
    if (!form.due_date) return toast.error("Due date is required");
    setSaving(true);
    try { await api.post("/follow-ups", form); toast.success("Follow up scheduled"); setOpen(false); setForm({ customer_id: "", activity_type: "Call", due_date: "", notes: "" }); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  const complete = async (f) => {
    try { await api.patch(`/follow-ups/${f._id}/complete`); toast.success("Marked complete"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <div className="space-y-6" data-testid="followups-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">Follow Ups</h1>
          <p className="text-slate-500 mt-1">Stay on top of every customer touchpoint.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-blue-600 hover:bg-blue-700" data-testid="add-followup-button"><Plus className="h-4 w-4 mr-2" aria-hidden="true" />New Follow Up</Button>
          </DialogTrigger>
          <DialogContent className="bg-white" data-testid="followup-dialog">
            <DialogHeader><DialogTitle className="font-display">Schedule Follow Up</DialogTitle><DialogDescription>Add a task tied to a customer.</DialogDescription></DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-2"><Label>Customer</Label>
                <Select value={form.customer_id} onValueChange={set("customer_id")}><SelectTrigger data-testid="fu-customer-select"><SelectValue placeholder="Select customer" /></SelectTrigger>
                  <SelectContent className="bg-white">{customers.map((c) => <SelectItem key={c._id} value={c._id}>{c.full_name}</SelectItem>)}</SelectContent></Select></div>
              <div className="space-y-2"><Label>Activity</Label>
                <Select value={form.activity_type} onValueChange={set("activity_type")}><SelectTrigger data-testid="fu-activity-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-white">{FOLLOWUP_ACTIVITIES.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}</SelectContent></Select></div>
              <div className="space-y-2"><Label>Due date</Label><Input type="date" value={form.due_date} onChange={(e) => set("due_date")(e.target.value)} data-testid="fu-date-input" /></div>
              <div className="space-y-2"><Label>Notes</Label><Textarea value={form.notes} onChange={(e) => set("notes")(e.target.value)} /></div>
            </div>
            <DialogFooter><Button onClick={create} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="fu-save-button">{saving ? "Saving..." : "Schedule"}</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Tabs value={scope} onValueChange={setScope}>
        <TabsList data-testid="followup-tabs">
          {SCOPES.map(([k, l]) => <TabsTrigger key={k} value={k} data-testid={`fu-tab-${k}`}>{l}</TabsTrigger>)}
        </TabsList>
      </Tabs>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-4 space-y-2">
          {rows === null ? <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
            : rows.length === 0 ? <p className="text-sm text-slate-400 text-center py-8">Nothing here.</p>
            : rows.map((f) => (
              <div key={f._id} className="flex items-center justify-between border border-slate-100 rounded-md p-3 hover:bg-slate-50" data-testid={`followup-row-${f._id}`}>
                <div className="flex items-center gap-3">
                  <div className="h-9 w-9 rounded-md bg-blue-50 flex items-center justify-center"><CalendarClock className="h-4 w-4 text-blue-600" aria-hidden="true" /></div>
                  <div>
                    <button onClick={() => f.customer_id && navigate(`/crm/${f.customer_id}`)} className="font-medium text-slate-900 hover:text-blue-700">{f.customer_name || "—"}</button>
                    <p className="text-xs text-slate-500">{f.activity_type} · {f.notes || "no notes"}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right"><p className="text-xs text-slate-500">Due {fmtDate(f.due_date)}</p>
                    <Badge variant="outline" className={f.status === "completed" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-amber-50 text-amber-700 border-amber-200"}>{f.status}</Badge></div>
                  {f.status !== "completed" && (
                    <Button size="sm" variant="outline" onClick={() => complete(f)} data-testid={`complete-${f._id}`}><CheckCircle2 className="h-4 w-4 mr-1" aria-hidden="true" />Done</Button>
                  )}
                </div>
              </div>
            ))}
        </CardContent>
      </Card>
    </div>
  );
}
