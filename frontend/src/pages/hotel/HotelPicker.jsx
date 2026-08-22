import { useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Plus, X, Building2 } from "lucide-react";

export default function HotelPicker({ onChange }) {
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState([]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState([]);
  const timer = useRef();

  useEffect(() => { onChange?.(selected.map((h) => h.hotelId)); }, [selected]); // eslint-disable-line

  useEffect(() => {
    clearTimeout(timer.current);
    const q = query.trim();
    if (!q) { setResults([]); return; }
    timer.current = setTimeout(() => {
      api.get("/hotel/hotels/search", { params: { q, limit: 20 } })
        .then((r) => setResults(r.data || [])).catch(() => {});
    }, 300);
    return () => clearTimeout(timer.current);
  }, [query]);

  const add = (h) => {
    setSelected((s) => (s.some((x) => x.hotelId === h.hotelId) ? s : [...s, h]));
    setOpen(false); setQuery("");
  };
  const remove = (id) => setSelected((s) => s.filter((x) => x.hotelId !== id));
  const isNum = /^\d+$/.test(query.trim());

  return (
    <div className="space-y-2" data-testid="hotel-picker">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" className="w-full justify-start font-normal" data-testid="hotel-picker-trigger">
            <Plus className="h-4 w-4 mr-2" />Cari & tambah hotel by nama…
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
          <Command shouldFilter={false}>
            <CommandInput placeholder="Ketik nama hotel (atau Hotel ID)…" value={query} onValueChange={setQuery} data-testid="hotel-picker-search" />
            <CommandList>
              <CommandEmpty>
                {isNum ? (
                  <button className="w-full text-sm text-blue-600 py-2 hover:underline" onClick={() => add({ hotelId: Number(query.trim()), name: `Hotel ${query.trim()}` })} data-testid="hotel-picker-manual">
                    Tambah Hotel ID {query.trim()}
                  </button>
                ) : (
                  <span className="block py-3 text-sm text-slate-400">Ketik nama hotel…</span>
                )}
              </CommandEmpty>
              <CommandGroup>
                {results.map((h) => (
                  <CommandItem key={h.hotelId} value={String(h.hotelId)} onSelect={() => add(h)} data-testid={`hotel-picker-opt-${h.hotelId}`}>
                    <div className="flex flex-col">
                      <span className="text-sm">{h.name}</span>
                      <span className="text-xs text-slate-400">{h.city}{h.country ? `, ${h.country}` : ""}{h.starRating ? ` · ${h.starRating}★` : ""}</span>
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
            <Badge key={h.hotelId} variant="secondary" className="pl-2 pr-1 py-1 flex items-center gap-1" data-testid={`hotel-picker-chip-${h.hotelId}`}>
              <Building2 className="h-3 w-3" />{h.name} <span className="text-slate-400">#{h.hotelId}</span>
              <button onClick={() => remove(h.hotelId)} className="ml-1 text-red-500 hover:text-red-700"><X className="h-3 w-3" /></button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
