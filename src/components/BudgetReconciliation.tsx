"use client";

import {
  formatMillions,
  formatPercent,
  summarizeBudget,
  type BudgetMode,
  type SpendNode,
} from "@/lib/spend";
import { type JurisdictionLabels } from "@/lib/jurisdiction";

type BudgetReconciliationProps = {
  node: SpendNode;
  mode: BudgetMode;
  jurisdiction: JurisdictionLabels;
  hoveredId: string | null;
  onHover: (id: string | null) => void;
  onSelectOffset?: (id: string) => void;
};

export default function BudgetReconciliation({
  node,
  mode,
  jurisdiction,
  hoveredId,
  onHover,
  onSelectOffset,
}: BudgetReconciliationProps) {
  const summary = summarizeBudget(node);
  const hasOffsets = summary.offsets.length > 0;
  const j = jurisdiction;
  const unit = mode === "spending" ? j.spendingUnit : j.revenueUnit;
  const grossLabel = mode === "spending" ? j.grossSpending : j.grossRevenue;
  const netLabel = mode === "spending" ? j.netSpending : j.netRevenue;

  if (!hasOffsets && summary.effect === "unchanged") {
    return (
      <section
        aria-label="Budget summary"
        className="rounded-2xl border border-[#eadfce] bg-white/80 px-4 py-3"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="text-sm font-semibold text-[#1f3d4d]">{summary.name}</p>
          <p className="text-sm tabular-nums text-[#1f3d4d]">
            {formatMillions(summary.netMillions)}
            <span className="ml-2 text-xs font-normal text-[#8a7358]">net {unit}</span>
          </p>
        </div>
        <p className="mt-1 text-xs text-[#8a7358]">No offsets in this category.</p>
      </section>
    );
  }

  const effectLabel =
    summary.effect === "reduced"
      ? `Reduced by ${formatMillions(Math.abs(summary.deltaMillions))}`
      : summary.effect === "expanded"
        ? `Expanded by ${formatMillions(summary.deltaMillions)}`
        : "No net change from offsets";

  return (
    <section
      aria-label="Budget reconciliation"
      className="rounded-2xl border border-[#eadfce] bg-white/80 px-4 py-3 sm:px-5 sm:py-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-[#1f3d4d]">{summary.name}</p>
          <p className="mt-0.5 text-xs text-[#8a7358]">{effectLabel}</p>
        </div>
        <p className="text-right text-sm font-semibold tabular-nums text-[#1f3d4d]">
          {formatMillions(summary.netMillions)}
          <span className="mt-0.5 block text-xs font-normal text-[#8a7358]">net total</span>
        </p>
      </div>

      <dl className="mt-3 grid gap-1.5 text-sm">
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-[#5c6b73]">{grossLabel}</dt>
          <dd className="tabular-nums text-[#1f3d4d]">{formatMillions(summary.grossMillions)}</dd>
        </div>
        <div className="flex items-baseline justify-between gap-3">
          <dt className="text-[#5c6b73]">
            Offsets
            {summary.effect === "reduced" ? (
              <span className="ml-1 text-[#8a7358]">(reduction)</span>
            ) : summary.effect === "expanded" ? (
              <span className="ml-1 text-[#2a6f97]">(expansion)</span>
            ) : null}
          </dt>
          <dd className="tabular-nums text-[#8a7358]">
            {formatMillions(summary.offsetMillions)}
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-3 border-t border-dashed border-[#eadfce] pt-1.5">
          <dt className="font-medium text-[#1f3d4d]">{netLabel}</dt>
          <dd className="font-medium tabular-nums text-[#1f3d4d]">
            {formatMillions(summary.netMillions)}
          </dd>
        </div>
      </dl>

      {hasOffsets ? (
        <div className="mt-3 border-t border-[#eadfce] pt-3">
          <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-[#8a7358]">
            Offset detail
          </p>
          <ul className="flex flex-col gap-1">
            {summary.offsets.map((offset) => {
              const active = hoveredId === offset.id;
              const remainingLabel =
                offset.remainingMillions > 0
                  ? `${formatMillions(offset.remainingMillions)} remains`
                  : `Nothing remains as ${unit}`;
              return (
                <li key={offset.id}>
                  <button
                    type="button"
                    className={`flex w-full flex-col gap-0.5 rounded-lg px-2 py-1.5 text-left transition-colors ${
                      active ? "bg-[#f4efe6]" : "hover:bg-[#f7f3ec]"
                    }`}
                    onMouseEnter={() => onHover(offset.id)}
                    onMouseLeave={() => onHover(null)}
                    onClick={() => onSelectOffset?.(offset.id)}
                  >
                    <span className="flex items-baseline justify-between gap-2">
                      <span className="min-w-0 truncate text-sm text-[#5c6b73]">
                        {offset.name}
                      </span>
                      <span className="shrink-0 text-xs tabular-nums text-[#8a7358]">
                        {formatMillions(offset.amountMillions)}
                        {offset.percentOfNet != null
                          ? ` · ${formatPercent(offset.percentOfNet)}`
                          : offset.percentOfGross != null
                            ? ` · ${formatPercent(offset.percentOfGross)} of gross`
                            : ""}
                      </span>
                    </span>
                    <span className="text-[11px] text-[#8a7358]">
                      Reduced gross by {formatMillions(Math.abs(offset.amountMillions))}
                      {" · "}
                      {remainingLabel}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
