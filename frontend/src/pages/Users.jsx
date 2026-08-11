import { useEffect, useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { UserPlus, MoreVertical, Loader2, Users2 } from "lucide-react";
import { toast } from "sonner";

const EMPTY = { name: "", email: "", phone: "", username: "", role: "sales", status: "active", branch: "", data_scope: "own", password: "" };

export default function Users() {
  const [users, setUsers] = useState(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = () => api.get("/users").then((r) => setUsers(r.data)).catch(() => setUsers([]));
  useEffect(() => { load(); }, []);

  const openCreate = () => { setEditing(null); setForm(EMPTY); setOpen(true); };
  const openEdit = (u) => {
    setEditing(u);
    setForm({ ...EMPTY, ...u, password: "" });
    setOpen(true);
  };

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      if (editing) {
        const payload = { ...form };
        if (!payload.password) delete payload.password;
        await api.put(`/users/${editing._id}`, payload);
        toast.success("User updated");
      } else {
        await api.post("/users", form);
        toast.success("User created");
      }
      setOpen(false);
      load();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  const toggleStatus = async (u) => {
    try {
      await api.patch(`/users/${u._id}/status`);
      load();
    } catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
  };

  const remove = async (u) => {
    try {
      await api.delete(`/users/${u._id}`);
      toast.success("User deleted");
      load();
    } catch (err) { toast.error(formatApiErrorDetail(err.response?.data?.detail)); }
  };

  const roleBadge = (role) => {
    const map = { super_admin: "bg-slate-900 text-white", sales: "bg-blue-50 text-blue-700 border-blue-200", accounting: "bg-slate-100 text-slate-700 border-slate-200" };
    return <Badge variant="outline" className={map[role]}>{role.replace("_", " ")}</Badge>;
  };

  return (
    <div className="space-y-6" data-testid="users-page">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">User Management</h1>
          <p className="text-slate-500 mt-1">Create and manage users, roles, and access scope.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-blue-600 hover:bg-blue-700" onClick={openCreate} data-testid="add-user-button">
              <UserPlus className="h-4 w-4 mr-2" aria-hidden="true" /> Add User
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-white max-w-lg" data-testid="user-dialog">
            <DialogHeader>
              <DialogTitle className="font-display">{editing ? "Edit user" : "New user"}</DialogTitle>
              <DialogDescription>Set the user's details, role, and access scope.</DialogDescription>
            </DialogHeader>
            <div className="grid grid-cols-2 gap-4 py-2">
              <div className="space-y-2 col-span-2 sm:col-span-1">
                <Label>Name</Label>
                <Input value={form.name} onChange={(e) => set("name")(e.target.value)} data-testid="user-name-input" />
              </div>
              <div className="space-y-2 col-span-2 sm:col-span-1">
                <Label>Username</Label>
                <Input value={form.username} onChange={(e) => set("username")(e.target.value)} data-testid="user-username-input" />
              </div>
              <div className="space-y-2 col-span-2 sm:col-span-1">
                <Label>Email</Label>
                <Input type="email" value={form.email} onChange={(e) => set("email")(e.target.value)} data-testid="user-email-input" />
              </div>
              <div className="space-y-2 col-span-2 sm:col-span-1">
                <Label>Phone</Label>
                <Input value={form.phone} onChange={(e) => set("phone")(e.target.value)} data-testid="user-phone-input" />
              </div>
              <div className="space-y-2 col-span-2 sm:col-span-1">
                <Label>Role</Label>
                <Select value={form.role} onValueChange={set("role")}>
                  <SelectTrigger data-testid="user-role-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-white">
                    <SelectItem value="super_admin">Super Admin</SelectItem>
                    <SelectItem value="sales">Sales</SelectItem>
                    <SelectItem value="accounting">Accounting</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2 col-span-2 sm:col-span-1">
                <Label>Branch</Label>
                <Input value={form.branch} onChange={(e) => set("branch")(e.target.value)} data-testid="user-branch-input" />
              </div>
              {form.role === "sales" && (
                <div className="space-y-2 col-span-2">
                  <Label>Data Scope (Sales)</Label>
                  <Select value={form.data_scope} onValueChange={set("data_scope")}>
                    <SelectTrigger data-testid="user-scope-select"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-white">
                      <SelectItem value="own">Own Data Only (default)</SelectItem>
                      <SelectItem value="branch">Branch Data</SelectItem>
                      <SelectItem value="all">All Sales Data</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
              <div className="space-y-2 col-span-2 sm:col-span-1">
                <Label>Status</Label>
                <Select value={form.status} onValueChange={set("status")}>
                  <SelectTrigger data-testid="user-status-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-white">
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2 col-span-2 sm:col-span-1">
                <Label>{editing ? "New password (optional)" : "Password"}</Label>
                <Input type="password" value={form.password} onChange={(e) => set("password")(e.target.value)} data-testid="user-password-input" />
              </div>
            </div>
            <DialogFooter>
              <Button onClick={save} disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="user-save-button">
                {saving ? "Saving..." : editing ? "Save changes" : "Create user"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card className="border-slate-200 shadow-sm overflow-hidden">
        {users === null ? (
          <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
        ) : users.length === 0 ? (
          <div className="p-12 text-center text-slate-500">
            <Users2 className="h-8 w-8 mx-auto text-slate-300" aria-hidden="true" />
            <p className="mt-2">No users yet.</p>
          </div>
        ) : (
          <Table data-testid="users-table">
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Branch</TableHead>
                <TableHead>Scope</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-12"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u._id} className="hover:bg-slate-50" data-testid={`user-row-${u.username}`}>
                  <TableCell>
                    <div className="font-medium text-slate-900">{u.name}</div>
                    <div className="text-xs text-slate-400">@{u.username}</div>
                  </TableCell>
                  <TableCell className="text-slate-600">{u.email}</TableCell>
                  <TableCell>{roleBadge(u.role)}</TableCell>
                  <TableCell className="text-slate-600">{u.branch || "—"}</TableCell>
                  <TableCell className="text-slate-600 capitalize">{u.role === "sales" ? u.data_scope : "all"}</TableCell>
                  <TableCell>
                    <button onClick={() => toggleStatus(u)} data-testid={`status-toggle-${u.username}`}>
                      <Badge variant="outline" className={u.status === "active" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-500"}>
                        {u.status}
                      </Badge>
                    </button>
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" data-testid={`user-actions-${u.username}`}>
                          <MoreVertical className="h-4 w-4" aria-hidden="true" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="bg-white">
                        <DropdownMenuItem onClick={() => openEdit(u)} data-testid={`edit-user-${u.username}`}>Edit</DropdownMenuItem>
                        <DropdownMenuItem onClick={() => toggleStatus(u)}>Toggle status</DropdownMenuItem>
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <div className="relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm text-red-600 hover:bg-red-50" data-testid={`delete-user-${u.username}`}>Delete</div>
                          </AlertDialogTrigger>
                          <AlertDialogContent className="bg-white">
                            <AlertDialogHeader>
                              <AlertDialogTitle>Delete {u.name}?</AlertDialogTitle>
                              <AlertDialogDescription>This action cannot be undone.</AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction className="bg-red-600 hover:bg-red-700" onClick={() => remove(u)} data-testid={`confirm-delete-${u.username}`}>Delete</AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
