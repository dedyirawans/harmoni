import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, ArrowDownCircle, ArrowUpCircle, Receipt, Wallet, Bell, TrendingUp } from "lucide-react";
import { ResponsiveContainer, LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from "recharts";

const rp = (v) => "Rp " + (Number(v || 0)).toLocaleString("id-ID");
const short = (v) => "Rp " + (Number(v || 0) / 1e6).toFixed(1) + "jt";
const COLORS = ["#2563eb", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"];

export default function AccountingDashboard() {
  const nav = useNavigate();
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/accounting-dashboard").then((r) => setD(r.data)).catch(() => setD(false)); }, []);
  if (d === null) return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  if (d === false) return <div className="p-8 text-slate-400">Gagal memuat dashboard.</div>;

  const Kpi = ({ label, value, testid }) => (
    <div className="rounded-lg border border-slate-100 px-4 py-3" data-testid={testid}>
      <p className="text-xs text-slate-400">{label}</p>
      <p className="text-lg font-bold text-slate-900 mt-0.5">{value}</p>
    </div>
  );
  const Group = ({ icon: Icon, title, color, children }) => (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="border-b border-slate-100 py-3"><CardTitle className="text-sm font-display flex items-center gap-2"><Icon className={`h-4 w-4 ${color}`} />{title}</CardTitle></CardHeader>
      <CardContent className="p-3 grid grid-cols-2 lg:grid-cols-3 gap-2">{children}</CardContent>
    </Card>
  );
  const Out = ({ label, value, to, testid, money }) => (
    <button onClick={() => to && nav(to)} data-testid={testid} className="flex items-center justify-between rounded-lg border border-slate-100 px-4 py-3 hover:bg-blue-50 hover:border-blue-200 transition-colors text-left w-full">
      <span className="text-sm text-slate-600">{label}</span>
      <Badge className="bg-blue-600 text-white">{money ? short(value) : value}</Badge>
    </button>
  );

  const cash = d.trends.cash_in.map((c, i) => ({ month: c.month, in: c.value, out: d.trends.cash_out[i].value }));
  const aging = [
    { b: "Current", v: d.receivable.current }, { b: "1-30", v: d.receivable.d1_30 }, { b: "31-60", v: d.receivable.d31_60 },
    { b: "61-90", v: d.receivable.d61_90 }, { b: ">90", v: d.receivable.d90 },
  ];
  const payStat = Object.entries(d.payment_status).map(([k, v]) => ({ status: k, count: v }));

  return (
    <div className="space-y-5" data-testid="accounting-dashboard">
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900">Accounting Dashboard</h1>
        <p className="text-slate-500 mt-0.5">Uang masuk, uang keluar &amp; outstanding · periode {d.period}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Group icon={ArrowDownCircle} title="Money In" color="text-emerald-600">
          <Kpi label="Revenue" value={short(d.money_in.revenue)} testid="ki-revenue" />
          <Kpi label="Payment Received" value={short(d.money_in.payment_received)} testid="ki-payment" />
          <Kpi label="Invoice" value={short(d.money_in.invoice)} testid="ki-invoice" />
          <Kpi label="DP" value={short(d.money_in.dp_received)} testid="ki-dp" />
          <Kpi label="Installment" value={short(d.money_in.installment_received)} testid="ki-inst" />
          <Kpi label="Final Payment" value={short(d.money_in.final_received)} testid="ki-final" />
        </Group>
        <Group icon={ArrowUpCircle} title="Money Out" color="text-red-500">
          <Kpi label="Expense" value={short(d.money_out.expense)} testid="ko-expense" />
          <Kpi label="Supplier Payment" value={short(d.money_out.supplier_payment)} testid="ko-supplier" />
          <Kpi label="Refund" value={short(d.money_out.refund)} testid="ko-refund" />
          <Kpi label="Commission Payable" value={short(d.money_out.commission_payable)} testid="ko-commission" />
          <Kpi label="Operational" value={short(d.money_out.operational_expense)} testid="ko-operational" />
          <Kpi label="—" value="" />
        </Group>
        <Group icon={Wallet} title="Receivable" color="text-amber-600">
          <Kpi label="Total" value={short(d.receivable.total)} testid="rc-total" />
          <Kpi label="Current" value={short(d.receivable.current)} testid="rc-current" />
          <Kpi label="1-30 Days" value={short(d.receivable.d1_30)} testid="rc-1-30" />
          <Kpi label="31-60 Days" value={short(d.receivable.d31_60)} testid="rc-31-60" />
          <Kpi label="61-90 Days" value={short(d.receivable.d61_90)} testid="rc-61-90" />
          <Kpi label=">90 Days" value={short(d.receivable.d90)} testid="rc-90" />
        </Group>
        <Group icon={Receipt} title="Tax & Refund" color="text-indigo-600">
          <Kpi label="DPP" value={short(d.tax.dpp)} testid="tx-dpp" />
          <Kpi label="PPN" value={short(d.tax.ppn)} testid="tx-ppn" />
          <Kpi label="Tax Payable" value={short(d.tax.tax_payable)} testid="tx-payable" />
          <Kpi label="Refund Pending" value={d.refund.pending_approval} testid="rf-pending" />
          <Kpi label="Refund Approved" value={short(d.refund.approved)} testid="rf-approved" />
          <Kpi label="Refund Paid" value={short(d.refund.paid)} testid="rf-paid" />
        </Group>
      </div>

      <Card className="border-slate-200 shadow-sm" data-testid="accounting-outstanding">
        <CardHeader className="border-b border-slate-100 py-3"><CardTitle className="text-sm font-display flex items-center gap-2"><Bell className="h-4 w-4 text-red-500" />Accounting Outstanding</CardTitle></CardHeader>
        <CardContent className="p-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
          <Out label="Unpaid Invoice" value={d.outstanding.unpaid_invoice} to="/accounting" testid="ao-unpaid" />
          <Out label="Overdue Invoice" value={d.outstanding.overdue_invoice} to="/accounting" testid="ao-overdue" />
          <Out label="Outstanding Receivable" value={d.outstanding.outstanding_receivable} money to="/accounting" testid="ao-receivable" />
          <Out label="Pending Refund" value={d.outstanding.pending_refund} to="/approvals" testid="ao-refund" />
          <Out label="Pending Commission" value={d.outstanding.pending_commission} to="/commission" testid="ao-commission" />
          <Out label="Tax Payable" value={d.outstanding.tax_payable} money to="/tax" testid="ao-tax" />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Cash Flow (In vs Out)">
          <BarChart data={cash}><CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" /><XAxis dataKey="month" tick={{ fontSize: 11 }} /><YAxis tickFormatter={(v) => (v / 1e6).toFixed(0) + "jt"} tick={{ fontSize: 11 }} /><Tooltip formatter={(v) => rp(v)} /><Bar dataKey="in" fill="#10b981" radius={[4, 4, 0, 0]} /><Bar dataKey="out" fill="#ef4444" radius={[4, 4, 0, 0]} /></BarChart>
        </ChartCard>
        <ChartCard title="Cash In Trend">
          <LineChart data={d.trends.cash_in}><CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" /><XAxis dataKey="month" tick={{ fontSize: 11 }} /><YAxis tickFormatter={(v) => (v / 1e6).toFixed(0) + "jt"} tick={{ fontSize: 11 }} /><Tooltip formatter={(v) => rp(v)} /><Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2} dot /></LineChart>
        </ChartCard>
        <ChartCard title="Receivable Aging">
          <BarChart data={aging}><CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" /><XAxis dataKey="b" tick={{ fontSize: 11 }} /><YAxis tickFormatter={(v) => (v / 1e6).toFixed(0) + "jt"} tick={{ fontSize: 11 }} /><Tooltip formatter={(v) => rp(v)} /><Bar dataKey="v" radius={[4, 4, 0, 0]}>{aging.map((e, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Bar></BarChart>
        </ChartCard>
        <ChartCard title="Payment Status">
          <BarChart data={payStat}><CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" /><XAxis dataKey="status" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="count" radius={[4, 4, 0, 0]}>{payStat.map((e, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Bar></BarChart>
        </ChartCard>
        <ChartCard title="Revenue by Package">
          <BarChart data={d.revenue_by_package} layout="vertical"><XAxis type="number" tickFormatter={(v) => (v / 1e6).toFixed(0) + "jt"} tick={{ fontSize: 11 }} /><YAxis dataKey="package" type="category" width={110} tick={{ fontSize: 10 }} /><Tooltip formatter={(v) => rp(v)} /><Bar dataKey="value" fill="#2563eb" radius={[0, 4, 4, 0]} /></BarChart>
        </ChartCard>
        <ChartCard title="Expense Breakdown">
          <BarChart data={d.expense_breakdown}><CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" /><XAxis dataKey="category" tick={{ fontSize: 10 }} /><YAxis tickFormatter={(v) => (v / 1e6).toFixed(0) + "jt"} tick={{ fontSize: 11 }} /><Tooltip formatter={(v) => rp(v)} /><Bar dataKey="value" radius={[4, 4, 0, 0]}>{d.expense_breakdown.map((e, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Bar></BarChart>
        </ChartCard>
      </div>
    </div>
  );
}

const ChartCard = ({ title, children }) => (
  <Card className="border-slate-200 shadow-sm">
    <CardHeader className="border-b border-slate-100 py-3"><CardTitle className="text-sm font-display">{title}</CardTitle></CardHeader>
    <CardContent className="p-3"><div style={{ width: "100%", height: 240 }}><ResponsiveContainer>{children}</ResponsiveContainer></div></CardContent>
  </Card>
);
