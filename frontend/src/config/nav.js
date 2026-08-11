import {
  LayoutDashboard, Users2, Briefcase, Package, CalendarCheck, Calculator,
  Receipt, Percent, FileBarChart, Plug, UserCog, Settings, ScrollText,
  Plane, PlaneTakeoff, Bell, Wallet, TrendingUp, ListChecks,
} from "lucide-react";

// Route -> permission required (mirrors backend). null = any authenticated user.
export const ROUTE_PERMS = {
  "/dashboard": null,
  "/crm": "crm.view",
  "/sales": "sales.view",
  "/products": ["product.view", "hpp.view"],
  "/booking": "booking.view",
  "/accounting": "accounting.view",
  "/transactions": "transactions.view",
  "/tax": "tax.view",
  "/commission": "commission.view",
  "/reports": "reports.view",
  "/integration": "integration.view",
  "/users": "users.view",
  "/settings": "settings.view",
  "/audit": "audit.view",
  "/packages": "packages.view",
  "/departures": "departures.view",
  "/hpp": "hpp.view",
  "/notifications": "notifications.view",
  "/follow-ups": "sales.view",
};

export const MENUS = {
  super_admin: [
    { label: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
    { label: "CRM", path: "/crm", icon: Users2 },
    { label: "Sales Management", path: "/sales", icon: Briefcase },
    { label: "Follow Ups", path: "/follow-ups", icon: ListChecks },
    { label: "Product Management", path: "/products", icon: Package },
    { label: "Booking", path: "/booking", icon: CalendarCheck },
    { label: "Accounting", path: "/accounting", icon: Calculator },
    { label: "Tax", path: "/tax", icon: Receipt },
    { label: "Commission", path: "/commission", icon: Percent },
    { label: "Reports", path: "/reports", icon: FileBarChart },
    { label: "Integration", path: "/integration", icon: Plug },
    { label: "User Management", path: "/users", icon: UserCog },
    { label: "Settings", path: "/settings", icon: Settings },
    { label: "Audit Log", path: "/audit", icon: ScrollText },
  ],
  sales: [
    { label: "My Dashboard", path: "/dashboard", icon: LayoutDashboard },
    { label: "My CRM", path: "/crm", icon: Users2 },
    { label: "My Sales", path: "/sales", icon: Briefcase },
    { label: "Follow Ups", path: "/follow-ups", icon: ListChecks },
    { label: "Packages", path: "/packages", icon: Plane },
    { label: "Departures", path: "/departures", icon: PlaneTakeoff },
    { label: "My Commission", path: "/commission", icon: Wallet },
    { label: "Notifications", path: "/notifications", icon: Bell },
  ],
  accounting: [
    { label: "Accounting Dashboard", path: "/dashboard", icon: LayoutDashboard },
    { label: "Transactions", path: "/transactions", icon: Receipt },
    { label: "Costing / HPP", path: "/hpp", icon: TrendingUp },
    { label: "Packages", path: "/products", icon: Package },
    { label: "Tax", path: "/tax", icon: Percent },
    { label: "Commission", path: "/commission", icon: Wallet },
    { label: "Reports", path: "/reports", icon: FileBarChart },
    { label: "Notifications", path: "/notifications", icon: Bell },
  ],
};

export const ROLE_LABELS = {
  super_admin: "Super Admin",
  sales: "Sales",
  accounting: "Accounting",
};
