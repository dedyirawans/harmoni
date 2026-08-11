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
import Forbidden from "@/pages/Forbidden";
import Dashboard from "@/pages/Dashboard";
import Users from "@/pages/Users";
import AuditLog from "@/pages/AuditLog";
import Settings from "@/pages/Settings";
import HPP from "@/pages/HPP";
import Placeholder from "@/pages/Placeholder";

const PAGES = {
  "/dashboard": Dashboard,
  "/users": Users,
  "/audit": AuditLog,
  "/settings": Settings,
  "/hpp": HPP,
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
