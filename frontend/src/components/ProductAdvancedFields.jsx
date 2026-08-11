import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SUB_BY_TYPE } from "@/config/product";
import { Plus, Trash2 } from "lucide-react";

export function TieredPricing({ tiers, onChange }) {
  const list = tiers || [];
  const add = () => onChange([...list, { min_pax: "", max_pax: "", price: "" }]);
  const upd = (i, k, v) => onChange(list.map((t, idx) => (idx === i ? { ...t, [k]: v } : t)));
  const del = (i) => onChange(list.filter((_, idx) => idx !== i));
  return (
    <div className="space-y-2" data-testid="tiered-pricing">
      <div className="flex items-center justify-between">
        <Label className="text-xs font-semibold uppercase text-slate-500">Harga Berjenjang (Private)</Label>
        <Button type="button" size="sm" variant="outline" onClick={add} data-testid="add-tier-button">
          <Plus className="h-3 w-3 mr-1" aria-hidden="true" />Tambah Tier
        </Button>
      </div>
      {list.length === 0 ? (
        <p className="text-xs text-slate-400">Belum ada tier. Contoh: 1–2 pax → harga X, 3–5 pax → harga Y, 6–10 pax → harga Z.</p>
      ) : (
        list.map((t, i) => (
          <div key={i} className="grid grid-cols-12 gap-2 items-end" data-testid={`tier-row-${i}`}>
            <div className="col-span-3 space-y-1">
              <Label className="text-[10px] text-slate-400">Min Pax</Label>
              <Input type="number" value={t.min_pax} onChange={(e) => upd(i, "min_pax", e.target.value)} data-testid={`tier-min-${i}`} />
            </div>
            <div className="col-span-3 space-y-1">
              <Label className="text-[10px] text-slate-400">Max Pax</Label>
              <Input type="number" value={t.max_pax} onChange={(e) => upd(i, "max_pax", e.target.value)} data-testid={`tier-max-${i}`} />
            </div>
            <div className="col-span-5 space-y-1">
              <Label className="text-[10px] text-slate-400">Harga / Pax</Label>
              <Input type="number" value={t.price} onChange={(e) => upd(i, "price", e.target.value)} data-testid={`tier-price-${i}`} />
            </div>
            <div className="col-span-1">
              <Button type="button" size="icon" variant="ghost" className="text-red-600" onClick={() => del(i)} data-testid={`tier-del-${i}`}>
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

export function ProductAdvancedFields({ f, set }) {
  const subs = SUB_BY_TYPE[f.product_type] || [];
  return (
    <div className="col-span-2 border-t pt-3 space-y-4">
      <p className="text-xs font-semibold uppercase text-slate-500">Kategori & Harga</p>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2 col-span-2 sm:col-span-1">
          <Label>Sub Kategori</Label>
          <Select value={f.sub_category || ""} onValueChange={set("sub_category")}>
            <SelectTrigger data-testid="package-subcategory-select"><SelectValue placeholder="Pilih sub kategori" /></SelectTrigger>
            <SelectContent className="bg-white">
              {subs.map((s) => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        {f.product_type === "UMROH_PLUS" && (
          <div className="space-y-2 col-span-2 sm:col-span-1">
            <Label>Porsi Harga Tour (kena pajak)</Label>
            <Input type="number" value={f.tour_price_portion ?? 0} onChange={(e) => set("tour_price_portion")(e.target.value)} data-testid="tour-portion-input" />
          </div>
        )}
        {["OPEN_TRIP", "SEAT_IN_COACH"].includes(f.sub_category) && (
          <div className="space-y-2 col-span-2 sm:col-span-1">
            <Label>Minimum Kuota Pax ({f.sub_category === "OPEN_TRIP" ? "Open Trip" : "Seat in Coach"})</Label>
            <Input type="number" value={f.min_quota_pax ?? 0} onChange={(e) => set("min_quota_pax")(e.target.value)} data-testid="min-quota-input" />
          </div>
        )}
      </div>
      {f.sub_category === "PRIVATE" && (
        <TieredPricing tiers={f.pricing_tiers || []} onChange={set("pricing_tiers")} />
      )}
    </div>
  );
}
