import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { fmtIDR, fmtDate } from "@/config/crm";
import { BOOKING_STATUS_COLORS } from "@/config/phase4";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, CalendarCheck } from "lucide-react";

export default function Bookings() {
  const navigate = useNavigate();
  const [rows, setRows] = useState(null);
  useEffect(() => { api.get("/bookings").then((r) => setRows(r.data)).catch(() => setRows([])); }, []);

  return (
    <div className="space-y-6" data-testid="bookings-page">
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900">Booking</h1>
        <p className="text-slate-500 mt-1">Kelola booking, jamaah, dokumen, invoice, dan pembayaran.</p>
      </div>
      {rows === null ? <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
        : rows.length === 0 ? <Card className="border-slate-200"><CardContent className="p-12 text-center text-slate-500"><CalendarCheck className="h-8 w-8 mx-auto text-slate-300" />Belum ada booking. Konversi quotation yang accepted.</CardContent></Card>
        : (
          <div className="space-y-3" data-testid="bookings-list">
            {rows.map((b) => (
              <Card key={b._id} onClick={() => navigate(`/booking/${b._id}`)} className="border-slate-200 shadow-sm hover:shadow-md cursor-pointer" data-testid={`booking-row-${b._id}`}>
                <CardContent className="p-4 flex items-center justify-between flex-wrap gap-3">
                  <div>
                    <p className="font-mono text-[11px] text-slate-400">{b.booking_number} · v{b.package_version}</p>
                    <p className="font-semibold text-slate-900">{b.customer_name}</p>
                    <p className="text-sm text-slate-500">{b.package_name} · {b.pax} pax · {b.booking_source}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-display text-lg font-bold text-slate-900">{fmtIDR(b.total)}</p>
                    <p className="text-xs text-slate-400">{fmtDate(b.created_at)}</p>
                  </div>
                  <Badge variant="outline" className={BOOKING_STATUS_COLORS[b.status] || "bg-slate-100"}>{b.status}</Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
    </div>
  );
}
