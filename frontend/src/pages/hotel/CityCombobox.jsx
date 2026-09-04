import { useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Check, ChevronsUpDown, MapPin } from "lucide-react";
import { cn } from "@/lib/utils";

// value: selected city object ({cityId, countryCode, name, country}) or null
// iso: selected country ISO code used to scope the master list
// onChange(cityObj|null)
export default function CityCombobox({ value, iso, onChange }) {
  const [open, setOpen] = useState(false);
  const [cities, setCities] = useState([]);
  const [query, setQuery] = useState("");
  const timer = useRef();

  const fetchCities = (q) => {
    if (!iso) { setCities([]); return; }
    api.get("/hotel/cities", { params: { iso, limit: 30, ...(q ? { q } : {}) } })
      .then((r) => setCities(r.data || [])).catch(() => {});
  };

  useEffect(() => { fetchCities(""); /* eslint-disable-next-line */ }, [iso]);

  useEffect(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => fetchCities(query.trim()), 250);
    return () => clearTimeout(timer.current);
    // eslint-disable-next-line
  }, [query]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" disabled={!iso} className="w-full justify-between font-normal" data-testid="hotel-city-combobox">
          <span className="flex items-center gap-2 truncate">
            <MapPin className="h-3.5 w-3.5 text-slate-400" />
            {value ? `${value.name}${value.country ? " · " + value.country : ""}` : (iso ? "Pilih / cari kota…" : "Pilih negara dulu")}
          </span>
          <ChevronsUpDown className="h-4 w-4 opacity-50 shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        <Command shouldFilter={false}>
          <CommandInput placeholder="Cari nama kota…" value={query} onValueChange={setQuery} data-testid="hotel-city-search" />
          <CommandList>
            <CommandEmpty>
              <span className="block py-3 text-sm text-slate-400">Kota tidak ditemukan. Sinkronkan master di API Settings.</span>
            </CommandEmpty>
            <CommandGroup>
              {cities.map((c) => (
                <CommandItem key={c._id || `${c.countryCode}-${c.cityId}`} value={String(c.cityId)}
                  onSelect={() => { onChange(c); setOpen(false); }} data-testid={`hotel-city-opt-${c.cityId}`}>
                  <Check className={cn("mr-2 h-4 w-4", value && String(c.cityId) === String(value.cityId) ? "opacity-100" : "opacity-0")} />
                  <span className="truncate">{c.name}</span>
                  <span className="ml-auto text-xs text-slate-400 shrink-0">{c.count ? `${c.count} hotel` : c.cityId}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
