import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { ROLE_LABELS } from "@/config/nav";
import { fmtIDR } from "@/config/crm";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  TrendingUp, UserPlus, Briefcase, CalendarClock, FileText, Users2,
} from "lucide-react";

export default function Dashboard() {
  const { user, hasPerm } = useAuth();
  const navigate = useNavigate();
  const isSales = hasPerm("sales.view");
  const [stats, setStats] = useState(null);
  const [sales, setSales] = useState(null);

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => setStats(r.data)).catch(() => setStats({ cards: [] }));
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

  const quickActions = [
    { label: "New Customer", icon: UserPlus, to: "/crm" },
    { label: "New Lead", icon: Briefcase, to: "/sales" },
    { label: "Follow Up", icon: CalendarClock, to: "/follow-ups" },
    { label: "Quotation", icon: FileText, to: "/sales" },
    { label: "Customers", icon: Users2, to: "/crm" },
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

      {isSales && (
        <div className="flex flex-wrap gap-2" data-testid="quick-actions">
          {quickActions.map((a) => (
            <Button key={a.label} variant="outline" onClick={() => navigate(a.to)} data-testid={`qa-${a.label.toLowerCase().replace(/\s+/g, "-")}`}
              className="border-slate-200 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-200">
              <a.icon className="h-4 w-4 mr-2" aria-hidden="true" />{a.label}
            </Button>
          ))}
        </div>
      )}

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

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-8 text-center">
          <h3 className="font-display text-lg font-semibold text-slate-900">More insights coming soon</h3>
          <p className="text-slate-500 mt-2 max-w-lg mx-auto">
            Deeper analytics and charts will arrive in a later phase. Phase 2 delivers CRM, leads pipeline, and follow-ups.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
