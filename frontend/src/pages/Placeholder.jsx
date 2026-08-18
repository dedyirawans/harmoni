import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Construction } from "lucide-react";

const META = {
  "/crm": ["CRM", "Manage customers, leads, and follow-ups."],
  "/sales": ["Sales Management", "Quotations, pipelines and sales performance."],
  "/products": ["Product Management", "Umrah & tour packages catalog."],
  "/booking": ["Booking", "Reservations, travelers and departures."],
  "/accounting": ["Accounting", "Transactions, ledgers and reconciliation."],
  "/transactions": ["Transactions", "Incoming and outgoing payment records."],
  "/tax": ["Tax", "PPN configuration and tax reports."],
  "/commission": ["Commission", "Sales commission tracking and payouts."],
  "/reports": ["Reports", "Operational and financial reports with export."],
  "/integration": ["Integration", "Third-party connections."],
  "/packages": ["Packages", "Browse available travel packages."],
  "/departures": ["Departures", "Upcoming departure schedules."],
  "/notifications": ["Notifications", "Your alerts and updates."],
};

export default function Placeholder() {
  const { pathname } = useLocation();
  const [title, desc] = META[pathname] || ["Coming Soon", "This module is under development."];
  const [notes, setNotes] = useState(null);

  useEffect(() => {
    if (pathname === "/notifications") api.get("/notifications").then((r) => setNotes(r.data)).catch(() => setNotes([]));
  }, [pathname]);

  return (
    <div className="space-y-6" data-testid={`placeholder-${pathname.slice(1)}`}>
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900">{title}</h1>
        <p className="text-slate-500 mt-1">{desc}</p>
      </div>

      {pathname === "/notifications" && notes ? (
        <div className="space-y-3">
          {notes.map((n) => (
            <Card key={n.id} className="border-slate-200 shadow-sm">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-slate-900">{n.title}</p>
                  <span className="text-xs text-slate-400">{n.time}</span>
                </div>
                <p className="text-sm text-slate-500 mt-1">{n.body}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="border-slate-200 shadow-sm border-dashed">
          <CardContent className="p-12 text-center">
            <div className="h-14 w-14 rounded-full bg-blue-50 border border-blue-200 flex items-center justify-center mx-auto">
              <Construction className="h-7 w-7 text-blue-600" aria-hidden="true" />
            </div>
            <h3 className="font-display text-lg font-semibold text-slate-900 mt-5">Planned for a later phase</h3>
            <p className="text-slate-500 mt-2 max-w-md mx-auto">
              This module is part of the roadmap. Phase 1 delivers the foundation: authentication, RBAC, users,
              audit log, and settings.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
