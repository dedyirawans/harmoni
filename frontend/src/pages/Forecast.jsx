import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Loader2, TrendingUp, Wallet, ArrowDownCircle, ArrowUpCircle, Percent, RefreshCw, Target,
} from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Cell, Legend,
} from "recharts";

const rp = (v) => "Rp " + Number(v || 0).toLocaleString("id-ID");
const rpShort = (v) => {
  const n = Number(v || 0);
  if (Math.abs(n) >= 1e9) return "Rp " + (n / 1e9).toFixed(1) + "M";
  if (Math.abs(n) >= 1e6) return "Rp " + (n / 1e6).toFixed(1) + "jt";
  if (Math.abs(n) >= 1e3) return "Rp " + (n / 1e3).toFixed(0) + "rb";
  return "Rp " + n;
};
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Ags", "Sep", "Okt", "Nov", "Des"];
const mLabel = (mk) => (mk && mk.length >= 7 ? `${MONTHS[+mk.slice(5, 7) - 1]} ${mk.slice(2, 4)}` : "—");

const STAGE_COLORS = {
  NEW: "#94a3b8", CONTACTED: "#60a5fa", QUALIFIED: "#818cf8",
  QUOTATION: "#a78bfa", NEGOTIATION: "#f59e0b", BOOKING: "#10b981",
};

const ActualBadge = () => (
  <Badge className="bg-slate-700 text-white border-slate-700 text-[10px] tracking-wide" data-testid="badge-actual">ACTUAL</Badge>
);
const ForecastBadge = () => (
  <Badge className="bg-indigo-100 text-indigo-700 border-indigo-200 text-[10px] tracking-wide" data-testid="badge-forecast">FORECAST</Badge>
);

