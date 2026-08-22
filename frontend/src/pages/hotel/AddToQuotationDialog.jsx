import { useEffect, useMemo, useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Hotel } from "lucide-react";

const rupiah = (n, cur) => {
  if (n == null || isNaN(Number(n))) return "-";
  try { return new Intl.NumberFormat("id-ID", { style: "currency", currency: cur || "IDR", maximumFractionDigits: 0 }).format(Number(n)); }
  catch { return `${cur || ""} ${Number(n).toLocaleString("id-ID")}`; }
};
const nightsBetween = (ci, co) => {
  try { return Math.max(Math.round((new Date(co) - new Date(ci)) / 86400000), 0); } catch { return 0; }
};

export default function AddToQuotationDialog({ open, onClose, hotel, searchCtx, customers, defaultCustomerId, onDone }) {
  const [mode, setMode] = useState("existing"); // existing | new
  const [customerId, setCustomerId] = useState(defaultCustomerId || "");
  const [nc, setNc] = useState({ full_name: "", whatsapp: "", email: "" });
  const [rooms, setRooms] = useState(1);
  const [target, setTarget] = useState("new"); // "new" | quotationId
  const [quotations, setQuotations] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setCustomerId(defaultCustomerId || "");
      setMode(defaultCustomerId ? "existing" : "existing");
      setTarget("new");
      setRooms(1);
      setNc({ full_name: "", whatsapp: "", email: "" });
      api.get("/quotations").then((r) => setQuotations(r.data || [])).catch(() => {});
    }
  }, [open, defaultCustomerId]);

  const custQuotations = useMemo(
    () => (quotations || []).filter((q) => q.customer_id === customerId && ["DRAFT", "SENT"].includes(q.status) && !q.converted_booking_id),
    [quotations, customerId]
  );

  const nights = nightsBetween(searchCtx?.checkInDate, searchCtx?.checkOutDate);
  const total = Number(hotel?.dailyRate || 0) * nights * Number(rooms || 1);

  const submit = async () => {
    if (mode === "existing" && !customerId) return toast.error("Pilih customer.");
    if (mode === "new" && !nc.full_name.trim()) return toast.error("Isi nama customer baru.");
    if (nights <= 0) return toast.error("Rentang tanggal tidak valid.");
    setSaving(true);
    try {
      const payload = {
        sales_pic_id: null,
        hotel: {
          hotelId: hotel.hotelId, hotelName: hotel.hotelName, roomtypeName: hotel.roomtypeName,
          checkInDate: searchCtx.checkInDate, checkOutDate: searchCtx.checkOutDate, numberOfRooms: Number(rooms) || 1,
          numberOfAdults: Number(searchCtx.adults) || 1, numberOfChildren: Number(searchCtx.children) || 0,
          currency: hotel.currency || searchCtx.currency || "IDR", dailyRate: Number(hotel.dailyRate) || 0,
          crossedOutRate: hotel.crossedOutRate, discountPercentage: hotel.discountPercentage,
          landingURL: hotel.landingURL, imageURL: hotel.imageURL,
          includeBreakfast: hotel.includeBreakfast, freeWifi: hotel.freeWifi, source: "AGODA_API",
        },
      };
      if (mode === "new") payload.new_customer = nc; else payload.customer_id = customerId;
      if (target !== "new") payload.quotation_id = target;
      const { data } = await api.post("/hotel/add-to-quotation", payload);
      toast.success(`Hotel ditambahkan ke Quotation ${data.quotation_number}`);
      onDone?.(data);
      onClose();
    } catch (e) {
      toast.error(formatApiErrorDetail(e?.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-lg" data-testid="hotel-addquote-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2"><Hotel className="h-4 w-4 text-blue-600" />Tambah ke Quotation</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 text-sm">
            <p className="font-semibold text-slate-800">{hotel?.hotelName}</p>
            <p className="text-slate-500 text-xs">{searchCtx?.checkInDate} → {searchCtx?.checkOutDate} · {nights} malam</p>
          </div>

          <div className="flex gap-2">
            <Button size="sm" variant={mode === "existing" ? "default" : "outline"} onClick={() => setMode("existing")} data-testid="addquote-mode-existing">Customer Existing</Button>
            <Button size="sm" variant={mode === "new" ? "default" : "outline"} onClick={() => setMode("new")} data-testid="addquote-mode-new">Customer Baru</Button>
          </div>

          {mode === "existing" ? (
            <div className="space-y-1">
              <Label>Customer</Label>
              <Select value={customerId} onValueChange={setCustomerId}>
                <SelectTrigger data-testid="addquote-customer-select"><SelectValue placeholder="Pilih customer" /></SelectTrigger>
                <SelectContent>{(customers || []).map((c) => <SelectItem key={c._id} value={c._id}>{c.full_name}{c.whatsapp ? ` · ${c.whatsapp}` : ""}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1 col-span-2"><Label>Nama Lengkap</Label><Input value={nc.full_name} onChange={(e) => setNc((f) => ({ ...f, full_name: e.target.value }))} data-testid="addquote-new-name" /></div>
              <div className="space-y-1"><Label>WhatsApp</Label><Input value={nc.whatsapp} onChange={(e) => setNc((f) => ({ ...f, whatsapp: e.target.value }))} data-testid="addquote-new-wa" /></div>
              <div className="space-y-1"><Label>Email</Label><Input value={nc.email} onChange={(e) => setNc((f) => ({ ...f, email: e.target.value }))} data-testid="addquote-new-email" /></div>
              <p className="col-span-2 text-[11px] text-slate-400">Jika WhatsApp/nama cocok dengan customer yang ada, sistem memakai customer tersebut (tidak duplikat).</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Jumlah Kamar</Label>
              <Input type="number" min="1" value={rooms} onChange={(e) => setRooms(e.target.value)} data-testid="addquote-rooms" />
            </div>
            <div className="space-y-1">
              <Label>Quotation Tujuan</Label>
              <Select value={target} onValueChange={setTarget}>
                <SelectTrigger data-testid="addquote-target-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="new">Buat Quotation Baru</SelectItem>
                  {custQuotations.map((q) => <SelectItem key={q._id} value={q._id}>{q.quotation_number} ({q.status})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm flex items-center justify-between">
            <span className="text-slate-600">{rupiah(hotel?.dailyRate, hotel?.currency)} × {nights} mlm × {rooms} kmr</span>
            <span className="font-bold text-blue-700" data-testid="addquote-total">{rupiah(total, hotel?.currency)}</span>
          </div>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={saving} data-testid="addquote-submit">
            {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}Tambah ke Quotation
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
