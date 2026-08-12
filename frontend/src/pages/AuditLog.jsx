import { useEffect, useState, Fragment } from "react";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, ScrollText, ChevronDown, ChevronRight } from "lucide-react";

const MODULES = ["all", "auth", "user", "customer", "lead", "quotation", "booking", "invoice", "payment", "refund", "commission", "tax", "package", "hpp", "settings"];

const DANGER = ["archive_user", "archive_customer", "archive_lead", "delete_user", "void", "reject", "reopen", "deactivate_ppn_config", "logout"];
const GOOD = ["create_user", "restore_user", "restore_customer", "restore_lead", "login", "approve", "process"];

export default function AuditLog() {
  const [logs, setLogs] = useState(null);
  const [module, setModule] = useState("all");
  const [userQ, setUserQ] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [expanded, setExpanded] = useState({});

  const load = () => {
    setLogs(null);
    api.get("/audit-logs", { params: {
      module,
      user_q: userQ || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    } }).then((r) => setLogs(r.data)).catch(() => setLogs([]));
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [module, dateFrom, dateTo]);

  const actionBadge = (a) => {
    const cls = DANGER.includes(a) ? "bg-red-50 text-red-700 border-red-200"
      : GOOD.includes(a) ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : "bg-slate-100 text-slate-600";
    return <Badge variant="outline" className={cls}>{a}</Badge>;
  };

  const toggle = (id) => setExpanded((e) => ({ ...e, [id]: !e[id] }));
  const hasDetail = (l) => l.old_value || l.new_value;

  return (
    <div className="space-y-6" data-testid="audit-page">
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900">Audit Log</h1>
        <p className="text-slate-500 mt-1">Setiap aksi sensitif tercatat dengan aktor, waktu, alasan, sesi, dan nilai lama/baru.</p>
      </div>

      <div className="flex items-end gap-3 flex-wrap">
        <div className="space-y-1">
          <label className="text-xs text-slate-500">Modul</label>
          <Select value={module} onValueChange={setModule}>
            <SelectTrigger className="w-44" data-testid="audit-module-filter"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-white max-h-72">
              {MODULES.map((m) => <SelectItem key={m} value={m}>{m === "all" ? "Semua modul" : m}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-slate-500">User</label>
          <Input className="w-48" placeholder="Nama / email" value={userQ}
            onChange={(e) => setUserQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} data-testid="audit-user-filter" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-slate-500">Dari tanggal</label>
          <Input type="date" className="w-40" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} data-testid="audit-date-from" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-slate-500">Sampai tanggal</label>
          <Input type="date" className="w-40" value={dateTo} onChange={(e) => setDateTo(e.target.value)} data-testid="audit-date-to" />
        </div>
        <Button variant="outline" onClick={load} data-testid="audit-search-button">Cari</Button>
      </div>

      <Card className="border-slate-200 shadow-sm overflow-hidden">
        {logs === null ? (
          <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <ScrollText className="h-8 w-8 mx-auto text-slate-300" aria-hidden="true" />
            <p className="mt-2">Tidak ada catatan audit untuk filter ini.</p>
          </div>
        ) : (
          <Table data-testid="audit-table">
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead className="w-8"></TableHead>
                <TableHead>Waktu</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Modul</TableHead>
                <TableHead>Aksi</TableHead>
                <TableHead>Record</TableHead>
                <TableHead>Alasan</TableHead>
                <TableHead>IP / Sesi</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((l) => (
                <Fragment key={l._id}>
                  <TableRow className="hover:bg-slate-50" data-testid={`audit-row-${l._id}`}>
                    <TableCell className="align-top">
                      {hasDetail(l) && (
                        <button onClick={() => toggle(l._id)} data-testid={`audit-expand-${l._id}`} className="text-slate-400 hover:text-slate-700">
                          {expanded[l._id] ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </button>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-slate-500 whitespace-nowrap align-top">{new Date(l.timestamp).toLocaleString()}</TableCell>
                    <TableCell className="align-top">
                      <div className="font-medium text-slate-900">{l.user_name || "system"}</div>
                      <div className="text-xs text-slate-400">{l.user_email}</div>
                      <div className="text-[10px] text-slate-400 capitalize">{(l.role || "").replace("_", " ")}</div>
                    </TableCell>
                    <TableCell className="text-slate-600 align-top">{l.module}</TableCell>
                    <TableCell className="align-top">{actionBadge(l.action)}</TableCell>
                    <TableCell className="text-xs text-slate-400 font-mono align-top">{l.record_id || "—"}</TableCell>
                    <TableCell className="text-xs text-slate-600 align-top max-w-[200px]" data-testid={`audit-reason-${l._id}`}>{l.reason || "—"}</TableCell>
                    <TableCell className="text-xs text-slate-400 align-top">
                      <div>{l.ip || "—"}</div>
                      {l.session_id && <div className="font-mono text-[10px] truncate max-w-[120px]" title={l.session_id}>{l.session_id}</div>}
                    </TableCell>
                  </TableRow>
                  {expanded[l._id] && hasDetail(l) && (
                    <TableRow className="bg-slate-50/60" data-testid={`audit-detail-${l._id}`}>
                      <TableCell></TableCell>
                      <TableCell colSpan={7} className="py-3">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <p className="text-[11px] font-semibold text-red-600 mb-1">Nilai Lama</p>
                            <pre className="text-[11px] bg-white border border-slate-200 rounded p-2 overflow-x-auto max-h-56">{JSON.stringify(l.old_value ?? {}, null, 2)}</pre>
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold text-emerald-600 mb-1">Nilai Baru</p>
                            <pre className="text-[11px] bg-white border border-slate-200 rounded p-2 overflow-x-auto max-h-56">{JSON.stringify(l.new_value ?? {}, null, 2)}</pre>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
