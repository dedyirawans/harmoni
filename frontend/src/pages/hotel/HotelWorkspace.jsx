import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Search, History, Settings2, ScrollText, SearchCheck, FileText, Wallet } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import HotelSearch from "@/pages/hotel/HotelSearch";
import SearchHistory from "@/pages/hotel/SearchHistory";
import ApiSettings from "@/pages/hotel/ApiSettings";
import ApiLogs from "@/pages/hotel/ApiLogs";

const rupiah = (n) => {
  try { return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(Number(n) || 0); }
  catch { return `Rp ${Number(n || 0).toLocaleString("id-ID")}`; }
};

function StatCard({ icon: Icon, label, value, testid }) {
  return (
    <Card className="border-slate-200 shadow-sm" data-testid={testid}>
      <CardContent className="p-4 flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-blue-50 flex items-center justify-center"><Icon className="h-4 w-4 text-blue-600" /></div>
        <div>
          <p className="text-xs text-slate-500">{label}</p>
          <p className="text-lg font-bold text-slate-800">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export default function HotelWorkspace() {
  const { user } = useAuth();
  const isAdmin = user?.role === "super_admin";
  const canStats = user?.role === "super_admin" || user?.role === "sales";
  const [tab, setTab] = useState("search");
  const [stats, setStats] = useState(null);

  useEffect(() => { if (canStats) api.get("/hotel/stats").then((r) => setStats(r.data)).catch(() => {}); }, [canStats]);

  const SUB = [
    ["search", "Hotel Search", Search, HotelSearch, true],
    ["history", "Search History", History, SearchHistory, true],
    ["settings", "API Settings", Settings2, ApiSettings, isAdmin],
    ["logs", "API Logs", ScrollText, ApiLogs, isAdmin],
  ].filter((x) => x[4]);

  return (
    <div className="space-y-6" data-testid="hotel-workspace">
      <PageHeader title="Hotel" subtitle="Pencarian hotel, integrasi Agoda, & integrasi ke Sales/Quotation." />

      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4" data-testid="hotel-stats">
          <StatCard icon={SearchCheck} label="Pencarian Hotel" value={stats.hotel_searches ?? 0} testid="hotel-stat-searches" />
          <StatCard icon={FileText} label="Quotation dengan Hotel" value={stats.hotel_quotations ?? 0} testid="hotel-stat-quotations" />
          <StatCard icon={Wallet} label="Nilai Hotel (Quotation)" value={rupiah(stats.hotel_revenue)} testid="hotel-stat-revenue" />
        </div>
      )}

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex flex-wrap h-auto gap-1" data-testid="hotel-tabs">
          {SUB.map(([k, label, Icon]) => (
            <TabsTrigger key={k} value={k} className="text-xs" data-testid={`hotel-tab-${k}`}>
              <Icon className="h-3.5 w-3.5 mr-1" />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
        {SUB.map(([k, , , Comp]) => (
          <TabsContent key={k} value={k} className="mt-4">
            <Comp />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