export default function Forecast() {
  const [data, setData] = useState(undefined);
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    api.get("/forecast/dashboard").then((r) => setData(r.data)).catch((e) => {
      setData(null);
      toast.error(e.response?.data?.detail || "Gagal memuat forecast");
    }).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  if (data === undefined) return <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-indigo-600" /></div>;
  if (data === null) return <div className="p-12 text-center text-red-600" data-testid="forecast-error">Forecast tidak tersedia (khusus Super Admin).</div>;

  const sf = data.sales_forecast;
  const cf = data.cash_flow_forecast;
  const rf = data.receivable_forecast;
  const ue = data.upcoming_expense;
  const uc = data.upcoming_commission;

  return (
    <div className="space-y-6" data-testid="forecast-page">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900 flex items-center gap-2">
            <Target className="h-7 w-7 text-indigo-600" aria-hidden="true" /> Forecasting
          </h1>
          <p className="text-sm text-slate-500 mt-1">Proyeksi penjualan &amp; keuangan. Dibedakan tegas dari data akuntansi aktual.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs text-slate-500"><ActualBadge /> = realisasi <span className="mx-1">·</span> <ForecastBadge /> = proyeksi</div>
          <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="forecast-refresh">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {/* ============ 1. SALES FORECAST ============ */}
      <section data-testid="section-sales-forecast">
        <SectionTitle icon={TrendingUp} color="text-indigo-600" title="Sales Forecast" subtitle="Pipeline weighted by probability" />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <KpiCard label="Pipeline Value" value={rp(sf.pipeline_value)} hint="Total nilai deal terbuka" badge="forecast" icon={TrendingUp} testid="kpi-pipeline-value" />
          <KpiCard label="Probability Weighted Value" value={rp(sf.weighted_value)} hint="Σ nilai × probability stage" badge="forecast" icon={Percent} testid="kpi-weighted-value" />
          <KpiCard label="Expected Closing (3 bln)" value={rp(sf.buckets.next_3_months.weighted)} hint={sf.buckets.next_3_months.label} badge="forecast" icon={Target} testid="kpi-expected-closing" />
        </div>

        {/* Period buckets */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
          {[["Current Month", sf.buckets.current_month], ["Next Month", sf.buckets.next_month], ["Next 3 Months", sf.buckets.next_3_months]].map(([lbl, b], i) => (
            <Card key={i} className="border-slate-200 shadow-sm" data-testid={`sales-bucket-${i}`}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <p className="text-xs uppercase tracking-wide font-semibold text-slate-500">{lbl}</p>
                  <span className="text-[11px] text-slate-400">{b.label}</span>
                </div>
                <div className="mt-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-xs text-slate-500"><ForecastBadge /> Weighted</span>
                    <span className="font-display text-lg font-bold text-indigo-700">{rpShort(b.weighted)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-slate-400">Pipeline (raw)</span>
                    <span className="text-sm font-medium text-slate-600">{rpShort(b.pipeline)}</span>
                  </div>
                  <div className="flex items-center justify-between border-t border-slate-100 pt-2">
                    <span className="flex items-center gap-1.5 text-xs text-slate-500"><ActualBadge /> Booked</span>
                    <span className="text-sm font-semibold text-slate-800">{rpShort(b.actual)}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Stage summary table */}
        <Card className="border-slate-200 shadow-sm mt-4">
          <CardHeader className="pb-2"><CardTitle className="text-sm text-slate-700">Pipeline per Stage</CardTitle></CardHeader>
          <CardContent className="p-4 pt-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="stage-summary-table">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-400 border-b border-slate-100">
                    <th className="py-2">Stage</th><th className="py-2">Probability</th><th className="py-2 text-right">Deals</th>
                    <th className="py-2 text-right">Pipeline Value</th><th className="py-2 text-right">Weighted</th>
                  </tr>
                </thead>
                <tbody>
                  {sf.stage_summary.map((s) => (
                    <tr key={s.stage} className="border-b border-slate-50" data-testid={`stage-row-${s.stage}`}>
                      <td className="py-2"><span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: STAGE_COLORS[s.stage] }} />{s.stage}</span></td>
                      <td className="py-2 text-slate-500">{Math.round(s.probability * 100)}%</td>
                      <td className="py-2 text-right">{s.count}</td>
                      <td className="py-2 text-right text-slate-600">{rp(s.value)}</td>
                      <td className="py-2 text-right font-semibold text-indigo-700">{rp(s.weighted)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* ============ 2. CASH FLOW FORECAST ============ */}
      <section data-testid="section-cash-flow">
        <SectionTitle icon={Wallet} color="text-emerald-600" title="Cash Flow Forecast" subtitle="Proyeksi arus kas 6 bulan (In − Out)" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card className="border-slate-200 shadow-sm lg:col-span-2">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2"><span className="text-sm font-medium text-slate-700">Cash In vs Cash Out</span><ForecastBadge /></div>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={cf.series.map((s) => ({ ...s, name: mLabel(s.month) }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tickFormatter={rpShort} tick={{ fontSize: 11 }} width={70} />
                  <Tooltip formatter={(v) => rp(v)} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="cash_in" name="Cash In" fill="#10b981" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="cash_out" name="Cash Out" fill="#ef4444" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <ResponsiveContainer width="100%" height={120}>
                <LineChart data={cf.series.map((s) => ({ ...s, name: mLabel(s.month) }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tickFormatter={rpShort} tick={{ fontSize: 11 }} width={70} />
                  <Tooltip formatter={(v) => rp(v)} />
                  <Line type="monotone" dataKey="net" name="Net Cash Flow" stroke="#6366f1" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
          <div className="space-y-4">
            <Card className="border-slate-700 bg-slate-800 text-white shadow-sm" data-testid="cf-actual-card">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2"><span className="text-xs uppercase tracking-wide font-semibold text-slate-300">Bulan Ini (Realisasi)</span><ActualBadge /></div>
                <p className="text-[11px] text-slate-400">{mLabel(cf.actual_current_month.month)}</p>
                <div className="mt-2 space-y-1.5 text-sm">
                  <Row l="Cash In" v={rp(cf.actual_current_month.cash_in)} c="text-emerald-300" />
                  <Row l="Cash Out" v={rp(cf.actual_current_month.cash_out)} c="text-red-300" />
                  <div className="border-t border-slate-700 pt-1.5"><Row l="Net" v={rp(cf.actual_current_month.net)} c="text-white font-bold" /></div>
                </div>
              </CardContent>
            </Card>
            <Card className="border-indigo-200 bg-indigo-50/50 shadow-sm">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-2"><span className="text-xs uppercase tracking-wide font-semibold text-indigo-600">Total Proyeksi (6 bln)</span><ForecastBadge /></div>
                <div className="mt-1 space-y-1.5 text-sm">
                  <Row l="Total Cash In" v={rp(cf.forecast_total_in)} c="text-emerald-700" />
                  <Row l="Total Cash Out" v={rp(cf.forecast_total_out)} c="text-red-700" />
                  <div className="border-t border-indigo-200 pt-1.5"><Row l="Net" v={rp(cf.forecast_total_in - cf.forecast_total_out)} c="text-indigo-800 font-bold" /></div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* ============ 3. RECEIVABLE + 4. EXPENSE + 5. COMMISSION ============ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Receivable */}
        <section data-testid="section-receivable">
          <SectionTitle icon={ArrowDownCircle} color="text-emerald-600" title="Receivable Forecast" subtitle={`Outstanding ${rpShort(rf.total_outstanding)}`} small />
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-end mb-1"><ForecastBadge /></div>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={rf.by_month.map((m) => ({ name: mLabel(m.month), amount: m.amount }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={rpShort} tick={{ fontSize: 10 }} width={55} />
                  <Tooltip formatter={(v) => rp(v)} />
                  <Bar dataKey="amount" name="Receivable" fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <ItemList testid="receivable-items" items={rf.items} render={(it) => (
                <><div><p className="font-medium text-slate-800">{it.booking_number}</p><p className="text-[11px] text-slate-400">{it.customer} · {it.label} · {it.due_date}</p></div>
                <span className="text-sm font-semibold text-emerald-700">{rpShort(it.amount)}</span></>
              )} />
            </CardContent>
          </Card>
        </section>

        {/* Upcoming Expense */}
        <section data-testid="section-expense">
          <SectionTitle icon={ArrowUpCircle} color="text-red-600" title="Upcoming Expense" subtitle={`Supplier + Refund ${rpShort(ue.total)}`} small />
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-end mb-1"><ForecastBadge /></div>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={ue.by_month.map((m) => ({ name: mLabel(m.month), supplier: m.supplier, refund: m.refund }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={rpShort} tick={{ fontSize: 10 }} width={55} />
                  <Tooltip formatter={(v) => rp(v)} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="supplier" name="Supplier" stackId="a" fill="#ef4444" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="refund" name="Refund" stackId="a" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <ItemList testid="expense-items" items={ue.items} render={(it) => (
                <><div><p className="font-medium text-slate-800">{it.name}<Badge className={`ml-2 text-[9px] ${it.type === "REFUND" ? "bg-amber-100 text-amber-700 border-amber-200" : "bg-red-100 text-red-700 border-red-200"}`}>{it.type}</Badge></p><p className="text-[11px] text-slate-400">{it.invoice_number} · {it.due_date}</p></div>
                <span className="text-sm font-semibold text-red-700">{rpShort(it.amount)}</span></>
              )} />
            </CardContent>
          </Card>
        </section>

        {/* Upcoming Commission */}
        <section data-testid="section-commission">
          <SectionTitle icon={Percent} color="text-purple-600" title="Upcoming Commission" subtitle={`Payable ${rpShort(uc.total)}`} small />
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-end mb-1"><ForecastBadge /></div>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={uc.by_month.map((m) => ({ name: mLabel(m.month), amount: m.amount }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={rpShort} tick={{ fontSize: 10 }} width={55} />
                  <Tooltip formatter={(v) => rp(v)} />
                  <Bar dataKey="amount" name="Commission" fill="#a855f7" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <ItemList testid="commission-items" items={uc.items} render={(it) => (
                <><div><p className="font-medium text-slate-800">{it.sales}</p><p className="text-[11px] text-slate-400">{it.customer} · {it.booking_number} · {mLabel(it.payout_month)}</p></div>
                <span className="text-sm font-semibold text-purple-700">{rpShort(it.amount)}</span></>
              )} />
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}

function SectionTitle({ icon: Icon, color, title, subtitle, small }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon className={`h-5 w-5 ${color}`} aria-hidden="true" />
      <div>
        <h2 className={`font-display font-bold text-slate-900 ${small ? "text-base" : "text-lg"}`}>{title}</h2>
        {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
      </div>
    </div>
  );
}

function KpiCard({ label, value, hint, badge, icon: Icon, testid }) {
  return (
    <Card className="border-slate-200 shadow-sm" data-testid={testid}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <p className="text-xs uppercase tracking-wide font-semibold text-slate-500">{label}</p>
          {badge === "forecast" ? <ForecastBadge /> : <ActualBadge />}
        </div>
        <div className="flex items-center gap-2 mt-2">
          <Icon className="h-5 w-5 text-indigo-400" aria-hidden="true" />
          <p className="font-display text-2xl font-bold text-slate-900">{value}</p>
        </div>
        <p className="text-[11px] text-slate-400 mt-1">{hint}</p>
      </CardContent>
    </Card>
  );
}

function Row({ l, v, c }) {
  return <div className="flex items-center justify-between"><span className="text-slate-400 text-xs">{l}</span><span className={c}>{v}</span></div>;
}

function ItemList({ items, render, testid }) {
  if (!items || items.length === 0) return <p className="text-xs text-slate-400 text-center py-4">Tidak ada data.</p>;
  return (
    <div className="mt-3 space-y-1.5 max-h-64 overflow-y-auto" data-testid={testid}>
      {items.map((it, i) => (
        <div key={i} className="flex items-center justify-between border border-slate-100 rounded-md px-3 py-2">{render(it)}</div>
      ))}
    </div>
  );
}
