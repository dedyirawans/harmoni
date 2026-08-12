import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import portalApi from "@/lib/portalApi";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, Plane, LogOut, User, CalendarCheck, Receipt, FileText, Wallet, RotateCcw, MapPin } from "lucide-react";
import { toast } from "sonner";

const idr = (n) => "Rp " + Number(n || 0).toLocaleString("id-ID");
const dt = (s) => (s ? new Date(s).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" }) : "—");
const SCHED = { PAID: "bg-emerald-50 text-emerald-700 border-emerald-200", PARTIAL: "bg-amber-50 text-amber-700 border-amber-200", OVERDUE: "bg-red-50 text-red-700 border-red-200", PENDING: "bg-slate-100 text-slate-500 border-slate-200", CANCELLED: "bg-slate-100 text-slate-400 border-slate-200" };
const BST = { CONFIRMED: "bg-blue-50 text-blue-700 border-blue-200", COMPLETED: "bg-emerald-50 text-emerald-700 border-emerald-200", CANCELLED: "bg-red-50 text-red-700 border-red-200", READY: "bg-indigo-50 text-indigo-700 border-indigo-200" };

export default function PortalDashboard() {
  const navigate = useNavigate();
  const [d, setD] = useState(null);

  const logout = useCallback(() => { localStorage.removeItem("portal_token"); navigate("/portal/login"); }, [navigate]);

  useEffect(() => {
    if (!localStorage.getItem("portal_token")) { navigate("/portal/login"); return; }
    portalApi.get("/portal/dashboard").then((r) => setD(r.data)).catch((e) => {
      if (e.response?.status === 401) { toast.error("Sesi berakhir, silакан login lagi"); logout(); }
      else { toast.error("Gagal memuat data"); setD(false); }
    });
  }, [navigate, logout]);

  if (d === null) return <div className="min-h-screen bg-slate-50 flex items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  if (d === false) return <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-400">Gagal memuat data.</div>;

  const p = d.profile, s = d.summary;
  return (
    <div className="min-h-screen bg-slate-50" data-testid="portal-dashboard">
      <header className="bg-slate-900 text-white">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-amber-400"><Plane className="h-5 w-5" /><span className="font-display font-bold text-white">Safar Customer Portal</span></div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-300 hidden sm:block">{p.full_name}</span>
            <Button size="sm" variant="outline" onClick={logout} className="bg-transparent text-white border-slate-600 hover:bg-slate-800" data-testid="portal-logout"><LogOut className="h-4 w-4 mr-1" />Keluar</Button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {/* Profile + summary */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card className="border-slate-200" data-testid="portal-profile">
            <CardHeader className="pb-2"><CardTitle className="text-base font-display flex items-center gap-2"><User className="h-4 w-4 text-blue-600" />Profil</CardTitle></CardHeader>
            <CardContent className="text-sm space-y-1">
              <p className="font-semibold text-slate-900">{p.full_name}</p>
              <p className="text-slate-500">{p.customer_code} · {p.customer_type || "—"}</p>
              <p className="text-slate-600">{p.email || "—"}</p>
              <p className="text-slate-600">{p.whatsapp || p.phone || "—"}</p>
              <p className="text-slate-500">{p.city || ""}</p>
            </CardContent>
          </Card>
          <Card className="border-slate-200 lg:col-span-2" data-testid="portal-summary">
            <CardHeader className="pb-2"><CardTitle className="text-base font-display flex items-center gap-2"><Wallet className="h-4 w-4 text-emerald-600" />Ringkasan Pembayaran</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div><p className="text-xs text-slate-400">Total</p><p className="text-lg font-bold text-slate-900" data-testid="sum-total">{idr(s.total)}</p></div>
              <div><p className="text-xs text-slate-400">Paid</p><p className="text-lg font-bold text-emerald-600" data-testid="sum-paid">{idr(s.paid)}</p></div>
              <div><p className="text-xs text-slate-400">Outstanding</p><p className="text-lg font-bold text-red-600" data-testid="sum-outstanding">{idr(s.outstanding)}</p></div>
              <div><p className="text-xs text-slate-400">Jatuh Tempo Berikutnya</p><p className="text-sm font-semibold text-slate-900" data-testid="sum-nextdue">{s.next_due ? `${dt(s.next_due.date)} · ${idr(s.next_due.amount)}` : "—"}</p></div>
            </CardContent>
          </Card>
        </div>

        {/* Bookings */}
        <Card className="border-slate-200" data-testid="portal-bookings">
          <CardHeader className="pb-2"><CardTitle className="text-base font-display flex items-center gap-2"><CalendarCheck className="h-4 w-4 text-blue-600" />Booking Saya ({d.bookings.length})</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {d.bookings.length === 0 ? <p className="text-sm text-slate-400" data-testid="bookings-empty">Belum ada booking.</p>
              : d.bookings.map((b) => (
                <div key={b.id} className="border border-slate-200 rounded-lg p-4" data-testid={`booking-${b.id}`}>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold text-slate-900">{b.package_name}</p>
                      <p className="text-xs text-slate-500">{b.booking_number} · {b.pax} pax · {b.room_type || "-"}</p>
                      {b.departure && <p className="text-xs text-slate-500 flex items-center gap-1 mt-0.5"><MapPin className="h-3 w-3" />{dt(b.departure.date)} → {dt(b.departure.return_date)} {b.departure.flight ? `· ${b.departure.flight}` : ""}</p>}
                    </div>
                    <div className="text-right">
                      <Badge variant="outline" className={BST[b.status] || "bg-slate-100"}>{b.status}</Badge>
                      <p className="text-sm font-bold text-slate-900 mt-1">{idr(b.total)}</p>
                    </div>
                  </div>
                  {(b.payment_schedule || []).length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs font-medium text-slate-500 mb-1">Jadwal Pembayaran</p>
                      <Table><TableHeader><TableRow className="bg-slate-50"><TableHead>Termin</TableHead><TableHead>Jatuh Tempo</TableHead><TableHead className="text-right">Tagihan</TableHead><TableHead className="text-right">Dibayar</TableHead><TableHead className="text-right">Sisa</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
                        <TableBody>{b.payment_schedule.map((it, i) => (
                          <TableRow key={i}>
                            <TableCell className="text-slate-700">{it.label || `Termin ${it.payment_number || i + 1}`}</TableCell>
                            <TableCell className="text-slate-600">{dt(it.due_date)}</TableCell>
                            <TableCell className="text-right">{idr(it.amount)}</TableCell>
                            <TableCell className="text-right text-emerald-600">{idr(it.paid_amount)}</TableCell>
                            <TableCell className="text-right text-red-600">{idr(it.outstanding)}</TableCell>
                            <TableCell><Badge variant="outline" className={SCHED[it.status]}>{it.status}</Badge></TableCell>
                          </TableRow>))}</TableBody></Table>
                    </div>
                  )}
                </div>
              ))}
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Invoices */}
          <Card className="border-slate-200" data-testid="portal-invoices">
            <CardHeader className="pb-2"><CardTitle className="text-base font-display flex items-center gap-2"><Receipt className="h-4 w-4 text-indigo-600" />Invoice ({d.invoices.length})</CardTitle></CardHeader>
            <CardContent>
              {d.invoices.length === 0 ? <p className="text-sm text-slate-400">Belum ada invoice.</p>
                : <Table><TableHeader><TableRow className="bg-slate-50"><TableHead>No.</TableHead><TableHead className="text-right">Total</TableHead><TableHead className="text-right">Sisa</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
                    <TableBody>{d.invoices.map((i) => (
                      <TableRow key={i.id} data-testid={`invoice-${i.id}`}>
                        <TableCell className="text-slate-700">{i.invoice_number || "—"}</TableCell>
                        <TableCell className="text-right">{idr(i.total)}</TableCell>
                        <TableCell className="text-right text-red-600">{idr(i.outstanding)}</TableCell>
                        <TableCell><Badge variant="outline" className={i.outstanding > 0 ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-emerald-50 text-emerald-700 border-emerald-200"}>{i.status || (i.outstanding > 0 ? "UNPAID" : "PAID")}</Badge></TableCell>
                      </TableRow>))}</TableBody></Table>}
            </CardContent>
          </Card>

          {/* Refunds */}
          <Card className="border-slate-200" data-testid="portal-refunds">
            <CardHeader className="pb-2"><CardTitle className="text-base font-display flex items-center gap-2"><RotateCcw className="h-4 w-4 text-amber-600" />Status Refund ({d.refunds.length})</CardTitle></CardHeader>
            <CardContent>
              {d.refunds.length === 0 ? <p className="text-sm text-slate-400">Tidak ada refund.</p>
                : <div className="space-y-2">{d.refunds.map((r, i) => (
                    <div key={i} className="flex items-center justify-between border border-slate-100 rounded-md px-3 py-2" data-testid={`refund-${i}`}>
                      <div><p className="text-sm text-slate-700">{r.refund_number || "Refund"}</p><p className="text-xs text-slate-400">{dt(r.created_at)}</p></div>
                      <div className="text-right"><Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">{r.status}</Badge><p className="text-sm font-medium text-slate-900 mt-0.5">{idr(r.amount)}</p></div>
                    </div>))}</div>}
            </CardContent>
          </Card>
        </div>

        {/* Documents */}
        <Card className="border-slate-200" data-testid="portal-documents">
          <CardHeader className="pb-2"><CardTitle className="text-base font-display flex items-center gap-2"><FileText className="h-4 w-4 text-slate-600" />Dokumen ({d.documents.length})</CardTitle></CardHeader>
          <CardContent>
            {d.documents.length === 0 ? <p className="text-sm text-slate-400">Belum ada dokumen.</p>
              : <div className="flex flex-wrap gap-2">{d.documents.map((doc, i) => (
                  <a key={i} href={doc.file_url || "#"} target="_blank" rel="noreferrer" onClick={(e) => !doc.file_url && e.preventDefault()}
                    className="flex items-center gap-2 border border-slate-200 rounded-lg px-3 py-2 text-sm hover:bg-slate-50" data-testid={`doc-${i}`}>
                    <FileText className="h-4 w-4 text-slate-400" />
                    <span className="text-slate-700">{doc.doc_type}</span>
                    <Badge variant="outline" className={doc.status === "VERIFIED" || doc.status === "COMPLETE" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-500"}>{doc.status || "—"}</Badge>
                  </a>))}</div>}
          </CardContent>
        </Card>

        <p className="text-center text-xs text-slate-400 pb-6">Pembayaran online akan tersedia pada tahap berikutnya.</p>
      </main>
    </div>
  );
}
