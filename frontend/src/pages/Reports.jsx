import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Loader2, TrendingUp, Scale, Waves, ShoppingCart, Users2, Receipt, ArrowDownCircle, ArrowUpCircle, AlertTriangle, FileSpreadsheet, FileText, Printer, Download, History } from "lucide-react";

const rp = (v) => "Rp " + Number(v || 0).toLocaleString("id-ID");
const num = (v) => Number(v || 0).toLocaleString("id-ID");

const REPORTS = [
  { key: "profit-loss", label: "Laba Rugi", icon: TrendingUp, finance: true },
  { key: "balance-sheet", label: "Neraca", icon: Scale, finance: true },
  { key: "cash-flow", label: "Arus Kas", icon: Waves, finance: true },
  { key: "sales-detail", label: "Penjualan", icon: ShoppingCart, finance: false },
  { key: "team-performance", label: "Kinerja Tim", icon: Users2, finance: false },
  { key: "tax-recap", label: "Rekap Pajak", icon: Receipt, finance: true },
  { key: "payable", label: "Utang Usaha", icon: ArrowUpCircle, finance: true },
  { key: "receivable-aging", label: "Piutang Usaha", icon: ArrowDownCircle, finance: false },
  { key: "pic-changes", label: "Perpindahan PIC", icon: Users2, finance: false, admin: true },
];

function presetRange(preset) {
  const d = new Date();
  const iso = (x) => x.toISOString().slice(0, 10);
  const y = d.getFullYear(), m = d.getMonth();
  if (preset === "daily") return { frm: iso(d), to: iso(d) };
  if (preset === "weekly") { const s = new Date(d); s.setDate(d.getDate() - 6); return { frm: iso(s), to: iso(d) }; }
  if (preset === "monthly") return { frm: iso(new Date(y, m, 1)), to: iso(new Date(y, m + 1, 0)) };
  if (preset === "quarterly") { const q = Math.floor(m / 3) * 3; return { frm: iso(new Date(y, q, 1)), to: iso(new Date(y, q + 3, 0)) }; }
  if (preset === "yearly") return { frm: `${y}-01-01`, to: `${y}-12-31` };
  return { frm: "", to: "" };
}

