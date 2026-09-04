import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, CalendarCheck, CheckCircle2, RefreshCw } from "lucide-react";

const rupiah = (n) => {
  if (n == null || isNaN(Number(n))) return "-";
  try { return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(Number(n)); }
  catch { return `Rp ${Number(n || 0).toLocaleString("id-ID")}`; }
};

function StatusBadge({ status }) {
  const map = { issued: "bg-emerald-500", waiting: "bg-amber-500", "expired / cancel": "bg-red-500" };
  return <Badge className={`${map[String(status).toLowerCase()] || "bg-slate-500"} hover:opacity-90`}>{status || "-"}</Badge>;
}

export default function BookingDialog({ open, onClose, hotel, customers, defaultCustomerId }) {
  const { user } = useAuth();
  const canIssue = ["super_admin", "accounting"].includes(user?.role);
  const [customerId, setCustomerId] = useState(defaultCustomerId || "none");
  const [pax, setPax] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [request, setRequest] = useState("");
  const [saving, setSaving] = useState(false);
  const [issuing, setIssuing] = useState(false);
  const [checking, setChecking] = useState(false);
  const [booking, setBooking] = useState(null);   // MMBC response data

  useEffect(() => {
    if (open) {
      setCustomerId(defaultCustomerId || "none");
      setPax(""); setEmail(""); setPhone(""); setRequest(""); setBooking(null);
    }
  }, [open, defaultCustomerId]);

  const hold = async () => {
    if (!pax.trim()) return toast.error("Nama tamu (pax) wajib diisi.");
    if (!hotel?.roomRateKey || !hotel?.hotelKey) return toast.error("Data kamar tidak lengkap untuk booking.");
    setSaving(true);
    try {
      const payload = {
        hotel: {
          hotelId: hotel.hotelId, hotelKey: hotel.hotelKey, roomRateKey: hotel.roomRateKey,
          hotelName: hotel.hotelName, roomName: hotel.roomName, roomtypeName: hotel.roomtypeName,
          boardName: hotel.boardName, cancellation: hotel.cancellation,
          checkInDate: hotel.checkInDate, checkOutDate: hotel.checkOutDate,
          numberOfRooms: hotel.numberOfRooms || 1, numberOfAdults: hotel.numberOfAdults, numberOfChildren: hotel.numberOfChildren,
          dailyRate: hotel.dailyRate, nta: hotel.nta, retail: hotel.retail, markupPct: hotel.markupPct,
          currency: hotel.currency || "IDR", imageURL: hotel.imageURL, source: "MMBC_API",
        },
        paxName: pax.trim(), email: email.trim(), phone: phone.trim(), request: request.trim(),
      };
      if (customerId && customerId !== "none") payload.customer_id = customerId;
      const { data } = await api.post("/hotel/booking/hold", payload);
      setBooking(data.data);
      toast.success("Booking di-hold. Selesaikan pembayaran sebelum time limit.");
    } catch (e) {
      toast.error(formatApiErrorDetail(e?.response?.data?.detail));
    } finally { setSaving(false); }
  };

  const issue = async () => {
    if (!booking?.paymentcode) return;
    setIssuing(true);
    try {
      const { data } = await api.post("/hotel/booking/issue", { paymentcode: booking.paymentcode });
      setBooking(data.data);
      toast.success(`Booking issued. Kode booking: ${data.data?.kodebooking || "-"}`);
    } catch (e) {
      toast.error(formatApiErrorDetail(e?.response?.data?.detail));
    } finally { setIssuing(false); }
  };

  const checkStatus = async () => {
    if (!booking?.paymentcode) return;
    setChecking(true);
    try {
      const { data } = await api.post("/hotel/booking/status", { paymentcode: booking.paymentcode });
      setBooking(data.data);
      toast.success(`Status: ${data.data?.hotel_statusbooking || "-"}`);
    } catch (e) {
      toast.error(formatApiErrorDetail(e?.response?.data?.detail));
    } finally { setChecking(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="hotel-booking-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><CalendarCheck className="h-4 w-4 text-blue-600" />Booking Hotel</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 text-sm">
            <p className="font-semibold text-slate-800">{hotel?.hotelName}</p>
            <p className="text-slate-500 text-xs">{hotel?.roomtypeName}</p>
            <p className="text-slate-500 text-xs">{hotel?.checkInDate} → {hotel?.checkOutDate} · {hotel?.nights || 1} malam · {hotel?.numberOfRooms || 1} kamar</p>
            <p className="text-blue-700 font-bold mt-1">{rupiah(hotel?.sellTotal)} <span className="text-xs font-normal text-slate-400">total</span></p>
          </div>

          {!booking ? (
            <>
              <div className="space-y-1">
                <Label>Customer (opsional)</Label>
                <Select value={customerId} onValueChange={setCustomerId}>
                  <SelectTrigger data-testid="booking-customer-select"><SelectValue placeholder="Tanpa customer" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Tanpa customer</SelectItem>
                    {(customers || []).map((c) => <SelectItem key={c._id} value={c._id}>{c.full_name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label>Nama Tamu (Pax)</Label>
                <Input value={pax} onChange={(e) => setPax(e.target.value)} placeholder="mis. Mr. Ahmad Fauzi" data-testid="booking-pax" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1"><Label>Email</Label><Input value={email} onChange={(e) => setEmail(e.target.value)} data-testid="booking-email" /></div>
                <div className="space-y-1"><Label>Telepon</Label><Input value={phone} onChange={(e) => setPhone(e.target.value)} data-testid="booking-phone" /></div>
              </div>
              <div className="space-y-1">
                <Label>Permintaan Khusus</Label>
                <Textarea value={request} onChange={(e) => setRequest(e.target.value)} rows={2} placeholder="mis. non-smoking, twin bed…" data-testid="booking-request" />
              </div>
            </>
          ) : (
            <div className="space-y-2 text-sm" data-testid="booking-result">
              <div className="flex items-center justify-between"><span className="text-slate-500">Status</span><StatusBadge status={booking.hotel_statusbooking} /></div>
              <div className="flex items-center justify-between"><span className="text-slate-500">Payment Code</span><span className="font-mono font-semibold">{booking.paymentcode}</span></div>
              {booking.kodebooking ? <div className="flex items-center justify-between"><span className="text-slate-500">Kode Booking</span><span className="font-mono font-semibold">{booking.kodebooking}</span></div> : null}
              <div className="flex items-center justify-between"><span className="text-slate-500">Time Limit</span><span>{booking.hotel_timelimit || "-"}</span></div>
              <div className="flex items-center justify-between"><span className="text-slate-500">Total Fare</span><span className="font-semibold">{rupiah(booking.hotel_totalfare)}</span></div>
              <p className="text-[11px] text-slate-400 pt-1">Selesaikan pembayaran (Issue) sebelum time limit agar booking tidak batal.</p>
            </div>
          )}
        </div>
        <DialogFooter className="gap-2">
          {!booking ? (
            <Button onClick={hold} disabled={saving} data-testid="booking-hold-submit">
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CalendarCheck className="h-4 w-4 mr-2" />}Hold Booking
            </Button>
          ) : (
            <>
              <Button variant="outline" onClick={checkStatus} disabled={checking} data-testid="booking-check-status">
                {checking ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}Cek Status
              </Button>
              {canIssue && String(booking.hotel_statusbooking).toLowerCase() !== "issued" && (
                <Button onClick={issue} disabled={issuing} data-testid="booking-issue-submit">
                  {issuing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CheckCircle2 className="h-4 w-4 mr-2" />}Issue / Bayar
                </Button>
              )}
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
