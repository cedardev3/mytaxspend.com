"use client";

import type { CountryBudget } from "@/data/budget";
import { type JurisdictionLabels } from "@/lib/jurisdiction";
import { formatMillions, formatPercent, shareOf } from "@/lib/spend";

type BudgetBalanceProps = {
  jurisdiction: JurisdictionLabels;
  budget: CountryBudget;
  sourceNote: string;
};

export default function BudgetBalance({
  jurisdiction,
  budget,
  sourceNote,
}: BudgetBalanceProps) {
  const revenue = budget.receipts.omb.amountMillions;
  const spending = budget.outlays.omb.amountMillions;
  const balance = revenue - spending;
  const isDeficit = balance < 0;
  const gap = Math.abs(balance);
  const covered = shareOf(revenue, spending);
  const j = jurisdiction;
  const fyLabel = budget.comparisonFiscalYearLabel;

  return (
    <section
      aria-label={`${j.revenue} versus ${j.spending}`}
      className="rounded-2xl border border-[#eadfce] bg-white/80 px-4 py-3 sm:px-5 sm:py-4"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-[#8a7358]">
            FY {fyLabel} {budget.comparisonStatus} · {sourceNote}
          </p>
          <p className="mt-1 text-sm text-[#5c6b73]">
            {isDeficit ? "Deficit" : "Surplus"}{" "}
            <span className="font-semibold tabular-nums text-[#1f3d4d]">
              {formatMillions(gap)}
            </span>
            <span className="text-[#8a7358]">
              {" "}
              · {j.revenueShort.toLowerCase()} covers {formatPercent(covered)} of{" "}
              {j.spendingShort.toLowerCase()}
            </span>
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-right text-sm tabular-nums">
          <div>
            <p className="text-[11px] uppercase tracking-wide text-[#8a7358]">
              {j.revenueShort}
            </p>
            <p className="font-semibold text-[#2f7d6d]">{formatMillions(revenue)}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wide text-[#8a7358]">
              {j.spendingShort}
            </p>
            <p className="font-semibold text-[#c45c26]">{formatMillions(spending)}</p>
          </div>
        </div>
      </div>

      <div
        className="mt-3 h-3 overflow-hidden rounded-full bg-[#eadfce]"
        role="img"
        aria-label={`${j.revenue} is ${formatPercent(covered)} of ${j.spending}`}
      >
        <div
          className="h-full rounded-full bg-[#2f7d6d]"
          style={{ width: `${Math.min(covered, 1) * 100}%` }}
        />
      </div>
      <div className="mt-1.5 flex justify-between gap-3 text-[11px] text-[#8a7358]">
        <span>
          {j.revenueShort} share of {j.spendingShort.toLowerCase()}
        </span>
        <span className="shrink-0 tabular-nums">{formatPercent(covered)}</span>
      </div>
    </section>
  );
}
