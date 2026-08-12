import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";
import { CheckSquare, Plus, CalendarClock, Loader2 } from "lucide-react";
import ExpiringDocsWidget from "@/components/ExpiringDocsWidget";

const STATUSES = ["TODO", "IN_PROGRESS", "COMPLETED", "CANCELLED"];
const PRIORITIES = ["LOW", "MEDIUM", "HIGH", "URGENT"];
const PRIO_COLOR = { LOW: "bg-slate-100 text-slate-600", MEDIUM: "bg-blue-50 text-blue-700 border-blue-200", HIGH: "bg-amber-50 text-amber-700 border-amber-200", URGENT: "bg-red-50 text-red-700 border-red-200" };
const ST_COLOR = { TODO: "bg-slate-100 text-slate-700", IN_PROGRESS: "bg-blue-50 text-blue-700 border-blue-200", COMPLETED: "bg-emerald-50 text-emerald-700 border-emerald-200", CANCELLED: "bg-slate-100 text-slate-400" };
const REMINDERS = [["today", "Today"], ["tomorrow", "Tomorrow"], ["3days", "3 Days"], ["7days", "7 Days"], ["custom", "Custom"]];

const dateFromPreset = (p, custom) => {
  const d = new Date();
  if (p === "tomorrow") d.setDate(d.getDate() + 1);
  else if (p === "3days") d.setDate(d.getDate() + 3);
  else if (p === "7days") d.setDate(d.getDate() + 7);
  else if (p === "custom") return custom || d.toISOString().slice(0, 10);
  return d.toISOString().slice(0, 10);
};

