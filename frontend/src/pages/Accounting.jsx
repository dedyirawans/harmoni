import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api, { API, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { fmtIDR } from "@/config/crm";
import { INVOICE_STATUS_COLORS } from "@/config/phase4";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Loader2, FileText, Plus, Trash2, Pencil, FileSpreadsheet, FileDown } from "lucide-react";
import { toast } from "sonner";

const HEAD = "bg-blue-600 text-white font-semibold text-xs uppercase tracking-wide border-r border-blue-500/40 last:border-r-0";
const CELL = "border-r border-slate-100 last:border-r-0 align-middle";
const ROW = "odd:bg-white even:bg-slate-50 hover:bg-blue-50/60 border-b border-slate-200";
const EXP_CATS = ["Flight", "Hotel", "Visa", "Transport", "Guide", "Marketing", "Commission", "Operational", "Refund", "Other"];
const TAX_TYPES = ["PPN", "PPh", "OTHER"];
const TAX_BASES = ["SELLING_PRICE", "TOUR_PORTION", "DPP", "CUSTOM"];
const TREATMENTS = ["NON_TAXABLE", "PPN_TERTENTU", "PPN_STANDARD", "CUSTOM_TAX", "UMRAH_MURNI", "UMRAH_PLUS"];

export default function Accounting() {
  const { hasPerm } = useAuth();
  const navigate = useNavigate();
  const canRec = hasPerm("receivable.view");
  const canTax = hasPerm("tax.view");
  const canTaxMng = hasPerm("tax.manage");
  const canExp = hasPerm("expense.view");
  const canHpp = hasPerm("hpp.view");
  const token = localStorage.getItem("token");
  const [rev, setRev] = useState(null);
  const [invoices, setInvoices] = useState(null);
  const [rec, setRec] = useState(null);
  const [expenses, setExpenses] = useState([]);
  const [refunds, setRefunds] = useState([]);
  const [hpp, setHpp] = useState(null);
  const [taxM, setTaxM] = useState([]);
  const [taxRep, setTaxRep] = useState(null);
  const [expDlg, setExpDlg] = useState(false);
  const [refDlg, setRefDlg] = useState(false);
  const [taxDlg, setTaxDlg] = useState(null);

  const loadExp = useCallback(() => { if (canExp) api.get("/expenses").then((r) => setExpenses(r.data)).catch(() => {}); }, [canExp]);
  const loadRef = useCallback(() => { if (canExp) api.get("/refunds").then((r) => setRefunds(r.data)).catch(() => {}); }, [canExp]);
  const loadTax = useCallback(() => { if (canTax) api.get("/tax-masters").then((r) => setTaxM(r.data)).catch(() => {}); }, [canTax]);

  useEffect(() => {
    api.get("/reports/revenue").then((r) => setRev(r.data)).catch(() => setRev(null));
    api.get("/invoices").then((r) => setInvoices(r.data)).catch(() => setInvoices([]));
    if (canRec) api.get("/receivables").then((r) => setRec(r.data)).catch(() => {});
    if (canHpp) api.get("/reports/hpp").then((r) => setHpp(r.data)).catch(() => {});
    if (canTax) api.get("/reports/tax").then((r) => setTaxRep(r.data)).catch(() => {});
    loadExp(); loadRef(); loadTax();
  }, [canRec, canHpp, canTax, loadExp, loadRef, loadTax]);

  const openPdf = (iid) => window.open(`${API}/invoices/${iid}/pdf?auth=${token}`, "_blank");
  const exportUrl = (name, fmt) => `${API}/reports/${name}/export?format=${fmt}&auth=${token}`;

  return (
    <div className="space-y-6" data-testid="accounting-page">
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900">Accounting Workspace</h1>
        <p className="text-slate-500 mt-1">Revenue, invoice, receivable, expense, refund, HPP, pajak & laporan.</p>
      </div>
      <Tabs defaultValue="dashboard">
        <TabsList className="flex-wrap h-auto">
          <TabsTrigger value="dashboard" data-testid="tab-dashboard">Dashboard</TabsTrigger>
          <TabsTrigger value="invoices" data-testid="tab-invoices">Invoice</TabsTrigger>
          {canRec && <TabsTrigger value="receivables" data-testid="tab-receivables">Receivable</TabsTrigger>}
          {canExp && <TabsTrigger value="expense" data-testid="tab-expense">Expense</TabsTrigger>}
          {canExp && <TabsTrigger value="refund" data-testid="tab-refund">Refund</TabsTrigger>}
          {canHpp && <TabsTrigger value="hpp" data-testid="tab-hpp">HPP</TabsTrigger>}
          {canTax && <TabsTrigger value="tax" data-testid="tab-tax">Tax</TabsTrigger>}
          <TabsTrigger value="reports" data-testid="tab-reports">Reports</TabsTrigger>
        </TabsList>

        <TabsContent value="dashboard">
          {!rev ? <Spin /> : (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="revenue-cards">
              <Kpi label="Gross Sales" v={rev.summary.gross_sales} tone="blue" />
              <Kpi label="Discount" v={rev.summary.discount} tone="amber" />
              <Kpi label="Net Sales" v={rev.summary.net_sales} tone="blue" />
              <Kpi label="Tax" v={rev.summary.tax} tone="violet" />
              <Kpi label="Revenue" v={rev.summary.revenue} tone="green" />
              <Kpi label="Cost" v={rev.summary.cost} tone="red" />
              <Kpi label="Gross Profit" v={rev.summary.gross_profit} tone="green" />
              <Kpi label="Gross Margin" v={`${rev.summary.gross_margin}%`} tone="blue" raw />
            </div>
          )}
        </TabsContent>

        <TabsContent value="invoices">
          {invoices === null ? <Spin /> : invoices.length === 0 ? <Empty text="Belum ada invoice." /> : (
            <TableCard testid="invoices-list" cols={["Invoice", "Customer", "Package", "Due", "Total", "Sisa", "Status", "Aksi"]}>
              {invoices.map((inv) => (
                <TableRow key={inv._id} className={ROW} data-testid={`acc-invoice-${inv._id}`}>
                  <TableCell className={`${CELL} font-mono text-xs`}>{inv.invoice_number}</TableCell>
                  <TableCell className={`${CELL} font-medium`}>{inv.customer_name}</TableCell>
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
            </TableCard>
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
                <TableCard cols={Object.keys(rec.aging)}>
                  <TableRow className="odd:bg-white even:bg-slate-50">
                    {Object.entries(rec.aging).map(([k, v]) => <TableCell key={k} className={`${CELL} text-right font-semibold ${k === "90+" ? "text-red-600" : ""}`}>{fmtIDR(v)}</TableCell>)}
                  </TableRow>
                </TableCard>
                <TableCard cols={["Invoice", "Customer", "Due", "Outstanding", "Aging"]}>
                  {rec.rows.length === 0 ? <TableRow><TableCell colSpan={5} className="text-center text-slate-400 py-6">Tidak ada outstanding.</TableCell></TableRow>
                    : rec.rows.map((r) => (
                      <TableRow key={r.invoice_id} className={ROW}>
                        <TableCell className={`${CELL} font-mono text-xs`}>{r.invoice_number}</TableCell>
                        <TableCell className={`${CELL} font-medium`}>{r.customer_name}</TableCell>
                        <TableCell className={CELL}>{r.due_date || "—"}</TableCell>
                        <TableCell className={`${CELL} text-right font-semibold text-red-600`}>{fmtIDR(r.outstanding)}</TableCell>
                        <TableCell className={CELL}><Badge variant="outline" className="bg-slate-50 text-slate-700">{r.aging}</Badge></TableCell>
                      </TableRow>
                    ))}
                </TableCard>
              </div>
            )}
          </TabsContent>
        )}

        {canExp && (
          <TabsContent value="expense">
            <div className="mb-3"><Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={() => setExpDlg(true)} data-testid="add-expense-button"><Plus className="h-4 w-4 mr-1" />Tambah Expense</Button></div>
            {expenses.length === 0 ? <Empty text="Belum ada expense." /> : (
              <TableCard testid="expense-list" cols={["Date", "Category", "Description", "Vendor", "Amount", ""]}>
                {expenses.map((e) => (
                  <TableRow key={e._id} className={ROW} data-testid={`expense-${e._id}`}>
                    <TableCell className={CELL}>{e.date}</TableCell>
                    <TableCell className={CELL}><Badge variant="outline" className="bg-blue-50 text-blue-700">{e.category}</Badge></TableCell>
                    <TableCell className={`${CELL} text-slate-500`}>{e.description}</TableCell>
                    <TableCell className={CELL}>{e.vendor}</TableCell>
                    <TableCell className={`${CELL} text-right font-semibold`}>{fmtIDR(e.amount)}</TableCell>
                    <TableCell className={`${CELL} text-right`}><Button size="icon" variant="ghost" className="text-red-600" onClick={() => api.delete(`/expenses/${e._id}`).then(loadExp)}><Trash2 className="h-4 w-4" /></Button></TableCell>
                  </TableRow>
                ))}
              </TableCard>
            )}
          </TabsContent>
        )}

        {canExp && (
          <TabsContent value="refund">
            <div className="mb-3"><Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={() => setRefDlg(true)} data-testid="add-refund-button"><Plus className="h-4 w-4 mr-1" />Tambah Refund</Button></div>
            {refunds.length === 0 ? <Empty text="Belum ada refund." /> : (
              <TableCard testid="refund-list" cols={["Date", "Customer", "Reason", "Method", "Amount", "Status"]}>
                {refunds.map((r) => (
                  <TableRow key={r._id} className={ROW} data-testid={`refund-${r._id}`}>
                    <TableCell className={CELL}>{r.date}</TableCell>
                    <TableCell className={`${CELL} font-medium`}>{r.customer_name}</TableCell>
                    <TableCell className={`${CELL} text-slate-500`}>{r.reason}</TableCell>
                    <TableCell className={CELL}>{r.method}</TableCell>
                    <TableCell className={`${CELL} text-right font-semibold`}>{fmtIDR(r.amount)}</TableCell>
                    <TableCell className={CELL}><Badge variant="outline" className="bg-amber-50 text-amber-700">{r.status}</Badge></TableCell>
                  </TableRow>
                ))}
              </TableCard>
            )}
          </TabsContent>
        )}

        {canHpp && (
          <TabsContent value="hpp">
            <div className="mb-3 flex gap-2"><ExportBtns urls={{ x: exportUrl("hpp", "xlsx"), c: exportUrl("hpp", "csv"), p: exportUrl("hpp", "pdf") }} testid="hpp" /></div>
            {!hpp ? <Spin /> : (
              <TableCard testid="hpp-list" cols={hpp.columns}>
                {hpp.rows.map((r, i) => (
                  <TableRow key={i} className={ROW}>
                    {r.map((c, j) => <TableCell key={j} className={`${CELL} ${j >= 2 ? "text-right" : ""}`}>{j >= 2 ? fmtIDR(c) : c}</TableCell>)}
                  </TableRow>
                ))}
              </TableCard>
            )}
          </TabsContent>
        )}

        {canTax && (
          <TabsContent value="tax">
            <div className="space-y-4">
              {taxRep && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <Kpi label="Taxable Sales" v={taxRep.summary.taxable_sales} tone="blue" />
                  <Kpi label="Non-Taxable" v={taxRep.summary.non_taxable_sales} tone="slate" />
                  <Kpi label="DPP" v={taxRep.summary.dpp} tone="violet" />
                  <Kpi label="Tax Amount" v={taxRep.summary.tax_amount} tone="green" />
                </div>
              )}
              <div className="flex items-center justify-between flex-wrap gap-2">
                <h3 className="font-display font-semibold text-slate-800">Tax Master</h3>
                <div className="flex gap-2">
                  <ExportBtns urls={{ x: exportUrl("tax", "xlsx"), c: exportUrl("tax", "csv"), p: exportUrl("tax", "pdf") }} testid="tax" />
                  {canTaxMng && <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={() => setTaxDlg({})} data-testid="add-tax-button"><Plus className="h-4 w-4 mr-1" />Tax Rate</Button>}
                </div>
              </div>
              <TableCard testid="tax-master-list" cols={["Code", "Name", "Type", "Rate %", "Base", "Treatment", "Effective", "Active", ""]}>
                {taxM.map((t) => (
                  <TableRow key={t._id} className={ROW} data-testid={`tax-row-${t._id}`}>
                    <TableCell className={`${CELL} font-mono text-xs`}>{t.tax_code}</TableCell>
                    <TableCell className={`${CELL} font-medium`}>{t.tax_name}</TableCell>
                    <TableCell className={CELL}>{t.tax_type}</TableCell>
                    <TableCell className={`${CELL} text-right`}>{t.rate}</TableCell>
                    <TableCell className={CELL}>{t.tax_base}</TableCell>
                    <TableCell className={CELL}><Badge variant="outline" className="bg-blue-50 text-blue-700 text-[10px]">{t.treatment}</Badge></TableCell>
                    <TableCell className={`${CELL} text-xs`}>{t.effective_from} → {t.effective_until || "∞"}</TableCell>
                    <TableCell className={CELL}>{t.active ? <Badge variant="outline" className="bg-emerald-50 text-emerald-700">Aktif</Badge> : <Badge variant="outline" className="bg-slate-100 text-slate-500">Off</Badge>}</TableCell>
                    <TableCell className={`${CELL} text-right`}>{canTaxMng && <Button size="icon" variant="ghost" onClick={() => setTaxDlg(t)} data-testid={`tax-edit-${t._id}`}><Pencil className="h-4 w-4" /></Button>}</TableCell>
                  </TableRow>
                ))}
              </TableCard>
            </div>
          </TabsContent>
        )}

        <TabsContent value="reports">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" data-testid="reports-list">
            {[["revenue", "Revenue Report", true], ["receivable", "Receivable Report", canRec], ["expense", "Expense Report", canExp],
              ["profitability", "Profitability Report", true], ["tax", "Tax Report", canTax], ["sales", "Sales Report", true],
              ["hpp", "HPP Report", canHpp]].filter((r) => r[2]).map(([name, label]) => (
              <Card key={name} className="border-slate-200 shadow-sm"><CardContent className="p-4 flex items-center justify-between">
                <span className="font-medium text-slate-800">{label}</span>
                <ExportBtns urls={{ x: exportUrl(name, "xlsx"), c: exportUrl(name, "csv"), p: exportUrl(name, "pdf") }} testid={name} />
              </CardContent></Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      {expDlg && <ExpenseDialog onClose={() => setExpDlg(false)} onSaved={() => { setExpDlg(false); loadExp(); }} />}
      {refDlg && <RefundDialog onClose={() => setRefDlg(false)} onSaved={() => { setRefDlg(false); loadRef(); }} />}
      {taxDlg && <TaxDialog data={taxDlg} onClose={() => setTaxDlg(null)} onSaved={() => { setTaxDlg(null); loadTax(); api.get("/reports/tax").then((r) => setTaxRep(r.data)).catch(() => {}); }} />}
    </div>
  );
}

function TableCard({ cols, children, testid }) {
  const right = (c) => typeof c === "string" && /(Amount|Total|Cost|Profit|Rate|Price|Sisa|Outstanding|Margin|Pax|DPP)/.test(c);
  return (
    <Card className="border-slate-200 shadow-sm overflow-hidden">
      <Table data-testid={testid}>
        <TableHeader><TableRow className="hover:bg-transparent">{cols.map((c, i) => <TableHead key={i} className={`${HEAD} ${right(c) ? "text-right" : ""}`}>{c}</TableHead>)}</TableRow></TableHeader>
        <TableBody>{children}</TableBody>
      </Table>
    </Card>
  );
}

function ExportBtns({ urls, testid }) {
  return (
    <div className="flex gap-1">
      <Button size="sm" variant="outline" onClick={() => window.open(urls.x, "_blank")} data-testid={testid ? `export-${testid}-xlsx` : undefined}><FileSpreadsheet className="h-4 w-4 mr-1" />Excel</Button>
      <Button size="sm" variant="outline" onClick={() => window.open(urls.c, "_blank")} data-testid={testid ? `export-${testid}-csv` : undefined}>CSV</Button>
      <Button size="sm" variant="outline" onClick={() => window.open(urls.p, "_blank")} data-testid={testid ? `export-${testid}-pdf` : undefined}><FileDown className="h-4 w-4 mr-1" />PDF</Button>
    </div>
  );
}

function ExpenseDialog({ onClose, onSaved }) {
  const [f, setF] = useState({ category: "Hotel", amount: 0, date: new Date().toISOString().slice(0, 10), description: "", vendor: "" });
  const set = (k) => (v) => setF((o) => ({ ...o, [k]: v }));
  const save = async () => {
    try { await api.post("/expenses", { ...f, amount: Number(f.amount) }); toast.success("Expense dicatat"); onSaved(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  return (
    <Dialog open onOpenChange={onClose}><DialogContent className="bg-white" data-testid="expense-dialog">
      <DialogHeader><DialogTitle className="font-display">Tambah Expense</DialogTitle></DialogHeader>
      <div className="grid grid-cols-2 gap-3 py-2">
        <div className="space-y-1"><Label className="text-xs">Category</Label><Select value={f.category} onValueChange={set("category")}><SelectTrigger data-testid="expense-category"><SelectValue /></SelectTrigger><SelectContent className="bg-white">{EXP_CATS.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select></div>
        <div className="space-y-1"><Label className="text-xs">Amount</Label><Input type="number" value={f.amount} onChange={(e) => set("amount")(e.target.value)} data-testid="expense-amount" /></div>
        <div className="space-y-1"><Label className="text-xs">Date</Label><Input type="date" value={f.date} onChange={(e) => set("date")(e.target.value)} /></div>
        <div className="space-y-1"><Label className="text-xs">Vendor</Label><Input value={f.vendor} onChange={(e) => set("vendor")(e.target.value)} /></div>
        <div className="space-y-1 col-span-2"><Label className="text-xs">Description</Label><Input value={f.description} onChange={(e) => set("description")(e.target.value)} /></div>
      </div>
      <DialogFooter><Button onClick={save} className="bg-blue-600 hover:bg-blue-700" data-testid="save-expense-button">Simpan</Button></DialogFooter>
    </DialogContent></Dialog>
  );
}

function RefundDialog({ onClose, onSaved }) {
  const [f, setF] = useState({ customer_name: "", amount: 0, reason: "", method: "Transfer", date: new Date().toISOString().slice(0, 10) });
  const set = (k) => (v) => setF((o) => ({ ...o, [k]: v }));
  const save = async () => {
    try { await api.post("/refunds", { ...f, amount: Number(f.amount) }); toast.success("Refund dicatat"); onSaved(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  return (
    <Dialog open onOpenChange={onClose}><DialogContent className="bg-white" data-testid="refund-dialog">
      <DialogHeader><DialogTitle className="font-display">Tambah Refund</DialogTitle></DialogHeader>
      <div className="grid grid-cols-2 gap-3 py-2">
        <div className="space-y-1"><Label className="text-xs">Customer</Label><Input value={f.customer_name} onChange={(e) => set("customer_name")(e.target.value)} data-testid="refund-customer" /></div>
        <div className="space-y-1"><Label className="text-xs">Amount</Label><Input type="number" value={f.amount} onChange={(e) => set("amount")(e.target.value)} data-testid="refund-amount" /></div>
        <div className="space-y-1"><Label className="text-xs">Method</Label><Input value={f.method} onChange={(e) => set("method")(e.target.value)} /></div>
        <div className="space-y-1"><Label className="text-xs">Date</Label><Input type="date" value={f.date} onChange={(e) => set("date")(e.target.value)} /></div>
        <div className="space-y-1 col-span-2"><Label className="text-xs">Reason</Label><Input value={f.reason} onChange={(e) => set("reason")(e.target.value)} /></div>
      </div>
      <DialogFooter><Button onClick={save} className="bg-blue-600 hover:bg-blue-700" data-testid="save-refund-button">Simpan</Button></DialogFooter>
    </DialogContent></Dialog>
  );
}

function TaxDialog({ data, onClose, onSaved }) {
  const editing = !!data._id;
  const [f, setF] = useState({
    tax_code: data.tax_code || "", tax_name: data.tax_name || "", tax_type: data.tax_type || "PPN",
    rate: data.rate ?? 0, tax_base: data.tax_base || "DPP", effective_from: data.effective_from || new Date().toISOString().slice(0, 10),
    effective_until: data.effective_until || "", treatment: data.treatment || "PPN_STANDARD", tax_account: data.tax_account || "",
    description: data.description || "", active: data.active !== false,
  });
  const set = (k) => (v) => setF((o) => ({ ...o, [k]: v }));
  const save = async () => {
    if (!f.tax_code || !f.tax_name) return toast.error("Tax code & name wajib");
    const body = { ...f, rate: Number(f.rate) };
    try {
      if (editing) await api.put(`/tax-masters/${data._id}`, body); else await api.post("/tax-masters", body);
      toast.success(editing ? "Tax rate diperbarui" : "Tax rate dibuat"); onSaved();
    } catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };
  return (
    <Dialog open onOpenChange={onClose}><DialogContent className="bg-white max-w-lg max-h-[90vh] overflow-y-auto" data-testid="tax-dialog">
      <DialogHeader><DialogTitle className="font-display">{editing ? "Edit Tax Rate" : "Tax Rate Baru"}</DialogTitle></DialogHeader>
      <div className="grid grid-cols-2 gap-3 py-2">
        <div className="space-y-1"><Label className="text-xs">Tax Code</Label><Input value={f.tax_code} onChange={(e) => set("tax_code")(e.target.value)} data-testid="tax-code" /></div>
        <div className="space-y-1"><Label className="text-xs">Tax Name</Label><Input value={f.tax_name} onChange={(e) => set("tax_name")(e.target.value)} data-testid="tax-name" /></div>
        <div className="space-y-1"><Label className="text-xs">Type</Label><Select value={f.tax_type} onValueChange={set("tax_type")}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent className="bg-white">{TAX_TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent></Select></div>
        <div className="space-y-1"><Label className="text-xs">Rate (%)</Label><Input type="number" value={f.rate} onChange={(e) => set("rate")(e.target.value)} data-testid="tax-rate" /></div>
        <div className="space-y-1"><Label className="text-xs">Tax Base</Label><Select value={f.tax_base} onValueChange={set("tax_base")}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent className="bg-white">{TAX_BASES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent></Select></div>
        <div className="space-y-1"><Label className="text-xs">Treatment</Label><Select value={f.treatment} onValueChange={set("treatment")}><SelectTrigger data-testid="tax-treatment"><SelectValue /></SelectTrigger><SelectContent className="bg-white">{TREATMENTS.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent></Select></div>
        <div className="space-y-1"><Label className="text-xs">Effective From</Label><Input type="date" value={f.effective_from} onChange={(e) => set("effective_from")(e.target.value)} data-testid="tax-effective-from" /></div>
        <div className="space-y-1"><Label className="text-xs">Effective Until</Label><Input type="date" value={f.effective_until} onChange={(e) => set("effective_until")(e.target.value)} /></div>
        <div className="space-y-1"><Label className="text-xs">Tax Account</Label><Input value={f.tax_account} onChange={(e) => set("tax_account")(e.target.value)} /></div>
        <div className="flex items-center gap-2 pt-6"><input type="checkbox" checked={f.active} onChange={(e) => set("active")(e.target.checked)} data-testid="tax-active" /><Label className="text-xs">Active</Label></div>
        <div className="space-y-1 col-span-2"><Label className="text-xs">Description</Label><Input value={f.description} onChange={(e) => set("description")(e.target.value)} /></div>
      </div>
      <DialogFooter><Button onClick={save} className="bg-blue-600 hover:bg-blue-700" data-testid="save-tax-button">Simpan</Button></DialogFooter>
    </DialogContent></Dialog>
  );
}

const Spin = () => <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
const Empty = ({ text }) => <Card className="border-slate-200"><CardContent className="p-12 text-center text-slate-500">{text}</CardContent></Card>;
const TONE = { blue: "text-blue-700", green: "text-emerald-600", red: "text-red-600", amber: "text-amber-600", violet: "text-violet-600", slate: "text-slate-600" };
const Kpi = ({ label, v, tone, raw }) => <Card className="border-slate-200 shadow-sm"><CardContent className="p-4"><p className="text-[11px] uppercase text-slate-500">{label}</p><p className={`font-display text-xl font-bold ${TONE[tone] || "text-slate-900"}`}>{raw ? v : fmtIDR(v)}</p></CardContent></Card>;
