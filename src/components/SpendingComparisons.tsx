"use client";

import { useState } from "react";
import type { CountryBudget } from "@/data/budget";
import { type JurisdictionLabels } from "@/lib/jurisdiction";
import { formatMillions, formatPercent, shareOf } from "@/lib/spend";

type ComparisonKind = "revenue" | "gdp";

type SpendingComparisonsProps = {
  jurisdiction: JurisdictionLabels;
  budget: CountryBudget;
  revenueSourceNote: string;
  gdpSourceNote: string;
};

export default function SpendingComparisons({
  jurisdiction,
  budget,
  revenueSourceNote,
  gdpSourceNote,
}: SpendingComparisonsProps) {
  const [kind, setKind] = useState<ComparisonKind>("revenue");
  const j = jurisdiction;

  return (
    <section className="rounded-2xl border border-[#eadfce] bg-white/80 px-4 py-3 sm:px-5 sm:py-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] font-medium uppercase tracking-wide text-[#8a7358]">
          Compare {j.spendingShort}
        </p>
        <div
          role="tablist"
          aria-label="Spending comparison"
          className="inline-flex rounded-full border border-[#eadfce] bg-[#fbf8f2] p-0.5"
        >
          {(
            [
              { id: "revenue" as const, label: "vs Revenue" },
              { id: "gdp" as const, label: "vs GDP" },
            ] as const
          ).map((option) => {
            const active = kind === option.id;
            return (
              <button
                key={option.id}
                type="button"
                role="tab"
                aria-selected={active}
                className={`rounded-full px-3 py-1 text-xs transition-colors sm:text-sm ${
                  active
                    ? "bg-white font-semibold text-[#1f3d4d] shadow-sm"
                    : "text-[#5c6b73] hover:text-[#1f3d4d]"
                }`}
                onClick={() => setKind(option.id)}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      {kind === "revenue" ? (
        <RevenueSharePanel j={j} budget={budget} sourceNote={revenueSourceNote} />
      ) : (
        <GdpSharePanel j={j} budget={budget} sourceNote={gdpSourceNote} />
      )}
    </section>
  );
}

function RevenueSharePanel({
  j,
  budget,
  sourceNote,
}: {
  j: JurisdictionLabels;
  budget: CountryBudget;
  sourceNote: string;
}) {
  const revenue = budget.receipts.omb.amountMillions;
  const spending = budget.outlays.omb.amountMillions;
  const balance = revenue - spending;
  const isDeficit = balance < 0;
  const gap = Math.abs(balance);
  const covered = shareOf(revenue, spending);
  const fyLabel = budget.comparisonFiscalYearLabel;

  return (
    <div aria-label={`${j.revenue} versus ${j.spending}`}>
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
    </div>
  );
}

function GdpSharePanel({
  j,
  budget,
  sourceNote,
}: {
  j: JurisdictionLabels;
  budget: CountryBudget;
  sourceNote: string;
}) {
  const spending = budget.outlays.omb.amountMillions;
  const gdpMillions = budget.gdp.amountMillions;
  const ofGdp = shareOf(spending, gdpMillions);
  const fyLabel = budget.comparisonFiscalYearLabel;

  return (
    <div aria-label={`${j.spending} versus ${j.gdp}`}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-[#8a7358]">
            FY {fyLabel} {budget.comparisonStatus} · {sourceNote}
          </p>
          <p className="mt-1 text-sm text-[#5c6b73]">
            {j.spending} is{" "}
            <span className="font-semibold tabular-nums text-[#1f3d4d]">
              {formatPercent(ofGdp)}
            </span>{" "}
            of {j.gdp}
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-right text-sm tabular-nums">
          <div>
            <p className="text-[11px] uppercase tracking-wide text-[#8a7358]">
              {j.spendingShort}
            </p>
            <p className="font-semibold text-[#c45c26]">{formatMillions(spending)}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wide text-[#8a7358]">{j.gdp}</p>
            <p className="font-semibold text-[#1f3d4d]">
              {formatMillions(gdpMillions)}
            </p>
          </div>
        </div>
      </div>

      <div
        className="mt-3 h-3 overflow-hidden rounded-full bg-[#eadfce]"
        role="img"
        aria-label={`${j.spending} is ${formatPercent(ofGdp)} of ${j.gdp}`}
      >
        <div
          className="h-full rounded-full bg-[#c45c26]"
          style={{ width: `${Math.min(ofGdp, 1) * 100}%` }}
        />
      </div>
      <div className="mt-1.5 flex justify-between gap-3 text-[11px] text-[#8a7358]">
        <span>
          {j.spendingShort} share of {j.gdp}
        </span>
        <span className="shrink-0 tabular-nums">{formatPercent(ofGdp)}</span>
      </div>
    </div>
  );
}
