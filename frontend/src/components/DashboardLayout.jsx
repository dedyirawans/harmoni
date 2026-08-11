import { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useBranding } from "@/context/BrandingContext";
import { MENUS, ROLE_LABELS } from "@/config/nav";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Plane, Menu, LogOut, KeyRound, ChevronDown, Search } from "lucide-react";
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
  const { company_name, logo } = useBranding();
  return (
    <div className="flex flex-col h-full bg-slate-900">
      <div className="flex items-center gap-2 px-5 h-16 border-b border-white/10 shrink-0">
        {logo ? (
          <img src={logo} alt="" className="h-8 w-8 rounded-md object-cover bg-white" />
        ) : (
          <div className="h-8 w-8 rounded-md bg-blue-600 flex items-center justify-center">
            <Plane className="h-4.5 w-4.5 text-white" aria-hidden="true" />
          </div>
        )}
        <span className="font-display text-lg font-bold text-white truncate">{company_name}</span>
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

function GlobalSearch() {
  const { hasPerm } = useAuth();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!q || q.length < 2) { setRes(null); setOpen(false); return; }
    const t = setTimeout(() => {
      api.get("/search", { params: { q } }).then((r) => { setRes(r.data); setOpen(true); }).catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  if (!hasPerm("crm.view")) return null;

  const go = (path) => { setOpen(false); setQ(""); setRes(null); navigate(path); };
  const empty = res && res.customers.length === 0 && res.leads.length === 0;

  return (
    <div className="relative hidden md:block w-72">
      <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
      <Input value={q} onChange={(e) => setQ(e.target.value)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        onFocus={() => res && setOpen(true)} placeholder="Search customers, leads, WhatsApp..."
        className="pl-9 h-9" data-testid="global-search-input" />
      {open && res && (
        <div className="absolute mt-2 w-full bg-white border border-slate-200 rounded-md shadow-xl z-50 max-h-96 overflow-y-auto" data-testid="global-search-results">
          {empty && <p className="p-3 text-sm text-slate-400">No results.</p>}
          {res.customers.length > 0 && <p className="px-3 pt-2 pb-1 text-[10px] uppercase font-semibold text-slate-400">Customers</p>}
          {res.customers.map((c) => (
            <button key={c._id} onMouseDown={() => go(`/crm/${c._id}`)} data-testid={`search-customer-${c._id}`}
              className="w-full text-left px-3 py-2 hover:bg-slate-50 text-sm">
              <span className="font-medium text-slate-900">{c.full_name}</span>
              <span className="text-slate-400 ml-2">{c.whatsapp || c.email}</span>
            </button>
          ))}
          {res.leads.length > 0 && <p className="px-3 pt-2 pb-1 text-[10px] uppercase font-semibold text-slate-400">Leads</p>}
          {res.leads.map((l) => (
            <button key={l._id} onMouseDown={() => go("/sales")} data-testid={`search-lead-${l._id}`}
              className="w-full text-left px-3 py-2 hover:bg-slate-50 text-sm">
              <span className="font-medium text-slate-900">{l.interested_package || l.lead_code}</span>
              <span className="text-slate-400 ml-2">{l.customer_name} · {l.status}</span>
            </button>
          ))}
        </div>
      )}
    </div>
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

          <div className="flex items-center gap-3">
            <GlobalSearch />
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
          </div>
        </header>

        <main className="p-4 md:p-8">{children}</main>
      </div>

      <ChangePasswordDialog open={cpOpen} onOpenChange={setCpOpen} />
    </div>
  );
}
