import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Search, History, Settings2, ScrollText } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import HotelSearch from "@/pages/hotel/HotelSearch";
import SearchHistory from "@/pages/hotel/SearchHistory";
import ApiSettings from "@/pages/hotel/ApiSettings";
import ApiLogs from "@/pages/hotel/ApiLogs";

export default function HotelWorkspace() {
  const { user } = useAuth();
  const isAdmin = user?.role === "super_admin";
  const [tab, setTab] = useState("search");

  const SUB = [
    ["search", "Hotel Search", Search, HotelSearch, true],
    ["history", "Search History", History, SearchHistory, true],
    ["settings", "API Settings", Settings2, ApiSettings, isAdmin],
    ["logs", "API Logs", ScrollText, ApiLogs, isAdmin],
  ].filter((x) => x[4]);

  return (
    <div className="space-y-6" data-testid="hotel-workspace">
      <PageHeader
        title="Hotel"
        subtitle="Pencarian hotel & integrasi Agoda Affiliate API."
      />
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
