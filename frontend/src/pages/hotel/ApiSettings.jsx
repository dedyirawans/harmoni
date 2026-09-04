import { useEffect, useRef, useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Save, PlugZap, ShieldCheck, KeyRound, RefreshCw, Database, DownloadCloud } from "lucide-react";

const DEFAULT_BASE = "https://klikmbc.co.id/json/hotel/";

export default function ApiSettings() {
  const [form, setForm] = useState({
    base_url: DEFAULT_BASE, username: "", password: "", markup_pct: 15, currency: "IDR", active: true,
  });
  const [meta, setMeta] = useState({ password_set: false, password_masked: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const [countries, setCountries] = useState([]);
  const [syncIso, setSyncIso] = useState("__all");
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const poll = useRef();

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/hotel/settings");
      setForm((f) => ({
        ...f, base_url: data.base_url || DEFAULT_BASE, username: data.username || "", password: "",
        markup_pct: data.markup_pct ?? 15, currency: data.currency || "IDR", active: data.active !== false,
      }));
      setMeta({ password_set: !!data.password_set, password_masked: data.password_masked || "" });
    } catch (e) {
      toast.error(formatApiErrorDetail(e?.response?.data?.detail));
    } finally { setLoading(false); }
  };

  const loadCountries = () => api.get("/hotel/countries").then((r) => setCountries(r.data || [])).catch(() => {});
  const loadSyncStatus = () => api.get("/hotel/sync-status").then((r) => {
    setSyncStatus(r.data);
    if (r.data && r.data.running === false && poll.current) { clearInterval(poll.current); poll.current = null; setSyncing(false); loadCountries(); }
  }).catch(() => {});

  useEffect(() => { load(); loadCountries(); loadSyncStatus(); return () => poll.current && clearInterval(poll.current); }, []); // eslint-disable-line

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        base_url: form.base_url.trim() || DEFAULT_BASE, username: form.username.trim(),
        markup_pct: Number(form.markup_pct) || 0, currency: form.currency, active: form.active,
      };
      if (form.password.trim()) payload.password = form.password.trim();
      const { data } = await api.put("/hotel/settings", payload);
      setMeta({ password_set: !!data.password_set, password_masked: data.password_masked || "" });
      setForm((f) => ({ ...f, password: "" }));
      toast.success("Pengaturan API tersimpan.");
    } catch (e) {
      toast.error(formatApiErrorDetail(e?.response?.data?.detail));
    } finally { setSaving(false); }
  };

  const testConnection = async () => {
    setTesting(true); setTestResult(null);
    try {
      const { data } = await api.post("/hotel/test-connection");
      setTestResult(data);
      if (data.success) { toast.success("Koneksi API berhasil."); loadCountries(); }
      else toast.error("Koneksi API gagal.");
    } catch (e) {
      const detail = formatApiErrorDetail(e?.response?.data?.detail);
      setTestResult({ success: false, message: detail });
      toast.error(detail);
    } finally { setTesting(false); }
  };

  const startSync = async () => {
    setSyncing(true);
    try {
      const body = syncIso && syncIso !== "__all" ? { country_code: syncIso } : {};
      const { data } = await api.post("/hotel/sync", body);
      if (data.started) {
        toast.success(data.message || "Sinkronisasi dimulai.");
        loadSyncStatus();
        if (poll.current) clearInterval(poll.current);
        poll.current = setInterval(loadSyncStatus, 3000);
      } else {
        toast.info(data.message || "Sinkronisasi sedang berjalan.");
        if (!poll.current) poll.current = setInterval(loadSyncStatus, 3000);
      }
    } catch (e) {
      setSyncing(false);
      toast.error(formatApiErrorDetail(e?.response?.data?.detail));
    }
  };

  if (loading) return <p className="text-sm text-slate-400 py-8 text-center">Memuat pengaturan…</p>;
  const counts = syncStatus?.counts || {};

  return (
    <div className="space-y-5" data-testid="hotel-api-settings">
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-5 space-y-5">
          <div className="flex items-center gap-2 text-slate-700">
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
            <p className="text-xs text-slate-500">Kredensial API dienkripsi saat disimpan (Fernet) & tidak pernah ditampilkan penuh maupun dicatat di log.</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <Label>Provider</Label>
              <Input value="API Hotel" disabled data-testid="hotel-settings-provider" />
            </div>
            <div className="space-y-1">
              <Label>Markup Agen (%)</Label>
              <Input type="number" min="0" step="0.5" value={form.markup_pct} data-testid="hotel-settings-markup"
                onChange={(e) => set("markup_pct", e.target.value)} placeholder="mis. 15" />
            </div>
            <div className="space-y-1">
              <Label>Username</Label>
              <Input value={form.username} data-testid="hotel-settings-username"
                onChange={(e) => set("username", e.target.value)} placeholder="username API" />
            </div>
            <div className="space-y-1">
              <Label className="flex items-center gap-2">
                Password
                {meta.password_set && (
                  <Badge variant="secondary" className="text-[10px]" data-testid="hotel-settings-pass-status">
                    <KeyRound className="h-3 w-3 mr-1" />Tersimpan: {meta.password_masked}
                  </Badge>
                )}
              </Label>
              <Input type="password" value={form.password} data-testid="hotel-settings-password"
                onChange={(e) => set("password", e.target.value)}
                placeholder={meta.password_set ? "•••• (biarkan kosong untuk mempertahankan)" : "Masukkan password API"} />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label>Base URL API</Label>
              <Input value={form.base_url} data-testid="hotel-settings-baseurl"
                onChange={(e) => set("base_url", e.target.value)} placeholder={DEFAULT_BASE} />
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
            <div className="flex items-center gap-3 pt-6">
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
                  {testResult.detail.reason ? ` · ${testResult.detail.reason}` : ""}
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center gap-2 text-slate-700">
            <Database className="h-4 w-4 text-blue-600" />
            <p className="text-sm font-semibold">Master Data Hotel (Negara / Kota / Hotel)</p>
          </div>
          <p className="text-xs text-slate-500">Sinkronkan daftar hotel & kota dari server agar pencarian by-nama cepat. Proses berjalan di latar belakang.</p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-lg border border-slate-200 p-3 text-center"><p className="text-xs text-slate-500">Negara</p><p className="text-lg font-bold text-slate-800">{counts.countries ?? 0}</p></div>
            <div className="rounded-lg border border-slate-200 p-3 text-center"><p className="text-xs text-slate-500">Kota</p><p className="text-lg font-bold text-slate-800">{(counts.cities ?? 0).toLocaleString("id-ID")}</p></div>
            <div className="rounded-lg border border-slate-200 p-3 text-center"><p className="text-xs text-slate-500">Hotel</p><p className="text-lg font-bold text-slate-800">{(counts.hotels ?? 0).toLocaleString("id-ID")}</p></div>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Negara</Label>
              <Select value={syncIso} onValueChange={setSyncIso}>
                <SelectTrigger className="w-56" data-testid="hotel-sync-country"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all">Semua negara</SelectItem>
                  {countries.map((c) => <SelectItem key={c.country_code} value={c.country_code}>{c.country_name} ({c.country_code})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Button onClick={startSync} disabled={syncing || syncStatus?.running} data-testid="hotel-sync-start">
              {(syncing || syncStatus?.running) ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <DownloadCloud className="h-4 w-4 mr-2" />}
              {(syncing || syncStatus?.running) ? "Menyinkron…" : "Mulai Sinkronisasi"}
            </Button>
            <Button variant="outline" onClick={loadSyncStatus} data-testid="hotel-sync-refresh"><RefreshCw className="h-4 w-4 mr-2" />Refresh</Button>
          </div>

          {syncStatus?.error && <p className="text-xs text-red-600">Error: {syncStatus.error}</p>}
          {Array.isArray(syncStatus?.per_country) && syncStatus.per_country.length > 0 && (
            <div className="space-y-1" data-testid="hotel-sync-percountry">
              {syncStatus.per_country.map((p, i) => (
                <div key={i} className="flex items-center justify-between text-xs border-b border-slate-100 py-1">
                  <span className="font-medium">{p.country}</span>
                  {p.ok ? <span className="text-emerald-600">{p.hotels} hotel · {p.cities} kota</span>
                    : <span className="text-red-500">{p.reason || "gagal"}</span>}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
