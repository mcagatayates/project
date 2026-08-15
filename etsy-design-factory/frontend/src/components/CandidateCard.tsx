import { CandidateSummary, imageUrl } from "@/lib/api";

export function CandidateCard({
  candidate,
  selected,
  onToggle,
  onApprove,
  onReject,
  busy,
}: {
  candidate: CandidateSummary;
  selected: boolean;
  onToggle: () => void;
  onApprove: () => void;
  onReject: () => void;
  busy: boolean;
}) {
  return (
    <div
      className={`overflow-hidden rounded-lg border bg-panel transition ${
        selected ? "border-accent ring-1 ring-accent" : "border-border"
      }`}
    >
      <button
        type="button"
        onClick={onToggle}
        className="block w-full text-left"
        aria-pressed={selected}
        aria-label={selected ? "Deselect candidate" : "Select candidate"}
      >
        <div className="relative aspect-square w-full bg-black">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl(candidate.id)}
            alt={candidate.subject ?? "generated wall-art candidate"}
            className="h-full w-full object-cover"
            loading="lazy"
          />
          <div className="absolute left-2 top-2 h-5 w-5 rounded border border-white/60 bg-black/40">
            {selected ? <div className="h-full w-full bg-accent" /> : null}
          </div>
        </div>
      </button>
      <div className="space-y-1 p-3 text-xs text-neutral-300">
        <div className="truncate font-medium text-neutral-100" title={candidate.collection_name ?? undefined}>
          {candidate.collection_name ?? "unassigned"}
        </div>
        <div
          className="truncate text-neutral-400"
          title={[candidate.subject, candidate.style, candidate.palette].filter(Boolean).join(" · ") || undefined}
        >
          {[candidate.subject, candidate.style, candidate.palette].filter(Boolean).join(" · ") || "no genome data"}
        </div>
        {candidate.scores?.commercial_potential ? (
          <div className="text-neutral-500">
            commercial: {candidate.scores.commercial_potential.value.toFixed(2)}
          </div>
        ) : null}
        {candidate.is_repair ? <div className="text-amber-400">repaired</div> : null}
      </div>
      <div className="flex gap-2 border-t border-border p-2">
        <button
          type="button"
          onClick={onApprove}
          disabled={busy}
          className="flex-1 rounded bg-emerald-700 px-2 py-1 text-xs font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
        >
          Approve
        </button>
        <button
          type="button"
          onClick={onReject}
          disabled={busy}
          className="flex-1 rounded bg-red-900 px-2 py-1 text-xs font-semibold text-white hover:bg-red-800 disabled:opacity-50"
        >
          Reject
        </button>
      </div>
    </div>
  );
}
