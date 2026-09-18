"use client";

import { useState, type ReactNode } from "react";
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

  const revenue = budget.receipts.omb.amountMillions;
  const spending = budget.outlays.omb.amountMillions;
  const gdpMillions = budget.gdp.amountMillions;
  const fyLabel = budget.comparisonFiscalYearLabel;
  const balance = revenue - spending;
  const isDeficit = balance < 0;
  const gap = Math.abs(balance);
  const covered = shareOf(revenue, spending);
  const ofGdp = shareOf(spending, gdpMillions);

  const panel =
    kind === "revenue"
      ? {
          aria: `${j.revenue} versus ${j.spending}`,
          sourceNote: revenueSourceNote,
          summary: (
            <>
              {isDeficit ? "Deficit" : "Surplus"}{" "}
              <span className="font-semibold tabular-nums text-[#1f3d4d]">
                {formatMillions(gap)}
              </span>
              <span className="text-[#8a7358]">
                {" "}
                · {j.revenueShort.toLowerCase()} covers {formatPercent(covered)} of{" "}
                {j.spendingShort.toLowerCase()}
              </span>
            </>
          ),
          left: {
            label: j.revenueShort,
            value: formatMillions(revenue),
            valueClass: "text-[#2f7d6d]",
          },
          right: {
            label: j.spendingShort,
            value: formatMillions(spending),
            valueClass: "text-[#c45c26]",
          },
          barColor: "#2f7d6d",
          barWidth: Math.min(covered, 1),
          barAria: `${j.revenue} is ${formatPercent(covered)} of ${j.spending}`,
          footerLeft: `${j.revenueShort} share of ${j.spendingShort.toLowerCase()}`,
          footerRight: formatPercent(covered),
        }
      : {
          aria: `${j.spending} versus ${j.gdp}`,
          sourceNote: gdpSourceNote,
          summary: (
            <>
              {j.spending} is{" "}
              <span className="font-semibold tabular-nums text-[#1f3d4d]">
                {formatPercent(ofGdp)}
              </span>{" "}
              of {j.gdp}
            </>
          ),
          left: {
            label: j.spendingShort,
            value: formatMillions(spending),
            valueClass: "text-[#c45c26]",
          },
          right: {
            label: j.gdp,
            value: formatMillions(gdpMillions),
            valueClass: "text-[#1f3d4d]",
          },
          barColor: "#c45c26",
          barWidth: Math.min(ofGdp, 1),
          barAria: `${j.spending} is ${formatPercent(ofGdp)} of ${j.gdp}`,
          footerLeft: `${j.spendingShort} share of ${j.gdp}`,
          footerRight: formatPercent(ofGdp),
        };

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

      <ComparisonPanel
        ariaLabel={panel.aria}
        sourceLine={`FY ${fyLabel} ${budget.comparisonStatus} · ${panel.sourceNote}`}
        summary={panel.summary}
        left={panel.left}
        right={panel.right}
        barColor={panel.barColor}
        barWidth={panel.barWidth}
        barAria={panel.barAria}
        footerLeft={panel.footerLeft}
        footerRight={panel.footerRight}
      />
    </section>
  );
}

function ComparisonPanel({
  ariaLabel,
  sourceLine,
  summary,
  left,
  right,
  barColor,
  barWidth,
  barAria,
  footerLeft,
  footerRight,
}: {
  ariaLabel: string;
  sourceLine: string;
  summary: ReactNode;
  left: { label: string; value: string; valueClass: string };
  right: { label: string; value: string; valueClass: string };
  barColor: string;
  barWidth: number;
  barAria: string;
  footerLeft: string;
  footerRight: string;
}) {
  return (
    <div aria-label={ariaLabel}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[11px] font-medium uppercase tracking-wide text-[#8a7358]">
            {sourceLine}
          </p>
          {/* Fixed two-line block so Revenue / GDP toggles keep the same height. */}
          <p className="mt-1 line-clamp-2 min-h-[2.5rem] text-sm leading-5 text-[#5c6b73]">
            {summary}
          </p>
        </div>
        <div className="flex shrink-0 gap-4 text-right text-sm tabular-nums">
          <Metric label={left.label} value={left.value} valueClass={left.valueClass} />
          <Metric label={right.label} value={right.value} valueClass={right.valueClass} />
        </div>
      </div>

      <div
        className="mt-3 h-3 overflow-hidden rounded-full bg-[#eadfce]"
        role="img"
        aria-label={barAria}
      >
        <div
          className="h-full rounded-full"
          style={{ width: `${barWidth * 100}%`, backgroundColor: barColor }}
        />
      </div>
      <div className="mt-1.5 flex justify-between gap-3 text-[11px] text-[#8a7358]">
        <span className="min-w-0 truncate">{footerLeft}</span>
        <span className="shrink-0 tabular-nums">{footerRight}</span>
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass: string;
}) {
  return (
    <div className="w-[7.75rem] sm:w-[9.5rem]">
      <p className="truncate text-[11px] uppercase tracking-wide text-[#8a7358]" title={label}>
        {label}
      </p>
      <p className={`font-semibold ${valueClass}`}>{value}</p>
    </div>
  );
}
