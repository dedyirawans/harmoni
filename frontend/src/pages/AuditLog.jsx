import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Loader2, ScrollText } from "lucide-react";

const MODULES = ["all", "auth", "user", "settings", "package", "booking", "payment"];

export default function AuditLog() {
  const [logs, setLogs] = useState(null);
  const [module, setModule] = useState("all");

  useEffect(() => {
    setLogs(null);
    api.get("/audit-logs", { params: { module } }).then((r) => setLogs(r.data)).catch(() => setLogs([]));
  }, [module]);

  const actionBadge = (a) => {
    const danger = ["delete_user", "logout"].includes(a);
    const good = ["create_user", "login"].includes(a);
    const cls = danger ? "bg-red-50 text-red-700 border-red-200" : good ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-600";
    return <Badge variant="outline" className={cls}>{a}</Badge>;
  };

  return (
    <div className="space-y-6" data-testid="audit-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">Audit Log</h1>
          <p className="text-slate-500 mt-1">Every sensitive action is recorded with actor, timestamp, and context.</p>
        </div>
        <Select value={module} onValueChange={setModule}>
          <SelectTrigger className="w-48" data-testid="audit-module-filter"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-white">
            {MODULES.map((m) => <SelectItem key={m} value={m}>{m === "all" ? "All modules" : m}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <Card className="border-slate-200 shadow-sm overflow-hidden">
        {logs === null ? (
          <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <ScrollText className="h-8 w-8 mx-auto text-slate-300" aria-hidden="true" />
            <p className="mt-2">No audit records for this filter.</p>
          </div>
        ) : (
          <Table data-testid="audit-table">
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead>Timestamp</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Module</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Record</TableHead>
                <TableHead>IP</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.map((l) => (
                <TableRow key={l._id} className="hover:bg-slate-50">
                  <TableCell className="text-xs text-slate-500 whitespace-nowrap">{new Date(l.timestamp).toLocaleString()}</TableCell>
                  <TableCell>
                    <div className="font-medium text-slate-900">{l.user_name || "system"}</div>
                    <div className="text-xs text-slate-400">{l.user_email}</div>
                  </TableCell>
                  <TableCell className="text-slate-600 capitalize">{(l.role || "").replace("_", " ")}</TableCell>
                  <TableCell className="text-slate-600">{l.module}</TableCell>
                  <TableCell>{actionBadge(l.action)}</TableCell>
                  <TableCell className="text-xs text-slate-400 font-mono">{l.record_id || "—"}</TableCell>
                  <TableCell className="text-xs text-slate-400">{l.ip || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
