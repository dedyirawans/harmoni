import { useEffect, useState } from "react";
import api, { formatApiErrorDetail } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Loader2, PlaneTakeoff, AlertTriangle, Users, LayoutDashboard, BedDouble } from "lucide-react";
import { toast } from "sonner";

const WINDOWS = [["all", "Semua"], ["7", "7 Hari"], ["14", "14 Hari"], ["30", "30 Hari"], ["60", "60 Hari"]];
const SEV = { danger: "bg-red-50 text-red-700 border-red-200", warning: "bg-amber-50 text-amber-700 border-amber-200", info: "bg-blue-50 text-blue-700 border-blue-200" };
const PAY = { PAID: "bg-emerald-50 text-emerald-700 border-emerald-200", PARTIAL: "bg-amber-50 text-amber-700 border-amber-200", UNPAID: "bg-slate-100 text-slate-500 border-slate-200" };

export default function Operations() {
  const [within, setWithin] = useState("all");
  const [list, setList] = useState(null);
  const [sel, setSel] = useState(null);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    setList(null);
    api.get("/operations/departures", { params: { within } }).then((r) => setList(r.data)).catch(() => setList([]));
  }, [within]);

  const openDep = (id) => {
    setSel(id); setDetail(null);
    api.get(`/operations/departures/${id}`).then((r) => setDetail(r.data)).catch(() => toast.error("Gagal memuat detail"));
  };

  return (
    <div className="space-y-6" data-testid="operations-page">
      <div>
        <h1 className="font-display text-3xl font-bold text-slate-900">Operations — Departure</h1>
        <p className="text-slate-500 mt-1">Kelola keberangkatan, passenger list, rooming, dan pantau kesiapan dokumen & pembayaran.</p>
      </div>

      <div className="flex gap-2 flex-wrap" data-testid="upcoming-filter">
        {WINDOWS.map(([v, l]) => (
          <Button key={v} size="sm" variant={within === v ? "default" : "outline"}
            className={within === v ? "bg-blue-600 hover:bg-blue-700" : ""} onClick={() => setWithin(v)}
            data-testid={`within-${v}`}>{l}</Button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="border-slate-200 shadow-sm lg:col-span-1 overflow-hidden">
          <div className="p-3 border-b border-slate-100 text-sm font-medium text-slate-600 flex items-center gap-2">
            <PlaneTakeoff className="h-4 w-4 text-blue-600" /> Departures
          </div>
          {list === null ? (
            <div className="p-8 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-blue-600" /></div>
          ) : list.length === 0 ? (
            <p className="p-6 text-center text-sm text-slate-400" data-testid="departures-empty">Tidak ada keberangkatan pada rentang ini.</p>
          ) : (
            <div className="divide-y divide-slate-100 max-h-[70vh] overflow-y-auto" data-testid="departures-list">
              {list.map((d) => (
                <button key={d.id} onClick={() => openDep(d.id)} data-testid={`departure-${d.id}`}
                  className={`w-full text-left px-4 py-3 hover:bg-slate-50 ${sel === d.id ? "bg-blue-50" : ""}`}>
                  <div className="flex items-center justify-between">
                    <p className="font-medium text-slate-900 text-sm truncate">{d.package_name || "—"}</p>
                    <Badge variant="outline" className="text-[10px] bg-slate-100 text-slate-600">{d.status}</Badge>
                  </div>
                  <p className="text-xs text-slate-500">{(d.departure_date || "").slice(0, 10)} · {d.product_type}</p>
                  <p className="text-xs mt-1"><span className="text-emerald-600 font-medium">{d.booked_seat}</span>/{d.total_seat} seat · <span className="text-slate-500">sisa {d.available_seat}</span></p>
                </button>
              ))}
            </div>
          )}
        </Card>

        <div className="lg:col-span-2">
          {!sel ? (
            <Card className="border-slate-200 shadow-sm p-12 text-center text-slate-400">Pilih keberangkatan untuk melihat detail.</Card>
          ) : detail === null ? (
            <Card className="border-slate-200 shadow-sm p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></Card>
          ) : (
            <DepartureDetail detail={detail} onReload={() => openDep(sel)} />
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }) {
  return (
    <div className="rounded-md border border-slate-200 p-3 bg-white" data-testid={`stat-${label.toLowerCase().replace(/\s/g, "-")}`}>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-2xl font-bold ${tone || "text-slate-900"}`}>{value}</p>
    </div>
  );
}

function DepartureDetail({ detail, onReload }) {
  const { departure: dep, dashboard: db, passengers, alerts } = detail;
  return (
    <Card className="border-slate-200 shadow-sm" data-testid="departure-detail">
      <div className="p-4 border-b border-slate-100">
        <h2 className="font-display text-xl font-bold text-slate-900">{dep.package_name}</h2>
        <p className="text-sm text-slate-500">{(dep.departure_date || "").slice(0, 10)} → {(dep.return_date || "").slice(0, 10)} · {dep.product_type} · Flight {dep.flight || "—"} · Hotel {dep.hotel || "—"}</p>
      </div>

      {alerts.length > 0 && (
        <div className="p-4 space-y-2 border-b border-slate-100" data-testid="alerts-panel">
          {alerts.map((a, i) => (
            <div key={i} className={`flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${SEV[a.severity] || SEV.info}`} data-testid={`alert-${a.type}`}>
              <AlertTriangle className="h-4 w-4 shrink-0" /> {a.message}
            </div>
          ))}
        </div>
      )}

      <Tabs defaultValue="dashboard" className="p-4">
        <TabsList>
          <TabsTrigger value="dashboard" data-testid="tab-dashboard"><LayoutDashboard className="h-4 w-4 mr-1" />Dashboard</TabsTrigger>
          <TabsTrigger value="passengers" data-testid="tab-passengers"><Users className="h-4 w-4 mr-1" />Passengers ({passengers.length})</TabsTrigger>
          <TabsTrigger value="rooming" data-testid="tab-rooming"><BedDouble className="h-4 w-4 mr-1" />Rooming</TabsTrigger>
        </TabsList>

        <TabsContent value="dashboard" className="pt-4">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3" data-testid="departure-dashboard">
            <Stat label="Total Seat" value={db.total_seat} />
            <Stat label="Booked" value={db.booked} tone="text-blue-600" />
            <Stat label="Available" value={db.available} tone="text-emerald-600" />
            <Stat label="Paid" value={db.paid} tone="text-emerald-600" />
            <Stat label="Partial" value={db.partial} tone="text-amber-600" />
            <Stat label="Unpaid" value={db.unpaid} tone="text-slate-500" />
            <Stat label="Docs Complete" value={db.documents_complete} tone="text-emerald-600" />
            <Stat label="Docs Missing" value={db.documents_missing} tone="text-red-600" />
          </div>
          <p className="text-xs text-slate-400 mt-3">Dokumen wajib: {db.required_docs.join(", ")}</p>
        </TabsContent>

        <TabsContent value="passengers" className="pt-4">
          <div className="overflow-x-auto">
            <Table data-testid="passenger-table">
              <TableHeader><TableRow className="bg-slate-50">
                <TableHead>Customer</TableHead><TableHead>Gender</TableHead><TableHead>Passport</TableHead>
                <TableHead>Payment</TableHead><TableHead>Document</TableHead><TableHead>Booking</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {passengers.map((p) => (
                  <TableRow key={p.traveler_id} data-testid={`passenger-${p.traveler_id}`}>
                    <TableCell><div className="font-medium text-slate-900">{p.full_name}</div><div className="text-xs text-slate-400">{p.customer_name}</div></TableCell>
                    <TableCell className="text-slate-600">{p.gender || "—"}</TableCell>
                    <TableCell><div className="text-slate-600">{p.passport_number || "—"}</div>{p.passport_expired && <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200 text-[10px]">EXPIRED</Badge>}</TableCell>
                    <TableCell><Badge variant="outline" className={PAY[p.payment_status]}>{p.payment_status}</Badge></TableCell>
                    <TableCell><Badge variant="outline" className={p.document_status === "COMPLETE" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-red-50 text-red-700 border-red-200"} title={p.missing_docs.join(", ")}>{p.document_status}</Badge></TableCell>
                    <TableCell><Badge variant="outline" className="bg-slate-100 text-slate-600">{p.booking_status}</Badge></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        <TabsContent value="rooming" className="pt-4">
          <RoomingTab passengers={passengers} onReload={onReload} />
        </TabsContent>
      </Tabs>
    </Card>
  );
}

function RoomingTab({ passengers, onReload }) {
  const [edits, setEdits] = useState({});
  const [saving, setSaving] = useState(null);
  const val = (p, k) => (edits[p.traveler_id]?.[k] ?? p[k] ?? "");
  const setVal = (tid, k, v) => setEdits((e) => ({ ...e, [tid]: { ...e[tid], [k]: v } }));
  const save = async (p) => {
    const body = { room: val(p, "room"), group: val(p, "group"), bus: val(p, "bus"), room_type: val(p, "room_type") };
    setSaving(p.traveler_id);
    try { await api.patch(`/operations/travelers/${p.traveler_id}/rooming`, body); toast.success("Rooming disimpan"); onReload(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
    finally { setSaving(null); }
  };
  return (
    <div className="overflow-x-auto">
      <Table data-testid="rooming-table">
        <TableHeader><TableRow className="bg-slate-50">
          <TableHead>Passenger</TableHead><TableHead>Room Type</TableHead><TableHead>Room</TableHead>
          <TableHead>Group</TableHead><TableHead>Bus</TableHead><TableHead></TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {passengers.map((p) => (
            <TableRow key={p.traveler_id} data-testid={`rooming-${p.traveler_id}`}>
              <TableCell className="font-medium text-slate-900">{p.full_name}</TableCell>
              <TableCell><Input className="h-8 w-28" value={val(p, "room_type")} onChange={(e) => setVal(p.traveler_id, "room_type", e.target.value)} data-testid={`rooming-room_type-${p.traveler_id}`} /></TableCell>
              <TableCell><Input className="h-8 w-24" value={val(p, "room")} onChange={(e) => setVal(p.traveler_id, "room", e.target.value)} data-testid={`rooming-room-${p.traveler_id}`} /></TableCell>
              <TableCell><Input className="h-8 w-24" value={val(p, "group")} onChange={(e) => setVal(p.traveler_id, "group", e.target.value)} data-testid={`rooming-group-${p.traveler_id}`} /></TableCell>
              <TableCell><Input className="h-8 w-24" value={val(p, "bus")} onChange={(e) => setVal(p.traveler_id, "bus", e.target.value)} data-testid={`rooming-bus-${p.traveler_id}`} /></TableCell>
              <TableCell><Button size="sm" className="bg-blue-600 hover:bg-blue-700" disabled={saving === p.traveler_id} onClick={() => save(p)} data-testid={`rooming-save-${p.traveler_id}`}>{saving === p.traveler_id ? "..." : "Simpan"}</Button></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
