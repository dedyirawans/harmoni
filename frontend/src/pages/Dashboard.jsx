import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { ROLE_LABELS } from "@/config/nav";
import { fmtIDR } from "@/config/crm";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { TrendingUp } from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";

const BLUES = ["#2563eb", "#3b82f6", "#60a5fa", "#1d4ed8", "#93c5fd", "#0ea5e9", "#38bdf8", "#1e40af", "#bfdbfe"];

export default function Dashboard() {
  const { user, hasPerm } = useAuth();
  const isSales = hasPerm("sales.view");
  const [stats, setStats] = useState(null);
  const [sales, setSales] = useState(null);
  const [charts, setCharts] = useState(null);

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => setStats(r.data)).catch(() => setStats({ cards: [] }));
    api.get("/dashboard/charts").then((r) => setCharts(r.data)).catch(() => setCharts(null));
    if (isSales) api.get("/sales/dashboard").then((r) => setSales(r.data)).catch(() => setSales(null));
  }, [isSales]);

  const salesCards = sales && [
    { label: "New Leads", value: sales.new_leads },
    { label: "Follow Up Today", value: sales.follow_up_today },
    { label: "Overdue Follow Up", value: sales.overdue_follow_up },
    { label: "My Quotations", value: sales.my_quotations },
    { label: "My Bookings", value: sales.my_bookings },
    { label: "My Pax", value: sales.my_pax },
    { label: "Upcoming Departure", value: sales.upcoming_departure },
    { label: "Outstanding Customer", value: sales.outstanding_customer },
    { label: "Estimated Sales", value: fmtIDR(sales.estimated_sales) },
    { label: "Conversion Rate", value: `${sales.conversion_rate}%` },
  ];

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="font-display text-3xl font-bold text-slate-900">
            {user.role === "sales" ? "My Dashboard" : user.role === "accounting" ? "Accounting Dashboard" : "Dashboard"}
          </h1>
          <Badge variant="outline" className="border-blue-200 bg-blue-50 text-blue-700">{ROLE_LABELS[user.role]}</Badge>
        </div>
        <p className="text-slate-500 mt-1">Welcome back, {user.name}. Here's your snapshot for today.</p>
      </div>

      {isSales ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4" data-testid="sales-dashboard">
          {!salesCards
            ? Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-md" />)
            : salesCards.map((c) => (
                <Card key={c.label} className="border-slate-200 shadow-sm" data-testid={`sales-stat-${c.label.toLowerCase().replace(/\s+/g, "-")}`}>
                  <CardContent className="p-4">
                    <p className="text-[11px] uppercase tracking-wide font-semibold text-slate-500">{c.label}</p>
                    <p className="font-display text-xl font-bold text-slate-900 mt-1">{c.value}</p>
                  </CardContent>
                </Card>
              ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {!stats
            ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-md" />)
            : stats.cards.map((c) => (
                <Card key={c.label} className="border-slate-200 shadow-sm" data-testid={`stat-${c.label.toLowerCase().replace(/\s+/g, "-")}`}>
                  <CardContent className="p-5">
                    <p className="text-xs uppercase tracking-wide font-semibold text-slate-500">{c.label}</p>
                    <p className="font-display text-3xl font-bold text-slate-900 mt-2">{c.value}</p>
                    <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
                      <TrendingUp className="h-3 w-3 text-emerald-500" aria-hidden="true" /> {c.hint}
                    </p>
                  </CardContent>
                </Card>
              ))}
        </div>
      )}

      {!charts ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-72 rounded-md" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="dashboard-charts">
          <ChartCard title="Leads per Tahap Pipeline" testid="chart-leads-stage">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={charts.leads_by_stage} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#64748b" }} interval={0} angle={-25} textAnchor="end" height={54} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#64748b" }} />
                <Tooltip cursor={{ fill: "#eff6ff" }} />
                <Bar dataKey="value" name="Leads" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Tren Leads 6 Bulan Terakhir" testid="chart-monthly-leads">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={charts.monthly_leads} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#64748b" }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#64748b" }} />
                <Tooltip />
                <Line type="monotone" dataKey="value" name="Leads" stroke="#2563eb" strokeWidth={2.5} dot={{ r: 3, fill: "#2563eb" }} activeDot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Distribusi Paket per Kategori" testid="chart-packages-type">
            {charts.packages_by_type.length === 0 ? <Empty /> : (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={charts.packages_by_type} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={92} label={(e) => `${e.name}: ${e.value}`} labelLine={false} fontSize={11}>
                    {charts.packages_by_type.map((_, i) => <Cell key={i} fill={BLUES[i % BLUES.length]} />)}
                  </Pie>
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartCard>

          <ChartCard title="Leads per Sumber" testid="chart-leads-source">
            {charts.leads_by_source.length === 0 ? <Empty /> : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart layout="vertical" data={charts.leads_by_source} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: "#64748b" }} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#64748b" }} width={90} />
                  <Tooltip cursor={{ fill: "#eff6ff" }} />
                  <Bar dataKey="value" name="Leads" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </ChartCard>
        </div>
      )}
    </div>
  );
}

function ChartCard({ title, children, testid }) {
  return (
    <Card className="border-slate-200 shadow-sm" data-testid={testid}>
      <CardHeader className="pb-2"><CardTitle className="font-display text-base">{title}</CardTitle></CardHeader>
      <CardContent className="pt-2">{children}</CardContent>
    </Card>
  );
}

const Empty = () => <div className="h-[280px] flex items-center justify-center text-sm text-slate-400">Belum ada data.</div>;
