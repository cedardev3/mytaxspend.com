"use client";

import { useMemo, useState } from "react";
import BudgetBalance from "@/components/BudgetBalance";
import BudgetReconciliation from "@/components/BudgetReconciliation";
import ContextPie from "@/components/ContextPie";
import CountryFlag from "@/components/CountryFlag";
import CountryToggle from "@/components/CountryToggle";
import DrilldownPie from "@/components/DrilldownPie";
import InfoTip from "@/components/InfoTip";
import InterestDefenseCompare from "@/components/InterestDefenseCompare";
import SourceLinks from "@/components/SourceLinks";
import SpendingComparisons from "@/components/SpendingComparisons";
import UpdateStamp from "@/components/UpdateStamp";
import { budgetFor } from "@/data/budget";
import {
  DEFAULT_COUNTRY_ID,
  getCountry,
  type CountryId,
  type JurisdictionLabels,
} from "@/lib/jurisdiction";
import {
  buildPieChart,
  formatCompactMillions,
  formatMillions,
  formatPercent,
  hasChildren,
  nodeAtPath,
  shareOf,
  type BudgetMode,
  type PieSlice,
} from "@/lib/spend";

function SliceRow({
  slice,
  active,
  drillable,
  showGdpShare,
  outflowTotalMillions,
  gdpMillions,
  jurisdiction,
  onHover,
  onOpen,
}: {
  slice: PieSlice;
  active: boolean;
  drillable: boolean;
  showGdpShare: boolean;
  outflowTotalMillions: number;
  gdpMillions: number;
  jurisdiction: JurisdictionLabels;
  onHover: (id: string | null) => void;
  onOpen: () => void;
}) {
  const amountClass = slice.isOffset ? "text-[#8a7358]" : "text-[#5c6b73]";
  const nameClass = slice.isOffset
    ? "text-[#5c6b73]"
    : drillable
      ? "text-[#1f3d4d]"
      : "text-[#5c6b73]";
  const swatch = slice.isOffset ? (
    <span
      className="relative h-2.5 w-2.5 shrink-0 overflow-hidden rounded-full border border-[#8a7358]"
      aria-hidden
      style={{
        backgroundImage:
          "repeating-linear-gradient(45deg, #f3ebe0 0 2px, #8a7358 2px 3.5px)",
      }}
    />
  ) : (
    <span
      className={`h-2.5 w-2.5 shrink-0 rounded-full ${drillable ? "" : "opacity-70"}`}
      style={{ backgroundColor: slice.color }}
    />
  );

  const ofOutflows = shareOf(slice.amountMillions, outflowTotalMillions);
  const ofGdp = shareOf(slice.amountMillions, gdpMillions);
  const amount = formatCompactMillions(slice.amountMillions);
  const metrics = showGdpShare
    ? `${amount} · ${formatPercent(ofOutflows)} · ${formatPercent(ofGdp)} GDP`
    : `${amount} · ${formatPercent(slice.percent)}`;
  const metricsTitle = showGdpShare
    ? `${formatMillions(slice.amountMillions)} · ${formatPercent(ofOutflows)} ${jurisdiction.ofSpending} · ${formatPercent(ofGdp)} ${jurisdiction.ofGdp}`
    : `${formatMillions(slice.amountMillions)} · ${formatPercent(slice.percent)}`;

  const label = (
    <>
      {swatch}
      <span className={`min-w-0 flex-1 truncate text-sm ${nameClass}`}>
        {slice.name}
      </span>
      <span
        className={`shrink-0 text-right text-xs tabular-nums ${amountClass}`}
        title={metricsTitle}
      >
        {metrics}
      </span>
      <span
        className={`w-3 shrink-0 text-center text-xs ${
          drillable ? "text-[#2a6f97]" : "text-[#d4c4ae]"
        }`}
        aria-hidden
      >
        {drillable ? "›" : "·"}
      </span>
    </>
  );

  return (
    <li
      className={`flex items-center gap-2 rounded-lg px-1.5 py-1 ${active ? "bg-[#f4efe6]" : ""}`}
      onMouseEnter={() => onHover(slice.id)}
      onMouseLeave={() => onHover(null)}
    >
      {drillable ? (
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          onClick={onOpen}
          aria-label={`${slice.name}, open details`}
        >
          {label}
        </button>
      ) : (
        <div
          className="flex min-w-0 flex-1 items-center gap-2"
          aria-label={`${slice.name}, no further detail`}
        >
          {label}
        </div>
      )}
      <InfoTip label={`Sources for ${slice.name}`} align="right">
        {slice.code ? (
          <p className="mb-1 text-[11px] text-[#8a7358]">{slice.code}</p>
        ) : null}
        <p className="mb-2 text-xs leading-5 text-[#5c6b73]">{slice.description}</p>
        <p className="mb-2 text-[11px] text-[#8a7358]">
          {drillable ? "Has subcategories — click to open." : "No further subcategories."}
        </p>
        {showGdpShare ? (
          <p className="mb-2 text-[11px] leading-4 text-[#8a7358]">
            {formatPercent(ofOutflows)} {jurisdiction.ofSpending} ·{" "}
            {formatPercent(ofGdp)} {jurisdiction.ofGdp}
          </p>
        ) : null}
        {slice.isOffset ? (
          <p className="mb-2 text-[11px] text-[#8a7358]">
            Offset (negative amount) — reduces the parent net total.
          </p>
        ) : null}
        <SourceLinks sources={slice.sources} />
      </InfoTip>
    </li>
  );
}

