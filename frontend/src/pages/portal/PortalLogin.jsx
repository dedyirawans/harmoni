import { useState } from "react";
import { useNavigate } from "react-router-dom";
import portalApi from "@/lib/portalApi";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Mail, MessageCircle, Loader2, Plane, ArrowLeft } from "lucide-react";
import { toast } from "sonner";

export default function PortalLogin() {
  const navigate = useNavigate();
  const [channel, setChannel] = useState("email");
  const [identifier, setIdentifier] = useState("");
  const [otp, setOtp] = useState("");
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);

  const requestOtp = async () => {
    if (!identifier.trim()) return toast.error(channel === "email" ? "Masukkan email" : "Masukkan nomor WhatsApp");
    setLoading(true);
    try {
      const { data } = await portalApi.post("/portal/auth/request-otp", { channel, identifier: identifier.trim() });
      setStep(2);
      if (data.debug_otp) toast.success(`OTP (preview): ${data.debug_otp}`, { duration: 8000 });
      else toast.success(`OTP dikirim via ${channel === "email" ? "Email" : "WhatsApp"}`);
    } catch (e) { toast.error(e.response?.data?.detail || "Gagal mengirim OTP"); }
    finally { setLoading(false); }
  };

  const verifyOtp = async () => {
    if (otp.trim().length < 6) return toast.error("Masukkan 6 digit OTP");
    setLoading(true);
    try {
      const { data } = await portalApi.post("/portal/auth/verify-otp", { channel, identifier: identifier.trim(), otp: otp.trim() });
      localStorage.setItem("portal_token", data.token);
      toast.success(`Selamat datang, ${data.customer.full_name || "Customer"}`);
      navigate("/portal");
    } catch (e) { toast.error(e.response?.data?.detail || "Verifikasi gagal"); }
    finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4" data-testid="portal-login-page">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-2 text-amber-400 mb-6 justify-center">
          <Plane className="h-6 w-6" /><span className="font-display text-xl font-bold text-white">Safar Customer Portal</span>
        </div>
        <Card className="border-slate-700 bg-white shadow-2xl">
          <CardContent className="p-6">
            {step === 1 ? (
              <>
                <h1 className="font-display text-2xl font-bold text-slate-900">Masuk ke Portal</h1>
                <p className="text-slate-500 text-sm mt-1 mb-4">Login dengan OTP via Email atau WhatsApp.</p>
                <div className="grid grid-cols-2 gap-2 mb-4">
                  <button onClick={() => setChannel("email")} data-testid="channel-email"
                    className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors ${channel === "email" ? "border-blue-600 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-500"}`}>
                    <Mail className="h-4 w-4" />Email</button>
                  <button onClick={() => setChannel("whatsapp")} data-testid="channel-whatsapp"
                    className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors ${channel === "whatsapp" ? "border-emerald-600 bg-emerald-50 text-emerald-700" : "border-slate-200 text-slate-500"}`}>
                    <MessageCircle className="h-4 w-4" />WhatsApp</button>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">{channel === "email" ? "Email" : "Nomor WhatsApp"}</Label>
                  <Input value={identifier} onChange={(e) => setIdentifier(e.target.value)}
                    placeholder={channel === "email" ? "nama@email.com" : "08xxxxxxxxxx"} data-testid="portal-identifier"
                    onKeyDown={(e) => e.key === "Enter" && requestOtp()} />
                </div>
                <Button onClick={requestOtp} disabled={loading} className="w-full mt-4 bg-blue-600 hover:bg-blue-700" data-testid="request-otp-btn">
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Kirim OTP"}</Button>
              </>
            ) : (
              <>
                <button onClick={() => { setStep(1); setOtp(""); }} className="flex items-center gap-1 text-sm text-slate-500 mb-3" data-testid="otp-back"><ArrowLeft className="h-4 w-4" />Ubah {channel === "email" ? "email" : "nomor"}</button>
                <h1 className="font-display text-2xl font-bold text-slate-900">Masukkan OTP</h1>
                <p className="text-slate-500 text-sm mt-1 mb-4">Kode 6 digit dikirim ke <b>{identifier}</b>. Berlaku 5 menit.</p>
                <Input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  placeholder="______" className="text-center text-2xl tracking-[0.5em] font-bold" data-testid="portal-otp"
                  onKeyDown={(e) => e.key === "Enter" && verifyOtp()} />
                <Button onClick={verifyOtp} disabled={loading} className="w-full mt-4 bg-blue-600 hover:bg-blue-700" data-testid="verify-otp-btn">
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Verifikasi & Masuk"}</Button>
                <button onClick={requestOtp} disabled={loading} className="w-full text-center text-sm text-blue-600 mt-3" data-testid="resend-otp-btn">Kirim ulang OTP</button>
              </>
            )}
          </CardContent>
        </Card>
        <p className="text-center text-slate-500 text-xs mt-4">Hanya untuk customer terdaftar. Butuh bantuan? Hubungi travel Anda.</p>
      </div>
    </div>
  );
}
