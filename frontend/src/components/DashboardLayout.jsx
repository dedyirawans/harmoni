import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { MENUS, ROLE_LABELS } from "@/config/nav";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Plane, Menu, LogOut, KeyRound, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";

function NavList({ onNavigate }) {
  const { user } = useAuth();
  const location = useLocation();
  const items = MENUS[user.role] || [];
  return (
    <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto" data-testid="sidebar-nav">
      {items.map((item) => {
        const active = location.pathname === item.path;
        const Icon = item.icon;
        return (
          <Link
            key={item.label}
            to={item.path}
            onClick={onNavigate}
            data-testid={`nav-${item.path.slice(1)}`}
            className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors duration-200 ${
              active ? "bg-white/10 text-white" : "text-slate-400 hover:text-white hover:bg-white/5"
            }`}
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

function SidebarInner({ onNavigate }) {
  const { user } = useAuth();
  return (
    <div className="flex flex-col h-full bg-slate-900">
      <div className="flex items-center gap-2 px-5 h-16 border-b border-white/10 shrink-0">
        <div className="h-8 w-8 rounded-md bg-amber-600 flex items-center justify-center">
          <Plane className="h-4.5 w-4.5 text-white" aria-hidden="true" />
        </div>
        <span className="font-display text-lg font-bold text-white">Safar CRM</span>
      </div>
      <NavList onNavigate={onNavigate} />
      <div className="px-5 py-4 border-t border-white/10 shrink-0">
        <p className="text-xs uppercase tracking-wide text-slate-500 font-semibold">{ROLE_LABELS[user.role]}</p>
        <p className="text-sm text-slate-300 truncate mt-0.5">{user.name}</p>
      </div>
    </div>
  );
}

function ChangePasswordDialog({ open, onOpenChange }) {
  const [cur, setCur] = useState("");
  const [np, setNp] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    try {
      await api.post("/auth/change-password", { current_password: cur, new_password: np });
      toast.success("Password changed");
      onOpenChange(false);
      setCur(""); setNp("");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white" data-testid="change-password-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Change password</DialogTitle>
          <DialogDescription>Enter your current password and choose a new one.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>Current password</Label>
            <Input type="password" value={cur} onChange={(e) => setCur(e.target.value)} data-testid="cp-current-input" />
          </div>
          <div className="space-y-2">
            <Label>New password</Label>
            <Input type="password" value={np} onChange={(e) => setNp(e.target.value)} data-testid="cp-new-input" />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={loading} className="bg-blue-600 hover:bg-blue-700" data-testid="cp-submit-button">
            {loading ? "Saving..." : "Update password"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function DashboardLayout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [cpOpen, setCpOpen] = useState(false);

  const doLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const initials = (user.name || "U").split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex fixed inset-y-0 left-0 w-64 flex-col">
        <SidebarInner />
      </aside>

      <div className="md:pl-64">
        {/* Header */}
        <header className="sticky top-0 z-30 h-16 flex items-center justify-between px-4 md:px-8 backdrop-blur-xl bg-white/90 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden" data-testid="mobile-menu-button">
                  <Menu className="h-5 w-5" aria-hidden="true" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="p-0 w-64 border-0">
                <SidebarInner onNavigate={() => setMobileOpen(false)} />
              </SheetContent>
            </Sheet>
            <span className="font-display font-semibold text-slate-900 hidden sm:block">
              {ROLE_LABELS[user.role]} Workspace
            </span>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-slate-100 transition-colors duration-200" data-testid="user-menu-trigger">
                <div className="h-8 w-8 rounded-full bg-slate-900 text-white text-xs font-semibold flex items-center justify-center">
                  {initials}
                </div>
                <span className="text-sm font-medium text-slate-700 hidden sm:block">{user.name}</span>
                <ChevronDown className="h-4 w-4 text-slate-400" aria-hidden="true" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56 bg-white">
              <DropdownMenuLabel>
                <div className="font-medium">{user.name}</div>
                <div className="text-xs text-slate-500 font-normal">{user.email}</div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => setCpOpen(true)} data-testid="menu-change-password">
                <KeyRound className="h-4 w-4 mr-2" aria-hidden="true" /> Change password
              </DropdownMenuItem>
              <DropdownMenuItem onClick={doLogout} data-testid="menu-logout" className="text-red-600 focus:text-red-600">
                <LogOut className="h-4 w-4 mr-2" aria-hidden="true" /> Logout
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>

        <main className="p-4 md:p-8">{children}</main>
      </div>

      <ChangePasswordDialog open={cpOpen} onOpenChange={setCpOpen} />
    </div>
  );
}