function ModeToggle({
  mode,
  jurisdiction,
  onChange,
}: {
  mode: BudgetMode;
  jurisdiction: JurisdictionLabels;
  onChange: (mode: BudgetMode) => void;
}) {
  const options: Array<{ id: BudgetMode; label: string }> = [
    { id: "spending", label: jurisdiction.spending },
    { id: "revenue", label: jurisdiction.revenue },
  ];

  return (
    <div
      role="tablist"
      aria-label={`${jurisdiction.name} budget view`}
      className="inline-flex max-w-full flex-wrap rounded-full border border-[#eadfce] bg-[#fbf8f2] p-0.5"
    >
      {options.map((option) => {
        const active = mode === option.id;
        return (
          <button
            key={option.id}
            type="button"
            role="tab"
            aria-selected={active}
            className={`rounded-full px-2.5 py-1.5 text-xs transition-colors sm:px-3.5 sm:text-sm ${
              active
                ? "bg-white font-semibold text-[#1f3d4d] shadow-sm"
                : "text-[#5c6b73] hover:text-[#1f3d4d]"
            }`}
            onClick={() => onChange(option.id)}
            aria-label={option.label}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export default function SpendExplorer() {
  const [countryId, setCountryId] = useState<CountryId>(DEFAULT_COUNTRY_ID);
  const [mode, setMode] = useState<BudgetMode>("spending");
  const [path, setPath] = useState<string[]>([]);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const country = getCountry(countryId);
  const jurisdiction = country.federal;
  const budget = useMemo(() => budgetFor(countryId), [countryId]);
  const dataset = mode === "spending" ? budget.outlays : budget.receipts;
  const root = mode === "spending" ? budget.spending : budget.revenue;
  const current = useMemo(() => nodeAtPath(root, path), [root, path]);
  const sourceNotes =
    countryId === "ca"
      ? {
          balance: "Public Accounts / FRT",
          revenueCompare: "Public Accounts / FRT",
          gdpCompare: "FRT GDP",
        }
      : {
          balance: "OMB Tables 2.1 & 3.2",
          revenueCompare: "OMB Tables 2.1 & 3.2",
          gdpCompare: "OMB Tables 3.2 & 10.1",
        };

  const selectCountry = (id: CountryId) => {
    setCountryId(id);
    setPath([]);
    setHoveredId(null);
    setMode("spending");
  };

  if (!country.available) {
    return (
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-[#1f3d4d] sm:text-3xl">
            My Tax Spend
          </h1>
          <CountryToggle countryId={countryId} onChange={selectCountry} />
        </header>
        <section className="rounded-3xl border border-[#eadfce] bg-white px-6 py-16 text-center">
          <div className="mx-auto flex h-10 w-16 items-center justify-center">
            <CountryFlag
              countryId={country.id}
              className="h-8 w-14 rounded-sm shadow-[0_0_0_1px_rgba(31,61,77,0.12)]"
            />
          </div>
          <h2 className="mt-4 text-xl font-semibold text-[#1f3d4d]">{country.name}</h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#5c6b73]">
            {country.comingSoonMessage}
          </p>
          <button
            type="button"
            className="mt-6 text-sm text-[#2a6f97] underline-offset-4 hover:underline"
            onClick={() => selectCountry(DEFAULT_COUNTRY_ID)}
          >
            Back to USA
          </button>
        </section>
      </div>
    );
  }

  if (!current.children) {
    throw new Error(`Explorer landed on "${current.id}" with no children to chart`);
  }

  const chart = buildPieChart(current);
  const slices = chart.legend;
  const crumbs = [
    {
      id: root.id,
      name: mode === "spending" ? jurisdiction.spending : jurisdiction.revenue,
      depth: 0,
    },
    ...path.map((id, index) => {
      const node = nodeAtPath(root, path.slice(0, index + 1));
      return { id, name: node.name, depth: index + 1 };
    }),
  ];
  const drilled = path.length > 0;

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-[#1f3d4d] sm:text-3xl">
            My Tax Spend
          </h1>
          <ModeToggle
            mode={mode}
            jurisdiction={jurisdiction}
            onChange={(next) => {
              setMode(next);
              setPath([]);
              setHoveredId(null);
            }}
          />
        </div>
        <div className="flex items-center gap-2">
          <CountryToggle countryId={countryId} onChange={selectCountry} />
          <InfoTip label={`About ${current.name}`}>
            {current.code ? (
              <p className="mb-1 text-[11px] text-[#8a7358]">{current.code}</p>
            ) : null}
            <p className="mb-2 text-xs leading-5 text-[#5c6b73]">{current.description}</p>
            <SourceLinks sources={current.sources} />
          </InfoTip>
          <UpdateStamp dataset={dataset} mode={mode} />
        </div>
      </header>

      <div className="grid items-stretch gap-3 lg:grid-cols-4">
        <div className="min-w-0 lg:col-span-3">
          {mode === "spending" ? (
            <SpendingComparisons
              jurisdiction={jurisdiction}
              budget={budget}
              revenueSourceNote={sourceNotes.revenueCompare}
              gdpSourceNote={sourceNotes.gdpCompare}
            />
          ) : (
            <BudgetBalance
              jurisdiction={jurisdiction}
              budget={budget}
              sourceNote={sourceNotes.balance}
            />
          )}
        </div>
        <div className="min-w-0 lg:col-span-1">
          <InterestDefenseCompare pair={budget.interestDefense} />
        </div>
      </div>

      <nav aria-label="Budget path" className="flex flex-wrap items-center gap-2 text-sm">
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <span key={`${crumb.id}-${crumb.depth}`} className="flex items-center gap-2">
              {index > 0 ? <span className="text-[#b3a28c]">/</span> : null}
              {isLast ? (
                <span className="font-semibold text-[#1f3d4d]">{crumb.name}</span>
              ) : (
                <button
                  type="button"
                  className="text-[#2a6f97] underline-offset-4 hover:underline"
                  onClick={() => {
                    setHoveredId(null);
                    setPath(path.slice(0, crumb.depth));
                  }}
                >
                  {crumb.name}
                </button>
              )}
            </span>
          );
        })}
        {drilled ? (
          <button
            type="button"
            className="ml-2 text-xs text-[#5c6b73] underline-offset-4 hover:underline"
            onClick={() => {
              setHoveredId(null);
              setPath(path.slice(0, -1));
            }}
          >
            Back
          </button>
        ) : null}
      </nav>

      <div
        className={`grid items-stretch gap-6 ${
          mode === "spending" && drilled
            ? "lg:grid-cols-[minmax(0,1fr)_20rem]"
            : "lg:grid-cols-[minmax(0,1fr)_16.5rem]"
        }`}
      >
        <section
          className={`relative rounded-3xl border border-[#eadfce] bg-white p-3 sm:p-6 ${drilled ? "sm:pr-[12rem]" : ""}`}
        >
          {drilled ? (
            <div className="mb-3 flex justify-end sm:absolute sm:right-4 sm:top-4 sm:z-20 sm:mb-0">
              <ContextPie
                root={root}
                section={current}
                hoveredId={hoveredId}
                totalLabel={
                  mode === "spending" ? jurisdiction.spending : jurisdiction.revenue
                }
              />
            </div>
          ) : null}
          <DrilldownPie
            key={`${countryId}-${mode}-${current.id}`}
            node={current}
            hoveredId={hoveredId}
            onHover={setHoveredId}
            onSelect={(id) => {
              setHoveredId(null);
              setPath([...path, id]);
            }}
          />
        </section>

        <aside className="flex min-h-0 min-w-0 flex-col">
          <p className="mb-2 shrink-0 truncate text-sm font-semibold text-[#1f3d4d]">
            {current.name}
          </p>
          <ul className="min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1 [scrollbar-gutter:stable] max-lg:max-h-[22rem]">
            {slices.map((slice) => (
                <SliceRow
                  key={slice.id}
                  slice={slice}
                  active={hoveredId === slice.id}
                  drillable={hasChildren(slice)}
                  showGdpShare={mode === "spending" && drilled}
                  outflowTotalMillions={budget.spending.amountMillions}
                  gdpMillions={budget.gdp.amountMillions}
                  jurisdiction={jurisdiction}
                  onHover={setHoveredId}
                  onOpen={() => {
                    setHoveredId(null);
                    setPath([...path, slice.id]);
                  }}
                />
            ))}
          </ul>
          <p className="mt-2 shrink-0 text-[11px] leading-4 text-[#b3a28c]">
            <span className="text-[#2a6f97]">›</span> has more detail ·{" "}
            <span className="text-[#d4c4ae]">·</span> end of detail
          </p>
        </aside>
      </div>

      <BudgetReconciliation
        node={current}
        mode={mode}
        jurisdiction={jurisdiction}
        hoveredId={hoveredId}
        onHover={setHoveredId}
        onSelectOffset={(id) => {
          const child = current.children?.find((c) => c.id === id);
          if (!child || !hasChildren(child)) return;
          setHoveredId(null);
          setPath([...path, id]);
        }}
      />
    </div>
  );
}

