import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Activity, Trophy } from "lucide-react";

const short = (n) => {
  const v = Number(n || 0);
  if (Math.abs(v) >= 1e9) return "Rp " + (v / 1e9).toFixed(1) + "M";
  if (Math.abs(v) >= 1e6) return "Rp " + (v / 1e6).toFixed(1) + "jt";
  return "Rp " + v.toLocaleString("id-ID");
};

export default function SalesActivityWidget() {
  const nav = useNavigate();
  const now = new Date();
  const period = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [rows, setRows] = useState(null);

  const load = useCallback(() => {
    api.get("/sales/performance", { params: { period } })
      .then((r) => setRows(r.data.rows || [])).catch(() => setRows([]));
  }, [period]);
  useEffect(() => { load(); }, [load]);

  const totalActs = (rows || []).reduce((a, r) => a + (r.total_activities || 0), 0);
  const topActivity = [...(rows || [])].sort((a, b) => b.activity_score - a.activity_score).slice(0, 3);
  const topRevenue = [...(rows || [])].sort((a, b) => b.revenue - a.revenue).slice(0, 3);

  return (
    <Card className="border-slate-200 shadow-sm" data-testid="dashboard-sales-activity-widget">
      <CardHeader className="border-b border-slate-100 py-3 flex flex-row items-center justify-between">
        <CardTitle className="text-sm font-display flex items-center gap-2"><Activity className="h-4 w-4 text-blue-600" />Sales Activity (Bulan Ini)</CardTitle>
        <button onClick={() => nav("/sales-activity")} className="text-xs text-blue-600 hover:underline" data-testid="widget-view-activity">Lihat semua →</button>
      </CardHeader>
      {rows === null ? <div className="p-8 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
        : rows.length === 0 ? <p className="p-6 text-center text-sm text-slate-400">Belum ada data sales.</p>
        : (
          <CardContent className="p-3 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-slate-400 mb-2 flex items-center gap-1"><Activity className="h-3.5 w-3.5" />Top Activity Score · Total {totalActs} aktivitas</p>
              <div className="space-y-1">
                {topActivity.map((r, i) => (
                  <button key={r.sales_id} onClick={() => nav("/sales-activity")} className="w-full flex items-center justify-between rounded-md border border-slate-100 px-3 py-2 hover:bg-blue-50 transition-colors text-left" data-testid={`widget-act-${r.sales_id}`}>
                    <span className="text-sm text-slate-700 flex items-center gap-2"><span className="text-xs text-slate-400 w-4">{i + 1}.</span>{r.sales}</span>
                    <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">{r.activity_score}</Badge>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-2 flex items-center gap-1"><Trophy className="h-3.5 w-3.5 text-amber-500" />Top Revenue</p>
              <div className="space-y-1">
                {topRevenue.map((r, i) => (
                  <button key={r.sales_id} onClick={() => nav("/sales-activity")} className="w-full flex items-center justify-between rounded-md border border-slate-100 px-3 py-2 hover:bg-emerald-50 transition-colors text-left" data-testid={`widget-rev-${r.sales_id}`}>
                    <span className="text-sm text-slate-700 flex items-center gap-2"><span className="text-xs text-slate-400 w-4">{i + 1}.</span>{r.sales}</span>
                    <span className="text-sm font-semibold text-emerald-700">{short(r.revenue)}</span>
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        )}
    </Card>
  );
}
