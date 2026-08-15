"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CandidateCard } from "@/components/CandidateCard";
import { ApiError, applyApproval, applyBulkApproval, CandidateSummary, listCandidates } from "@/lib/api";

const STATUS_OPTIONS = [
  { value: "AWAITING_APPROVAL", label: "Awaiting approval" },
  { value: "SELECTED", label: "Selected (tournament winners)" },
  { value: "APPROVED", label: "Approved" },
  { value: "REJECTED", label: "Rejected" },
];

export default function CandidatesPage() {
  const [status, setStatus] = useState("AWAITING_APPROVAL");
  const [actor, setActor] = useState("control-center-operator");
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (s: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCandidates({ status: s });
      setCandidates(data.items);
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the Design Factory API.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(status);
  }, [load, status]);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    setSelected(new Set(candidates.map((c) => c.id)));
  }

  function clearSelection() {
    setSelected(new Set());
  }

  async function decideOne(id: string, action: "APPROVE" | "REJECT") {
    setBusyIds((prev) => new Set(prev).add(id));
    setError(null);
    try {
      await applyApproval(id, { action, actor });
      setCandidates((prev) => prev.filter((c) => c.id !== id));
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Approval action failed.");
    } finally {
      setBusyIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  async function decideBulk(action: "APPROVE" | "REJECT") {
    if (selected.size === 0) return;
    setBulkBusy(true);
    setError(null);
    try {
      const ids = Array.from(selected);
      await applyBulkApproval({ candidate_ids: ids, action, actor });
      setCandidates((prev) => prev.filter((c) => !selected.has(c.id)));
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Bulk approval action failed.");
    } finally {
      setBulkBusy(false);
    }
  }

  const selectionLabel = useMemo(
    () => (selected.size > 0 ? `${selected.size} selected` : "none selected"),
    [selected]
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Approval Queue</h1>
        <p className="mt-1 text-sm text-neutral-400">
          Every image below is a real generation from the pipeline. Approving one triggers a real genome mutation
          for the next candidate in its lineage (see docs/DESIGN_GENOME_SCHEMA.md).
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-border bg-panel p-4">
        <label className="flex flex-col gap-1 text-sm text-neutral-300">
          Status
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded border border-border bg-canvas px-2 py-1 text-neutral-100"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-neutral-300">
          Actor
          <input
            value={actor}
            onChange={(e) => setActor(e.target.value)}
            className="rounded border border-border bg-canvas px-2 py-1 text-neutral-100"
          />
        </label>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-neutral-500">{selectionLabel}</span>
          <button
            type="button"
            onClick={selectAll}
            className="rounded border border-border px-3 py-1 text-xs text-neutral-300 hover:border-neutral-500"
          >
            Select all
          </button>
          <button
            type="button"
            onClick={clearSelection}
            className="rounded border border-border px-3 py-1 text-xs text-neutral-300 hover:border-neutral-500"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={() => decideBulk("APPROVE")}
            disabled={selected.size === 0 || bulkBusy}
            className="rounded bg-emerald-700 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
          >
            Bulk approve
          </button>
          <button
            type="button"
            onClick={() => decideBulk("REJECT")}
            disabled={selected.size === 0 || bulkBusy}
            className="rounded bg-red-900 px-3 py-1 text-xs font-semibold text-white hover:bg-red-800 disabled:opacity-50"
          >
            Bulk reject
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-300">{error}</div>
      ) : null}

      {loading ? (
        <div className="text-sm text-neutral-500">Loading...</div>
      ) : candidates.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-neutral-500">
          No candidates in status &quot;{status}&quot; right now.
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {candidates.map((c) => (
            <CandidateCard
              key={c.id}
              candidate={c}
              selected={selected.has(c.id)}
              onToggle={() => toggle(c.id)}
              onApprove={() => decideOne(c.id, "APPROVE")}
              onReject={() => decideOne(c.id, "REJECT")}
              busy={busyIds.has(c.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
