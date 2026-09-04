import { useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Plus, X, Building2 } from "lucide-react";

// iso: selected country ISO; cityId: optional selected city_code to scope
// onChange(arrayOfHotelObjects [{hotelId, cityId, countryCode, name, city}])
export default function HotelPicker({ iso, cityId, onChange }) {
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState([]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState([]);
  const timer = useRef();

  useEffect(() => { onChange?.(selected); }, [selected]); // eslint-disable-line
  useEffect(() => { setSelected([]); }, [iso, cityId]);

  useEffect(() => {
    clearTimeout(timer.current);
    const q = query.trim();
    if (!q || !iso) { setResults([]); return; }
    timer.current = setTimeout(() => {
      api.get("/hotel/hotels/search", { params: { q, iso, cityId: cityId || undefined, limit: 20 } })
        .then((r) => setResults(r.data || [])).catch(() => {});
    }, 300);
    return () => clearTimeout(timer.current);
  }, [query, iso, cityId]);

  const add = (h) => {
    setSelected((s) => (s.some((x) => String(x.hotelId) === String(h.hotelId) && x.cityId === h.cityId) ? s : [...s, h]));
    setOpen(false); setQuery("");
  };
  const remove = (h) => setSelected((s) => s.filter((x) => !(String(x.hotelId) === String(h.hotelId) && x.cityId === h.cityId)));

  return (
    <div className="space-y-2" data-testid="hotel-picker">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" disabled={!iso} className="w-full justify-start font-normal" data-testid="hotel-picker-trigger">
            <Plus className="h-4 w-4 mr-2" />{iso ? "Cari & tambah hotel by nama…" : "Pilih negara dulu"}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput placeholder="Ketik nama hotel…" value={query} onValueChange={setQuery} data-testid="hotel-picker-search" />
            <CommandList>
              <CommandEmpty>
                <span className="block py-3 text-sm text-slate-400">Ketik nama hotel. Master belum ada? Sinkronkan di API Settings.</span>
              </CommandEmpty>
              <CommandGroup>
                {results.map((h) => (
                  <CommandItem key={h._id || `${h.countryCode}-${h.hotelId}`} value={String(h.hotelId)} onSelect={() => add(h)} data-testid={`hotel-picker-opt-${h.hotelId}`}>
                    <div className="flex flex-col">
                      <span className="text-sm">{h.name}</span>
                      <span className="text-xs text-slate-400">{h.city}{h.country ? `, ${h.country}` : ""}</span>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-2" data-testid="hotel-picker-selected">
          {selected.map((h) => (
            <Badge key={`${h.countryCode}-${h.hotelId}`} variant="secondary" className="pl-2 pr-1 py-1 flex items-center gap-1" data-testid={`hotel-picker-chip-${h.hotelId}`}>
              <Building2 className="h-3 w-3" />{h.name} <span className="text-slate-400">#{h.hotelId}</span>
              <button onClick={() => remove(h)} className="ml-1 text-red-500 hover:text-red-700"><X className="h-3 w-3" /></button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
