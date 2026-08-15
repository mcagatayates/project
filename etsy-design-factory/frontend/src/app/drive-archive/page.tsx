"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  DriveArchiveRecordOut,
  getDriveArchiveHistory,
  getDriveArchivePendingCount,
  lookupDriveArchiveBySku,
  syncToDriveArchive,
} from "@/lib/api";

export default function DriveArchivePage() {
  const [pendingCount, setPendingCount] = useState<number | null>(null);
  const [history, setHistory] = useState<DriveArchiveRecordOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [skuQuery, setSkuQuery] = useState("");
  const [lookupResult, setLookupResult] = useState<DriveArchiveRecordOut | null>(null);
  const [lookupSearched, setLookupSearched] = useState(false);
  const [looking, setLooking] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [pending, hist] = await Promise.all([getDriveArchivePendingCount(), getDriveArchiveHistory()]);
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

  async function handleSync() {
    setSyncing(true);
    setError(null);
    try {
      await syncToDriveArchive();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Drive sync failed.");
    } finally {
      setSyncing(false);
    }
  }

  async function handleLookup(e: React.FormEvent) {
    e.preventDefault();
    if (!skuQuery.trim()) return;
    setLooking(true);
    setLookupError(null);
    setLookupSearched(false);
    try {
      const result = await lookupDriveArchiveBySku(skuQuery.trim());
      setLookupResult(result);
      setLookupSearched(true);
    } catch (err) {
      setLookupError(err instanceof ApiError ? err.message : "Lookup failed.");
    } finally {
      setLooking(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-white">Drive Archive</h1>
        <p className="mt-1 text-sm text-neutral-400">
          Every approved design&apos;s master image gets uploaded to Google Drive, named by SKU. When an Etsy order
          comes in, search the SKU below to jump straight to the file -- no more hunting through Drive by hand.
        </p>
      </div>

      <div className="rounded-lg border border-accent/40 bg-panel p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-accent">Find a master image by SKU</h2>
        <form onSubmit={handleLookup} className="mt-3 flex gap-2">
          <input
            value={skuQuery}
            onChange={(e) => setSkuQuery(e.target.value)}
            placeholder="e.g. WA-982A52DF39"
            className="flex-1 rounded border border-border bg-canvas px-3 py-2 text-neutral-100"
          />
          <button
            type="submit"
            disabled={looking}
            className="rounded bg-accent px-4 py-2 text-sm font-semibold text-canvas hover:opacity-90 disabled:opacity-50"
          >
            {looking ? "Searching..." : "Find"}
          </button>
        </form>
        {lookupError ? <div className="mt-3 text-sm text-red-300">{lookupError}</div> : null}
        {lookupSearched && !lookupError ? (
          lookupResult ? (
            <div className="mt-3 rounded border border-emerald-800 bg-emerald-950/30 p-3 text-sm">
              <div className="text-neutral-100">SKU {lookupResult.sku}</div>
              <a
                href={lookupResult.drive_file_url}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-block text-accent underline"
              >
                Open in Google Drive →
              </a>
            </div>
          ) : (
            <div className="mt-3 rounded border border-dashed border-border p-3 text-sm text-neutral-500">
              No Drive archive record for that SKU yet -- it may not be synced yet, or the SKU doesn&apos;t exist.
            </div>
          )
        ) : null}
      </div>

      {error ? (
        <div className="rounded border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-300">{error}</div>
      ) : null}

      <div className="flex flex-wrap items-center gap-4 rounded-lg border border-border bg-panel p-4">
        <div className="text-sm text-neutral-300">
          <div className="text-xs uppercase tracking-wide text-neutral-500">Waiting to archive</div>
          <div className="text-2xl font-semibold text-white">{loading ? "..." : (pendingCount ?? "-")}</div>
        </div>
        <button
          onClick={handleSync}
          disabled={syncing || pendingCount === 0}
          className="ml-auto rounded bg-accent px-4 py-2 text-sm font-semibold text-canvas hover:opacity-90 disabled:opacity-50"
        >
          {syncing ? "Syncing..." : "Sync to Drive"}
        </button>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-400">Recently archived</h2>
        {loading ? (
          <div className="text-sm text-neutral-500">Loading...</div>
        ) : history.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-sm text-neutral-500">
            Nothing archived yet.
          </div>
        ) : (
          <div className="divide-y divide-border rounded-lg border border-border bg-panel">
            {history.map((r) => (
              <div key={r.artwork_id} className="flex items-center justify-between p-3 text-sm">
                <div>
                  <div className="text-neutral-100">{r.sku}</div>
                  <div className="text-xs text-neutral-500">{new Date(r.created_at).toLocaleString()}</div>
                </div>
                <a href={r.drive_file_url} target="_blank" rel="noreferrer" className="text-accent underline">
                  Open in Drive →
                </a>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
