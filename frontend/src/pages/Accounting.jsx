import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { API } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { fmtIDR } from "@/config/crm";
import { INVOICE_STATUS_COLORS } from "@/config/phase4";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, FileText } from "lucide-react";

const HEAD = "bg-blue-600 text-white font-semibold text-xs uppercase tracking-wide border-r border-blue-500/40 last:border-r-0";
const CELL = "border-r border-slate-100 last:border-r-0";
const ROW = "odd:bg-white even:bg-slate-50 hover:bg-blue-50/60 border-b border-slate-200";

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
  const Spin = () => <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;

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
          {invoices === null ? <Spin />
            : invoices.length === 0 ? <Empty text="Belum ada invoice." />
            : (
              <Card className="border-slate-200 shadow-sm overflow-hidden">
                <Table data-testid="invoices-list">
                  <TableHeader><TableRow className="hover:bg-transparent">
                    <TableHead className={HEAD}>Invoice</TableHead><TableHead className={HEAD}>Customer</TableHead>
                    <TableHead className={HEAD}>Package</TableHead><TableHead className={HEAD}>Due</TableHead>
                    <TableHead className={`${HEAD} text-right`}>Total</TableHead><TableHead className={`${HEAD} text-right`}>Sisa</TableHead>
                    <TableHead className={HEAD}>Status</TableHead><TableHead className={`${HEAD} text-right`}>Aksi</TableHead>
                  </TableRow></TableHeader>
                  <TableBody>
                    {invoices.map((inv) => (
                      <TableRow key={inv._id} className={ROW} data-testid={`acc-invoice-${inv._id}`}>
                        <TableCell className={`${CELL} font-mono text-xs`}>{inv.invoice_number}</TableCell>
                        <TableCell className={`${CELL} font-medium text-slate-900`}>{inv.customer_name}</TableCell>
                        <TableCell className={`${CELL} text-slate-500`}>{inv.package_name}</TableCell>
                        <TableCell className={CELL}>{inv.due_date || "—"}</TableCell>
                        <TableCell className={`${CELL} text-right font-semibold`}>{fmtIDR(inv.total)}</TableCell>
                        <TableCell className={`${CELL} text-right text-red-600`}>{fmtIDR(inv.outstanding)}</TableCell>
                        <TableCell className={CELL}><Badge variant="outline" className={INVOICE_STATUS_COLORS[inv.status]}>{inv.status}</Badge></TableCell>
                        <TableCell className={`${CELL} text-right whitespace-nowrap`}>
                          <Button size="sm" variant="outline" className="mr-1" onClick={() => openPdf(inv._id)}><FileText className="h-4 w-4" /></Button>
                          <Button size="sm" variant="outline" onClick={() => navigate(`/booking/${inv.booking_id}`)}>Booking</Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            )}
        </TabsContent>

        {canRec && (
          <TabsContent value="receivables">
            {!rec ? <Spin /> : (
              <div className="space-y-4" data-testid="receivables-panel">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <Kpi label="Total Invoice" v={rec.total_invoice} tone="blue" />
                  <Kpi label="Total Payment" v={rec.total_payment} tone="green" />
                  <Kpi label="Outstanding" v={rec.total_outstanding} tone="red" />
                </div>
                <Card className="border-slate-200 shadow-sm overflow-hidden">
                  <Table>
                    <TableHeader><TableRow className="hover:bg-transparent">
                      {Object.keys(rec.aging).map((k) => <TableHead key={k} className={`${HEAD} text-right`}>{k}</TableHead>)}
                    </TableRow></TableHeader>
                    <TableBody><TableRow className="odd:bg-white even:bg-slate-50">
                      {Object.entries(rec.aging).map(([k, v]) => <TableCell key={k} className={`${CELL} text-right font-semibold ${k === "90+" ? "text-red-600" : "text-slate-800"}`}>{fmtIDR(v)}</TableCell>)}
                    </TableRow></TableBody>
                  </Table>
                </Card>
                <Card className="border-slate-200 shadow-sm overflow-hidden">
                  <Table>
                    <TableHeader><TableRow className="hover:bg-transparent">
                      <TableHead className={HEAD}>Invoice</TableHead><TableHead className={HEAD}>Customer</TableHead>
                      <TableHead className={HEAD}>Due</TableHead><TableHead className={`${HEAD} text-right`}>Outstanding</TableHead>
                      <TableHead className={HEAD}>Aging</TableHead>
                    </TableRow></TableHeader>
                    <TableBody>
                      {rec.rows.length === 0 ? <TableRow><TableCell colSpan={5} className="text-center text-slate-400 py-8">Tidak ada outstanding.</TableCell></TableRow>
                        : rec.rows.map((r) => (
                          <TableRow key={r.invoice_id} className={ROW}>
                            <TableCell className={`${CELL} font-mono text-xs`}>{r.invoice_number}</TableCell>
                            <TableCell className={`${CELL} font-medium text-slate-900`}>{r.customer_name}</TableCell>
                            <TableCell className={CELL}>{r.due_date || "—"}</TableCell>
                            <TableCell className={`${CELL} text-right font-semibold text-red-600`}>{fmtIDR(r.outstanding)}</TableCell>
                            <TableCell className={CELL}><Badge variant="outline" className="bg-slate-50 text-slate-700">{r.aging}</Badge></TableCell>
                          </TableRow>
                        ))}
                    </TableBody>
                  </Table>
                </Card>
              </div>
            )}
          </TabsContent>
        )}

        {canRec && (
          <TabsContent value="reminders">
            {reminders === null ? <Spin />
              : reminders.length === 0 ? <Empty text="Tidak ada reminder hari ini. (Trigger n8n: H-30/H-14/H-7/H-3/DUE/OVERDUE)" />
              : (
                <Card className="border-slate-200 shadow-sm overflow-hidden">
                  <Table data-testid="reminders-list">
                    <TableHeader><TableRow className="hover:bg-transparent">
                      <TableHead className={HEAD}>Invoice</TableHead><TableHead className={HEAD}>Customer</TableHead>
                      <TableHead className={HEAD}>Stage</TableHead><TableHead className={HEAD}>Due</TableHead>
                      <TableHead className={`${HEAD} text-right`}>Outstanding</TableHead>
                    </TableRow></TableHeader>
                    <TableBody>
                      {reminders.map((r) => (
                        <TableRow key={r.invoice_id} className={ROW}>
                          <TableCell className={`${CELL} font-mono text-xs`}>{r.invoice_number}</TableCell>
                          <TableCell className={`${CELL} font-medium text-slate-900`}>{r.customer_name}</TableCell>
                          <TableCell className={CELL}><Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">{r.stage}</Badge></TableCell>
                          <TableCell className={CELL}>{r.due_date}</TableCell>
                          <TableCell className={`${CELL} text-right font-semibold`}>{fmtIDR(r.outstanding)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </Card>
              )}
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

const TONE = { blue: "text-blue-700", green: "text-emerald-600", red: "text-red-600" };
const Kpi = ({ label, v, tone }) => <Card className="border-slate-200 shadow-sm"><CardContent className="p-4"><p className="text-[11px] uppercase text-slate-500">{label}</p><p className={`font-display text-xl font-bold ${TONE[tone] || "text-slate-900"}`}>{fmtIDR(v)}</p></CardContent></Card>;
const Empty = ({ text }) => <Card className="border-slate-200"><CardContent className="p-12 text-center text-slate-500">{text}</CardContent></Card>;
