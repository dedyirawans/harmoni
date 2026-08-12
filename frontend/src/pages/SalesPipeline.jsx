import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import { LEAD_STAGES, LEAD_LOST, STAGE_COLORS, STAGE_BAR, STAGE_LEFT, LEAD_SOURCES, fmtIDR, fmtDate } from "@/config/crm";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Loader2, User, Users, CalendarClock, GripVertical, Lock } from "lucide-react";
import { toast } from "sonner";

const ALL_STAGES = [...LEAD_STAGES, LEAD_LOST];

export default function SalesPipeline() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [leads, setLeads] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [open, setOpen] = useState(false);
  const [packages, setPackages] = useState([]);
  const [form, setForm] = useState({ customer_id: "", source: "WhatsApp", interested_package: "", package_id: "", package_type: "", package_name: "", destination_id: "", destination_name: "", destination: "", pax: 1, budget: 0, departure_date: "", status: "NEW", notes: "" });
  const [saving, setSaving] = useState(false);
  const [draggedId, setDraggedId] = useState(null);
  const [dropCol, setDropCol] = useState(null);

  const canMove = (lead) => user.role === "super_admin" || lead.sales_pic_id === user._id;

  const load = () => { setLeads(null); api.get("/leads").then((r) => setLeads(r.data)).catch(() => setLeads([])); };
  useEffect(() => { load(); api.get("/customers").then((r) => setCustomers(r.data)).catch(() => {}); api.get("/lead-packages").then((r) => setPackages(r.data || [])).catch(() => {}); }, []);

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  const create = async () => {
    if (!form.package_id) return toast.error("Interested Package wajib dipilih");
    setSaving(true);
    try {
      await api.post("/leads", { ...form, pax: Number(form.pax), budget: Number(form.budget) });
      toast.success("Lead created"); setOpen(false); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  const move = async (lead, stage) => {
    if (!canMove(lead)) { toast.error("Only the assigned sales or super admin can move this lead"); return; }
    if (lead.status === stage) return;
    try { await api.patch(`/leads/${lead._id}/stage`, { stage }); load(); toast.success(`Moved to ${stage}`); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  const onDrop = (stage) => {
    setDropCol(null);
    const lead = (leads || []).find((l) => l._id === draggedId);
    setDraggedId(null);
    if (lead) move(lead, stage);
  };

  const grouped = (stage) => (leads || []).filter((l) => l.status === stage);

  return (
    <div className="space-y-6" data-testid="pipeline-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">Sales Pipeline</h1>
          <p className="text-slate-500 mt-1">Drag a card between columns or use the dropdown. You can only move leads assigned to you.</p>
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
              <div className="space-y-2 col-span-2"><Label>Interested Package *</Label>
                <PackageCombobox packages={packages} value={form.package_id}
                  onSelect={(p) => setForm((f) => ({ ...f, package_id: p.id, package_type: p.product_type, package_name: p.package_name, destination_id: p.id, destination_name: p.destination || "", interested_package: p.package_name, destination: p.destination || "" }))} /></div>
              <div className="space-y-2 col-span-2 sm:col-span-1"><Label>Destination (auto)</Label><Input value={form.destination_name || ""} readOnly disabled placeholder="Otomatis dari package" data-testid="lead-destination-input" /></div>
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="kanban-board">
          {ALL_STAGES.map((stage) => (
            <div key={stage}
              onDragOver={(e) => { if (draggedId) { e.preventDefault(); setDropCol(stage); } }}
              onDragLeave={() => setDropCol((c) => (c === stage ? null : c))}
              onDrop={(e) => { e.preventDefault(); onDrop(stage); }}
              className={`rounded-lg border bg-white overflow-hidden flex flex-col transition-colors duration-150 ${dropCol === stage ? "border-blue-500 ring-2 ring-blue-200" : "border-slate-200"}`}
              data-testid={`kanban-col-${stage}`}>
              <div className={`h-1.5 w-full ${STAGE_BAR[stage]}`} aria-hidden="true" />
              <div className={`flex items-center justify-between px-3 py-2 border-b ${STAGE_COLORS[stage]}`}>
                <span className="text-xs font-bold uppercase tracking-wide">{stage}</span>
                <Badge variant="outline" className="text-[10px] bg-white/70 border-transparent">{grouped(stage).length}</Badge>
              </div>
              <div className="space-y-3 min-h-[120px] p-2 flex-1">
                {grouped(stage).map((l) => {
                  const movable = canMove(l);
                  return (
                  <Card key={l._id}
                    draggable={movable}
                    onDragStart={() => movable && setDraggedId(l._id)}
                    onDragEnd={() => { setDraggedId(null); setDropCol(null); }}
                    className={`border-slate-200 border-l-4 ${STAGE_LEFT[stage]} shadow-sm hover:shadow-md transition-shadow duration-200 ${movable ? "cursor-grab active:cursor-grabbing" : ""} ${draggedId === l._id ? "opacity-50" : ""}`}
                    data-testid={`lead-card-${l._id}`}>
                    <CardContent className="p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <button onClick={() => l.customer_id && navigate(`/crm/${l.customer_id}`)} className="text-sm font-semibold text-slate-900 hover:text-blue-700 text-left flex items-center gap-1">
                          {movable ? <GripVertical className="h-3 w-3 text-slate-300" aria-hidden="true" /> : <Lock className="h-3 w-3 text-slate-300" aria-hidden="true" />}
                          {l.customer_name || "No customer"}
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
                        <Select value={l.status} onValueChange={(v) => move(l, v)} disabled={!movable}>
                          <SelectTrigger className="h-7 w-28 text-xs" data-testid={`move-stage-${l._id}`}><SelectValue /></SelectTrigger>
                          <SelectContent className="bg-white">{ALL_STAGES.map((s) => <SelectItem key={s} value={s} className="text-xs">{s}</SelectItem>)}</SelectContent>
                        </Select>
                      </div>
                    </CardContent>
                  </Card>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PackageCombobox({ packages, value, onSelect }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const sel = packages.find((p) => p.id === value);
  const s = (q || "").toLowerCase();
  const filtered = packages.filter((p) => !s || ["package_name", "package_code", "product_type", "destination"].some((k) => (p[k] || "").toLowerCase().includes(s)));
  return (
    <div className="relative">
      <Input placeholder="Cari nama / kode / tipe / destinasi..."
        value={open ? q : (sel ? `${sel.package_name} (${sel.package_code})` : q)}
        onChange={(e) => { setQ(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        data-testid="lead-package-input" />
      {open && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-64 overflow-y-auto" data-testid="lead-package-dropdown">
          {filtered.length === 0 ? <div className="px-3 py-2 text-sm text-slate-400">Tidak ada package ACTIVE.</div> :
            filtered.map((p) => (
              <button key={p.id} type="button" onClick={() => { onSelect(p); setOpen(false); setQ(""); }}
                className="w-full text-left px-3 py-2 hover:bg-blue-50 border-b border-slate-50" data-testid={`lead-package-option-${p.id}`}>
                <div className="flex justify-between gap-2"><span className="font-medium text-sm">{p.package_name}</span><span className="text-xs text-slate-400">{p.package_code}</span></div>
                <div className="text-xs text-slate-500">{p.product_type} · {p.destination || "-"} · {p.duration || "-"} · {p.departure_date || "TBA"} · Rp {(p.selling_price || 0).toLocaleString("id-ID")} · Seat {p.available_seat}</div>
              </button>
            ))}
        </div>
      )}
    </div>
  );
}
