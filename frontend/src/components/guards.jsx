import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Loader2 } from "lucide-react";
import Forbidden from "@/pages/Forbidden";

function Splash() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50" data-testid="auth-loading">
      <Loader2 className="h-8 w-8 animate-spin text-amber-600" aria-hidden="true" />
    </div>
  );
}

export function ProtectedRoute({ children }) {
  const { user, booting } = useAuth();
  if (booting || user === undefined) return <Splash />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export function RequirePermission({ perm, children }) {
  const { hasPerm } = useAuth();
  if (perm && !hasPerm(perm)) return <Forbidden />;
  return children;
}
