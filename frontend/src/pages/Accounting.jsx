import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { API } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { fmtIDR, fmtDate } from "@/config/crm";
import { INVOICE_STATUS_COLORS } from "@/config/phase4";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, FileText } from "lucide-react";

export default function Accounting() {
  const { hasPerm } = useAuth();
  const navigate = useNavigate();
  const canInv = hasPerm("invoice.view");
  const canRec = hasPerm("receivable.view");
  const [invoices, setInvoices] = useState(null);
  const [rec, setRec] = useState(null);
  const [reminders, setReminders] = useState(null);
  useEffect(() => {
    if (canInv) api.get("/invoices").then((r) => setInvoices(r.data)).catch(() => setInvoices([]));
    if (canRec) {
      api.get("/receivables").then((r) => setRec(r.data)).catch(() => setRec(null));
      api.get("/payment-reminders").then((r) => setReminders(r.data.reminders)).catch(() => setReminders([]));
    }
  }, [canInv, canRec]);
  const openPdf = (iid) => window.open(`${API}/invoices/${iid}/pdf?auth=${localStorage.getItem("token")}`, "_blank");

  return (
    <div className="space-y-6" data-testid="accounting-page">
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900">Accounting</h1>
        <p className="text-slate-500 mt-1">Invoice, receivable (aging), dan payment reminder.</p>
      </div>
      <Tabs defaultValue="invoices">
        <TabsList>
          <TabsTrigger value="invoices" data-testid="tab-invoices">Invoices</TabsTrigger>
          {canRec && <TabsTrigger value="receivables" data-testid="tab-receivables">Receivables</TabsTrigger>}
          {canRec && <TabsTrigger value="reminders" data-testid="tab-reminders">Reminders</TabsTrigger>}
        </TabsList>

        <TabsContent value="invoices">
          {invoices === null ? <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
            : invoices.length === 0 ? <Card className="border-slate-200"><CardContent className="p-12 text-center text-slate-500">Belum ada invoice.</CardContent></Card>
            : <div className="space-y-2" data-testid="invoices-list">{invoices.map((inv) => (
                <Card key={inv._id} className="border-slate-200" data-testid={`acc-invoice-${inv._id}`}><CardContent className="p-4 flex items-center justify-between flex-wrap gap-3">
                  <div><p className="font-mono text-[11px] text-slate-400">{inv.invoice_number}</p><p className="font-medium text-slate-900">{inv.customer_name}</p><p className="text-xs text-slate-500">{inv.package_name} · jatuh tempo {inv.due_date || "—"}</p></div>
                  <div className="text-right"><p className="font-semibold">{fmtIDR(inv.total)}</p><p className="text-xs text-slate-400">Sisa {fmtIDR(inv.outstanding)}</p></div>
                  <div className="flex items-center gap-2"><Badge variant="outline" className={INVOICE_STATUS_COLORS[inv.status]}>{inv.status}</Badge>
                    <Button size="sm" variant="outline" onClick={() => openPdf(inv._id)}><FileText className="h-4 w-4 mr-1" />PDF</Button>
                    <Button size="sm" variant="outline" onClick={() => navigate(`/booking/${inv.booking_id}`)}>Open Booking</Button></div>
                </CardContent></Card>))}</div>}
        </TabsContent>

        {canRec && (
          <TabsContent value="receivables">
            {!rec ? <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div> : (
              <div className="space-y-4" data-testid="receivables-panel">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <Kpi label="Total Invoice" v={rec.total_invoice} /><Kpi label="Total Payment" v={rec.total_payment} />
                  <Kpi label="Outstanding" v={rec.total_outstanding} accent />
                  <Kpi label="Overdue (90+)" v={rec.aging["90+"]} />
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  {Object.entries(rec.aging).map(([k, v]) => <Card key={k} className="border-slate-200"><CardContent className="p-3"><p className="text-[11px] uppercase text-slate-500">{k}</p><p className="font-semibold text-slate-900">{fmtIDR(v)}</p></CardContent></Card>)}
                </div>
                <div className="space-y-2">{rec.rows.map((r) => (
                  <Card key={r.invoice_id} className="border-slate-200"><CardContent className="p-3 flex items-center justify-between flex-wrap gap-2">
                    <div><p className="font-mono text-[11px] text-slate-400">{r.invoice_number}</p><p className="font-medium text-slate-900">{r.customer_name}</p></div>
                    <p className="text-sm text-slate-500">Due {r.due_date || "—"}</p>
                    <p className="font-semibold text-red-600">{fmtIDR(r.outstanding)}</p>
                    <Badge variant="outline" className="bg-slate-50 text-slate-700">{r.aging}</Badge>
                  </CardContent></Card>))}</div>
              </div>
            )}
          </TabsContent>
        )}

        {canRec && (
          <TabsContent value="reminders">
            {reminders === null ? <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
              : reminders.length === 0 ? <Card className="border-slate-200"><CardContent className="p-12 text-center text-slate-500">Tidak ada reminder untuk hari ini. (Trigger untuk n8n: H-30/H-14/H-7/H-3/DUE/OVERDUE)</CardContent></Card>
              : <div className="space-y-2" data-testid="reminders-list">{reminders.map((r) => (
                  <Card key={r.invoice_id} className="border-slate-200"><CardContent className="p-3 flex items-center justify-between flex-wrap gap-2">
                    <div><p className="font-mono text-[11px] text-slate-400">{r.invoice_number}</p><p className="font-medium text-slate-900">{r.customer_name}</p></div>
                    <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">{r.stage}</Badge>
                    <p className="text-sm text-slate-500">Due {r.due_date}</p><p className="font-semibold">{fmtIDR(r.outstanding)}</p>
                  </CardContent></Card>))}</div>}
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

const Kpi = ({ label, v, accent }) => <Card className="border-slate-200"><CardContent className="p-4"><p className="text-[11px] uppercase text-slate-500">{label}</p><p className={`font-display text-xl font-bold ${accent ? "text-red-600" : "text-slate-900"}`}>{fmtIDR(v)}</p></CardContent></Card>;
