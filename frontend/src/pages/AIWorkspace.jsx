import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { Navigate } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { MessageCircle, BrainCircuit, MessageSquareHeart, Wrench, Gauge, Repeat, Bot } from "lucide-react";
import WhatsAppIntegration from "@/pages/WhatsAppIntegration";
import KnowledgeBase from "@/pages/KnowledgeBase";
import CommunicationStyle from "@/pages/CommunicationStyle";
import AITools from "@/pages/AITools";
import AIMonitoring from "@/pages/AIMonitoring";
import AutoFollowUp from "@/pages/AutoFollowUp";

const SUB = [
  ["whatsapp", "WhatsApp", MessageCircle, WhatsAppIntegration],
  ["knowledge", "Knowledge Base", BrainCircuit, KnowledgeBase],
  ["style", "Communication Style", MessageSquareHeart, CommunicationStyle],
  ["tools", "AI Tools", Wrench, AITools],
  ["monitoring", "AI Monitoring", Gauge, AIMonitoring],
  ["followup", "Auto Follow-Up", Repeat, AutoFollowUp],
];

export default function AIWorkspace() {
  const { user } = useAuth();
  const [tab, setTab] = useState("whatsapp");
  if (user?.role !== "super_admin") return <Navigate to="/dashboard" replace />;
  return (
    <div className="space-y-4" data-testid="ai-workspace">
      <div className="flex items-center gap-3">
        <div className="h-11 w-11 rounded-xl bg-blue-500/10 flex items-center justify-center"><Bot className="h-6 w-6 text-blue-600" /></div>
        <div>
          <h1 className="text-2xl font-bold text-slate-800">AI &amp; WhatsApp</h1>
          <p className="text-sm text-slate-500">Pusat kendali integrasi AI &amp; WhatsApp dalam satu tempat.</p>
        </div>
      </div>
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="flex flex-wrap h-auto gap-1" data-testid="ai-hub-tabs">
          {SUB.map(([k, label, Icon]) => (
            <TabsTrigger key={k} value={k} className="text-xs" data-testid={`ai-hub-tab-${k}`}><Icon className="h-3.5 w-3.5 mr-1" />{label}</TabsTrigger>
          ))}
        </TabsList>
        {SUB.map(([k, , , Comp]) => (
          <TabsContent key={k} value={k} className="mt-4"><Comp /></TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
