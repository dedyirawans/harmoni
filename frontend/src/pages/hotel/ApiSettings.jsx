import { useEffect, useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Save, PlugZap, ShieldCheck, KeyRound } from "lucide-react";

const DEFAULT_ENDPOINT = "http://affiliateapi7643.agoda.com/affiliateservice/lt_v1";

export default function ApiSettings() {
  const [form, setForm] = useState({
    provider: "Agoda",
    site_id: "",
    api_key: "",
    endpoint: DEFAULT_ENDPOINT,
    language: "id-id",
    currency: "IDR",
    active: true,
  });
  const [meta, setMeta] = useState({ api_key_set: false, api_key_masked: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/hotel/settings");
      setForm((f) => ({
        ...f,
        provider: data.provider || "Agoda",
        site_id: data.site_id || "",
        api_key: "",
        endpoint: data.endpoint || DEFAULT_ENDPOINT,
        language: data.language || "id-id",
        currency: data.currency || "IDR",
        active: data.active !== false,
      }));
      setMeta({ api_key_set: !!data.api_key_set, api_key_masked: data.api_key_masked || "" });
    } catch (e) {
      toast.error(formatApiErrorDetail(e?.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!form.site_id.trim()) return toast.error("Site ID wajib diisi.");
    setSaving(true);
    try {
      const payload = {
        provider: form.provider,
        site_id: form.site_id.trim(),
        endpoint: form.endpoint.trim() || DEFAULT_ENDPOINT,
        language: form.language,
        currency: form.currency,
        active: form.active,
      };
      if (form.api_key.trim()) payload.api_key = form.api_key.trim();
      const { data } = await api.put("/hotel/settings", payload);
      setMeta({ api_key_set: !!data.api_key_set, api_key_masked: data.api_key_masked || "" });
      setForm((f) => ({ ...f, api_key: "" }));
      toast.success("Pengaturan API Agoda tersimpan.");
    } catch (e) {
      toast.error(formatApiErrorDetail(e?.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const { data } = await api.post("/hotel/test-connection");
      setTestResult(data);
      if (data.success) toast.success("Koneksi Agoda API berhasil.");
      else toast.error("Koneksi Agoda API gagal.");
    } catch (e) {
      const detail = formatApiErrorDetail(e?.response?.data?.detail);
      setTestResult({ success: false, message: detail });
      toast.error(detail);
    } finally {
      setTesting(false);
    }
  };

  if (loading) return <p className="text-sm text-slate-400 py-8 text-center">Memuat pengaturan…</p>;

  return (
    <div className="space-y-5" data-testid="hotel-api-settings">
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-5 space-y-5">
          <div className="flex items-center gap-2 text-slate-700">
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
            <p className="text-xs text-slate-500">API Key dienkripsi saat disimpan (Fernet) dan tidak pernah ditampilkan penuh maupun dicatat di log.</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label>Provider</Label>
              <Input value={form.provider} disabled data-testid="hotel-settings-provider" />
            </div>
            <div className="space-y-1">
              <Label>Site ID</Label>
              <Input value={form.site_id} data-testid="hotel-settings-siteid"
                onChange={(e) => set("site_id", e.target.value)} placeholder="mis. 1234567" />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label className="flex items-center gap-2">
                API Key
                {meta.api_key_set && (
                  <Badge variant="secondary" className="text-[10px]" data-testid="hotel-settings-key-status">
                    <KeyRound className="h-3 w-3 mr-1" />Tersimpan: {meta.api_key_masked}
                  </Badge>
                )}
              </Label>
              <Input type="password" value={form.api_key} data-testid="hotel-settings-apikey"
                onChange={(e) => set("api_key", e.target.value)}
                placeholder={meta.api_key_set ? "•••• (biarkan kosong untuk mempertahankan key lama)" : "Masukkan API Key Agoda"} />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label>API Endpoint</Label>
              <Input value={form.endpoint} data-testid="hotel-settings-endpoint"
                onChange={(e) => set("endpoint", e.target.value)} placeholder={DEFAULT_ENDPOINT} />
            </div>
            <div className="space-y-1">
              <Label>Bahasa</Label>
              <Select value={form.language} onValueChange={(v) => set("language", v)}>
                <SelectTrigger data-testid="hotel-settings-language"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="id-id">id-id (Indonesia)</SelectItem>
                  <SelectItem value="en-us">en-us (English)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Mata Uang</Label>
              <Select value={form.currency} onValueChange={(v) => set("currency", v)}>
                <SelectTrigger data-testid="hotel-settings-currency"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="IDR">IDR</SelectItem>
                  <SelectItem value="USD">USD</SelectItem>
                  <SelectItem value="SAR">SAR</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-3 pt-2">
              <Switch checked={form.active} onCheckedChange={(v) => set("active", v)} data-testid="hotel-settings-active" />
              <Label className="cursor-pointer">Status Aktif</Label>
            </div>
          </div>

          <div className="flex items-center gap-3 pt-2 border-t border-slate-100">
            <Button onClick={save} disabled={saving} className="mt-4" data-testid="hotel-settings-save">
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
              Simpan Pengaturan
            </Button>
            <Button onClick={testConnection} disabled={testing} variant="outline" className="mt-4" data-testid="hotel-settings-test">
              {testing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <PlugZap className="h-4 w-4 mr-2" />}
              Test Koneksi
            </Button>
          </div>

          {testResult && (
            <div className={`rounded-lg border p-3 text-sm ${testResult.success ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-700"}`} data-testid="hotel-settings-test-result">
              <p className="font-medium">{testResult.message}</p>
              {testResult.detail && (
                <p className="text-xs mt-1 opacity-80">
                  Status: {testResult.detail.status ?? "-"} · {testResult.detail.response_time_ms ?? "-"}ms
                  {testResult.detail.error_message ? ` · ${testResult.detail.error_message}` : ""}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
