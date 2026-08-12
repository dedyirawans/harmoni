import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Loader2, TrendingUp, DollarSign, PieChart as PieIcon, Percent, Receipt, Bell, Users2,
} from "lucide-react";
import ExpiringDocsWidget from "@/components/ExpiringDocsWidget";
import {
  ResponsiveContainer, ComposedChart, LineChart, Line, BarChart, Bar, Area,
  XAxis, YAxis, Tooltip, CartesianGrid, Cell, Legend,
} from "recharts";

const rp = (v) => "Rp " + Number(v || 0).toLocaleString("id-ID");
const short = (v) => {
  const n = Number(v || 0);
  if (Math.abs(n) >= 1e9) return "Rp " + (n / 1e9).toFixed(2) + "M";
  return "Rp " + (n / 1e6).toFixed(1) + "jt";
};
const COLORS = ["#2563eb", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"];

export default function SuperAdminDashboard() {
  const nav = useNavigate();
  const now = new Date();
  const defMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [month, setMonth] = useState(defMonth);
  const [d, setD] = useState(null);

  useEffect(() => {
    setD(null);
    api.get(`/executive-dashboard?month=${month}`).then((r) => setD(r.data)).catch(() => setD(false));
  }, [month]);

  const Kpi = ({ label, value, sub, testid, to, accent }) => (
    <button
      onClick={() => to && nav(to)}
      data-testid={testid}
      className={`rounded-lg border border-slate-100 px-4 py-3 text-left w-full ${to ? "hover:bg-blue-50 hover:border-blue-200 cursor-pointer" : "cursor-default"} transition-colors`}
    >
      <p className="text-xs text-slate-400">{label}</p>
      <p className={`text-lg font-bold mt-0.5 ${accent || "text-slate-900"}`}>{value}</p>
      {sub && <p className="text-[11px] text-slate-400 mt-0.5">{sub}</p>}
    </button>
  );

  const Group = ({ icon: Icon, title, color, children, testid, cols = "grid-cols-2 lg:grid-cols-3" }) => (
    <Card className="border-slate-200 shadow-sm" data-testid={testid}>
      <CardHeader className="border-b border-slate-100 py-3">
        <CardTitle className="text-sm font-display flex items-center gap-2"><Icon className={`h-4 w-4 ${color}`} />{title}</CardTitle>
      </CardHeader>
      <CardContent className={`p-3 grid ${cols} gap-2`}>{children}</CardContent>
    </Card>
  );

  const Out = ({ label, value, to, testid, money }) => (
    <button onClick={() => to && nav(to)} data-testid={testid}
      className="flex items-center justify-between rounded-lg border border-slate-100 px-4 py-3 hover:bg-blue-50 hover:border-blue-200 transition-colors text-left w-full">
      <span className="text-sm text-slate-600">{label}</span>
      <Badge className="bg-blue-600 text-white">{money ? short(value) : value}</Badge>
    </button>
  );

  return (
    <div className="space-y-5" data-testid="executive-dashboard">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">Executive Dashboard</h1>
          <p className="text-slate-500 mt-0.5">Ringkasan Sales, Keuangan, Profitabilitas &amp; Pajak lintas modul</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500">Periode</label>
          <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-40 h-9" data-testid="exec-period-filter" />
        </div>
      </div>

      {d === null ? (
        <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
      ) : d === false ? (
        <div className="p-8 text-slate-400">Gagal memuat dashboard.</div>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Group icon={Users2} title="Sales KPI" color="text-blue-600" testid="exec-sales">
              <Kpi label="Leads" value={d.sales.leads_total} sub={`${d.sales.leads_new} new`} testid="ex-leads" to="/sales" />
              <Kpi label="Qualified" value={d.sales.leads_qualified} testid="ex-qualified" to="/sales" />
              <Kpi label="Quotation" value={d.sales.quotation_total} sub={`${d.sales.quotation_converted} converted`} testid="ex-quotation" to="/quotations" />
              <Kpi label="Conversion" value={`${d.sales.conversion_rate}%`} testid="ex-conversion" />
              <Kpi label="Bookings" value={d.sales.booking_total} sub={`${d.sales.total_pax} pax`} testid="ex-bookings" to="/booking" />
              <Kpi label="Booking Value" value={short(d.sales.booking_revenue)} testid="ex-bookvalue" accent="text-blue-700" />
            </Group>

            <Group icon={DollarSign} title="Financial KPI" color="text-emerald-600" testid="exec-financial">
              <Kpi label="Revenue" value={short(d.financial.revenue)} testid="ex-revenue" accent="text-emerald-700" to="/accounting" />
              <Kpi label="Cash In" value={short(d.financial.cash_in)} testid="ex-cashin" accent="text-emerald-700" to="/accounting" />
              <Kpi label="Cash Out" value={short(d.financial.cash_out)} testid="ex-cashout" accent="text-red-600" to="/accounting" />
              <Kpi label="Net Cash Flow" value={short(d.financial.net_cash_flow)} testid="ex-netcash" accent={d.financial.net_cash_flow >= 0 ? "text-emerald-700" : "text-red-600"} />
              <Kpi label="Receivable" value={short(d.financial.outstanding_receivable)} testid="ex-receivable" accent="text-amber-600" to="/accounting" />
              <Kpi label="Refund Paid" value={short(d.financial.refund_paid)} testid="ex-refundpaid" accent="text-red-600" to="/approvals" />
            </Group>

            <Group icon={Percent} title="Profitability" color="text-indigo-600" testid="exec-profit">
              <Kpi label="Revenue (Booking)" value={short(d.profitability.revenue)} testid="ex-p-revenue" />
              <Kpi label="HPP (COGS)" value={short(d.profitability.hpp)} testid="ex-p-hpp" accent="text-red-600" />
              <Kpi label="Gross Profit" value={short(d.profitability.gross_profit)} testid="ex-p-gp" accent="text-emerald-700" />
              <Kpi label="Gross Margin" value={`${d.profitability.gross_margin}%`} testid="ex-p-gm" accent="text-indigo-700" />
              <Kpi label="Commission Payable" value={short(d.profitability.commission_payable)} testid="ex-p-comm" accent="text-amber-600" to="/commission" />
              <Kpi label="—" value="" />
            </Group>

            <Group icon={Receipt} title="Tax &amp; Refund" color="text-purple-600" testid="exec-tax">
              <Kpi label="DPP" value={short(d.tax.dpp)} testid="ex-t-dpp" to="/tax" />
              <Kpi label="PPN" value={short(d.tax.ppn)} testid="ex-t-ppn" to="/tax" />
              <Kpi label="Tax Payable" value={short(d.tax.tax_payable)} testid="ex-t-payable" accent="text-purple-700" to="/tax" />
              <Kpi label="Refund Pending" value={d.refund.pending_approval} testid="ex-t-refpending" to="/approvals" />
              <Kpi label="Refund Approved" value={short(d.refund.approved)} testid="ex-t-refapproved" to="/approvals" />
              <Kpi label="Refund Outstanding" value={short(d.refund.outstanding)} testid="ex-t-refout" accent="text-red-600" to="/approvals" />
            </Group>
          </div>

          <Card className="border-slate-200 shadow-sm" data-testid="exec-outstanding">
            <CardHeader className="border-b border-slate-100 py-3">
              <CardTitle className="text-sm font-display flex items-center gap-2"><Bell className="h-4 w-4 text-red-500" />Company Outstanding</CardTitle>
            </CardHeader>
            <CardContent className="p-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
              <Out label="Unpaid Invoice" value={d.outstanding.unpaid_invoice} to="/accounting" testid="eo-unpaid" />
              <Out label="Overdue Invoice" value={d.outstanding.overdue_invoice} to="/accounting" testid="eo-overdue" />
              <Out label="Outstanding Receivable" value={d.outstanding.outstanding_receivable} money to="/accounting" testid="eo-receivable" />
              <Out label="Pending Refund" value={d.outstanding.pending_refund} to="/approvals" testid="eo-refund" />
              <Out label="Pending Commission" value={d.outstanding.pending_commission} to="/commission" testid="eo-commission" />
              <Out label="Commission Payable" value={d.outstanding.commission_payable} money to="/commission" testid="eo-commpayable" />
              <Out label="Supplier Payable" value={d.outstanding.outstanding_supplier} money to="/accounting" testid="eo-supplier" />
              <Out label="Tax Payable" value={d.outstanding.tax_payable} money to="/tax" testid="eo-tax" />
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ChartCard title="Revenue, HPP & Gross Profit (6 Bulan)" testid="chart-profit-trend">
              <ComposedChart data={d.trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => (v / 1e6).toFixed(0) + "jt"} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => rp(v)} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="revenue" name="Revenue" fill="#2563eb" radius={[4, 4, 0, 0]} />
                <Bar dataKey="hpp" name="HPP" fill="#ef4444" radius={[4, 4, 0, 0]} />
                <Line type="monotone" dataKey="gross_profit" name="Gross Profit" stroke="#10b981" strokeWidth={2.5} dot />
              </ComposedChart>
            </ChartCard>

            <ChartCard title="Cash Flow (In vs Out)" testid="chart-cashflow">
              <BarChart data={d.trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => (v / 1e6).toFixed(0) + "jt"} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => rp(v)} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="cash_in" name="Cash In" fill="#10b981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="cash_out" name="Cash Out" fill="#ef4444" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ChartCard>

            <ChartCard title="Lead Funnel" testid="chart-funnel">
              <BarChart data={d.funnel} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" horizontal={false} />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis dataKey="stage" type="category" width={90} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" name="Leads" radius={[0, 4, 4, 0]}>
                  {d.funnel.map((e, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ChartCard>

            <ChartCard title="Receivable Aging" testid="chart-aging">
              <BarChart data={[
                { b: "Current", v: d.receivable_aging.current }, { b: "1-30", v: d.receivable_aging.d1_30 },
                { b: "31-60", v: d.receivable_aging.d31_60 }, { b: "61-90", v: d.receivable_aging.d61_90 },
                { b: ">90", v: d.receivable_aging.d90 },
              ]}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis dataKey="b" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => (v / 1e6).toFixed(0) + "jt"} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => rp(v)} />
                <Bar dataKey="v" name="Receivable" radius={[4, 4, 0, 0]}>
                  {[0, 1, 2, 3, 4].map((i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ChartCard>

            <ChartCard title="Revenue by Package" testid="chart-rev-package">
              {d.revenue_by_package.length === 0 ? <Empty /> : (
                <BarChart data={d.revenue_by_package} layout="vertical">
                  <XAxis type="number" tickFormatter={(v) => (v / 1e6).toFixed(0) + "jt"} tick={{ fontSize: 11 }} />
                  <YAxis dataKey="package" type="category" width={110} tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v) => rp(v)} />
                  <Bar dataKey="value" fill="#2563eb" radius={[0, 4, 4, 0]} />
                </BarChart>
              )}
            </ChartCard>

            <ChartCard title="Sales Performance (per PIC)" testid="chart-sales-perf">
              {d.sales_performance.length === 0 ? <Empty /> : (
                <BarChart data={d.sales_performance}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                  <XAxis dataKey="sales" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={50} />
                  <YAxis tickFormatter={(v) => (v / 1e6).toFixed(0) + "jt"} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v) => rp(v)} />
                  <Bar dataKey="value" name="Sales Value" radius={[4, 4, 0, 0]}>
                    {d.sales_performance.map((e, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Bar>
                </BarChart>
              )}
            </ChartCard>
          </div>

          <ExpiringDocsWidget within={90} />
        </>
      )}
    </div>
  );
}

const ChartCard = ({ title, children, testid }) => (
  <Card className="border-slate-200 shadow-sm" data-testid={testid}>
    <CardHeader className="border-b border-slate-100 py-3"><CardTitle className="text-sm font-display">{title}</CardTitle></CardHeader>
    <CardContent className="p-3"><div style={{ width: "100%", height: 260 }}><ResponsiveContainer>{children}</ResponsiveContainer></div></CardContent>
  </Card>
);

const Empty = () => <div className="h-[260px] flex items-center justify-center text-sm text-slate-400">Belum ada data.</div>;
