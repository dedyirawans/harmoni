import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Check, ChevronsUpDown, MapPin } from "lucide-react";
import { cn } from "@/lib/utils";

export default function CityCombobox({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const [cities, setCities] = useState([]);
  const [query, setQuery] = useState("");

  useEffect(() => { api.get("/hotel/cities").then((r) => setCities(r.data || [])).catch(() => {}); }, []);

  const selected = useMemo(() => cities.find((c) => String(c.cityId) === String(value)), [cities, value]);
  const isNum = /^\d+$/.test(query.trim());

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" className="w-full justify-between font-normal" data-testid="hotel-city-combobox">
          <span className="flex items-center gap-2 truncate">
            <MapPin className="h-3.5 w-3.5 text-slate-400" />
            {selected ? `${selected.name}${selected.country ? " · " + selected.country : ""}` : (value ? `City ID ${value}` : "Pilih / cari kota…")}
          </span>
          <ChevronsUpDown className="h-4 w-4 opacity-50 shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        <Command shouldFilter>
          <CommandInput placeholder="Cari kota atau ketik City ID…" value={query} onValueChange={setQuery} data-testid="hotel-city-search" />
          <CommandList>
            <CommandEmpty>
              {isNum ? (
                <button className="w-full text-sm text-blue-600 py-2 hover:underline" onClick={() => { onChange(query.trim()); setOpen(false); }} data-testid="hotel-city-manual">
                  Pakai City ID {query.trim()}
                </button>
              ) : (
                <span className="block py-3 text-sm text-slate-400">Kota tidak ditemukan.</span>
              )}
            </CommandEmpty>
            <CommandGroup>
              {cities.map((c) => (
                <CommandItem key={c._id} value={`${c.name} ${c.country} ${c.cityId}`}
                  onSelect={() => { onChange(c.cityId); setOpen(false); }} data-testid={`hotel-city-opt-${c.cityId}`}>
                  <Check className={cn("mr-2 h-4 w-4", String(c.cityId) === String(value) ? "opacity-100" : "opacity-0")} />
                  <span>{c.name}</span>
                  <span className="ml-auto text-xs text-slate-400">{c.country ? `${c.country} · ` : ""}{c.cityId}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
