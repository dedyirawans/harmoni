import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useBranding } from "@/context/BrandingContext";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Plane } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

const MECCA_IMG =
  "https://images.unsplash.com/photo-1720549973451-018d3623b55a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2NzV8MHwxfHNlYXJjaHwxfHxtZWNjYSUyMHVtcmFoJTIwYXJjaGl0ZWN0dXJlfGVufDB8fHx8MTc4NjQxMjMyOHww&ixlib=rb-4.1.0&q=85";

export default function Login() {
  const { login } = useAuth();
  const { company_name: companyName, logo } = useBranding();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [forgotOpen, setForgotOpen] = useState(false);
  const [cfg, setCfg] = useState({
    heading: "Run your Umrah & Travel business with clarity.",
    subheading: "Leads, bookings, costing and commissions — unified with strict role-based access control.",
    background_image: MECCA_IMG,
  });

  useEffect(() => {
    api
      .get("/public/login-config")
      .then((r) => {
        const d = r.data || {};
        setCfg((c) => ({
          heading: d.heading || c.heading,
          subheading: d.subheading || c.subheading,
          background_image: d.background_image || c.background_image,
        }));
      })
      .catch(() => {});
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const res = await login(email, password);
    setLoading(false);
    if (res.ok) {
      toast.success("Welcome back");
      navigate("/dashboard", { replace: true });
    } else {
      setError(res.error);
    }
  };

  if (forgotOpen) return <ForgotInline onBack={() => setForgotOpen(false)} />;

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-2 bg-slate-50">
      {/* Left visual */}
      <div className="relative hidden md:block">
        <img src={cfg.background_image} alt="Login background" className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute inset-0 bg-slate-950/60" />
        <div className="relative z-10 flex flex-col justify-between h-full p-10 text-white">
          <div className="flex items-center gap-2">
            {logo ? (
              <img src={logo} alt="" className="h-9 w-9 rounded-md object-cover bg-white" />
            ) : (
              <div className="h-9 w-9 rounded-md bg-blue-600 flex items-center justify-center">
                <Plane className="h-5 w-5" aria-hidden="true" />
              </div>
            )}
            <span className="font-display text-xl font-bold">{companyName}</span>
          </div>
          <div className="max-w-md">
            <h1 className="font-display text-4xl font-bold leading-tight">{cfg.heading}</h1>
            <p className="mt-4 text-slate-200 leading-relaxed">{cfg.subheading}</p>
          </div>
          <p className="text-xs text-slate-300">© 2026 {companyName}</p>
        </div>
      </div>

      {/* Right form */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-sm">
          <div className="md:hidden flex items-center gap-2 mb-8">
            {logo ? (
              <img src={logo} alt="" className="h-9 w-9 rounded-md object-cover border border-slate-200" />
            ) : (
              <div className="h-9 w-9 rounded-md bg-blue-600 flex items-center justify-center">
                <Plane className="h-5 w-5 text-white" aria-hidden="true" />
              </div>
            )}
            <span className="font-display text-xl font-bold text-slate-900">{companyName}</span>
          </div>
          <h2 className="font-display text-2xl font-bold text-slate-900">Sign in</h2>
          <p className="text-sm text-slate-500 mt-1">Use your work email or username to continue.</p>

          <form onSubmit={submit} className="mt-8 space-y-4" data-testid="login-form">
            <div className="space-y-2">
              <Label htmlFor="email">Email or Username</Label>
              <Input id="email" data-testid="login-email-input" value={email}
                onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" autoFocus />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" data-testid="login-password-input" value={password}
                onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
            </div>
            {error && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2" data-testid="login-error">
                {error}
              </p>
            )}
            <Button type="submit" disabled={loading} data-testid="login-submit-button"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white">
              {loading ? "Signing in..." : "Sign in"}
            </Button>
            <button type="button" onClick={() => setForgotOpen(true)} data-testid="forgot-password-link"
              className="text-sm text-blue-700 hover:text-blue-800 hover:underline block mx-auto">
              Forgot your password?
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function ForgotInline({ onBack }) {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await api.post("/auth/forgot-password", { email });
      setSent(true);
      toast.success(data.message);
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-slate-50">
      <div className="w-full max-w-sm">
        <h2 className="font-display text-2xl font-bold text-slate-900">Forgot password</h2>
        <p className="text-sm text-slate-500 mt-1">Enter your email and we'll send a reset link.</p>
        {sent ? (
          <div className="mt-8 rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700" data-testid="forgot-success">
            If an account exists for <b>{email}</b>, a reset link has been sent. Check your inbox.
          </div>
        ) : (
          <form onSubmit={submit} className="mt-8 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="fp-email">Email</Label>
              <Input id="fp-email" data-testid="forgot-email-input" value={email}
                onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
            </div>
            <Button type="submit" disabled={loading} data-testid="forgot-submit-button"
              className="w-full bg-blue-600 hover:bg-blue-700 text-white">
              {loading ? "Sending..." : "Send reset link"}
            </Button>
          </form>
        )}
        <button onClick={onBack} className="mt-6 text-sm text-blue-700 hover:underline" data-testid="back-to-login">
          ← Back to sign in
        </button>
      </div>
    </div>
  );
}
