import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { fmtIDR, fmtDate } from "@/config/crm";
import { BOOKING_STATUS_COLORS } from "@/config/phase4";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, CalendarCheck } from "lucide-react";

const HEAD = "bg-blue-600 text-white font-semibold text-xs uppercase tracking-wide border-r border-blue-500/40 last:border-r-0";
const CELL = "border-r border-slate-100 last:border-r-0 align-middle";
const ROW = "odd:bg-white even:bg-slate-50 hover:bg-blue-50/60 border-b border-slate-200 cursor-pointer";

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
                  <div className="flex items-center gap-2">
                    {b.booking_source === "AUTO SALES" && (
                      <Badge className="bg-violet-600 text-white border-violet-600" data-testid={`auto-sales-badge-${b._id}`}>AUTO SALES</Badge>
                    )}
                    <Badge variant="outline" className={BOOKING_STATUS_COLORS[b.status] || "bg-slate-100"}>{b.status}</Badge>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
    </div>
  );
}