export default function Tasks() {
  const { user } = useAuth();
  const [stats, setStats] = useState({ due_today: 0, overdue: 0, upcoming: 0, completed: 0 });
  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState("all");
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    const params = filter === "all" ? {} : { scope: filter };
    Promise.all([
      api.get("/tasks", { params }),
      api.get("/tasks/stats"),
    ]).then(([t, s]) => { setTasks(t.data || []); setStats(s.data || {}); }).finally(() => setLoading(false));
  }, [filter]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/customers").then((r) => setCustomers(r.data || [])).catch(() => {}); }, []);

  const setStatus = async (id, status) => {
    await api.patch(`/tasks/${id}`, { status });
    toast.success("Task updated");
    load();
  };

  const cards = [
    ["Due Today", stats.due_today, "due_today", "text-blue-600"],
    ["Overdue", stats.overdue, "overdue", "text-red-600"],
    ["Upcoming", stats.upcoming, "upcoming", "text-amber-600"],
    ["Completed", stats.completed, "completed", "text-emerald-600"],
  ];

  return (
    <div className="space-y-5" data-testid="tasks-page">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-xl bg-slate-900 flex items-center justify-center"><CheckSquare className="h-6 w-6 text-white" /></div>
          <div><h1 className="font-display text-3xl font-bold text-slate-900">My Tasks</h1>
            <p className="text-slate-500 mt-0.5">Task, follow-up &amp; reminder untuk {user.name}.</p></div>
        </div>
        <div className="flex gap-2">
          <FollowUpDialog customers={customers} onDone={load} />
          <TaskDialog customers={customers} onDone={load} />
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="tasks-stats">
        {cards.map(([l, v, key, color]) => (
          <button key={key} onClick={() => setFilter(key)} data-testid={`task-stat-${key}`}
            className={`text-left rounded-xl border bg-white p-4 shadow-sm transition-all ${filter === key ? "border-slate-900 ring-1 ring-slate-900" : "border-slate-200 hover:border-slate-300"}`}>
            <p className="text-xs uppercase tracking-wide font-semibold text-slate-400">{l}</p>
            <p className={`font-display text-3xl font-bold mt-1 ${color}`}>{v}</p>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-1.5" data-testid="tasks-filters">
        {[["all", "All"], ...STATUSES.map((s) => [s, s.replace("_", " ")])].map(([v, l]) => (
          <button key={v} onClick={() => setFilter(v)} data-testid={`task-filter-${v}`}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${filter === v ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"}`}>{l}</button>
        ))}
      </div>

      <Card className="border-slate-200 shadow-sm"><CardContent className="p-0">
        {loading ? <div className="p-10 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
          : tasks.length === 0 ? <p className="p-10 text-center text-slate-400 text-sm">Tidak ada task.</p> : (
            <div className="divide-y divide-slate-100" data-testid="tasks-list">
              {tasks.map((t) => (
                <div key={t.id || t._id} className="flex items-center gap-3 px-4 py-3" data-testid={`task-row-${t.id || t._id}`}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-medium text-slate-900 truncate">{t.task_name}</p>
                      <Badge variant="outline" className={PRIO_COLOR[t.priority] || ""}>{t.priority}</Badge>
                      {t.auto && <Badge className="bg-purple-100 text-purple-700 border-purple-200 text-[10px]">AUTO</Badge>}
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-2 flex-wrap">
                      <span className="flex items-center gap-1"><CalendarClock className="h-3 w-3" /> {(t.due_date || "—").slice(0, 10)}</span>
                      {t.assigned_user_name && <span>• {t.assigned_user_name}</span>}
                      {t.notes && <span className="truncate">• {t.notes}</span>}
                    </p>
                  </div>
                  <Badge variant="outline" className={ST_COLOR[t.status] || ""}>{(t.status || "").replace("_", " ")}</Badge>
                  <Select value={t.status} onValueChange={(v) => setStatus(t.id || t._id, v)}>
                    <SelectTrigger className="w-36 h-8" data-testid={`task-status-${t.id || t._id}`}><SelectValue /></SelectTrigger>
                    <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{s.replace("_", " ")}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              ))}
            </div>
          )}
      </CardContent></Card>

      <ExpiringDocsWidget within={90} />
    </div>
  );
}

function TaskDialog({ customers, onDone }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [f, setF] = useState({ task_name: "", priority: "MEDIUM", due_date: new Date().toISOString().slice(0, 10), customer_id: "", notes: "" });
  const submit = async () => {
    if (!f.task_name.trim()) { toast.error("Nama task wajib diisi"); return; }
    setSaving(true);
    try {
      const body = { ...f };
      if (body.customer_id === "none" || body.customer_id === "") delete body.customer_id;
      await api.post("/tasks", body);
      toast.success("Task dibuat");
      setOpen(false); setF({ task_name: "", priority: "MEDIUM", due_date: new Date().toISOString().slice(0, 10), customer_id: "", notes: "" });
      onDone();
    } catch { toast.error("Gagal membuat task"); } finally { setSaving(false); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button data-testid="new-task-btn"><Plus className="h-4 w-4 mr-1" />New Task</Button></DialogTrigger>
      <DialogContent className="bg-white">
        <DialogHeader><DialogTitle>New Task</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div><Label>Task Name</Label><Input value={f.task_name} onChange={(e) => setF({ ...f, task_name: e.target.value })} data-testid="task-name-input" /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Priority</Label>
              <Select value={f.priority} onValueChange={(v) => setF({ ...f, priority: v })}><SelectTrigger data-testid="task-priority-select"><SelectValue /></SelectTrigger>
                <SelectContent>{PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent></Select></div>
            <div><Label>Due Date</Label><Input type="date" value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} data-testid="task-due-input" /></div>
          </div>
          <div><Label>Related Customer (optional)</Label>
            <Select value={f.customer_id || "none"} onValueChange={(v) => setF({ ...f, customer_id: v })}><SelectTrigger data-testid="task-customer-select"><SelectValue placeholder="—" /></SelectTrigger>
              <SelectContent><SelectItem value="none">— None —</SelectItem>{customers.map((c) => <SelectItem key={c.id || c._id} value={c.id || c._id}>{c.full_name}</SelectItem>)}</SelectContent></Select></div>
          <div><Label>Notes</Label><Textarea rows={2} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} data-testid="task-notes-input" /></div>
        </div>
        <DialogFooter><Button onClick={submit} disabled={saving} data-testid="task-save-btn">{saving ? "Saving..." : "Create Task"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function FollowUpDialog({ customers, onDone }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [f, setF] = useState({ activity_type: "Call", reminder: "today", custom: "", customer_id: "", notes: "" });
  const submit = async () => {
    setSaving(true);
    try {
      const due_date = dateFromPreset(f.reminder, f.custom);
      const body = { activity_type: f.activity_type, due_date, notes: f.notes };
      if (f.customer_id && f.customer_id !== "none") body.customer_id = f.customer_id;
      await api.post("/follow-ups", body);
      toast.success("Follow up dibuat (task & notifikasi terkirim)");
      setOpen(false); setF({ activity_type: "Call", reminder: "today", custom: "", customer_id: "", notes: "" });
      onDone();
    } catch { toast.error("Gagal membuat follow up"); } finally { setSaving(false); }
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button variant="outline" data-testid="new-followup-btn"><CalendarClock className="h-4 w-4 mr-1" />New Follow Up</Button></DialogTrigger>
      <DialogContent className="bg-white">
        <DialogHeader><DialogTitle>New Follow Up</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div><Label>Type</Label>
            <Select value={f.activity_type} onValueChange={(v) => setF({ ...f, activity_type: v })}><SelectTrigger data-testid="fu-type-select"><SelectValue /></SelectTrigger>
              <SelectContent>{["Call", "WhatsApp", "Meeting", "Email", "Other"].map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent></Select></div>
          <div><Label>Reminder</Label>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {REMINDERS.map(([v, l]) => (
                <button key={v} type="button" onClick={() => setF({ ...f, reminder: v })} data-testid={`fu-reminder-${v}`}
                  className={`text-xs px-3 py-1.5 rounded-full border ${f.reminder === v ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 border-slate-200"}`}>{l}</button>
              ))}
            </div>
            {f.reminder === "custom" && <Input type="date" className="mt-2" value={f.custom} onChange={(e) => setF({ ...f, custom: e.target.value })} data-testid="fu-custom-date" />}
          </div>
          <div><Label>Related Customer (optional)</Label>
            <Select value={f.customer_id || "none"} onValueChange={(v) => setF({ ...f, customer_id: v })}><SelectTrigger data-testid="fu-customer-select"><SelectValue placeholder="—" /></SelectTrigger>
              <SelectContent><SelectItem value="none">— None —</SelectItem>{customers.map((c) => <SelectItem key={c.id || c._id} value={c.id || c._id}>{c.full_name}</SelectItem>)}</SelectContent></Select></div>
          <div><Label>Notes</Label><Textarea rows={2} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} data-testid="fu-notes-input" /></div>
        </div>
        <DialogFooter><Button onClick={submit} disabled={saving} data-testid="fu-save-btn">{saving ? "Saving..." : "Create Follow Up"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
