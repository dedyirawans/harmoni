import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { BrandingProvider } from "@/context/BrandingContext";
import { ProtectedRoute, RequirePermission } from "@/components/guards";
import DashboardLayout from "@/components/DashboardLayout";
import { ROUTE_PERMS } from "@/config/nav";
import { Toaster } from "@/components/ui/sonner";

import Login from "@/pages/Login";
import ResetPassword from "@/pages/ResetPassword";
import PortalLogin from "@/pages/portal/PortalLogin";
import PortalDashboard from "@/pages/portal/PortalDashboard";
import Forbidden from "@/pages/Forbidden";
import Dashboard from "@/pages/Dashboard";
import Users from "@/pages/Users";
import AuditLog from "@/pages/AuditLog";
import Settings from "@/pages/Settings";
import HPP from "@/pages/HPP";
import Placeholder from "@/pages/Placeholder";
import Customers from "@/pages/Customers";
import Customer360 from "@/pages/Customer360";
import SalesPipeline from "@/pages/SalesPipeline";
import SalesActivity from "@/pages/SalesActivity";
import FollowUps from "@/pages/FollowUps";
import Products from "@/pages/Products";
import ProductDetail from "@/pages/ProductDetail";
import Departures from "@/pages/Departures";
import Operations from "@/pages/Operations";
import Suppliers from "@/pages/Suppliers";
import Quotations from "@/pages/Quotations";
import Bookings from "@/pages/Bookings";
import BookingDetail from "@/pages/BookingDetail";
import Accounting from "@/pages/Accounting";
import Integration from "@/pages/Integration";
import Commission from "@/pages/Commission";
import Approvals from "@/pages/Approvals";
import Tax from "@/pages/Tax";
import Reports from "@/pages/Reports";
import Forecast from "@/pages/Forecast";
import N8N from "@/pages/N8N";
import WhatsAppIntegration from "@/pages/WhatsAppIntegration";
import KnowledgeBase from "@/pages/KnowledgeBase";
import CommunicationStyle from "@/pages/CommunicationStyle";
import AITools from "@/pages/AITools";
import Tasks from "@/pages/Tasks";
import ApprovalCenter from "@/pages/ApprovalCenter";

const PAGES = {
  "/dashboard": Dashboard,
  "/users": Users,
  "/audit": AuditLog,
  "/settings": Settings,
  "/hpp": HPP,
  "/crm": Customers,
  "/sales": SalesPipeline,
  "/sales-activity": SalesActivity,
  "/follow-ups": FollowUps,
  "/products": Products,
  "/packages": Products,
  "/departures": Departures,
  "/operations": Operations,
  "/suppliers": Suppliers,
  "/quotations": Quotations,
  "/booking": Bookings,
  "/accounting": Accounting,
  "/integration": Integration,
  "/commission": Commission,
  "/approvals": Approvals,
  "/tax": Tax,
  "/reports": Reports,
  "/forecast": Forecast,
  "/n8n": N8N,
  "/whatsapp": WhatsAppIntegration,
  "/knowledge-base": KnowledgeBase,
  "/communication-style": CommunicationStyle,
  "/ai-tools": AITools,
  "/tasks": Tasks,
  "/approval-center": ApprovalCenter,
};

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <BrandingProvider>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/portal/login" element={<PortalLogin />} />
            <Route path="/portal" element={<PortalDashboard />} />

            {Object.entries(ROUTE_PERMS).map(([path, perm]) => {
              const Page = PAGES[path] || Placeholder;
              return (
                <Route
                  key={path}
                  path={path}
                  element={
                    <ProtectedRoute>
                      <DashboardLayout>
                        <RequirePermission perm={perm}>
                          <Page />
                        </RequirePermission>
                      </DashboardLayout>
                    </ProtectedRoute>
                  }
                />
              );
            })}

            <Route
              path="/crm/:id"
              element={
                <ProtectedRoute>
                  <DashboardLayout>
                    <RequirePermission perm="crm.view">
                      <Customer360 />
                    </RequirePermission>
                  </DashboardLayout>
                </ProtectedRoute>
              }
            />

            <Route
              path="/products/:id"
              element={
                <ProtectedRoute>
                  <DashboardLayout>
                    <RequirePermission perm={["product.view", "hpp.view"]}>
                      <ProductDetail />
                    </RequirePermission>
                  </DashboardLayout>
                </ProtectedRoute>
              }
            />

            <Route
              path="/packages/:id"
              element={
                <ProtectedRoute>
                  <DashboardLayout>
                    <RequirePermission perm="packages.view">
                      <ProductDetail />
                    </RequirePermission>
                  </DashboardLayout>
                </ProtectedRoute>
              }
            />

            <Route
              path="/booking/:id"
              element={
                <ProtectedRoute>
                  <DashboardLayout>
                    <RequirePermission perm="booking.view">
                      <BookingDetail />
                    </RequirePermission>
                  </DashboardLayout>
                </ProtectedRoute>
              }
            />

            <Route
              path="/forbidden"
              element={
                <ProtectedRoute>
                  <DashboardLayout><Forbidden /></DashboardLayout>
                </ProtectedRoute>
              }
            />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </AuthProvider>
        </BrandingProvider>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;
