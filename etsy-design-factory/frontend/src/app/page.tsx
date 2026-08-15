"use client";

import { useCallback, useEffect, useState } from "react";
import { KpiCard } from "@/components/KpiCard";
import {
  ApiError,
  DashboardSummary,
  getDashboard,
  ProductionPlanResponse,
  triggerProductionPlan,
} from "@/lib/api";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function DashboardPage() {
  const [planDate, setPlanDate] = useState(todayIso());
  const [target, setTarget] = useState("30");
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [plan, setPlan] = useState<ProductionPlanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (date: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDashboard(date);
      setSummary(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the Design Factory API.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(planDate);
  }, [load, planDate]);

  async function handleTriggerPlan() {
    setTriggering(true);
    setError(null);
    try {
      const targetNum = target.trim() ? Number(target) : undefined;
      const result = await triggerProductionPlan({ plan_date: planDate, target_final_designs: targetNum });
      setPlan(result);
      await load(planDate);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not trigger the production plan.");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-white">Daily Production Dashboard</h1>
        <p className="mt-1 text-sm text-neutral-400">
          Live headline KPIs for the autonomous design pipeline. Nothing shown here is invented -- every number is a
          real count from the database.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-border bg-panel p-4">
        <label className="flex flex-col gap-1 text-sm text-neutral-300">
          Plan date
          <input
            type="date"
            value={planDate}
            onChange={(e) => setPlanDate(e.target.value)}
            className="rounded border border-border bg-canvas px-2 py-1 text-neutral-100"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-neutral-300">
          Target final designs
          <input
            type="number"
            min={1}
            max={500}
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className="w-32 rounded border border-border bg-canvas px-2 py-1 text-neutral-100"
          />
        </label>
        <button
          onClick={handleTriggerPlan}
          disabled={triggering}
          className="rounded bg-accent px-4 py-2 text-sm font-semibold text-canvas hover:opacity-90 disabled:opacity-50"
        >
          {triggering ? "Planning..." : "Trigger production plan"}
        </button>
      </div>

      {error ? (
        <div className="rounded border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-300">{error}</div>
      ) : null}

      {plan ? (
        <div className="rounded-lg border border-border bg-panel p-4 text-sm text-neutral-300">
          <div className="font-semibold text-white">
            Plan for {plan.plan_date}: {plan.target_final_designs} designs, ${plan.budget_cap_usd.toFixed(2)} budget
            cap
          </div>
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs">
            {Object.entries(plan.portfolio_allocation).map(([bucket, count]) => (
              <span key={bucket}>
                {bucket}: <span className="text-neutral-100">{count}</span>
              </span>
            ))}
          </div>
          <div className="mt-2 text-xs text-neutral-500">{plan.rationale}</div>
        </div>
      ) : null}

      {loading && !summary ? (
        <div className="text-sm text-neutral-500">Loading...</div>
      ) : summary ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          <KpiCard label="Target" value={summary.target_final_designs ?? "-"} hint={summary.plan_date} />
          <KpiCard label="Generated" value={summary.generated} />
          <KpiCard label="QC passed" value={summary.qc_passed} />
          <KpiCard label="Repairing" value={summary.repairing} />
          <KpiCard label="Awaiting approval" value={summary.awaiting_approval} />
          <KpiCard label="Approved" value={summary.approved} />
          <KpiCard label="Rejected" value={summary.rejected} />
          <KpiCard label="Cost today" value={`$${summary.today_cost_usd.toFixed(2)}`} />
          <KpiCard
            label="Cost / approved design"
            value={
              summary.cost_per_approved_design_usd != null
                ? `$${summary.cost_per_approved_design_usd.toFixed(2)}`
                : "n/a"
            }
            hint={summary.cost_per_approved_design_usd == null ? "no approvals yet" : undefined}
          />
        </div>
      ) : null}
    </div>
  );
}
