import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import { CUSTOMER_TYPES, LEAD_SOURCES, GENDERS, fmtDate } from "@/config/crm";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { UserPlus, Search, Loader2, Users2, Phone, Mail, Archive, RotateCcw, UserCog } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";

const EMPTY = {
  full_name: "", whatsapp: "", email: "", gender: "", date_of_birth: "", nik: "",
  passport_number: "", passport_expiry: "", address: "", city: "", country: "Indonesia",
  customer_type: "Prospect", customer_source: "WhatsApp", tags: "", notes: "",
};

export default function Customers() {
  const navigate = useNavigate();
  const { user: me } = useAuth();
  const isSA = me?.role === "super_admin";
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState("");
  const [type, setType] = useState("all");
  const [showArchived, setShowArchived] = useState(false);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [dupWarn, setDupWarn] = useState([]);
  const [selected, setSelected] = useState([]);
  const [bulkOpen, setBulkOpen] = useState(false);

  const load = () => {
    setRows(null);
    api.get("/customers", { params: { q: q || undefined, customer_type: type, include_archived: showArchived } })
      .then((r) => setRows(r.data)).catch(() => setRows([]));
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [type, showArchived]);

  useEffect(() => {
    if (!open) { setDupWarn([]); return; }
    const t = setTimeout(() => {
      const { whatsapp, email, passport_number } = form;
      if (!whatsapp?.trim() && !email?.trim() && !passport_number?.trim()) { setDupWarn([]); return; }
      api.get("/customers/check-duplicate", { params: { whatsapp: whatsapp || undefined, email: email || undefined, passport_number: passport_number || undefined } })
        .then((r) => setDupWarn(r.data?.duplicates || [])).catch(() => setDupWarn([]));
    }, 400);
    return () => clearTimeout(t);
    /* eslint-disable-next-line */
  }, [form.whatsapp, form.email, form.passport_number, open]);

  const archive = async (c) => {
    const reason = window.prompt(`Alasan mengarsipkan customer "${c.full_name}" (wajib):`, "");
    if (reason === null) return;
    if (!reason.trim()) return toast.error("Alasan wajib diisi");
    try { await api.delete(`/customers/${c._id}`, { params: { reason } }); toast.success("Customer diarsipkan"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const restore = async (c) => {
    try { await api.post(`/customers/${c._id}/restore`); toast.success("Customer dipulihkan"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  const toggleSel = (id) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  const toggleAll = () => setSelected((s) => (rows && s.length === rows.length) ? [] : (rows || []).map((c) => c._id));

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    if (!form.full_name.trim()) return toast.error("Full name is required");
    setSaving(true);
    try {
      const payload = { ...form, tags: form.tags ? form.tags.split(",").map((t) => t.trim()).filter(Boolean) : [] };
      await api.post("/customers", payload);
      toast.success("Customer created");
      setOpen(false); setForm(EMPTY); setDupWarn([]); load();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-6" data-testid="customers-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">Customers</h1>
          <p className="text-slate-500 mt-1">Your customer master — you only see customers assigned to you.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-blue-600 hover:bg-blue-700" data-testid="add-customer-button">
              <UserPlus className="h-4 w-4 mr-2" aria-hidden="true" /> Add Customer
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-white max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="customer-dialog">
            <DialogHeader>
              <DialogTitle className="font-display">New Customer</DialogTitle>
              <DialogDescription>Create a customer record assigned to you.</DialogDescription>
            </DialogHeader>
            <div className="grid grid-cols-2 gap-4 py-2">
              <Field label="Full Name *"><Input value={form.full_name} onChange={(e) => set("full_name")(e.target.value)} data-testid="customer-name-input" /></Field>
              <Field label="WhatsApp"><Input value={form.whatsapp} onChange={(e) => set("whatsapp")(e.target.value)} data-testid="customer-whatsapp-input" /></Field>
              <Field label="Email"><Input value={form.email} onChange={(e) => set("email")(e.target.value)} data-testid="customer-email-input" /></Field>
              <Field label="Gender">
                <Select value={form.gender} onValueChange={set("gender")}>
                  <SelectTrigger data-testid="customer-gender-select"><SelectValue placeholder="Select" /></SelectTrigger>
                  <SelectContent className="bg-white">{GENDERS.map((g) => <SelectItem key={g} value={g}>{g}</SelectItem>)}</SelectContent>
                </Select>
              </Field>
              <Field label="Date of Birth"><Input type="date" value={form.date_of_birth} onChange={(e) => set("date_of_birth")(e.target.value)} /></Field>
              <Field label="NIK"><Input value={form.nik} onChange={(e) => set("nik")(e.target.value)} /></Field>
              <Field label="Passport Number"><Input value={form.passport_number} onChange={(e) => set("passport_number")(e.target.value)} /></Field>
              <Field label="Passport Expiry"><Input type="date" value={form.passport_expiry} onChange={(e) => set("passport_expiry")(e.target.value)} /></Field>
              <Field label="City"><Input value={form.city} onChange={(e) => set("city")(e.target.value)} /></Field>
              <Field label="Country"><Input value={form.country} onChange={(e) => set("country")(e.target.value)} /></Field>
              <Field label="Customer Type">
                <Select value={form.customer_type} onValueChange={set("customer_type")}>
                  <SelectTrigger data-testid="customer-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-white">{CUSTOMER_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                </Select>
              </Field>
              <Field label="Customer Source">
                <Select value={form.customer_source} onValueChange={set("customer_source")}>
                  <SelectTrigger data-testid="customer-source-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-white">{LEAD_SOURCES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                </Select>
              </Field>
              <Field label="Address" full><Textarea value={form.address} onChange={(e) => set("address")(e.target.value)} /></Field>
              <Field label="Tags (comma separated)" full><Input value={form.tags} onChange={(e) => set("tags")(e.target.value)} placeholder="vip, hot-lead" /></Field>
              <Field label="Notes" full><Textarea value={form.notes} onChange={(e) => set("notes")(e.target.value)} /></Field>
            </div>
            {dupWarn.length > 0 && (
              <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm" data-testid="customer-dup-warning">
                <p className="font-medium text-amber-800">Peringatan — kemungkinan duplikat ({dupWarn.length}):</p>
                <ul className="mt-1 space-y-1">
                  {dupWarn.map((d) => (
                    <li key={d.id} className="text-amber-700 text-xs" data-testid={`dup-item-${d.id}`}>
                      {d.full_name} ({d.customer_code}) — cocok pada: {d.matched_fields.join(", ")}
                    </li>
                  ))}
                </ul>
                <p className="mt-1 text-[11px] text-amber-600">Anda tetap dapat melanjutkan pembuatan customer.</p>
              </div>
            )}
            <DialogFooter>
              <Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="customer-save-button">
                {saving ? "Saving..." : "Create customer"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <Input className="pl-9" placeholder="Search name, WhatsApp, email..." value={q}
            onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} data-testid="customer-search-input" />
        </div>
        <Select value={type} onValueChange={setType}>
          <SelectTrigger className="w-52" data-testid="customer-type-filter"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-white">
            <SelectItem value="all">All types</SelectItem>
            {CUSTOMER_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button variant="outline" onClick={load} data-testid="customer-search-button">Search</Button>
        {isSA && (
          <label className="flex items-center gap-2 text-sm text-slate-500">
            <Switch checked={showArchived} onCheckedChange={setShowArchived} data-testid="customers-show-archived" /> Show archived
          </label>
        )}
      </div>

      {isSA && selected.length > 0 && (
        <div className="flex items-center justify-between rounded-md border border-blue-200 bg-blue-50 px-4 py-2.5" data-testid="bulk-action-bar">
          <span className="text-sm font-medium text-blue-800">{selected.length} customer dipilih</span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => setSelected([])}>Batal</Button>
            <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={() => setBulkOpen(true)} data-testid="bulk-reassign-btn"><UserCog className="h-4 w-4 mr-1" />Pindah PIC</Button>
          </div>
        </div>
      )}

      <Card className="border-slate-200 shadow-sm overflow-hidden">
        {rows === null ? (
          <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
        ) : rows.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <Users2 className="h-8 w-8 mx-auto text-slate-300" aria-hidden="true" />
            <p className="mt-2">No customers yet. Add your first customer.</p>
          </div>
        ) : (
          <Table data-testid="customers-table">
            <TableHeader>
              <TableRow className="bg-slate-50">
                {isSA && <TableHead className="w-10"><Checkbox checked={rows.length > 0 && selected.length === rows.length} onCheckedChange={toggleAll} data-testid="select-all-customers" /></TableHead>}
                <TableHead>Code</TableHead><TableHead>Name</TableHead><TableHead>Contact</TableHead>
                <TableHead>Type</TableHead><TableHead>City</TableHead><TableHead>Created</TableHead>
                {isSA && <TableHead className="w-24 text-right">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((c) => (
                <TableRow key={c._id} className="hover:bg-slate-50 cursor-pointer" onClick={() => navigate(`/crm/${c._id}`)} data-testid={`customer-row-${c._id}`}>
                  {isSA && <TableCell onClick={(e) => e.stopPropagation()}><Checkbox checked={selected.includes(c._id)} onCheckedChange={() => toggleSel(c._id)} data-testid={`select-customer-${c._id}`} /></TableCell>}
                  <TableCell className="font-mono text-xs text-slate-500">{c.customer_code}</TableCell>
                  <TableCell><div className="font-medium text-slate-900 flex items-center gap-2">{c.full_name}{c.is_deleted && <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200 text-[10px]">ARCHIVED</Badge>}</div>
                    <div className="flex gap-1 mt-1">{(c.tags || []).map((t) => <Badge key={t} variant="outline" className="text-[10px] bg-blue-50 text-blue-700 border-blue-200">{t}</Badge>)}</div>
                  </TableCell>
                  <TableCell className="text-slate-600 text-sm">
                    {c.whatsapp && <div className="flex items-center gap-1"><Phone className="h-3 w-3" aria-hidden="true" />{c.whatsapp}</div>}
                    {c.email && <div className="flex items-center gap-1 text-slate-400"><Mail className="h-3 w-3" aria-hidden="true" />{c.email}</div>}
                  </TableCell>
                  <TableCell><Badge variant="outline" className="bg-slate-100 text-slate-700">{c.customer_type}</Badge></TableCell>
                  <TableCell className="text-slate-600">{c.city || "—"}</TableCell>
                  <TableCell className="text-slate-500 text-sm">{fmtDate(c.created_at)}</TableCell>
                  {isSA && (
                    <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                      {c.is_deleted ? (
                        <Button size="sm" variant="ghost" className="text-emerald-600" onClick={() => restore(c)} data-testid={`restore-customer-${c._id}`}><RotateCcw className="h-4 w-4" /></Button>
                      ) : (
                        <Button size="sm" variant="ghost" className="text-red-600" onClick={() => archive(c)} data-testid={`archive-customer-${c._id}`}><Archive className="h-4 w-4" /></Button>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      {isSA && <BulkPicDialog open={bulkOpen} onOpenChange={setBulkOpen} customerIds={selected} onDone={() => { setSelected([]); load(); }} />}
    </div>
  );
}

function Field({ label, children, full }) {
  return (
    <div className={`space-y-2 ${full ? "col-span-2" : "col-span-2 sm:col-span-1"}`}>
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function BulkPicDialog({ open, onOpenChange, customerIds, onDone }) {
  const [users, setUsers] = useState([]);
  const [sel, setSel] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (open && users.length === 0) {
      api.get("/users").then((r) => setUsers((r.data || []).filter((u) => ["sales", "super_admin"].includes(u.role) && u.status !== "ARCHIVED"))).catch(() => {});
    }
  }, [open, users.length]);
  const save = async () => {
    if (!sel) return toast.error("Pilih PIC sales tujuan");
    setSaving(true);
    try {
      const r = await api.post("/customers/bulk-reassign-pic", { customer_ids: customerIds, sales_pic_id: sel });
      toast.success(`${r.data.reassigned} customer dipindahkan ke ${r.data.sales_pic_name}`);
      onOpenChange(false); onDone();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white" data-testid="bulk-pic-dialog">
        <DialogHeader><DialogTitle className="font-display">Pindah PIC Sales</DialogTitle>
          <DialogDescription>Pindahkan {customerIds.length} customer terpilih ke sales lain (mis. saat sales resign).</DialogDescription></DialogHeader>
        <div className="space-y-2 py-2">
          <Label className="text-xs">PIC Sales Tujuan</Label>
          <Select value={sel} onValueChange={setSel}>
            <SelectTrigger data-testid="bulk-pic-select"><SelectValue placeholder="Pilih sales" /></SelectTrigger>
            <SelectContent className="bg-white">
              {users.map((u) => <SelectItem key={u._id} value={u._id} data-testid={`bulk-pic-option-${u._id}`}>{u.name} ({u.role})</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Batal</Button>
          <Button className="bg-blue-600 hover:bg-blue-700" onClick={save} disabled={saving} data-testid="bulk-pic-save">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : `Pindahkan ${customerIds.length} customer`}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
