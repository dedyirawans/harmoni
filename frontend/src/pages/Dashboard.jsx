import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { ROLE_LABELS } from "@/config/nav";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { TrendingUp } from "lucide-react";

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => setStats(r.data)).catch(() => setStats({ cards: [] }));
  }, []);

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="font-display text-3xl font-bold text-slate-900">
            {user.role === "sales" ? "My Dashboard" : user.role === "accounting" ? "Accounting Dashboard" : "Dashboard"}
          </h1>
          <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-700">{ROLE_LABELS[user.role]}</Badge>
        </div>
        <p className="text-slate-500 mt-1">Welcome back, {user.name}. Here's your snapshot for today.</p>
      </div>

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

      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-8 text-center">
          <h3 className="font-display text-lg font-semibold text-slate-900">More insights coming soon</h3>
          <p className="text-slate-500 mt-2 max-w-lg mx-auto">
            Detailed dashboard widgets and analytics for your role will be delivered in the next phase. This foundation
            build focuses on authentication, RBAC, and administration.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
