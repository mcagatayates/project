"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  MarketSignalOut,
  ResearchQueryOut,
  getResearchQueries,
  listMarketSignals,
  refreshMarketSignals,
} from "@/lib/api";

export default function MarketSignalsPage() {
  const [signals, setSignals] = useState<MarketSignalOut[]>([]);
  const [queries, setQueries] = useState<ResearchQueryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshResult, setRefreshResult] = useState<string | null>(null);

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

  async function handleRefresh() {
    setRefreshing(true);
    setError(null);
    setRefreshResult(null);
    try {
      const result = await refreshMarketSignals();
      setRefreshResult(
        result.items.length > 0
          ? `Found ${result.items.length} new real signal${result.items.length === 1 ? "" : "s"}.`
          : "Ran successfully, nothing new found this time."
      );
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Refresh failed.");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-white">Market Intelligence</h1>
        <p className="mt-1 text-sm text-neutral-400">
          Real signals only -- nothing here is fabricated. Runs automatically once a day (organic search +
          Google Trends rising topics + seasonal onset learning), or trigger it now below. Also accepts
          agent-driven web research findings (see docs/ROADMAP.md &quot;Agent-driven market research&quot;).
        </p>
      </div>

      <div className="flex items-center gap-4 rounded-lg border border-border bg-panel p-4">
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded bg-accent px-4 py-2 text-sm font-semibold text-canvas hover:opacity-90 disabled:opacity-50"
        >
          {refreshing ? "Refreshing..." : "Refresh now"}
        </button>
        {refreshResult ? <span className="text-sm text-neutral-400">{refreshResult}</span> : null}
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
            No market signals recorded yet. Configure SERPAPI_KEY and click &quot;Refresh now&quot; above, or POST
            findings via /api/market-intelligence/signals.
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
