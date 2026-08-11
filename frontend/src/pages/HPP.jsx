import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Loader2, ShieldCheck } from "lucide-react";

const fmt = (n) => "Rp " + n.toLocaleString("id-ID");

export default function HPP() {
  const [data, setData] = useState(null);
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    api.get("/hpp").then((r) => setData(r.data)).catch((e) => {
      if (e.response?.status === 403) setForbidden(true);
      setData({ packages: [] });
    });
  }, []);

  if (forbidden) {
    return (
      <div className="p-12 text-center" data-testid="hpp-forbidden">
        <p className="text-red-600 font-medium">403 Forbidden — HPP is restricted to Super Admin & Accounting.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="hpp-page">
      <div className="flex items-center gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-slate-900">Costing / HPP</h1>
          <p className="text-slate-500 mt-1">Supplier cost, gross profit and margins. Restricted to Super Admin & Accounting.</p>
        </div>
        <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
          <ShieldCheck className="h-3 w-3 mr-1" aria-hidden="true" /> Confidential
        </Badge>
      </div>

      <Card className="border-slate-200 shadow-sm overflow-hidden">
        {data === null ? (
          <div className="p-12 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-amber-600" /></div>
        ) : (
          <Table data-testid="hpp-table">
            <TableHeader>
              <TableRow className="bg-slate-50">
                <TableHead>Package</TableHead>
                <TableHead className="text-right">Supplier Cost</TableHead>
                <TableHead className="text-right">Selling Price</TableHead>
                <TableHead className="text-right">Gross Profit</TableHead>
                <TableHead className="text-right">Gross Margin</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.packages.map((p) => (
                <TableRow key={p.name} className="hover:bg-slate-50">
                  <TableCell className="font-medium text-slate-900">{p.name}</TableCell>
                  <TableCell className="text-right text-slate-600">{fmt(p.supplier_cost)}</TableCell>
                  <TableCell className="text-right text-slate-600">{fmt(p.selling_price)}</TableCell>
                  <TableCell className="text-right font-medium text-emerald-700">{fmt(p.gross_profit)}</TableCell>
                  <TableCell className="text-right">
                    <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">{p.gross_margin}%</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
