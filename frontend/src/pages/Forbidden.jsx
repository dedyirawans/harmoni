import { Link } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function Forbidden() {
  return (
    <div className="min-h-[70vh] flex items-center justify-center p-6" data-testid="forbidden-page">
      <div className="text-center max-w-md">
        <div className="h-16 w-16 rounded-full bg-red-50 border border-red-200 flex items-center justify-center mx-auto">
          <ShieldAlert className="h-8 w-8 text-red-600" aria-hidden="true" />
        </div>
        <h1 className="font-display text-3xl font-bold text-slate-900 mt-6">403 — Forbidden</h1>
        <p className="text-slate-500 mt-2 leading-relaxed">
          You don't have permission to access this page. This restriction is enforced by the backend, not just hidden in the menu.
        </p>
        <Button asChild className="mt-6 bg-blue-600 hover:bg-blue-700" data-testid="forbidden-back-button">
          <Link to="/dashboard">Back to dashboard</Link>
        </Button>
      </div>
    </div>
  );
}
