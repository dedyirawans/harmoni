import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, TrendingUp, Users2, FileText, CalendarCheck, Bell, Wallet } from "lucide-react";
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell,
} from "recharts";

const rp = (v) => "Rp " + (Number(v || 0)).toLocaleString("id-ID");
const short = (v) => "Rp " + (Number(v || 0) / 1e6).toFixed(1) + "jt";
const COLORS = ["#2563eb", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"];

export default function SalesDashboard() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/sales-dashboard").then((r) => setD(r.data)).catch(() => setD(false)); }, []);
  if (d === null) return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>;
  if (d === false) return <div className="p-8 text-slate-400">Gagal memuat dashboard.</div>;
  const k = d.kpi;

  const Kpi = ({ label, value, sub, testid }) => (
    <div className="rounded-lg border border-slate-100 px-4 py-3" data-testid={testid}>
      <p className="text-xs text-slate-400">{label}</p>
      <p className="text-xl font-bold text-slate-900 mt-0.5">{value}</p>
      {sub && <p className="text-[11px] text-slate-400">{sub}</p>}
    </div>
  );
  const Group = ({ icon: Icon, title, color, children }) => (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="border-b border-slate-100 py-3"><CardTitle className="text-sm font-display flex items-center gap-2"><Icon className={`h-4 w-4 ${color}`} />{title}</CardTitle></CardHeader>
      <CardContent className="p-3 grid grid-cols-2 lg:grid-cols-4 gap-2">{children}</CardContent>
    </Card>
  );
  const Out = ({ label, value, to, testid }) => (
    <button onClick={() => to && nav(to)} data-testid={testid}
      className="flex items-center justify-between rounded-lg border border-slate-100 px-4 py-3 hover:bg-blue-50 hover:border-blue-200 transition-colors text-left w-full">
      <span className="text-sm text-slate-600">{label}</span>
      <Badge className="bg-blue-600 text-white">{value}</Badge>
    </button>
  );

  return (
    <div className="space-y-5" data-testid="sales-dashboard">
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900">Sales Dashboard</h1>
        <p className="text-slate-500 mt-0.5">Performa &amp; follow up milik {user.name} · periode {d.period}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Group icon={Users2} title="Lead" color="text-blue-600">
          <Kpi label="New" value={k.lead.new} testid="kpi-lead-new" />
          <Kpi label="Active" value={k.lead.active} testid="kpi-lead-active" />
          <Kpi label="Qualified" value={k.lead.qualified} testid="kpi-lead-qualified" />
          <Kpi label="Lost" value={k.lead.lost} testid="kpi-lead-lost" />
        </Group>
        <Group icon={FileText} title="Quotation" color="text-indigo-600">
          <Kpi label="Total" value={k.quotation.total} testid="kpi-quot-total" />
          <Kpi label="Outstanding" value={k.quotation.outstanding} testid="kpi-quot-outstanding" />
          <Kpi label="Converted" value={k.quotation.converted} testid="kpi-quot-converted" />
          <Kpi label="Conversion" value={k.quotation.conversion_rate + "%"} testid="kpi-quot-conversion" />
        </Group>
        <Group icon={CalendarCheck} title="Booking" color="text-emerald-600">
          <Kpi label="Total Booking" value={k.booking.total} testid="kpi-booking-total" />
          <Kpi label="Total Pax" value={k.booking.total_pax} testid="kpi-booking-pax" />
          <Kpi label="Total Sales" value={short(k.booking.total_sales)} testid="kpi-booking-sales" />
          <Kpi label="Avg Pax/Booking" value={k.booking.total ? (k.booking.total_pax / k.booking.total).toFixed(1) : 0} testid="kpi-booking-avgpax" />
        </Group>
        <Group icon={Wallet} title="Commission (bulan ini)" color="text-amber-600">
          <Kpi label="Pax" value={k.commission.current_pax} testid="kpi-comm-pax" />
          <Kpi label="Tier" value={k.commission.tier} testid="kpi-comm-tier" />
          <Kpi label="Estimated" value={rp(k.commission.estimated)} testid="kpi-comm-est" />
          <Kpi label="Approved / Paid" value={`${short(k.commission.approved)} / ${short(k.commission.paid)}`} testid="kpi-comm-paid" />
        </Group>
      </div>

      <Card className="border-slate-200 shadow-sm" data-testid="my-outstanding">
        <CardHeader className="border-b border-slate-100 py-3"><CardTitle className="text-sm font-display flex items-center gap-2"><Bell className="h-4 w-4 text-red-500" />My Outstanding</CardTitle></CardHeader>
        <CardContent className="p-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          <Out label="Lead belum di-follow up" value={d.outstanding.leads_no_followup} to="/sales" testid="out-leads" />
          <Out label="Quotation outstanding" value={d.outstanding.quotation_outstanding} to="/quotations" testid="out-quotation" />
          <Out label="Follow up due today" value={k.follow_up.due_today} to="/follow-ups" testid="out-fu-today" />
          <Out label="Follow up overdue" value={k.follow_up.overdue} to="/follow-ups" testid="out-fu-overdue" />
          <Out label="Payment outstanding" value={d.outstanding.payment_outstanding} to="/booking" testid="out-payment" />
          <Out label="Upcoming departure" value={d.outstanding.upcoming_departure} to="/booking" testid="out-departure" />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Sales Trend (per bulan)">
          <LineChart data={d.trends.sales}><CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" /><XAxis dataKey="month" tick={{ fontSize: 11 }} /><YAxis tickFormatter={(v) => (v / 1e6).toFixed(0) + "jt"} tick={{ fontSize: 11 }} /><Tooltip formatter={(v) => rp(v)} /><Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2} dot /></LineChart>
        </ChartCard>
        <ChartCard title="Lead Funnel">
          <BarChart data={d.funnel} layout="vertical"><XAxis type="number" tick={{ fontSize: 11 }} /><YAxis dataKey="stage" type="category" width={90} tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="count" radius={[0, 4, 4, 0]}>{d.funnel.map((e, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Bar></BarChart>
        </ChartCard>
        <ChartCard title="Booking & Pax Trend">
          <BarChart data={d.trends.booking.map((b, i) => ({ month: b.month, booking: b.count, pax: d.trends.pax[i].pax }))}><CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" /><XAxis dataKey="month" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="booking" fill="#10b981" radius={[4, 4, 0, 0]} /><Bar dataKey="pax" fill="#0ea5e9" radius={[4, 4, 0, 0]} /></BarChart>
        </ChartCard>
        <ChartCard title="Lead Source">
          <BarChart data={d.lead_source}><CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" /><XAxis dataKey="source" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="count" radius={[4, 4, 0, 0]}>{d.lead_source.map((e, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Bar></BarChart>
        </ChartCard>
      </div>

      <Card className="border-slate-200 shadow-sm" data-testid="package-performance">
        <CardHeader className="border-b border-slate-100 py-3"><CardTitle className="text-sm font-display flex items-center gap-2"><TrendingUp className="h-4 w-4 text-blue-600" />Package Performance</CardTitle></CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead><tr className="bg-slate-800 text-white text-left"><th className="px-3 py-2">Package</th><th className="px-3 py-2 border-l border-slate-600">Lead</th><th className="px-3 py-2 border-l border-slate-600">Quotation</th><th className="px-3 py-2 border-l border-slate-600">Booking</th><th className="px-3 py-2 border-l border-slate-600">Pax</th><th className="px-3 py-2 border-l border-slate-600">Sales Value</th></tr></thead>
            <tbody>
              {d.package_performance.length === 0 ? <tr><td colSpan={6} className="px-3 py-6 text-center text-slate-400">Belum ada data.</td></tr> :
                d.package_performance.map((p, i) => (
                  <tr key={i} className={i % 2 ? "bg-slate-50" : "bg-white"}>
                    <td className="px-3 py-2 font-medium">{p.package}</td>
                    <td className="px-3 py-2 border-l border-slate-100">{p.lead}</td>
                    <td className="px-3 py-2 border-l border-slate-100">{p.quotation}</td>
                    <td className="px-3 py-2 border-l border-slate-100">{p.booking}</td>
                    <td className="px-3 py-2 border-l border-slate-100">{p.pax}</td>
                    <td className="px-3 py-2 border-l border-slate-100 font-semibold">{rp(p.sales_value)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

const ChartCard = ({ title, children }) => (
  <Card className="border-slate-200 shadow-sm">
    <CardHeader className="border-b border-slate-100 py-3"><CardTitle className="text-sm font-display">{title}</CardTitle></CardHeader>
    <CardContent className="p-3"><div style={{ width: "100%", height: 240 }}><ResponsiveContainer>{children}</ResponsiveContainer></div></CardContent>
  </Card>
);
