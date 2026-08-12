import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import api from "@/lib/api";
import { AlertTriangle, ShieldAlert, Loader2 } from "lucide-react";

export const expiryTone = (daysLeft) => {
  if (daysLeft == null) return null;
  if (daysLeft < 0) return { label: `Expired ${Math.abs(daysLeft)}d`, cls: "bg-red-100 text-red-700 border-red-300" };
  if (daysLeft <= 30) return { label: `${daysLeft}d left`, cls: "bg-red-50 text-red-700 border-red-200" };
  if (daysLeft <= 60) return { label: `${daysLeft}d left`, cls: "bg-orange-50 text-orange-700 border-orange-200" };
  if (daysLeft <= 90) return { label: `${daysLeft}d left`, cls: "bg-amber-50 text-amber-700 border-amber-200" };
  return null;
};

export const daysUntil = (isoDate) => {
  if (!isoDate) return null;
  try {
    const exp = new Date((isoDate || "").slice(0, 10) + "T00:00:00");
    const today = new Date(new Date().toISOString().slice(0, 10) + "T00:00:00");
    return Math.round((exp - today) / 86400000);
  } catch { return null; }
};

export default function ExpiringDocsWidget({ within = 90, className = "" }) {
  const nav = useNavigate();
  const [docs, setDocs] = useState(null);
  useEffect(() => {
    api.get(`/documents/expiring?within=${within}`).then((r) => setDocs(r.data || [])).catch(() => setDocs([]));
  }, [within]);

  return (
    <Card className={`border-slate-200 shadow-sm ${className}`} data-testid="expiring-docs-widget">
      <CardHeader className="border-b border-slate-100 py-3">
        <CardTitle className="text-sm font-display flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-red-600" />
          Dokumen Akan Kedaluwarsa
          {docs && docs.length > 0 && <Badge className="bg-red-100 text-red-700 border-red-200" data-testid="expiring-docs-count">{docs.length}</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {docs === null ? (
          <div className="p-8 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
        ) : docs.length === 0 ? (
          <p className="p-6 text-center text-sm text-slate-400" data-testid="expiring-docs-empty">Tidak ada dokumen mendekati kedaluwarsa.</p>
        ) : (
          <div className="divide-y divide-slate-100 max-h-80 overflow-y-auto" data-testid="expiring-docs-list">
            {docs.map((d) => {
              const tone = expiryTone(d.days_left);
              return (
                <button key={d.id || d._id} data-testid={`expiring-doc-${d.id || d._id}`}
                  onClick={() => d.booking_id && nav(`/booking/${d.booking_id}`)}
                  className="w-full text-left flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors">
                  <AlertTriangle className={`h-4 w-4 shrink-0 ${d.days_left < 0 ? "text-red-600" : d.days_left <= 30 ? "text-red-500" : d.days_left <= 60 ? "text-orange-500" : "text-amber-500"}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">
                      {d.doc_type} {d.document_number ? `· ${d.document_number}` : ""}
                    </p>
                    <p className="text-xs text-slate-500">Kedaluwarsa {(d.expiry_date || "").slice(0, 10)}</p>
                  </div>
                  {tone && <Badge variant="outline" className={`${tone.cls} text-[10px] shrink-0`}>{tone.label}</Badge>}
                </button>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
