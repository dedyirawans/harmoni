import { useAuth } from "@/context/AuthContext";
import SalesDashboard from "@/pages/SalesDashboard";
import AccountingDashboard from "@/pages/AccountingDashboard";
import SuperAdminDashboard from "@/pages/SuperAdminDashboard";

export default function Dashboard() {
  const { user } = useAuth();
  if (user.role === "sales") return <SalesDashboard />;
  if (user.role === "accounting") return <AccountingDashboard />;
  return <SuperAdminDashboard />;
}
