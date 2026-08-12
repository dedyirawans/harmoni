import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import api from "@/lib/api";
import { PlaneTakeoff, AlertTriangle, Loader2 } from "lucide-react";

const LABEL = { SEAT_ALMOST_FULL: "Seat menipis", PAYMENT_DUE: "Belum lunas", PASSPORT_EXPIRED: "Paspor exp", DOCS_INCOMPLETE: "Dok. kurang", DEPARTURE_APPROACHING: "Segera berangkat" };

export default function DepartureAlertsWidget() {
  const nav = useNavigate();
  const [rows, setRows] = useState(null);
  useEffect(() => { api.get("/operations/alerts-summary").then((r) => setRows(r.data || [])).catch(() => setRows([])); }, []);
  return (
    <Card className="border-slate-200 shadow-sm" data-testid="departure-alerts-widget">
      <CardHeader className="border-b border-slate-100 py-3">
        <CardTitle className="text-sm font-display flex items-center gap-2">
          <PlaneTakeoff className="h-4 w-4 text-blue-600" />
          Keberangkatan Mendekat (30 hari) & Alert
          {rows && rows.length > 0 && <Badge className="bg-amber-100 text-amber-700 border-amber-200" data-testid="departure-alerts-count">{rows.length}</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {rows === null ? (
          <div className="p-8 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
        ) : rows.length === 0 ? (
          <p className="p-6 text-center text-sm text-slate-400" data-testid="departure-alerts-empty">Tidak ada keberangkatan mendekat yang perlu perhatian.</p>
        ) : (
          <div className="divide-y divide-slate-100 max-h-80 overflow-y-auto" data-testid="departure-alerts-list">
            {rows.map((d) => (
              <button key={d.id} onClick={() => nav("/operations")} data-testid={`departure-alert-${d.id}`} className="w-full text-left px-4 py-3 hover:bg-slate-50">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-slate-900 truncate">{d.package_name}</p>
                  <span className="text-xs text-slate-500">{d.departure_date}{d.days_to != null ? ` · ${d.days_to}h` : ""}</span>
                </div>
                <div className="flex flex-wrap gap-1 mt-1">
                  {d.alerts.map((a) => (
                    <Badge key={a} variant="outline" className="bg-amber-50 text-amber-700 border-amber-200 text-[10px]">
                      <AlertTriangle className="h-3 w-3 mr-1" />{LABEL[a] || a}
                    </Badge>
                  ))}
                </div>
              </button>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
