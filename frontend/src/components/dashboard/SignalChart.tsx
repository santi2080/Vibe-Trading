/**
 * Signal Chart - Display signal distribution as pie chart
 */

import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { ScanSummary } from "@/lib/dashboardApi";

interface Props {
  data: ScanSummary | null | undefined;
}

export function SignalChart({ data }: Props) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    // Initialize chart
    chartInstance.current = echarts.init(chartRef.current, undefined, {
      renderer: "canvas",
    });

    return () => {
      chartInstance.current?.dispose();
    };
  }, []);

  useEffect(() => {
    if (!chartInstance.current || !data) return;

    const chartData = [
      { value: data.actionable, name: "Actionable", itemStyle: { color: "#22c55e" } },
      { value: data.watch, name: "Watch", itemStyle: { color: "#eab308" } },
      { value: data.risk, name: "Risk", itemStyle: { color: "#ef4444" } },
      { value: data.skipped, name: "Skipped", itemStyle: { color: "#94a3b8" } },
      { value: data.failed, name: "Failed", itemStyle: { color: "#64748b" } },
    ].filter((d) => d.value > 0);

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: "item",
        formatter: "{b}: {c} ({d}%)",
      },
      legend: {
        orient: "vertical",
        right: 10,
        top: "center",
        textStyle: {
          color: "#94a3b8",
        },
      },
      series: [
        {
          name: "Signals",
          type: "pie",
          radius: ["40%", "70%"],
          center: ["35%", "50%"],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 4,
            borderColor: "#0f172a",
            borderWidth: 2,
          },
          label: {
            show: false,
            position: "center",
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 16,
              fontWeight: "bold",
            },
          },
          labelLine: {
            show: false,
          },
          data: chartData,
        },
      ],
    };

    chartInstance.current.setOption(option);
  }, [data]);

  if (!data) {
    return (
      <div className="rounded-lg border border-border/60 bg-card p-4">
        <h3 className="font-semibold mb-3">Signal Distribution</h3>
        <div className="h-64 bg-muted animate-pulse rounded" />
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border/60 bg-card p-4">
      <h3 className="font-semibold mb-3">Signal Distribution</h3>
      <div ref={chartRef} className="h-64" />
    </div>
  );
}
