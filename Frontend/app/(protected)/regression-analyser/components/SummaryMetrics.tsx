"use client";

import React from "react";
import { ImpactSummary } from "@/types/impactAnalyzer";

interface MetricCardProps {
  value: number;
  label: string;
  variant: "danger" | "warning" | "success";
}

function MetricCard({ value, label, variant }: MetricCardProps) {
  return (
    <div className={`ra-metric-card ra-metric-card--${variant}`}>
      <span className={`ra-metric-value ra-metric-value--${variant}`}>
        {value}
      </span>
      <span className="ra-metric-label">{label}</span>
    </div>
  );
}

interface SummaryMetricsProps {
  summary: ImpactSummary;
}

export default function SummaryMetrics({ summary }: SummaryMetricsProps) {
  return (
    <div className="ra-metrics-row">
      <MetricCard value={summary.mustRun} label="Must Run" variant="danger" />
      <MetricCard
        value={summary.shouldRun}
        label="Should Run"
        variant="warning"
      />
      <MetricCard value={summary.canSkip} label="Can Skip" variant="success" />
    </div>
  );
}
