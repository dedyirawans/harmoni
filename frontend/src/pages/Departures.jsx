import { useEffect, useState } from "react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { fmtIDR, fmtDate } from "@/config/crm";
import { DEP_STATUS_COLORS } from "@/config/product";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, PlaneTakeoff, MapPin, Users } from "lucide-react";

export default function Departures() {
  const { hasPerm } = useAuth();
  const [rows, setRows] = useState(null);
  useEffect(() => { api.get("/departures").then((r) => setRows(r.data)).catch(() => setRows([])); }, []);

  return (
    <div className="space-y-6" data-testid="departures-page">
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900">Departures</h1>
        <p className="text-slate-500 mt-1">Upcoming departures with live seat availability.</p>
      </div>
      {rows === null ? (
        <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
      ) : rows.length === 0 ? (
        <Card className="border-slate-200"><CardContent className="p-12 text-center text-slate-500"><PlaneTakeoff className="h-8 w-8 mx-auto text-slate-300" aria-hidden="true" /><p className="mt-2">No departures scheduled.</p></CardContent></Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="departures-grid">
          {rows.map((d) => (
            <Card key={d._id} className="border-slate-200 shadow-sm" data-testid={`departure-${d._id}`}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <Badge variant="outline" className="bg-slate-100 text-slate-700">{d.product_type}</Badge>
                  <Badge variant="outline" className={DEP_STATUS_COLORS[d.status] || "bg-slate-100"}>{d.status}</Badge>
                </div>
                <h3 className="font-display font-semibold text-slate-900 mt-2">{d.package_name}</h3>
                <p className="text-xs text-slate-500 flex items-center gap-1 mt-1"><MapPin className="h-3 w-3" aria-hidden="true" />{d.destination}</p>
                <div className="mt-3 text-sm text-slate-600">
                  <p>Depart: <b>{fmtDate(d.departure_date)}</b></p>
                  <p>Return: {fmtDate(d.return_date)}</p>
                </div>
                <div className="flex items-center justify-between mt-3">
                  <span className="text-sm flex items-center gap-1 text-slate-600"><Users className="h-4 w-4" aria-hidden="true" />{d.available_seat} / {d.quota} seats</span>
                  <span className="font-display font-bold text-slate-900">{fmtIDR(d.price)}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
