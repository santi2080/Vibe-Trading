/**
 * Health Status Card - Display data health status
 */

import { cn } from "@/lib/utils";
import { DataHealthInfo } from "@/lib/dashboardApi";
import { CheckCircle, AlertTriangle, XCircle } from "lucide-react";

interface Props {
  data: DataHealthInfo | null | undefined;
}

const STATUS_CONFIG = {
  PASS: {
    icon: CheckCircle,
    color: "text-green-500",
    bg: "bg-green-500/10",
    label: "Healthy",
  },
  WARN: {
    icon: AlertTriangle,
    color: "text-yellow-500",
    bg: "bg-yellow-500/10",
    label: "Warning",
  },
  FAIL: {
    icon: XCircle,
    color: "text-red-500",
    bg: "bg-red-500/10",
    label: "Failed",
  },
};

export function HealthStatus({ data }: Props) {
  if (!data) {
    return (
      <div className="rounded-lg border border-border/60 bg-card p-4">
        <div className="h-4 w-24 bg-muted animate-pulse rounded mb-2" />
        <div className="h-8 w-16 bg-muted animate-pulse rounded" />
      </div>
    );
  }

  const config = STATUS_CONFIG[data.status];
  const Icon = config.icon;

  return (
    <div className="rounded-lg border border-border/60 bg-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Icon className={cn("h-5 w-5", config.color)} />
        <h3 className="font-semibold">Data Health</h3>
      </div>

      <div className={cn("inline-flex items-center gap-2 px-3 py-1 rounded-full", config.bg)}>
        <span className={cn("text-sm font-medium", config.color)}>{config.label}</span>
      </div>

      {data.message && (
        <p className="text-sm text-muted-foreground mt-3">{data.message}</p>
      )}

      {data.stale_symbols.length > 0 && (
        <div className="mt-3">
          <p className="text-sm font-medium text-muted-foreground">Stale symbols:</p>
          <div className="flex flex-wrap gap-1 mt-1">
            {data.stale_symbols.slice(0, 5).map((symbol) => (
              <span
                key={symbol}
                className="px-2 py-0.5 text-xs rounded bg-yellow-500/10 text-yellow-500"
              >
                {symbol}
              </span>
            ))}
            {data.stale_symbols.length > 5 && (
              <span className="px-2 py-0.5 text-xs rounded bg-muted text-muted-foreground">
                +{data.stale_symbols.length - 5} more
              </span>
            )}
          </div>
        </div>
      )}

      <p className="text-xs text-muted-foreground mt-3">
        Last updated: {new Date(data.last_updated).toLocaleString()}
      </p>
    </div>
  );
}
