import { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useBranding } from "@/context/BrandingContext";
import { MENUS, ROLE_LABELS } from "@/config/nav";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Plane, Menu, LogOut, KeyRound, ChevronDown, Search, Bell, FileSignature } from "lucide-react";
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

function ProfileDialog({ open, onOpenChange }) {
  const [title, setTitle] = useState("");
  const [signature, setSignature] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!open) return;
    api.get("/auth/me").then((r) => { setTitle(r.data?.title || ""); setSignature(r.data?.signature || ""); }).catch(() => {});
  }, [open]);
  const submit = async () => {
    setLoading(true);
    try {
      await api.put("/auth/me/profile", { title, signature });
      toast.success("Profil & tanda tangan tersimpan");
      onOpenChange(false);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally { setLoading(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white" data-testid="profile-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Profil & Tanda Tangan</DialogTitle>
          <DialogDescription>Atur jabatan dan unggah tanda tangan digital (PNG) Anda. Dipakai pada quotation yang Anda buat.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>Jabatan</Label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="mis. Sales Consultant" data-testid="profile-title-input" />
          </div>
          <div className="space-y-2">
            <Label>Tanda Tangan Digital (PNG, maks 2MB)</Label>
            <div className="flex items-center gap-3">
              {signature ? <img src={signature} alt="signature" className="h-14 w-28 rounded object-contain border border-slate-200 bg-white" data-testid="profile-signature-preview" /> : <div className="h-14 w-28 rounded bg-slate-100 flex items-center justify-center text-[10px] text-slate-400">TTD</div>}
              <div className="flex-1 space-y-1">
                <input type="file" accept="image/png,image/*" data-testid="profile-signature-upload" onChange={(e) => {
                  const f = e.target.files?.[0]; if (!f) return;
                  if (f.size > 2 * 1024 * 1024) { toast.error("Tanda tangan maksimal 2MB"); return; }
                  const rd = new FileReader(); rd.onload = () => setSignature(rd.result); rd.readAsDataURL(f);
                }} />
                {signature && <Button variant="ghost" size="sm" className="text-red-600 h-7" onClick={() => setSignature("")} data-testid="profile-signature-clear">Hapus tanda tangan</Button>}
              </div>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={loading} className="bg-blue-600 hover:bg-blue-700" data-testid="profile-submit-button">
            {loading ? "Menyimpan..." : "Simpan profil"}
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
  const cust = (id) => (id ? `/crm/${id}` : null);

  const groups = res ? [
    ["Customer", (res.customers || []).map((c) => ({ key: c._id, title: c.full_name, sub: `${c.customer_code || ""} · ${c.whatsapp || c.phone || c.email || ""}`, path: cust(c._id), tid: `search-customer-${c._id}` }))],
    ["Lead", (res.leads || []).map((l) => ({ key: l._id, title: l.interested_package || l.lead_code, sub: `${l.customer_name || ""} · ${l.status || ""}`, path: cust(l.customer_id) || "/sales", tid: `search-lead-${l._id}` }))],
    ["Quotation", (res.quotations || []).map((x) => ({ key: x._id, title: x.quotation_number, sub: `${x.customer_name || ""} · ${x.package_name || ""}`, path: cust(x.customer_id) || "/quotations", tid: `search-quotation-${x._id}` }))],
    ["Booking", (res.bookings || []).map((x) => ({ key: x._id, title: x.booking_number, sub: `${x.customer_name || ""} · ${x.package_name || ""}`, path: cust(x.customer_id) || "/booking", tid: `search-booking-${x._id}` }))],
    ["Invoice", (res.invoices || []).map((x) => ({ key: x._id, title: x.invoice_number, sub: `${x.customer_name || ""} · ${x.booking_number || ""}`, path: cust(x.customer_id) || "/accounting", tid: `search-invoice-${x._id}` }))],
    ["Payment", (res.payments || []).map((x) => ({ key: x._id, title: x.reference_number || x.invoice_number || "Payment", sub: `${x.invoice_number || ""} · Rp ${x.amount || 0}`, path: "/accounting", tid: `search-payment-${x._id}` }))],
    ["Package", (res.packages || []).map((x) => ({ key: x._id, title: x.package_name, sub: `${x.package_code || ""} · ${x.product_type || ""}`, path: "/products", tid: `search-package-${x._id}` }))],
    ["Refund", (res.refunds || []).map((x) => ({ key: x._id, title: x.refund_number, sub: `${x.customer_name || ""} · ${x.status || ""}`, path: cust(x.customer_id) || "/approvals", tid: `search-refund-${x._id}` }))],
    ["Conversation", (res.conversations || []).map((x) => ({ key: x._id || x.conversation_id, title: x.customer_name || x.whatsapp || "Chat", sub: (x.message || "").slice(0, 40), path: cust(x.customer_id) || "/ai-hub", tid: `search-conv-${x._id || x.conversation_id}` }))],
  ] : [];
  const empty = res && groups.every(([, items]) => items.length === 0);

  return (
    <div className="relative hidden md:block w-72">
      <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
      <Input value={q} onChange={(e) => setQ(e.target.value)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        onFocus={() => res && setOpen(true)} placeholder="Cari customer, booking, invoice, paket..."
        className="pl-9 h-9" data-testid="global-search-input" />
      {open && res && (
        <div className="absolute mt-2 right-0 w-96 bg-white border border-slate-200 rounded-md shadow-xl z-50 max-h-[28rem] overflow-y-auto" data-testid="global-search-results">
          {empty && <p className="p-3 text-sm text-slate-400">Tidak ada hasil.</p>}
          {groups.map(([label, items]) => items.length > 0 && (
            <div key={label} data-testid={`search-group-${label.toLowerCase()}`}>
              <p className="px-3 pt-2 pb-1 text-[10px] uppercase font-semibold text-slate-400 bg-slate-50">{label}</p>
              {items.map((it) => (
                <button key={it.key} onMouseDown={() => go(it.path)} data-testid={it.tid}
                  className="w-full text-left px-3 py-2 hover:bg-slate-50 text-sm">
                  <span className="font-medium text-slate-900">{it.title}</span>
                  <span className="text-slate-400 ml-2">{it.sub}</span>
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function NotificationBell() {
  const navigate = useNavigate();
  const [count, setCount] = useState(0);
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const loadCount = () => api.get("/notifications/unread-count").then((r) => setCount(r.data.count || 0)).catch(() => {});
  useEffect(() => { loadCount(); const t = setInterval(loadCount, 30000); return () => clearInterval(t); }, []);
  const onOpen = (v) => { setOpen(v); if (v) api.get("/notifications").then((r) => setItems(r.data || [])).catch(() => {}); };
  const click = async (n) => { if (!n.read) { await api.patch(`/notifications/${n.id}/read`); loadCount(); } setOpen(false); if (n.link) navigate(n.link); };
  const readAll = async () => { await api.post("/notifications/read-all"); setItems(items.map((i) => ({ ...i, read: true }))); setCount(0); };
  const pc = (p) => (p === "urgent" ? "bg-red-500" : p === "high" ? "bg-amber-500" : "bg-blue-500");
  return (
    <DropdownMenu open={open} onOpenChange={onOpen}>
      <DropdownMenuTrigger asChild>
        <button className="relative rounded-md p-2 hover:bg-slate-100 transition-colors" data-testid="notification-bell">
          <Bell className="h-5 w-5 text-slate-600" aria-hidden="true" />
          {count > 0 && <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center" data-testid="notification-count">{count > 99 ? "99+" : count}</span>}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 bg-white p-0 max-h-[26rem] overflow-y-auto" data-testid="notification-list">
        <div className="flex items-center justify-between px-3 py-2 border-b border-slate-100 sticky top-0 bg-white z-10">
          <span className="font-semibold text-sm text-slate-800">Notifications</span>
          <button onClick={readAll} className="text-xs text-blue-600 hover:underline" data-testid="notification-read-all">Mark all read</button>
        </div>
        {items.length === 0 ? <p className="p-4 text-sm text-slate-400 text-center">No notifications.</p> :
          items.map((n) => (
            <button key={n.id} onClick={() => click(n)} data-testid={`notification-item-${n.id}`}
              className={`w-full text-left px-3 py-2.5 border-b border-slate-50 hover:bg-slate-50 flex gap-2 ${n.read ? "" : "bg-blue-50/40"}`}>
              <span className={`mt-1 h-2 w-2 rounded-full shrink-0 ${n.read ? "bg-transparent" : pc(n.priority)}`} />
              <div className="min-w-0 flex-1">
                <p className={`text-sm truncate ${n.read ? "text-slate-600" : "font-semibold text-slate-900"}`}>{n.title}</p>
                <p className="text-xs text-slate-500 truncate">{n.body}</p>
                <p className="text-[10px] text-slate-400 mt-0.5">{(n.time || "").replace("T", " ").slice(0, 16)}</p>
              </div>
            </button>
          ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default function DashboardLayout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [cpOpen, setCpOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

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
            <NotificationBell />
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
              <DropdownMenuItem onClick={() => setProfileOpen(true)} data-testid="menu-profile">
                <FileSignature className="h-4 w-4 mr-2" aria-hidden="true" /> Profil & Tanda Tangan
              </DropdownMenuItem>
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
      <ProfileDialog open={profileOpen} onOpenChange={setProfileOpen} />
    </div>
  );
}