export default function Reports() {
  const { user } = useAuth();
  const list = REPORTS.filter((r) => (user.role !== "sales" || !r.finance) && (!r.admin || user.role === "super_admin"));
  const [active, setActive] = useState(list[0].key);
  const [preset, setPreset] = useState("monthly");
  const [range, setRange] = useState(presetRange("monthly"));
  const [filters, setFilters] = useState({ product_type: "", package_id: "", sales_id: "", destination: "", status: "", vendor: "", customer: "", tax_type: "PPN", month: String(new Date().getMonth() + 1), year: String(new Date().getFullYear()) });
  const [opts, setOpts] = useState({ packages: [], sales: [], product_types: [], destinations: [], tax_types: [] });
  const [data, setData] = useState(null);
  const [brand, setBrand] = useState({ company_name: "", logo: "" });
  const [history, setHistory] = useState(null);

  useEffect(() => {
    api.get("/mgmt-reports/filters").then((r) => setOpts(r.data)).catch(() => {});
    api.get("/public/branding").then((r) => setBrand(r.data || {})).catch(() => {});
  }, []);

  const buildQuery = () => {
    const q = new URLSearchParams();
    if (active !== "tax-recap" && active !== "balance-sheet") { if (range.frm) q.set("frm", range.frm); if (range.to) q.set("to", range.to); }
    if (active === "balance-sheet" && range.to) q.set("as_of", range.to);
    if (active === "tax-recap") { q.set("month", filters.month); q.set("year", filters.year); q.set("tax_type", filters.tax_type); }
    ["product_type", "package_id", "sales_id", "destination", "status", "vendor", "customer"].forEach((k) => { if (filters[k]) q.set(k, filters[k]); });
    return q.toString();
  };

  const load = () => {
    setData(null);
    const url = active === "pic-changes"
      ? `/reports/pic-changes?${range.frm ? `frm=${range.frm}&` : ""}${range.to ? `to=${range.to}` : ""}`
      : `/mgmt-reports/${active}?${buildQuery()}`;
    api.get(url).then((r) => setData(r.data)).catch((e) => setData({ __err: e.response?.status === 403 ? "403 Forbidden" : "Gagal memuat laporan" }));
  };

  const doExport = async (fmt) => {
    try {
      const res = await api.get(`/mgmt-reports/${active}/export?format=${fmt}&${buildQuery()}`, { responseType: "blob" });
      const cd = res.headers["content-disposition"] || "";
      const m = cd.match(/filename=([^;]+)/);
      const name = m ? m[1].trim() : `${active}.${fmt}`;
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
      toast.success(`Export ${fmt.toUpperCase()} berhasil`);
    } catch (e) {
      let msg = "Export gagal";
      if (e.response?.status === 403) msg = "Anda tidak diizinkan meng-export laporan ini";
      else if (e.response?.status === 409) { try { msg = JSON.parse(await e.response.data.text()).detail; } catch { msg = "Data tidak konsisten"; } }
      toast.error(msg);
    }
  };
  const openHistory = () => api.get("/report-exports").then((r) => setHistory(r.data || [])).catch(() => setHistory([]));
  const periodLabel = active === "balance-sheet" ? `Per ${range.to || "-"}` : active === "tax-recap" ? `${filters.month}/${filters.year}` : `${range.frm || "..."} s/d ${range.to || "..."}`;
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [active, range, filters.product_type, filters.package_id, filters.sales_id, filters.destination, filters.status, filters.vendor, filters.customer, filters.tax_type, filters.month, filters.year]);

  const applyPreset = (p) => { setPreset(p); if (p !== "custom") setRange(presetRange(p)); };
  const meta = REPORTS.find((r) => r.key === active);

  return (
    <div className="space-y-5" data-testid="reports-page">
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900">Reports</h1>
        <p className="text-slate-500 mt-0.5">Laporan finansial &amp; manajemen dari data transaksi aktual.</p>
      </div>
      <div className="flex flex-wrap gap-2" data-testid="report-tabs">
        {list.map((r) => (
          <button key={r.key} onClick={() => { setActive(r.key); setData(null); }} data-testid={`report-tab-${r.key}`}
            className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm border transition-colors ${active === r.key ? "bg-blue-600 text-white border-blue-600" : "bg-white text-slate-600 border-slate-200 hover:border-blue-300"}`}>
            <r.icon className="h-4 w-4" /> {r.label}
          </button>
        ))}
      </div>

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-4 flex flex-wrap items-end gap-3">
          {active === "tax-recap" ? (
            <>
              <Sel label="Bulan" value={filters.month} onChange={(v) => setFilters({ ...filters, month: v })} testid="rf-month" options={Array.from({ length: 12 }, (_, i) => ({ v: String(i + 1), l: String(i + 1) }))} />
              <div><Label>Tahun</Label><Input className="w-28" value={filters.year} onChange={(e) => setFilters({ ...filters, year: e.target.value })} data-testid="rf-year" /></div>
              <Sel label="Tax Type" value={filters.tax_type} onChange={(v) => setFilters({ ...filters, tax_type: v })} testid="rf-taxtype" options={(opts.tax_types || []).map((t) => ({ v: t, l: t }))} />
            </>
          ) : (
            <>
              <Sel label="Periode" value={preset} onChange={applyPreset} testid="rf-preset" options={[["daily", "Harian"], ["weekly", "Mingguan"], ["monthly", "Bulanan"], ["quarterly", "Kuartal"], ["yearly", "Tahunan"], ["custom", "Custom"]].map(([v, l]) => ({ v, l }))} />
              {active === "balance-sheet" ? (
                <div><Label>Per Tanggal</Label><Input type="date" className="w-40" value={range.to} onChange={(e) => { setPreset("custom"); setRange({ ...range, to: e.target.value }); }} data-testid="rf-asof" /></div>
              ) : (
                <>
                  <div><Label>Dari</Label><Input type="date" className="w-40" value={range.frm} onChange={(e) => { setPreset("custom"); setRange({ ...range, frm: e.target.value }); }} data-testid="rf-from" /></div>
                  <div><Label>Sampai</Label><Input type="date" className="w-40" value={range.to} onChange={(e) => { setPreset("custom"); setRange({ ...range, to: e.target.value }); }} data-testid="rf-to" /></div>
                </>
              )}
              {["profit-loss", "sales-detail"].includes(active) && <Sel label="Product Type" value={filters.product_type} onChange={(v) => setFilters({ ...filters, product_type: v === "ALL" ? "" : v })} testid="rf-product" options={[{ v: "ALL", l: "Semua" }, ...(opts.product_types || []).map((t) => ({ v: t, l: t }))]} />}
              {["profit-loss", "sales-detail"].includes(active) && <Sel label="Package" value={filters.package_id} onChange={(v) => setFilters({ ...filters, package_id: v === "ALL" ? "" : v })} testid="rf-package" options={[{ v: "ALL", l: "Semua" }, ...(opts.packages || []).map((p) => ({ v: p.id, l: p.name }))]} />}
              {["sales-detail", "team-performance", "receivable-aging"].includes(active) && (opts.sales || []).length > 0 && <Sel label="Sales" value={filters.sales_id} onChange={(v) => setFilters({ ...filters, sales_id: v === "ALL" ? "" : v })} testid="rf-sales" options={[{ v: "ALL", l: "Semua" }, ...(opts.sales || []).map((s) => ({ v: s.id, l: s.name }))]} />}
            </>
          )}
          <Button onClick={load} data-testid="report-apply-btn">Terapkan</Button>
          <div className="flex flex-wrap gap-2 ml-auto no-print">
            <Button variant="outline" onClick={() => doExport("xlsx")} data-testid="export-excel-btn"><FileSpreadsheet className="h-4 w-4 mr-1" />Excel</Button>
            <Button variant="outline" onClick={() => doExport("csv")} data-testid="export-csv-btn"><Download className="h-4 w-4 mr-1" />CSV</Button>
            <Button variant="outline" onClick={() => doExport("pdf")} data-testid="export-pdf-btn"><FileText className="h-4 w-4 mr-1" />PDF</Button>
            <Button variant="outline" onClick={() => window.print()} data-testid="print-btn"><Printer className="h-4 w-4 mr-1" />Print</Button>
            <Button variant="ghost" onClick={openHistory} data-testid="history-btn"><History className="h-4 w-4 mr-1" />Riwayat</Button>
          </div>
        </CardContent>
      </Card>

      <div id="print-area">
        <div className="print-only mb-4">
          <div className="text-xl font-bold">{brand.company_name || "Safar Travel CRM"}</div>
          <div className="text-lg font-semibold">{meta?.label} — {data && !data.__err && data.title ? data.title : ""}</div>
          <div className="text-sm text-slate-600">Periode: {periodLabel} · Generated: {new Date().toISOString().slice(0, 10)}</div>
        </div>
        {data === null ? <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
          : data.__err ? <div className="p-8 text-slate-400" data-testid="report-error">{data.__err}</div>
            : <div data-testid={`report-body-${active}`}>{renderReport(active, data)}</div>}
      </div>

      <Dialog open={history !== null} onOpenChange={(o) => !o && setHistory(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="history-dialog">
          <DialogHeader><DialogTitle>Report Export History</DialogTitle><DialogDescription className="sr-only">Riwayat export laporan</DialogDescription></DialogHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="history-table">
              <thead><tr className="bg-slate-800 text-white text-left"><th className="px-3 py-2">Report</th><th className="px-3 py-2 border-l border-slate-600">User</th><th className="px-3 py-2 border-l border-slate-600">Waktu</th><th className="px-3 py-2 border-l border-slate-600">Format</th><th className="px-3 py-2 border-l border-slate-600">File</th></tr></thead>
              <tbody>
                {(history || []).length === 0 ? <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Belum ada riwayat export.</td></tr>
                  : (history || []).map((h, i) => (
                    <tr key={h.id || i} className={i % 2 ? "bg-slate-50" : "bg-white"} data-testid={`history-row-${i}`}>
                      <td className="px-3 py-2">{h.report_name}</td>
                      <td className="px-3 py-2 border-l border-slate-100">{h.user_name}</td>
                      <td className="px-3 py-2 border-l border-slate-100">{(h.created_at || "").replace("T", " ").slice(0, 16)}</td>
                      <td className="px-3 py-2 border-l border-slate-100"><Badge className="bg-slate-100 text-slate-600 border-slate-200">{(h.format || "").toUpperCase()}</Badge></td>
                      <td className="px-3 py-2 border-l border-slate-100 text-xs">{h.file_name}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

const Sel = ({ label, value, onChange, options, testid }) => (
  <div><Label>{label}</Label>
    <Select value={value} onValueChange={onChange}><SelectTrigger className="w-44" data-testid={testid}><SelectValue /></SelectTrigger>
      <SelectContent>{options.map((o) => <SelectItem key={o.v} value={o.v}>{o.l}</SelectItem>)}</SelectContent>
    </Select>
  </div>
);

const SummaryCards = ({ items }) => (
  <div className="grid grid-cols-2 lg:grid-cols-5 gap-3" data-testid="report-summary">
    {items.map(([l, v, money], i) => (
      <Card key={i} className="border-slate-200 shadow-sm" data-testid={`sum-${i}`}><CardContent className="p-4"><p className="text-xs text-slate-400">{l}</p><p className="text-lg font-bold text-slate-900 mt-0.5">{typeof v === "string" ? v : money === false ? num(v) : rp(v)}</p></CardContent></Card>
    ))}
  </div>
);

function Table({ columns, rows, render }) {
  return (
    <Card className="border-slate-200 shadow-sm"><CardContent className="p-0"><div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="report-table">
        <thead><tr className="bg-blue-600 text-white text-left">{columns.map((c) => <th key={c} className="px-3 py-2.5 border-l border-blue-500 first:border-l-0">{c}</th>)}</tr></thead>
        <tbody>
          {rows.length === 0 ? <tr><td colSpan={columns.length} className="px-4 py-8 text-center text-slate-400">Tidak ada data.</td></tr>
            : rows.map((r, i) => <tr key={i} className={i % 2 ? "bg-slate-50" : "bg-white"}>{render(r).map((c, j) => <td key={j} className="px-3 py-2.5 border-l border-slate-100 first:border-l-0">{c}</td>)}</tr>)}
        </tbody>
      </table>
    </div></CardContent></Card>
  );
}

const PLGroup = ({ title, node, keys, strong }) => (
  <div className="rounded-lg border border-slate-100">
    <div className="bg-slate-800 text-white px-4 py-2 rounded-t-lg font-medium text-sm">{title}</div>
    <table className="w-full text-sm"><tbody>
      {keys.map((k) => (
        <tr key={k} className="border-b border-slate-50"><td className="px-4 py-2 text-slate-600">{node[k].label}</td>
          <td className="px-4 py-2 text-right font-medium">{rp(node[k].amount)}</td>
          <td className="px-4 py-2 text-right text-slate-400 w-20">{node[k].percent}%</td></tr>
      ))}
      {strong && <tr className="bg-slate-50 font-bold"><td className="px-4 py-2">{node.total.label}</td><td className="px-4 py-2 text-right">{rp(node.total.amount)}</td><td className="px-4 py-2 text-right text-slate-500">{node.total.percent}%</td></tr>}
    </tbody></table>
  </div>
);

function renderReport(key, d) {
  if (key === "pic-changes") {
    return (
      <Card className="border-slate-200 shadow-sm"><CardContent className="p-0"><div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="report-table">
          <thead><tr className="bg-slate-800 text-white text-left"><th className="px-3 py-2">Waktu</th><th className="px-3 py-2 border-l border-slate-600">Customer</th><th className="px-3 py-2 border-l border-slate-600">Perubahan PIC</th><th className="px-3 py-2 border-l border-slate-600">Tipe</th><th className="px-3 py-2 border-l border-slate-600">Oleh</th></tr></thead>
          <tbody>
            {(d.rows || []).length === 0 ? <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Belum ada perpindahan PIC.</td></tr>
              : (d.rows || []).map((r, i) => (
                <tr key={i} className={i % 2 ? "bg-slate-50" : "bg-white"} data-testid={`pic-change-row-${i}`}>
                  <td className="px-3 py-2 whitespace-nowrap">{r.date}</td>
                  <td className="px-3 py-2 border-l border-slate-100">{r.customer}</td>
                  <td className="px-3 py-2 border-l border-slate-100">{r.change}</td>
                  <td className="px-3 py-2 border-l border-slate-100"><Badge className={r.mode === "Massal" ? "bg-indigo-50 text-indigo-700 border-indigo-200" : "bg-slate-100 text-slate-600 border-slate-200"}>{r.mode}</Badge></td>
                  <td className="px-3 py-2 border-l border-slate-100">{r.by}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div></CardContent></Card>
    );
  }
  if (key === "profit-loss") {
    return (
      <div className="space-y-4">
        <SummaryCards items={[["Revenue", d.summary.revenue], ["HPP", d.summary.hpp], ["Gross Profit", d.summary.gross_profit], ["Operating Exp", d.summary.opex], ["Net Profit", d.summary.net_profit]]} />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <PLGroup title="Pendapatan" node={d.revenue} keys={["tour", "umrah", "other"]} strong />
          <PLGroup title="HPP / Cost of Sales" node={d.hpp} keys={["flight", "hotel", "visa", "transport", "supplier", "other"]} strong />
        </div>
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 flex justify-between font-bold text-emerald-800" data-testid="pl-gross-profit"><span>{d.gross_profit.label}</span><span>{rp(d.gross_profit.amount)} · {d.gross_profit.percent}%</span></div>
        <PLGroup title="Operating Expense" node={d.opex} keys={["salary", "marketing", "office", "transportation", "commission", "bank_fee", "other"]} strong />
        <div className="rounded-lg border border-blue-300 bg-blue-600 px-4 py-3 flex justify-between font-bold text-white" data-testid="pl-net-profit"><span>{d.net_profit.label} (Margin {d.summary.net_margin}%)</span><span>{rp(d.net_profit.amount)}</span></div>
      </div>
    );
  }
  if (key === "balance-sheet") {
    const secRows = (obj) => Object.entries(obj).map(([k, v]) => <tr key={k} className="border-b border-slate-50"><td className="px-4 py-2 capitalize text-slate-600">{k.replace(/_/g, " ")}</td><td className="px-4 py-2 text-right font-medium">{rp(v)}</td></tr>);
    return (
      <div className="space-y-4">
        {!d.balanced && <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 flex items-center gap-2 text-amber-800" data-testid="balance-warning"><AlertTriangle className="h-4 w-4" /> Neraca tidak balance. Selisih {rp(d.difference)}.</div>}
        <SummaryCards items={[["Total Asset", d.total_assets], ["Total Liability", d.total_liabilities], ["Total Equity", d.total_equity], ["Current Year P/L", d.equity.current_year_pl], ["Balanced", d.balanced ? "OK" : "NO", false]]} />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="rounded-lg border border-slate-100" data-testid="bs-assets"><div className="bg-blue-600 text-white px-4 py-2 rounded-t-lg font-medium">ASSET</div><table className="w-full text-sm"><tbody>{secRows(d.assets_current)}{secRows(d.assets_noncurrent)}<tr className="bg-slate-50 font-bold"><td className="px-4 py-2">Total Asset</td><td className="px-4 py-2 text-right">{rp(d.total_assets)}</td></tr></tbody></table></div>
          <div className="rounded-lg border border-slate-100" data-testid="bs-liabilities"><div className="bg-rose-600 text-white px-4 py-2 rounded-t-lg font-medium">LIABILITY</div><table className="w-full text-sm"><tbody>{secRows(d.liabilities)}<tr className="bg-slate-50 font-bold"><td className="px-4 py-2">Total Liability</td><td className="px-4 py-2 text-right">{rp(d.total_liabilities)}</td></tr></tbody></table></div>
          <div className="rounded-lg border border-slate-100" data-testid="bs-equity"><div className="bg-emerald-600 text-white px-4 py-2 rounded-t-lg font-medium">EQUITY</div><table className="w-full text-sm"><tbody>{secRows(d.equity)}<tr className="bg-slate-50 font-bold"><td className="px-4 py-2">Total Equity</td><td className="px-4 py-2 text-right">{rp(d.total_equity)}</td></tr></tbody></table></div>
        </div>
      </div>
    );
  }
  if (key === "cash-flow") {
    const grp = (title, obj) => (<div className="rounded-lg border border-slate-100"><div className="bg-slate-800 text-white px-4 py-2 rounded-t-lg font-medium text-sm">{title}</div><table className="w-full text-sm"><tbody>{Object.entries(obj).map(([k, v]) => <tr key={k} className="border-b border-slate-50"><td className="px-4 py-2 capitalize text-slate-600">{k.replace(/_/g, " ")}</td><td className={`px-4 py-2 text-right font-medium ${v < 0 ? "text-rose-600" : "text-slate-800"}`}>{rp(v)}</td></tr>)}</tbody></table></div>);
    return (
      <div className="space-y-4">
        <SummaryCards items={[["Opening Cash", d.opening_cash], ["Cash In", d.cash_in], ["Cash Out", d.cash_out], ["Net Cash Flow", d.net_cash_flow], ["Ending Cash", d.ending_cash]]} />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">{grp("Operating Activities", d.operating)}{grp("Investing Activities", d.investing)}{grp("Financing Activities", d.financing)}</div>
      </div>
    );
  }
  if (key === "sales-detail") {
    const s = d.summary;
    return (
      <div className="space-y-4">
        <SummaryCards items={[["Total Booking", s.total_booking, false], ["Total Pax", s.total_pax, false], ["Gross Sales", s.gross_sales], ["Net Sales", s.net_sales], ["Outstanding", s.outstanding]]} />
        <Table columns={["Booking", "Date", "Customer", "Sales", "Package", "Type", "Departure", "Pax", "Selling", "Disc", "Net", "Paid", "Outstanding", "Status"]} rows={d.rows}
          render={(r) => [r.booking_number, r.date, r.customer, r.sales, r.package, r.product_type, r.departure || "-", r.pax, rp(r.selling_price), rp(r.discount), rp(r.net_sales), rp(r.payment), rp(r.outstanding), <Badge className="bg-slate-100 text-slate-600 border-slate-200">{r.status}</Badge>]} />
      </div>
    );
  }
  if (key === "team-performance") {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-3" data-testid="team-rankings">
          {[["Top by Revenue", "by_revenue", "sales_value", true], ["Top by Pax", "by_pax", "pax", false], ["Top by Conversion", "by_conversion", "conversion_rate", "pct"], ["Top by Booking", "by_booking", "bookings", false]].map(([t, rk, f, money]) => (
            <Card key={rk} className="border-slate-200 shadow-sm"><CardHeader className="py-2 border-b border-slate-100"><CardTitle className="text-sm">{t}</CardTitle></CardHeader><CardContent className="p-2 space-y-1">
              {(d.rankings[rk] || []).map((r, i) => <div key={i} className="flex justify-between text-sm px-2 py-1"><span className="text-slate-600">{i + 1}. {r.sales}</span><span className="font-medium">{money === true ? rp(r[f]) : money === "pct" ? r[f] + "%" : num(r[f])}</span></div>)}
            </CardContent></Card>
          ))}
        </div>
        <Table columns={["Sales", "Leads", "Qualified", "Quotations", "Converted", "Bookings", "Pax", "Sales Value", "Conversion", "Follow Up", "Overdue FU", "Commission"]} rows={d.rows}
          render={(r) => [r.sales, r.leads, r.qualified, r.quotations, r.converted, r.bookings, r.pax, rp(r.sales_value), r.conversion_rate + "%", r.follow_up, r.overdue_follow_up, rp(r.commission)]} />
      </div>
    );
  }
  if (key === "tax-recap") {
    const s = d.summary || {};
    const cards = d.tax_type === "PPN" ? [["Taxable Sales", s.taxable_sales], ["DPP", s.dpp], ["PPN Output", s.ppn_output], ["PPN Input", d.ppn?.ppn_input || 0], ["PPN Payable", s.ppn_payable]] : [["Tax Amount", s.tax_amount]];
    return (
      <div className="space-y-4">
        <SummaryCards items={cards} />
        <Table columns={d.columns} rows={d.rows} render={(r) => r.map((c) => typeof c === "number" ? num(c) : c)} />
      </div>
    );
  }
  if (key === "payable") {
    const s = d.summary;
    return (
      <div className="space-y-4">
        <SummaryCards items={[["Total Payable", s.total_payable], ["Outstanding", s.total_outstanding], ["Current", s.current], ["31-60", s.d31_60], [">90", s.d90]]} />
        <Table columns={["Vendor", "Invoice", "Inv Date", "Due", "Amount", "Paid", "Outstanding", "Aging", "Status"]} rows={d.rows}
          render={(r) => [r.vendor, r.invoice, r.invoice_date, r.due_date, rp(r.amount), rp(r.paid), rp(r.outstanding), r.aging, <Badge className="bg-slate-100 text-slate-600 border-slate-200">{r.status}</Badge>]} />
      </div>
    );
  }
  if (key === "receivable-aging") {
    const s = d.summary;
    return (
      <div className="space-y-4">
        <SummaryCards items={[["Total Receivable", s.total_receivable], ["Current", s.current], ["Overdue", s.overdue], ["61-90", s.d61_90], [">90", s.d90]]} />
        <Table columns={["Customer", "Invoice", "Inv Date", "Due", "Total", "Paid", "Outstanding", "Aging", "Status", "Sales"]} rows={d.rows}
          render={(r) => [r.customer, r.invoice, r.invoice_date, r.due_date, rp(r.total_invoice), rp(r.paid), rp(r.outstanding), r.aging, <Badge className="bg-slate-100 text-slate-600 border-slate-200">{r.status}</Badge>, r.sales || "-"]} />
      </div>
    );
  }
  return null;
}
