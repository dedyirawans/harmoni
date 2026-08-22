import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { RefreshCw, ScrollText } from "lucide-react";

const fmt = (iso) => {
  if (!iso) return "-";
  try { return new Date(iso).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" }); }
  catch { return iso; }
};

export default function ApiLogs() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/hotel/logs");
      setRows(data || []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const statusVariant = (s) => ([200, 206, 202, 204].includes(s) ? "default" : "destructive");

  return (
    <Card className="border-slate-200 shadow-sm" data-testid="hotel-api-logs">
      <CardContent className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-500">Log request Agoda API (tanpa header otorisasi & tanpa API Key).</p>
          <Button size="sm" variant="outline" onClick={load} data-testid="hotel-logs-refresh">
            <RefreshCw className="h-3.5 w-3.5 mr-1" />Muat Ulang
          </Button>
        </div>
        {loading ? (
          <p className="text-sm text-slate-400 py-8 text-center">Memuat…</p>
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-14 text-slate-400" data-testid="hotel-logs-empty">
            <ScrollText className="h-10 w-10 mb-3 text-slate-300" />
            <p className="text-sm">Belum ada log API.</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Waktu</TableHead>
                <TableHead>Tipe</TableHead>
                <TableHead>Search</TableHead>
                <TableHead className="text-center">Status</TableHead>
                <TableHead className="text-center">Waktu (ms)</TableHead>
                <TableHead className="text-center">Hasil</TableHead>
                <TableHead>Error</TableHead>
                <TableHead>Oleh</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r, i) => (
                <TableRow key={r.id || i} data-testid={`hotel-log-row-${i}`}>
                  <TableCell className="text-sm whitespace-nowrap">{fmt(r.timestamp)}</TableCell>
                  <TableCell><Badge variant="outline">{r.request_type || "-"}</Badge></TableCell>
                  <TableCell className="text-sm text-slate-600">{r.search_type || "-"}</TableCell>
                  <TableCell className="text-center">
                    <Badge variant={statusVariant(r.response_status)}>{r.response_status ?? "-"}</Badge>
                  </TableCell>
                  <TableCell className="text-center text-sm">{r.response_time_ms ?? "-"}</TableCell>
                  <TableCell className="text-center text-sm">{r.result_count ?? 0}</TableCell>
                  <TableCell className="text-sm text-red-600 max-w-[220px] truncate">{r.error_message || "-"}</TableCell>
                  <TableCell className="text-sm text-slate-500">{r.by || "-"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
