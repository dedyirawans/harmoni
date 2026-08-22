import { cn } from "@/lib/utils";

export const PageHeader = ({ title, subtitle, actions, className }) => (
  <div
    className={cn(
      "flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between border-b border-slate-200 pb-4",
      className,
    )}
    data-testid="page-header"
  >
    <div className="min-w-0">
      <h1 className="font-display text-3xl font-bold tracking-tight text-slate-900">{title}</h1>
      {subtitle && <p className="text-slate-500 mt-1 text-sm">{subtitle}</p>}
    </div>
    {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
  </div>
);

export default PageHeader;
