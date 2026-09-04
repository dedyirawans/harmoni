import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, RefreshCw, CheckCircle2, Hotel } from "lucide-react";

const rupiah = (n) => {
  if (n == null || isNaN(Number(n))) return "-";
  try { return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(Number(n)); }
  catch { return `Rp ${Number(n || 0).toLocaleString("id-ID")}`; }
};

function StatusBadge({ status }) {
  const map = { issued: "bg-emerald-500", waiting: "bg-amber-500", "expired / cancel": "bg-red-500" };
  return <Badge className={`${map[String(status).toLowerCase()] || "bg-slate-500"} hover:opacity-90`}>{status || "-"}</Badge>;
}

export default function HotelBookings() {
  const { user } = useAuth();
  const canIssue = ["super_admin", "accounting"].includes(user?.role);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");

  const load = () => { setLoading(true); api.get("/hotel/bookings").then((r) => setRows(r.data || [])).catch(() => {}).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  const act = async (code, kind) => {
    setBusy(code + kind);
    try {
      const { data } = await api.post(`/hotel/booking/${kind}`, { paymentcode: code });
      toast.success(kind === "issue" ? `Issued: ${data.data?.kodebooking || "-"}` : `Status: ${data.data?.hotel_statusbooking || "-"}`);
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e?.response?.data?.detail));
    } finally { setBusy(""); }
  };

  if (loading) return <p className="text-sm text-slate-400 py-8 text-center">Memuat booking…</p>;

  return (
    <div className="space-y-3" data-testid="hotel-bookings">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-600">{rows.length} booking</p>
        <Button size="sm" variant="outline" onClick={load}><RefreshCw className="h-3.5 w-3.5 mr-1" />Refresh</Button>
      </div>
      {rows.length === 0 && <div className="flex flex-col items-center py-16 text-slate-400"><Hotel className="h-10 w-10 mb-2 text-slate-300" /><p className="text-sm">Belum ada booking hotel.</p></div>}
      <div className="grid grid-cols-1 gap-3">
        {rows.map((b) => (
          <Card key={b._id} className="border-slate-200" data-testid={`booking-row-${b.payment_code}`}>
            <CardContent className="p-4 flex flex-wrap items-center gap-4 justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-2"><p className="font-semibold text-slate-800 text-sm">{b.hotel_name || b.hotel_snapshot?.hotelName}</p><StatusBadge status={b.status} /></div>
                <p className="text-xs text-slate-500">{b.room_name || b.hotel_snapshot?.roomName} · {b.checkin || b.hotel_snapshot?.checkInDate} → {b.checkout || b.hotel_snapshot?.checkOutDate}</p>
                <p className="text-xs text-slate-400">Pax: {b.pax_name} · PC: <span className="font-mono">{b.payment_code}</span>{b.kodebooking ? ` · Kode: ${b.kodebooking}` : ""}</p>
              </div>
              <div className="text-right">
                <p className="font-bold text-blue-600">{rupiah(b.totalfare || b.hotel_snapshot?.total)}</p>
                <p className="text-[11px] text-slate-400">Time limit: {b.timelimit || "-"}</p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={busy === b.payment_code + "status"} onClick={() => act(b.payment_code, "status")} data-testid={`booking-status-${b.payment_code}`}>
                  {busy === b.payment_code + "status" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                </Button>
                {canIssue && String(b.status).toLowerCase() !== "issued" && (
                  <Button size="sm" disabled={busy === b.payment_code + "issue"} onClick={() => act(b.payment_code, "issue")} data-testid={`booking-issue-${b.payment_code}`}>
                    {busy === b.payment_code + "issue" ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5 mr-1" />}Issue
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
