import { useState } from "react";
import { useSearchParams, useNavigate, Link } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { CheckCircle2 } from "lucide-react";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (pw !== confirm) return toast.error("Passwords do not match");
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: pw });
      setDone(true);
      toast.success("Password reset successful");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-slate-50">
      <div className="w-full max-w-sm">
        {done ? (
          <div className="text-center" data-testid="reset-success">
            <CheckCircle2 className="h-12 w-12 text-emerald-600 mx-auto" aria-hidden="true" />
            <h2 className="font-display text-2xl font-bold text-slate-900 mt-4">Password updated</h2>
            <p className="text-sm text-slate-500 mt-1">You can now sign in with your new password.</p>
            <Button className="mt-6 bg-amber-600 hover:bg-amber-700" data-testid="go-to-login"
              onClick={() => navigate("/login")}>Back to sign in</Button>
          </div>
        ) : (
          <>
            <h2 className="font-display text-2xl font-bold text-slate-900">Set a new password</h2>
            <p className="text-sm text-slate-500 mt-1">Choose a strong password for your account.</p>
            {!token && (
              <p className="mt-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
                Missing reset token. Please use the link from your email.
              </p>
            )}
            <form onSubmit={submit} className="mt-8 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="np">New password</Label>
                <Input id="np" type="password" data-testid="reset-password-input" value={pw}
                  onChange={(e) => setPw(e.target.value)} placeholder="At least 6 characters" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cp">Confirm password</Label>
                <Input id="cp" type="password" data-testid="reset-confirm-input" value={confirm}
                  onChange={(e) => setConfirm(e.target.value)} />
              </div>
              <Button type="submit" disabled={loading || !token} data-testid="reset-submit-button"
                className="w-full bg-amber-600 hover:bg-amber-700 text-white">
                {loading ? "Updating..." : "Reset password"}
              </Button>
            </form>
            <Link to="/login" className="mt-6 inline-block text-sm text-amber-700 hover:underline">← Back to sign in</Link>
          </>
        )}
      </div>
    </div>
  );
}
