/**
 * Dashboard Page - Scan results overview and statistics
 */

import { ScanSummary } from "@/components/dashboard/ScanSummary";
import { HealthStatus } from "@/components/dashboard/HealthStatus";
import { SignalChart } from "@/components/dashboard/SignalChart";
import { ScanHistory } from "@/components/dashboard/ScanHistory";
import { useEffect, useState } from "react";
import { getDashboardData, type DashboardData } from "@/lib/dashboardApi";

function LoadingSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-32 rounded-lg border border-border/60 bg-card animate-pulse" />
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const dashboardData = await getDashboardData();
        setData(dashboardData);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
      </div>

      {loading ? (
        <LoadingSkeleton />
      ) : (
        <>
          {/* Summary Cards */}
          <ScanSummary data={data?.summary} />

          {/* Charts and Health */}
          <div className="grid gap-4 md:grid-cols-2">
            <SignalChart data={data?.summary} />
            <HealthStatus data={data?.health} />
          </div>

          {/* History */}
          <ScanHistory items={data?.history || []} />
        </>
      )}
    </div>
  );
}
