import { PageHeader } from "@/components/PageHeader";
import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { fmtIDR, fmtDate } from "@/config/crm";
import { BOOKING_STATUS_COLORS } from "@/config/phase4";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, CalendarCheck, Search, X } from "lucide-react";

const STATUSES = ["all", "DRAFT", "PENDING", "CONFIRMED", "PARTIAL_PAID", "PAID", "READY", "COMPLETED", "CANCELLED", "REFUNDED"];

export default function Bookings() {
  const navigate = useNavigate();
  const [rows, setRows] = useState(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(false);
  const debRef = useRef(null);

  const load = (s, st) => {
    setLoading(true);
    const params = {};
    if (s && s.trim()) params.search = s.trim();
    if (st && st !== "all") params.status = st;
    api.get("/bookings", { params }).then((r) => setRows(r.data)).catch(() => setRows([])).finally(() => setLoading(false));
  };

  useEffect(() => { load("", "all"); }, []);

  // debounce search + status changes
  useEffect(() => {
    if (debRef.current) clearTimeout(debRef.current);
    debRef.current = setTimeout(() => load(search, status), 350);
    return () => debRef.current && clearTimeout(debRef.current);
    // eslint-disable-next-line
  }, [search, status]);

  return (
    <div className="space-y-6" data-testid="bookings-page">
      <PageHeader title="Booking" subtitle="Kelola booking, peserta, dokumen, invoice, dan pembayaran." />

      {/* Search + Filter bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" aria-hidden="true" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Cari nomor booking, nama customer, nomor HP, atau email..."
            className="pl-9 pr-9"
            data-testid="booking-search-input"
          />
          {search && (
            <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600" data-testid="booking-search-clear">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-full sm:w-52" data-testid="booking-status-filter"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-white">
            {STATUSES.map((s) => <SelectItem key={s} value={s}>{s === "all" ? "Semua Status" : s}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {rows === null || loading ? <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
        : rows.length === 0 ? (
          <Card className="border-slate-200"><CardContent className="p-12 text-center text-slate-500" data-testid="bookings-empty">
            <CalendarCheck className="h-8 w-8 mx-auto text-slate-300" />
            {search || status !== "all" ? "Tidak ada booking yang cocok dengan pencarian/filter." : "Belum ada booking. Konversi quotation yang accepted."}
          </CardContent></Card>
        ) : (
          <div className="space-y-3" data-testid="bookings-list">
            {rows.map((b) => (
              <Card key={b._id} onClick={() => navigate(`/booking/${b._id}`)} className="border-slate-200 shadow-sm hover:shadow-md cursor-pointer" data-testid={`booking-row-${b._id}`}>
                <CardContent className="p-4 flex items-center justify-between flex-wrap gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge className="bg-blue-600 text-white border-blue-600 font-mono tracking-wide" data-testid={`booking-number-${b._id}`}>{b.booking_number}</Badge>
                      <span className="text-[11px] text-slate-400">v{b.package_version}</span>
                    </div>
                    <p className="font-semibold text-slate-900 mt-1">{b.customer_name}</p>
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
