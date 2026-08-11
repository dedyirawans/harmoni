import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
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
import { Loader2 } from "lucide-react";

const COMPANY_FIELDS = [
  ["company_name", "Company Name"], ["email", "Email"], ["phone", "Phone"],
  ["website", "Website"], ["npwp", "NPWP"], ["nib", "NIB"],
  ["address", "Address"], ["bank_account", "Bank Account"],
];

export default function Settings() {
  const { user } = useAuth();
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
    try { await api.put("/company-settings", company); toast.success("Company settings saved"); }
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
    return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-amber-600" /></div>;

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
          {isAdmin && <TabsTrigger value="roles" data-testid="tab-roles">Roles & Permissions</TabsTrigger>}
        </TabsList>

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
              <CardHeader><CardTitle className="font-display text-lg">Integration & Notifications</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>N8N Webhook URL</Label>
                  <Input value={system.n8n?.webhook_url || ""} disabled={!canManage}
                    onChange={(e) => setSystem({ ...system, n8n: { ...system.n8n, webhook_url: e.target.value } })}
                    data-testid="n8n-url-input" />
                </div>
                <div className="flex items-center justify-between">
                  <Label>Enable N8N</Label>
                  <Switch checked={!!system.n8n?.enabled} disabled={!canManage}
                    onCheckedChange={(v) => setSystem({ ...system, n8n: { ...system.n8n, enabled: v } })} data-testid="n8n-switch" />
                </div>
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

  if (rp === null) return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-amber-600" /></div>;

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
