import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/context/AuthContext";
import { Navigate } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import {
  Wrench, ShieldCheck, ScrollText, PlayCircle, Loader2, Lock, Eye, PenLine, AlertTriangle, RefreshCw,
} from "lucide-react";

const err = (e) => toast.error(formatApiErrorDetail(e?.response?.data?.detail) || "Terjadi kesalahan");
const fmt = (t) => (t || "—").toString().replace("T", " ").slice(0, 19);
const riskColor = (r) =>
  r === "HIGH_RISK" ? "bg-red-50 text-red-700 border-red-200"
    : r === "TRANSACTIONAL" ? "bg-amber-50 text-amber-700 border-amber-200"
      : "bg-slate-100 text-slate-600 border-slate-200";
const typeIcon = (t) => t === "READ" ? <Eye className="h-3.5 w-3.5" /> : <PenLine className="h-3.5 w-3.5" />;

// ============================================================ Permission matrix
function MatrixTab() {
  const [tools, setTools] = useState(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => api.get("/ai/tools").then((r) => setTools(r.data)).catch(() => setTools([])), []);
  useEffect(() => { load(); }, [load]);
  const toggle = async (t, enabled) => {
    setBusy(t.tool);
    try { await api.put(`/ai/tools/${t.tool}`, { enabled }); setTools((prev) => prev.map((x) => x.tool === t.tool ? { ...x, enabled } : x)); toast.success(`${t.label} ${enabled ? "diaktifkan" : "dinonaktifkan"}`); }
    catch (e) { err(e); load(); } finally { setBusy(""); }
  };
  if (tools === null) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  const groups = [["READ", "Read Tools", Eye], ["WRITE", "Write & Action Tools", PenLine]];
  return (
    <div className="space-y-5" data-testid="ai-matrix-tab">
      <div className="p-3 rounded-lg bg-blue-50 border border-blue-100 text-sm text-blue-800">
        AI berinteraksi dengan CRM HANYA melalui tool aman ini — tanpa akses database langsung. Aksi <b>berisiko tinggi</b> tidak pernah dieksekusi AI, hanya membuat permintaan approval manusia.
      </div>
      {groups.map(([type, title, Icon]) => (
        <div key={type}>
          <h3 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-1.5"><Icon className="h-4 w-4" />{title}</h3>
          <Card><CardContent className="p-0">
            <Table>
              <TableHeader><TableRow><TableHead>Tool</TableHead><TableHead>Tipe</TableHead><TableHead>Risiko</TableHead><TableHead>Konfirmasi</TableHead><TableHead className="text-right">Aktif</TableHead></TableRow></TableHeader>
              <TableBody>
                {tools.filter((t) => t.type === type).map((t) => (
                  <TableRow key={t.tool} data-testid={`ai-tool-row-${t.tool}`}>
                    <TableCell><span className="font-mono text-xs font-medium">{t.tool}</span><div className="text-xs text-slate-400">{t.label}</div></TableCell>
                    <TableCell><Badge variant="outline" className="gap-1">{typeIcon(t.type)}{t.type}</Badge></TableCell>
                    <TableCell><Badge variant="outline" className={riskColor(t.risk)}>{t.risk === "HIGH_RISK" && <Lock className="h-3 w-3 mr-1" />}{t.risk}</Badge></TableCell>
                    <TableCell>{t.confirm ? <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">Wajib</Badge> : <span className="text-slate-400 text-xs">—</span>}</TableCell>
                    <TableCell className="text-right">
                      {busy === t.tool ? <Loader2 className="h-4 w-4 animate-spin inline text-blue-600" />
                        : <Switch checked={!!t.enabled} onCheckedChange={(v) => toggle(t, v)} data-testid={`ai-tool-switch-${t.tool}`} />}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent></Card>
        </div>
      ))}
    </div>
  );
}

// ============================================================ Tool test playground
function PlaygroundTab() {
  const [tools, setTools] = useState([]);
  const [tool, setTool] = useState("");
  const [paramsText, setParamsText] = useState("{}");
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState(null);
  useEffect(() => { api.get("/ai/tools").then((r) => { setTools(r.data); if (r.data[0]) setTool(r.data[0].tool); }).catch(() => {}); }, []);
  const meta = tools.find((t) => t.tool === tool);
  const presets = {
    SEARCH_CUSTOMER: '{"q": "budi"}', GET_PACKAGE: '{"package_id": ""}',
    SEARCH_PACKAGE: '{"q": "umrah"}', CHECK_SEAT: '{"package_id": "", "departure_id": ""}',
    GET_FAQ: '{"q": "visa"}', GET_COMPANY_POLICY: '{}',
    CREATE_BOOKING: '{"customer_id": "", "package_id": "", "departure_id": "", "pax": 2}',
  };
  const run = async () => {
    let params;
    try { params = JSON.parse(paramsText || "{}"); } catch { toast.error("Params bukan JSON valid"); return; }
    setLoading(true); setRes(null);
    try { const r = await api.post("/ai/tools/execute", { tool, params, confirmed }); setRes(r.data); }
    catch (e) { err(e); } finally { setLoading(false); }
  };
  return (
    <div className="grid md:grid-cols-2 gap-4" data-testid="ai-playground-tab">
      <Card><CardContent className="p-5 space-y-3">
        <div className="flex items-center gap-2 text-slate-800 font-medium"><PlayCircle className="h-4 w-4 text-purple-600" />Tool Test Playground</div>
        <div><Label>Tool</Label>
          <Select value={tool} onValueChange={(v) => { setTool(v); setParamsText(presets[v] || "{}"); setRes(null); }}>
            <SelectTrigger data-testid="ai-play-tool"><SelectValue /></SelectTrigger>
            <SelectContent className="max-h-72">{tools.map((t) => <SelectItem key={t.tool} value={t.tool}>{t.tool}{t.enabled ? "" : " (off)"}</SelectItem>)}</SelectContent></Select>
          {meta && <div className="flex gap-1 mt-1"><Badge variant="outline" className="gap-1">{typeIcon(meta.type)}{meta.type}</Badge><Badge variant="outline" className={riskColor(meta.risk)}>{meta.risk}</Badge>{meta.confirm && <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">butuh konfirmasi</Badge>}</div>}
        </div>
        <div><Label>Parameters (JSON)</Label><Textarea rows={6} value={paramsText} onChange={(e) => setParamsText(e.target.value)} className="font-mono text-xs" data-testid="ai-play-params" /></div>
        {meta?.confirm && (
          <div className="flex items-center gap-2"><Switch checked={confirmed} onCheckedChange={setConfirmed} data-testid="ai-play-confirmed" /><Label className="cursor-pointer">Customer sudah konfirmasi (confirmed=true)</Label></div>
        )}
        <Button onClick={run} disabled={loading || !tool} data-testid="ai-play-run">{loading ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <PlayCircle className="h-4 w-4 mr-1" />}Jalankan Tool</Button>
      </CardContent></Card>
      <Card><CardContent className="p-5 space-y-2 min-h-[300px]">
        <div className="font-medium text-slate-800">Hasil</div>
        {loading ? <div className="flex items-center justify-center h-40"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
          : !res ? <p className="text-sm text-slate-400">Hasil eksekusi tool akan tampil di sini.</p>
            : (<div className="space-y-2" data-testid="ai-play-result">
              <Badge variant="outline" className={res.ok ? "bg-emerald-50 text-emerald-700 border-emerald-200" : res.needs_confirmation ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-red-50 text-red-700 border-red-200"}>
                {res.ok ? (res.request_created ? "REQUEST DIBUAT (perlu approval)" : "OK") : res.needs_confirmation ? "PERLU KONFIRMASI" : "GAGAL"}
              </Badge>
              {res.message && <p className="text-sm text-slate-700">{res.message}</p>}
              {res.error && <p className="text-sm text-red-600">{res.error}</p>}
              <pre className="text-xs bg-slate-900 text-slate-100 rounded-lg p-3 overflow-auto max-h-[340px]">{JSON.stringify(res.result ?? res, null, 2)}</pre>
            </div>)}
      </CardContent></Card>
    </div>
  );
}

// ============================================================ Audit log
function AuditTab() {
  const [logs, setLogs] = useState(null);
  const load = useCallback(() => api.get("/ai/action-logs").then((r) => setLogs(r.data)).catch(() => setLogs([])), []);
  useEffect(() => { load(); }, [load]);
  if (logs === null) return <div className="p-8 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  return (
    <div className="space-y-3" data-testid="ai-audit-tab">
      <div className="flex justify-end"><Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-4 w-4 mr-1" />Muat Ulang</Button></div>
      <Card><CardContent className="p-0">
        <Table>
          <TableHeader><TableRow><TableHead>Waktu</TableHead><TableHead>Agent</TableHead><TableHead>Tool</TableHead><TableHead>Customer</TableHead><TableHead>Approval</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
          <TableBody>
            {logs.length === 0 ? (<TableRow><TableCell colSpan={6} className="text-center py-8 text-slate-400">Belum ada aktivitas AI.</TableCell></TableRow>)
              : logs.map((l) => (
                <TableRow key={l.id} data-testid={`ai-audit-row-${l.id}`}>
                  <TableCell className="text-xs text-slate-500">{fmt(l.timestamp)}</TableCell>
                  <TableCell className="text-xs">{l.agent}</TableCell>
                  <TableCell><span className="font-mono text-xs">{l.tool}</span></TableCell>
                  <TableCell className="text-xs text-slate-500">{l.customer_id || "—"}</TableCell>
                  <TableCell>{l.approval_required ? <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200"><AlertTriangle className="h-3 w-3 mr-1" />Perlu</Badge> : <span className="text-slate-400 text-xs">—</span>}</TableCell>
                  <TableCell>{l.ok ? <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">OK</Badge> : <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">FAIL</Badge>}</TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </CardContent></Card>
    </div>
  );
}

// ============================================================ Main
export default function AITools() {
  const { user } = useAuth();
  const [tab, setTab] = useState("matrix");
  if (user?.role !== "super_admin") return <Navigate to="/dashboard" replace />;
  return (
    <div className="space-y-5" data-testid="ai-tools-page">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-indigo-500/10 flex items-center justify-center"><Wrench className="h-6 w-6 text-indigo-600" /></div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">AI Agent Tools & Actions</h1>
          <p className="text-sm text-slate-500">Kontrol tool CRM yang boleh dipakai AI, uji tiap tool, dan pantau seluruh aksi AI.</p>
        </div>
      </div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList data-testid="ai-tabs-list">
          <TabsTrigger value="matrix" data-testid="ai-tab-matrix"><ShieldCheck className="h-4 w-4 mr-1.5" />Permission Matrix</TabsTrigger>
          <TabsTrigger value="playground" data-testid="ai-tab-playground"><PlayCircle className="h-4 w-4 mr-1.5" />Tool Test</TabsTrigger>
          <TabsTrigger value="audit" data-testid="ai-tab-audit"><ScrollText className="h-4 w-4 mr-1.5" />Audit Log</TabsTrigger>
        </TabsList>
        <div className="mt-4">
          <TabsContent value="matrix"><MatrixTab /></TabsContent>
          <TabsContent value="playground"><PlaygroundTab /></TabsContent>
          <TabsContent value="audit"><AuditTab /></TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
