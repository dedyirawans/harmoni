import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import { LEAD_STAGES, LEAD_LOST, STAGE_COLORS, LEAD_SOURCES, fmtIDR, fmtDate } from "@/config/crm";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Loader2, User, Users, CalendarClock } from "lucide-react";
import { toast } from "sonner";

const ALL_STAGES = [...LEAD_STAGES, LEAD_LOST];

export default function SalesPipeline() {
  const navigate = useNavigate();
  const [leads, setLeads] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ customer_id: "", source: "WhatsApp", interested_package: "", destination: "", pax: 1, budget: 0, departure_date: "", status: "NEW", notes: "" });
  const [saving, setSaving] = useState(false);

  const load = () => { setLeads(null); api.get("/leads").then((r) => setLeads(r.data)).catch(() => setLeads([])); };
  useEffect(() => { load(); api.get("/customers").then((r) => setCustomers(r.data)).catch(() => {}); }, []);

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  const create = async () => {
    if (!form.interested_package.trim()) return toast.error("Package/interest is required");
    setSaving(true);
    try {
      await api.post("/leads", { ...form, pax: Number(form.pax), budget: Number(form.budget) });
      toast.success("Lead created"); setOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  const move = async (lead, stage) => {
    try { await api.patch(`/leads/${lead._id}/stage`, { stage }); load(); toast.success(`Moved to ${stage}`); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const grouped = (stage) => (leads || []).filter((l) => l.status === stage);

  return (
    <div className="space-y-6" data-testid="pipeline-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">Sales Pipeline</h1>
          <p className="text-slate-500 mt-1">Kanban view of your leads. Move cards through the pipeline.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-blue-600 hover:bg-blue-700" data-testid="add-lead-button"><Plus className="h-4 w-4 mr-2" aria-hidden="true" />New Lead</Button>
          </DialogTrigger>
          <DialogContent className="bg-white max-w-lg" data-testid="lead-dialog">
            <DialogHeader><DialogTitle className="font-display">New Lead</DialogTitle><DialogDescription>Add a lead to your pipeline.</DialogDescription></DialogHeader>
            <div className="grid grid-cols-2 gap-4 py-2">
              <div className="space-y-2 col-span-2"><Label>Customer</Label>
                <Select value={form.customer_id} onValueChange={set("customer_id")}>
                  <SelectTrigger data-testid="lead-customer-select"><SelectValue placeholder="Select customer (optional)" /></SelectTrigger>
                  <SelectContent className="bg-white">{customers.map((c) => <SelectItem key={c._id} value={c._id}>{c.full_name}</SelectItem>)}</SelectContent>
                </Select></div>
              <div className="space-y-2 col-span-2"><Label>Interested Package *</Label><Input value={form.interested_package} onChange={(e) => set("interested_package")(e.target.value)} data-testid="lead-package-input" /></div>
              <div className="space-y-2 col-span-2 sm:col-span-1"><Label>Destination</Label><Input value={form.destination} onChange={(e) => set("destination")(e.target.value)} /></div>
              <div className="space-y-2 col-span-2 sm:col-span-1"><Label>Source</Label>
                <Select value={form.source} onValueChange={set("source")}><SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-white">{LEAD_SOURCES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
              <div className="space-y-2 col-span-2 sm:col-span-1"><Label>Pax</Label><Input type="number" value={form.pax} onChange={(e) => set("pax")(e.target.value)} data-testid="lead-pax-input" /></div>
              <div className="space-y-2 col-span-2 sm:col-span-1"><Label>Budget (Rp)</Label><Input type="number" value={form.budget} onChange={(e) => set("budget")(e.target.value)} data-testid="lead-budget-input" /></div>
              <div className="space-y-2 col-span-2 sm:col-span-1"><Label>Departure Date</Label><Input type="date" value={form.departure_date} onChange={(e) => set("departure_date")(e.target.value)} /></div>
              <div className="space-y-2 col-span-2 sm:col-span-1"><Label>Stage</Label>
                <Select value={form.status} onValueChange={set("status")}><SelectTrigger data-testid="lead-stage-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-white">{ALL_STAGES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></div>
              <div className="space-y-2 col-span-2"><Label>Notes</Label><Textarea value={form.notes} onChange={(e) => set("notes")(e.target.value)} /></div>
            </div>
            <DialogFooter><Button onClick={create} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="lead-save-button">{saving ? "Saving..." : "Create lead"}</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {leads === null ? (
        <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-4" data-testid="kanban-board">
          {ALL_STAGES.map((stage) => (
            <div key={stage} className="w-72 shrink-0" data-testid={`kanban-col-${stage}`}>
              <div className="flex items-center justify-between px-1 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-600">{stage}</span>
                <Badge variant="outline" className="text-[10px] bg-slate-100 text-slate-600">{grouped(stage).length}</Badge>
              </div>
              <div className="space-y-3 min-h-[100px] bg-slate-100/50 rounded-lg p-2">
                {grouped(stage).map((l) => (
                  <Card key={l._id} className="border-slate-200 shadow-sm hover:shadow-md transition-shadow duration-200" data-testid={`lead-card-${l._id}`}>
                    <CardContent className="p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <button onClick={() => l.customer_id && navigate(`/crm/${l.customer_id}`)} className="text-sm font-semibold text-slate-900 hover:text-blue-700 text-left flex items-center gap-1">
                          <User className="h-3 w-3" aria-hidden="true" />{l.customer_name || "No customer"}
                        </button>
                        <span className="text-[10px] font-mono text-slate-400">{l.lead_code}</span>
                      </div>
                      <p className="text-sm text-slate-700">{l.interested_package}</p>
                      <div className="flex items-center gap-3 text-xs text-slate-500">
                        <span className="flex items-center gap-1"><Users className="h-3 w-3" aria-hidden="true" />{l.pax} pax</span>
                        <span className="font-medium text-slate-700">{fmtIDR(l.budget)}</span>
                      </div>
                      {l.departure_date && <p className="text-xs text-slate-400 flex items-center gap-1"><CalendarClock className="h-3 w-3" aria-hidden="true" />Dep {fmtDate(l.departure_date)}</p>}
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-[11px] text-slate-400">{l.sales_pic_name}</span>
                        <Select value={l.status} onValueChange={(v) => move(l, v)}>
                          <SelectTrigger className="h-7 w-28 text-xs" data-testid={`move-stage-${l._id}`}><SelectValue /></SelectTrigger>
                          <SelectContent className="bg-white">{ALL_STAGES.map((s) => <SelectItem key={s} value={s} className="text-xs">{s}</SelectItem>)}</SelectContent>
                        </Select>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
