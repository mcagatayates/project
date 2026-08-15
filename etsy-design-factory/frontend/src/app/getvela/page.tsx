"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  GetvelaExportBatchOut,
  GetvelaExportResponse,
  exportToGetvela,
  getGetvelaExportHistory,
  getGetvelaPendingCount,
} from "@/lib/api";

function downloadCsv(filename: string, csvText: string) {
  const blob = new Blob([csvText], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export default function GetvelaPage() {
  const [pendingCount, setPendingCount] = useState<number | null>(null);
  const [history, setHistory] = useState<GetvelaExportBatchOut[]>([]);
  const [requestedBy, setRequestedBy] = useState("control-center-operator");
  const [limit, setLimit] = useState("50");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<GetvelaExportResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [pending, hist] = await Promise.all([getGetvelaPendingCount(), getGetvelaExportHistory()]);
      setPendingCount(pending.pending_count);
      setHistory(hist.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the Design Factory API.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleExport() {
    setExporting(true);
    setError(null);
    try {
      const result = await exportToGetvela({
        requested_by: requestedBy,
        limit: limit.trim() ? Number(limit) : undefined,
      });
      setLastResult(result);
      const stamp = new Date().toISOString().slice(0, 10);
      downloadCsv(`getvela-export-${stamp}.csv`, result.csv);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Getvela export failed.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-white">Getvela Export</h1>
        <p className="mt-1 text-sm text-neutral-400">
          Approved designs, packaged as a CSV matching your real Getvela &quot;Import new listings&quot; template
          (physical print, one listing per design with a Size variation). Upload the downloaded file through
          Getvela&apos;s own Import button -- listings land in your archive and you activate them day by day, same
          as today. Nothing here calls Getvela or Etsy directly.
        </p>
      </div>

      {error ? (
        <div className="rounded border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-300">{error}</div>
      ) : null}

      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-border bg-panel p-4">
        <div className="text-sm text-neutral-300">
          <div className="text-xs uppercase tracking-wide text-neutral-500">Waiting to export</div>
          <div className="text-2xl font-semibold text-white">{loading ? "..." : (pendingCount ?? "-")}</div>
        </div>
        <label className="flex flex-col gap-1 text-sm text-neutral-300">
          Requested by
          <input
            value={requestedBy}
            onChange={(e) => setRequestedBy(e.target.value)}
            className="rounded border border-border bg-canvas px-2 py-1 text-neutral-100"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-neutral-300">
          Max designs this batch
          <input
            type="number"
            min={1}
            max={200}
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
            className="w-28 rounded border border-border bg-canvas px-2 py-1 text-neutral-100"
          />
        </label>
        <button
          onClick={handleExport}
          disabled={exporting || pendingCount === 0}
          className="rounded bg-accent px-4 py-2 text-sm font-semibold text-canvas hover:opacity-90 disabled:opacity-50"
        >
          {exporting ? "Exporting..." : "Export & download CSV"}
        </button>
      </div>

      {lastResult ? (
        <div className="rounded-lg border border-border bg-panel p-4 text-sm text-neutral-300">
          <div className="font-semibold text-white">
            Exported {lastResult.listing_count} listing{lastResult.listing_count === 1 ? "" : "s"} (
            {lastResult.row_count} CSV rows, including size variations).
          </div>
          <div className="mt-2 text-xs text-neutral-500">SKUs: {lastResult.skus.join(", ")}</div>
          <div className="mt-2 text-xs text-neutral-500">
            These designs are now marked exported and won&apos;t appear in your next batch.
          </div>
        </div>
      ) : null}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-400">Export history</h2>
        {loading ? (
          <div className="text-sm text-neutral-500">Loading...</div>
        ) : history.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-sm text-neutral-500">
            No exports yet.
          </div>
        ) : (
          <div className="divide-y divide-border rounded-lg border border-border bg-panel">
            {history.map((b) => (
              <div key={b.id} className="flex items-center justify-between p-3 text-sm">
                <div>
                  <div className="text-neutral-100">
                    {b.listing_count} listing{b.listing_count === 1 ? "" : "s"} · {b.row_count} rows
                  </div>
                  <div className="text-xs text-neutral-500">
                    by {b.requested_by} · {new Date(b.created_at).toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
