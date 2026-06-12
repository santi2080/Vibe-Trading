/**
 * Scan Summary Card - Display scan results overview
 */

import { cn } from "@/lib/utils";
import { ScanSummary as ScanSummaryType } from "@/lib/dashboardApi";

interface Props {
  data: ScanSummaryType | null | undefined;
}

export function ScanSummary({ data }: Props) {
  if (!data) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border border-border/60 bg-card p-4">
            <div className="h-4 w-20 bg-muted animate-pulse rounded" />
            <div className="h-8 w-16 bg-muted animate-pulse rounded mt-2" />
          </div>
        ))}
      </div>
    );
  }

  const stats = [
    { label: "Actionable", value: data.actionable, color: "text-green-500" },
    { label: "Watch", value: data.watch, color: "text-yellow-500" },
    { label: "Risk", value: data.risk, color: "text-red-500" },
    { label: "Total", value: data.total_symbols, color: "text-primary" },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => (
        <div key={stat.label} className="rounded-lg border border-border/60 bg-card p-4">
          <p className="text-sm font-medium text-muted-foreground">{stat.label}</p>
          <div className={cn("text-2xl font-bold mt-1", stat.color)}>
            {stat.value}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {data.timestamp ? new Date(data.timestamp).toLocaleString() : "No scan yet"}
          </p>
        </div>
      ))}
    </div>
  );
}
