import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { RefreshCw, History } from "lucide-react";

const fmt = (iso) => {
  if (!iso) return "-";
  try { return new Date(iso).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" }); }
  catch { return iso; }
};

const summarize = (p) => {
  const c = (p && p.criteria) || p || {};
  const parts = [];
  if (c.cityId) parts.push(`City ${c.cityId}`);
  if (c.checkIn) parts.push(`${c.checkIn}${c.checkOut ? " → " + c.checkOut : ""}`);
  return parts.join(" · ") || "-";
};

export default function SearchHistory() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/hotel/search-history");
      setRows(data || []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <Card className="border-slate-200 shadow-sm" data-testid="hotel-history">
      <CardContent className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-500">Riwayat pencarian hotel Anda (tanpa data kredensial).</p>
          <Button size="sm" variant="outline" onClick={load} data-testid="hotel-history-refresh">
            <RefreshCw className="h-3.5 w-3.5 mr-1" />Muat Ulang
          </Button>
        </div>
        {loading ? (
          <p className="text-sm text-slate-400 py-8 text-center">Memuat…</p>
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-14 text-slate-400" data-testid="hotel-history-empty">
            <History className="h-10 w-10 mb-3 text-slate-300" />
            <p className="text-sm">Belum ada riwayat pencarian.</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Waktu</TableHead>
                <TableHead>Kriteria</TableHead>
                <TableHead className="text-center">Hasil</TableHead>
                <TableHead className="text-center">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r, i) => (
                <TableRow key={i} data-testid={`hotel-history-row-${i}`}>
                  <TableCell className="text-sm">{fmt(r.timestamp)}</TableCell>
                  <TableCell className="text-sm text-slate-600">{summarize(r.params)}</TableCell>
                  <TableCell className="text-center text-sm">{r.result_count ?? 0}</TableCell>
                  <TableCell className="text-center">
                    <Badge variant={[200, 206].includes(r.response_status) ? "default" : "secondary"}>
                      {r.response_status || "-"}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
