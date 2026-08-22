import { useEffect, useState, useRef } from "react";
import { useAuth } from "@/context/AuthContext";
import { useBranding } from "@/context/BrandingContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ROLE_LABELS } from "@/config/nav";
import { toast } from "sonner";
import { Loader2, Trash2, Plus } from "lucide-react";

const COMPANY_FIELDS = [
  ["company_name", "Company Name"], ["email", "Email"], ["phone", "Phone"],
  ["website", "Website"], ["npwp", "NPWP"], ["nib", "NIB"],
  ["address", "Address"], ["bank_account", "Bank Account"],
];

export default function Settings() {
  const { user } = useAuth();
  const { refreshBranding } = useBranding();
  const isAdmin = user.role === "super_admin";
  const canManage = (user.permissions || []).includes("settings.manage");

  const [company, setCompany] = useState(null);
  const [system, setSystem] = useState(null);
  const [savingC, setSavingC] = useState(false);
  const [savingS, setSavingS] = useState(false);

  useEffect(() => {
    api.get("/company-settings").then((r) => setCompany(r.data || {})).catch(() => setCompany({}));
    api.get("/system-settings").then((r) => setSystem(r.data?.settings || {})).catch(() => setSystem({}));
  }, []);

  const saveCompany = async () => {
    setSavingC(true);
    try { await api.put("/company-settings", company); toast.success("Company settings saved"); refreshBranding(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSavingC(false); }
  };

  const saveSystem = async () => {
    setSavingS(true);
    try { await api.put("/system-settings", { settings: system }); toast.success("Global settings saved"); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSavingS(false); }
  };

  if (company === null || system === null)
    return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;

  return (
    <div className="space-y-6" data-testid="settings-page">
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900">Settings</h1>
        <p className="text-slate-500 mt-1">Company profile, global configuration, and role permissions.</p>
      </div>

      <Tabs defaultValue="company">
        <TabsList data-testid="settings-tabs">
          <TabsTrigger value="company" data-testid="tab-company">Company</TabsTrigger>
          <TabsTrigger value="global" data-testid="tab-global">Global</TabsTrigger>
          <TabsTrigger value="login" data-testid="tab-login">Login Page</TabsTrigger>
          {isAdmin && <TabsTrigger value="doctpl" data-testid="tab-doctpl">Template Dokumen</TabsTrigger>}
          {isAdmin && <TabsTrigger value="roles" data-testid="tab-roles">Roles & Permissions</TabsTrigger>}
        </TabsList>

        {isAdmin && <TabsContent value="doctpl"><DocTemplateTab canManage={canManage} /></TabsContent>}

        {/* Company */}
        <TabsContent value="company">
          <Card className="border-slate-200 shadow-sm">
            <CardHeader><CardTitle className="font-display">Company Profile</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {COMPANY_FIELDS.map(([k, label]) => (
                <div key={k} className={`space-y-2 ${k === "address" || k === "bank_account" ? "sm:col-span-2" : ""}`}>
                  <Label>{label}</Label>
                  <Input value={company[k] || ""} disabled={!canManage}
                    onChange={(e) => setCompany({ ...company, [k]: e.target.value })}
                    data-testid={`company-${k}-input`} />
                </div>
              ))}
              <div className="space-y-2 sm:col-span-2">
                <Label>Company Logo</Label>
                <p className="text-xs text-slate-400">Shown in the sidebar and login screen. The Company Name is also used as the browser tab title.</p>
                <div className="flex items-center gap-4 pt-1">
                  {company.logo ? (
                    <img src={company.logo} alt="Logo" className="h-14 w-14 rounded-md object-cover border border-slate-200" />
                  ) : (
                    <div className="h-14 w-14 rounded-md bg-blue-600 flex items-center justify-center text-white text-[10px] font-semibold">LOGO</div>
                  )}
                  <div className="flex-1 space-y-2">
                    <Input value={company.logo || ""} disabled={!canManage}
                      onChange={(e) => setCompany({ ...company, logo: e.target.value })}
                      placeholder="Logo image URL, or upload below" data-testid="company-logo-input" />
                    {canManage && (
                      <Input type="file" accept="image/*" data-testid="company-logo-upload"
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (!f) return;
                          const reader = new FileReader();
                          reader.onload = () => setCompany({ ...company, logo: reader.result });
                          reader.readAsDataURL(f);
                        }} />
                    )}
                  </div>
                </div>
              </div>
              {canManage && (
                <div className="sm:col-span-2">
                  <Button onClick={saveCompany} disabled={savingC} className="bg-blue-600 hover:bg-blue-700" data-testid="save-company-button">
                    {savingC ? "Saving..." : "Save company settings"}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Global */}
        <TabsContent value="global">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="border-slate-200 shadow-sm">
              <CardHeader><CardTitle className="font-display text-lg">Tax & Commission</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>PPN (%)</Label>
                  <Input type="number" value={system.tax?.ppn_percent ?? ""} disabled={!canManage}
                    onChange={(e) => setSystem({ ...system, tax: { ...system.tax, ppn_percent: Number(e.target.value) } })}
                    data-testid="ppn-input" />
                </div>
                <div className="space-y-2">
                  <Label>Default Commission (%)</Label>
                  <Input type="number" value={system.commission?.default_percent ?? ""} disabled={!canManage}
                    onChange={(e) => setSystem({ ...system, commission: { ...system.commission, default_percent: Number(e.target.value) } })}
                    data-testid="commission-input" />
                </div>
              </CardContent>
            </Card>

            <Card className="border-slate-200 shadow-sm">
              <CardHeader><CardTitle className="font-display text-lg">Pajak per Kategori Produk</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <p className="text-xs text-slate-500">Persentase pajak diterapkan otomatis: Tour dari harga jual, Umroh Plus dari porsi harga tour, Umroh tidak dikenakan pajak.</p>
                <div className="space-y-2">
                  <Label>Umroh (%)</Label>
                  <Input type="number" value={system.category_tax?.umroh_percent ?? 0} disabled={!canManage}
                    onChange={(e) => setSystem({ ...system, category_tax: { ...system.category_tax, umroh_percent: Number(e.target.value) } })}
                    data-testid="tax-umroh-input" />
                </div>
                <div className="space-y-2">
                  <Label>Paket Tour (%)</Label>
                  <Input type="number" value={system.category_tax?.tour_percent ?? 0} disabled={!canManage}
                    onChange={(e) => setSystem({ ...system, category_tax: { ...system.category_tax, tour_percent: Number(e.target.value) } })}
                    data-testid="tax-tour-input" />
                </div>
                <div className="space-y-2">
                  <Label>Umroh Plus (%)</Label>
                  <Input type="number" value={system.category_tax?.umroh_plus_percent ?? 0} disabled={!canManage}
                    onChange={(e) => setSystem({ ...system, category_tax: { ...system.category_tax, umroh_plus_percent: Number(e.target.value) } })}
                    data-testid="tax-umroh-plus-input" />
                </div>
              </CardContent>
            </Card>

            <Card className="border-slate-200 shadow-sm">
              <CardHeader><CardTitle className="font-display text-lg">Notifications</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label>Email notifications</Label>
                  <Switch checked={!!system.notification?.email_enabled} disabled={!canManage}
                    onCheckedChange={(v) => setSystem({ ...system, notification: { ...system.notification, email_enabled: v } })} data-testid="email-notif-switch" />
                </div>
              </CardContent>
            </Card>

            <Card className="border-slate-200 shadow-sm lg:col-span-2">
              <CardHeader><CardTitle className="font-display text-lg">Reference Lists</CardTitle></CardHeader>
              <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {[["payment_methods", "Payment Methods"], ["lead_sources", "Lead Sources"], ["booking_sources", "Booking Sources"], ["customer_categories", "Customer Categories"]].map(([k, label]) => (
                  <div key={k}>
                    <p className="text-xs uppercase tracking-wide font-semibold text-slate-500 mb-2">{label}</p>
                    <div className="flex flex-wrap gap-2">
                      {(system[k] || []).map((v) => <Badge key={v} variant="outline" className="bg-slate-50 text-slate-700">{v}</Badge>)}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            {canManage && (
              <div className="lg:col-span-2">
                <Button onClick={saveSystem} disabled={savingS} className="bg-blue-600 hover:bg-blue-700" data-testid="save-global-button">
                  {savingS ? "Saving..." : "Save global settings"}
                </Button>
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="login">
          <Card className="border-slate-200 shadow-sm">
            <CardHeader><CardTitle className="font-display">Login Page Appearance</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Heading</Label>
                <Input value={system.login_page?.heading || ""} disabled={!canManage}
                  onChange={(e) => setSystem({ ...system, login_page: { ...system.login_page, heading: e.target.value } })}
                  data-testid="login-heading-input" />
              </div>
              <div className="space-y-2">
                <Label>Subheading</Label>
                <Textarea value={system.login_page?.subheading || ""} disabled={!canManage}
                  onChange={(e) => setSystem({ ...system, login_page: { ...system.login_page, subheading: e.target.value } })}
                  data-testid="login-subheading-input" />
              </div>
              <div className="space-y-2">
                <Label>Background Image URL</Label>
                <Input value={system.login_page?.background_image || ""} disabled={!canManage}
                  onChange={(e) => setSystem({ ...system, login_page: { ...system.login_page, background_image: e.target.value } })}
                  placeholder="https://... or upload below" data-testid="login-bg-url-input" />
              </div>
              {canManage && (
                <div className="space-y-2">
                  <Label>Or upload an image</Label>
                  <Input type="file" accept="image/*" data-testid="login-bg-upload"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (!f) return;
                      const reader = new FileReader();
                      reader.onload = () => setSystem({ ...system, login_page: { ...system.login_page, background_image: reader.result } });
                      reader.readAsDataURL(f);
                    }} />
                </div>
              )}
              {system.login_page?.background_image && (
                <div className="rounded-md overflow-hidden border border-slate-200 max-w-sm">
                  <img src={system.login_page.background_image} alt="Login background preview" className="w-full h-40 object-cover" />
                </div>
              )}
              {canManage && (
                <Button onClick={saveSystem} disabled={savingS} className="bg-blue-600 hover:bg-blue-700" data-testid="save-login-page-button">
                  {savingS ? "Saving..." : "Save login page"}
                </Button>
              )}
            </CardContent>
          </Card>
        </TabsContent>


        {isAdmin && (
          <TabsContent value="roles"><RolePermissions /></TabsContent>
        )}
      </Tabs>
    </div>
  );
}

function RolePermissions() {
  const [all, setAll] = useState([]);
  const [rp, setRp] = useState(null);
  const [saving, setSaving] = useState("");

  useEffect(() => {
    Promise.all([api.get("/permissions"), api.get("/role-permissions")])
      .then(([p, r]) => { setAll(p.data); setRp(r.data); })
      .catch(() => setRp({}));
  }, []);

  const toggle = (role, perm) => {
    const cur = new Set(rp[role]);
    cur.has(perm) ? cur.delete(perm) : cur.add(perm);
    setRp({ ...rp, [role]: Array.from(cur) });
  };

  const save = async (role) => {
    setSaving(role);
    try { await api.put(`/role-permissions/${role}`, { permissions: rp[role] }); toast.success(`${ROLE_LABELS[role]} permissions saved`); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(""); }
  };

  if (rp === null) return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="role-permissions">
      {["sales", "accounting"].map((role) => (
        <Card key={role} className="border-slate-200 shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="font-display text-lg">{ROLE_LABELS[role]}</CardTitle>
            <Button size="sm" onClick={() => save(role)} disabled={saving === role} className="bg-blue-600 hover:bg-blue-700" data-testid={`save-perms-${role}`}>
              {saving === role ? "Saving..." : "Save"}
            </Button>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-2 max-h-96 overflow-y-auto">
            {all.map((perm) => (
              <label key={perm} className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                <Checkbox checked={(rp[role] || []).includes(perm)} onCheckedChange={() => toggle(role, perm)} data-testid={`perm-${role}-${perm}`} />
                {perm}
              </label>
            ))}
          </CardContent>
        </Card>
      ))}
      <Card className="border-slate-200 shadow-sm bg-slate-900 lg:col-span-2">
        <CardContent className="p-5 text-slate-300 text-sm">
          <b className="text-white">Super Admin</b> always has full access and cannot be restricted.
        </CardContent>
      </Card>
    </div>
  );
}


function RichText({ value, onChange, disabled, testid }) {
  const ref = useRef(null);
  useEffect(() => { if (ref.current) ref.current.innerHTML = value || ""; }, []); // eslint-disable-line
  const cmd = (c) => { document.execCommand(c, false, null); if (ref.current) { ref.current.focus(); onChange(ref.current.innerHTML); } };
  const btns = [["bold", "B"], ["italic", "I"], ["underline", "U"], ["insertUnorderedList", "•"], ["insertOrderedList", "1."]];
  return (
    <div className="rounded-md border border-slate-200">
      <div className="flex gap-1 border-b border-slate-100 p-1">
        {btns.map(([c, l]) => (
          <button key={c} type="button" onMouseDown={(e) => { e.preventDefault(); if (!disabled) cmd(c); }} className="h-7 min-w-[28px] px-2 rounded text-sm font-semibold hover:bg-slate-100" data-testid={`${testid}-${c}`}>{l}</button>
        ))}
      </div>
      <div ref={ref} contentEditable={!disabled} suppressContentEditableWarning onInput={(e) => onChange(e.currentTarget.innerHTML)} className="min-h-[80px] p-2 text-sm focus:outline-none" data-testid={testid} />
    </div>
  );
}

function DocTemplateTab({ canManage }) {
  const [t, setT] = useState(null);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const [previewKind, setPreviewKind] = useState("invoice");
  const doPreview = async (kind) => {
    setPreviewing(true);
    try {
      const r = await api.post("/doc-template/preview", { ...t, kind: kind || previewKind }, { responseType: "blob" });
      setPreview((old) => { if (old) URL.revokeObjectURL(old); return URL.createObjectURL(r.data); });
    } catch { toast.error("Gagal membuat preview"); } finally { setPreviewing(false); }
  };
  useEffect(() => {
    api.get("/doc-template").then((r) => {
      const d = r.data || {};
      if (!d.public_base_url) d.public_base_url = process.env.REACT_APP_BACKEND_URL;
      setT(d);
    }).catch(() => setT({}));
  }, []);
  if (!t) return <div className="p-8 text-center text-slate-400 text-sm">Loading...</div>;
  const set = (k) => (e) => setT({ ...t, [k]: e.target.value });
  const save = async () => {
    setSaving(true);
    try { await api.put("/doc-template", t); toast.success("Template dokumen tersimpan"); }
    catch { toast.error("Gagal menyimpan"); } finally { setSaving(false); }
  };
  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader><CardTitle className="font-display">Template Dokumen (Invoice · Quotation · Kwitansi)</CardTitle></CardHeader>
      <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2"><Label>Warna Utama</Label><input type="color" value={t.primary_color || "#1d4ed8"} onChange={set("primary_color")} className="h-10 w-20 rounded border" data-testid="tpl-primary" disabled={!canManage} /></div>
        <div className="space-y-2"><Label>Warna Aksen</Label><input type="color" value={t.accent_color || "#f59e0b"} onChange={set("accent_color")} className="h-10 w-20 rounded border" data-testid="tpl-accent" disabled={!canManage} /></div>
        <div className="space-y-2"><Label>Font</Label>
          <select value={t.font || "Helvetica"} onChange={set("font")} className="w-full h-10 rounded-md border border-slate-200 px-2 text-sm" data-testid="tpl-font" disabled={!canManage}>
            {["Helvetica", "Times-Roman", "Courier"].map((f) => <option key={f} value={f}>{f}</option>)}</select></div>
        <div className="space-y-2"><Label>Tampilkan QR Code</Label>
          <select value={t.show_qr ? "yes" : "no"} onChange={(e) => setT({ ...t, show_qr: e.target.value === "yes" })} className="w-full h-10 rounded-md border border-slate-200 px-2 text-sm" data-testid="tpl-qr" disabled={!canManage}>
            <option value="yes">Ya</option><option value="no">Tidak</option></select></div>
        <div className="space-y-2"><Label>Judul Invoice</Label><Input value={t.invoice_title || ""} onChange={set("invoice_title")} data-testid="tpl-invoice-title" disabled={!canManage} /></div>
        <div className="space-y-2"><Label>Judul Quotation</Label><Input value={t.quotation_title || ""} onChange={set("quotation_title")} data-testid="tpl-quotation-title" disabled={!canManage} /></div>
        <div className="space-y-2"><Label>Judul Kwitansi</Label><Input value={t.receipt_title || ""} onChange={set("receipt_title")} data-testid="tpl-receipt-title" disabled={!canManage} /></div>
        <div className="space-y-2"><Label>Teks Stempel Lunas</Label><Input value={t.paid_stamp_text || ""} onChange={set("paid_stamp_text")} data-testid="tpl-paid-text" disabled={!canManage} /></div>
        <div className="space-y-2"><Label>Watermark Quotation (belum disetujui)</Label><Input value={t.quotation_watermark_text || ""} onChange={set("quotation_watermark_text")} placeholder="DRAFT" data-testid="tpl-quotation-wm" disabled={!canManage} /></div>
        <div className="space-y-2 sm:col-span-2"><Label>Nama Perusahaan (dokumen)</Label><Input value={t.company_name || ""} onChange={set("company_name")} data-testid="tpl-company" disabled={!canManage} /></div>
        <div className="space-y-2 sm:col-span-2"><Label>Alamat</Label><Input value={t.address || ""} onChange={set("address")} disabled={!canManage} /></div>
        <div className="space-y-2"><Label>Telepon</Label><Input value={t.phone || ""} onChange={set("phone")} disabled={!canManage} /></div>
        <div className="space-y-2"><Label>Email</Label><Input value={t.email || ""} onChange={set("email")} disabled={!canManage} /></div>
        <div className="space-y-2 sm:col-span-2"><Label>Logo</Label>
          <div className="flex items-center gap-3">
            {t.logo_url ? <img src={t.logo_url} alt="logo" className="h-12 w-12 rounded object-contain border border-slate-200 bg-white" /> : <div className="h-12 w-12 rounded bg-slate-100 flex items-center justify-center text-[10px] text-slate-400">LOGO</div>}
            <div className="flex-1 space-y-2">
              <Input value={t.logo_url || ""} onChange={set("logo_url")} placeholder="URL logo, atau unggah file di bawah" data-testid="tpl-logo" disabled={!canManage} />
              {canManage && <input type="file" accept="image/*" data-testid="tpl-logo-upload" onChange={(e) => {
                const f = e.target.files?.[0]; if (!f) return;
                if (f.size > 2 * 1024 * 1024) { toast.error("Logo maksimal 2MB"); return; }
                const rd = new FileReader(); rd.onload = () => setT((o) => ({ ...o, logo_url: rd.result })); rd.readAsDataURL(f);
              }} />}
            </div>
          </div>
        </div>
        <div className="sm:col-span-2 border-t border-slate-100 pt-3 mt-1"><p className="font-semibold text-slate-700 text-sm">Tanda Tangan & Stempel (Default)</p><p className="text-xs text-slate-400">Dipakai untuk Invoice, Kwitansi, dan Quotation dari AI/Auto Sales. Stempel dipakai di semua dokumen.</p></div>
        <div className="space-y-2"><Label>Nama Penanda Tangan (Default)</Label><Input value={t.signer_name || ""} onChange={set("signer_name")} placeholder="mis. Dedy Irawan" data-testid="tpl-signer-name" disabled={!canManage} /></div>
        <div className="space-y-2"><Label>Jabatan (Default)</Label><Input value={t.signer_title || ""} onChange={set("signer_title")} placeholder="mis. Direktur" data-testid="tpl-signer-title" disabled={!canManage} /></div>
        <div className="space-y-2 sm:col-span-2"><Label>Tanda Tangan Default (PNG)</Label>
          <div className="flex items-center gap-3">
            {t.signature_url ? <img src={t.signature_url} alt="signature" className="h-14 w-28 rounded object-contain border border-slate-200 bg-white" data-testid="tpl-signature-preview" /> : <div className="h-14 w-28 rounded bg-slate-100 flex items-center justify-center text-[10px] text-slate-400">TTD</div>}
            <div className="flex-1 space-y-2">
              {canManage && <input type="file" accept="image/png,image/*" data-testid="tpl-signature-upload" onChange={(e) => {
                const f = e.target.files?.[0]; if (!f) return;
                if (f.size > 2 * 1024 * 1024) { toast.error("Tanda tangan maksimal 2MB"); return; }
                const rd = new FileReader(); rd.onload = () => setT((o) => ({ ...o, signature_url: rd.result })); rd.readAsDataURL(f);
              }} />}
              {t.signature_url && canManage && <Button variant="ghost" size="sm" className="text-red-600 h-7" onClick={() => setT((o) => ({ ...o, signature_url: "" }))} data-testid="tpl-signature-clear">Hapus</Button>}
            </div>
          </div>
        </div>
        <div className="space-y-2 sm:col-span-2"><Label>Stempel Perusahaan (PNG)</Label>
          <div className="flex items-center gap-3">
            {t.stamp_url ? <img src={t.stamp_url} alt="stamp" className="h-16 w-16 rounded object-contain border border-slate-200 bg-white" data-testid="tpl-stamp-preview" /> : <div className="h-16 w-16 rounded bg-slate-100 flex items-center justify-center text-[10px] text-slate-400">STEMPEL</div>}
            <div className="flex-1 space-y-2">
              {canManage && <input type="file" accept="image/png,image/*" data-testid="tpl-stamp-upload" onChange={(e) => {
                const f = e.target.files?.[0]; if (!f) return;
                if (f.size > 2 * 1024 * 1024) { toast.error("Stempel maksimal 2MB"); return; }
                const rd = new FileReader(); rd.onload = () => setT((o) => ({ ...o, stamp_url: rd.result })); rd.readAsDataURL(f);
              }} />}
              {t.stamp_url && canManage && <Button variant="ghost" size="sm" className="text-red-600 h-7" onClick={() => setT((o) => ({ ...o, stamp_url: "" }))} data-testid="tpl-stamp-clear">Hapus</Button>}
            </div>
          </div>
        </div>
        <div className="space-y-2 sm:col-span-2"><Label>Kota / Tempat Tanda Tangan</Label><Input value={t.signer_place || ""} onChange={set("signer_place")} placeholder="mis. Jakarta" data-testid="tpl-signer-place" disabled={!canManage} /><p className="text-xs text-slate-400">Muncul di atas blok tanda tangan, mis. "Jakarta, 19 Agustus 2026". Tanggal mengikuti tanggal dokumen.</p></div>
        <div className="space-y-2"><Label>Ukuran Stempel: {Math.round((parseFloat(t.stamp_scale ?? 1) || 1) * 100)}%</Label>
          <input type="range" min="0.4" max="2" step="0.1" value={t.stamp_scale ?? 1} onChange={(e) => setT((o) => ({ ...o, stamp_scale: parseFloat(e.target.value) }))} className="w-full" data-testid="tpl-stamp-scale" disabled={!canManage} /></div>
        <div className="space-y-2"><Label>Geser Stempel ↔ (Horizontal): {t.stamp_offset_x ?? 0}</Label>
          <input type="range" min="-90" max="90" step="1" value={t.stamp_offset_x ?? 0} onChange={(e) => setT((o) => ({ ...o, stamp_offset_x: parseInt(e.target.value, 10) }))} className="w-full" data-testid="tpl-stamp-offset-x" disabled={!canManage} /></div>
        <div className="space-y-2"><Label>Geser Stempel ↕ (Vertikal): {t.stamp_offset_y ?? 0}</Label>
          <input type="range" min="-90" max="90" step="1" value={t.stamp_offset_y ?? 0} onChange={(e) => setT((o) => ({ ...o, stamp_offset_y: parseInt(e.target.value, 10) }))} className="w-full" data-testid="tpl-stamp-offset-y" disabled={!canManage} /></div>
        <div className="space-y-2 sm:col-span-2"><Label>Teks Footer</Label><Input value={t.footer_text || ""} onChange={set("footer_text")} data-testid="tpl-footer" disabled={!canManage} /></div>
        <div className="space-y-2 sm:col-span-2"><Label>Terms &amp; Conditions — Invoice</Label><RichText value={t.invoice_terms} onChange={(v) => setT((o) => ({ ...o, invoice_terms: v }))} disabled={!canManage} testid="tpl-invoice-terms" /></div>
        <div className="space-y-2 sm:col-span-2"><Label>Terms &amp; Conditions — Quotation</Label><RichText value={t.quotation_terms} onChange={(v) => setT((o) => ({ ...o, quotation_terms: v }))} disabled={!canManage} testid="tpl-quotation-terms" /></div>
        <div className="space-y-2 sm:col-span-2"><Label>Base URL Publik (untuk QR)</Label><Input value={t.public_base_url || ""} onChange={set("public_base_url")} data-testid="tpl-baseurl" disabled={!canManage} /><p className="text-xs text-slate-400">Dipakai di QR agar customer dapat membuka PDF tanpa login.</p></div>
        <div className="sm:col-span-2 flex items-center gap-2">
          {canManage && <Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="save-doctpl-button">{saving ? "Saving..." : "Simpan template"}</Button>}
          <select value={previewKind} onChange={(e) => setPreviewKind(e.target.value)} className="h-10 rounded-md border border-slate-200 px-2 text-sm" data-testid="preview-kind">
            <option value="invoice">Invoice</option><option value="quotation">Quotation</option><option value="receipt">Kwitansi</option>
          </select>
          <Button variant="outline" onClick={() => doPreview()} disabled={previewing} data-testid="preview-doctpl-button">{previewing ? "Membuat..." : "Preview PDF"}</Button>
        </div>
        {preview && (
          <div className="sm:col-span-2 mt-2" data-testid="doctpl-preview">
            <Label className="mb-1 block">Pratinjau ({previewKind})</Label>
            <iframe title="preview" src={preview} className="w-full h-[520px] rounded-md border border-slate-200" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
