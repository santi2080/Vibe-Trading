/**
 * Scan History - Display list of historical scans
 */

import { ScanHistoryItem } from "@/lib/dashboardApi";
import { cn } from "@/lib/utils";
import { Clock, CheckCircle, AlertTriangle, XCircle } from "lucide-react";

interface Props {
  items: ScanHistoryItem[];
}

const STATUS_CONFIG = {
  PASS: {
    icon: CheckCircle,
    color: "text-green-500",
    bg: "bg-green-500/10",
  },
  WARN: {
    icon: AlertTriangle,
    color: "text-yellow-500",
    bg: "bg-yellow-500/10",
  },
  FAIL: {
    icon: XCircle,
    color: "text-red-500",
    bg: "bg-red-500/10",
  },
};

export function ScanHistory({ items }: Props) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-border/60 bg-card p-4">
        <h3 className="font-semibold mb-3">Scan History</h3>
        <div className="text-center py-8 text-muted-foreground">
          <Clock className="h-12 w-12 mx-auto mb-2 opacity-50" />
          <p>No scan history yet</p>
          <p className="text-sm">Run a scan to see results here</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border/60 bg-card p-4">
      <h3 className="font-semibold mb-3">Scan History</h3>

      <div className="space-y-2">
        {items.map((item) => {
          const config = STATUS_CONFIG[item.health_status];
          const Icon = config.icon;

          return (
            <div
              key={item.id}
              className="flex items-center justify-between p-3 rounded-lg hover:bg-muted/30 transition"
            >
              <div className="flex items-center gap-3">
                <div className={cn("p-2 rounded-full", config.bg)}>
                  <Icon className={cn("h-4 w-4", config.color)} />
                </div>
                <div>
                  <p className="font-medium">
                    {new Date(item.timestamp).toLocaleDateString()} at{" "}
                    {new Date(item.timestamp).toLocaleTimeString()}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {item.total_symbols} symbols · {item.actionable} actionable
                  </p>
                </div>
              </div>

              <div className="flex gap-4 text-sm">
                <div className="text-right">
                  <p className="text-green-500">{item.actionable}</p>
                  <p className="text-xs text-muted-foreground">Actionable</p>
                </div>
                <div className="text-right">
                  <p className="text-yellow-500">{item.watch}</p>
                  <p className="text-xs text-muted-foreground">Watch</p>
                </div>
                <div className="text-right">
                  <p className="text-red-500">{item.risk}</p>
                  <p className="text-xs text-muted-foreground">Risk</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
