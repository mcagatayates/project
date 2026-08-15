"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  MarketSignalOut,
  ResearchQueryOut,
  getResearchQueries,
  listMarketSignals,
} from "@/lib/api";

export default function MarketSignalsPage() {
  const [signals, setSignals] = useState<MarketSignalOut[]>([]);
  const [queries, setQueries] = useState<ResearchQueryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [signalData, planData] = await Promise.all([listMarketSignals(7), getResearchQueries()]);
      setSignals(signalData.items);
      setQueries(planData.queries);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the Design Factory API.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-white">Market Intelligence</h1>
        <p className="mt-1 text-sm text-neutral-400">
          Real signals only -- nothing here is fabricated. Signals come from a code-level search adapter or an
          agent-driven web research job (see docs/ROADMAP.md &quot;Agent-driven market research&quot;).
        </p>
      </div>

      {error ? (
        <div className="rounded border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-300">{error}</div>
      ) : null}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-400">
          Recent signals (last 7 days)
        </h2>
        {loading ? (
          <div className="text-sm text-neutral-500">Loading...</div>
        ) : signals.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-sm text-neutral-500">
            No market signals recorded yet. Configure SERPAPI_KEY for the code-level adapter, or POST findings via
            /api/market-intelligence/signals.
          </div>
        ) : (
          <div className="divide-y divide-border rounded-lg border border-border bg-panel">
            {signals.map((s) => (
              <div key={s.id} className="p-4 text-sm">
                <div className="flex items-center justify-between gap-4">
                  <span className="rounded bg-canvas px-2 py-0.5 text-xs text-accent">{s.category}</span>
                  <span className="text-xs text-neutral-500">confidence {(s.confidence * 100).toFixed(0)}%</span>
                </div>
                <div className="mt-2 text-neutral-100">{s.description}</div>
                <div className="mt-1 text-xs text-neutral-500">
                  source: {s.source} · {new Date(s.created_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-400">
          Today&apos;s research plan
        </h2>
        <p className="text-xs text-neutral-500">
          Always-on bestseller/trend tracking plus any seasonal occasion currently inside its research lead-time
          window (e.g. Halloween starts appearing ~12 weeks out, not the week of).
        </p>
        {loading ? (
          <div className="text-sm text-neutral-500">Loading...</div>
        ) : (
          <div className="divide-y divide-border rounded-lg border border-border bg-panel">
            {queries.map((q, idx) => (
              <div key={`${q.query}-${idx}`} className="p-3 text-sm">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-neutral-100">{q.query}</span>
                  <span className="rounded bg-canvas px-2 py-0.5 text-xs text-neutral-400">{q.category}</span>
                </div>
                <div className="mt-1 text-xs text-neutral-500">{q.reason}</div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
