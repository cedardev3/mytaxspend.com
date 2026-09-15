"use client";

import { useMemo, useState } from "react";
import ContextPie from "@/components/ContextPie";
import DrilldownPie from "@/components/DrilldownPie";
import InfoTip from "@/components/InfoTip";
import SourceLinks from "@/components/SourceLinks";
import UpdateStamp from "@/components/UpdateStamp";
import { federalBudget } from "@/data/budget";
import {
  formatMillions,
  formatPercent,
  hasChildren,
  nodeAtPath,
  offsetChildren,
  pieSlices,
  positiveChildren,
  type SpendNode,
} from "@/lib/spend";

function SliceRow({
  slice,
  percent,
  active,
  drillable,
  onHover,
  onOpen,
}: {
  slice: SpendNode;
  percent?: number;
  active: boolean;
  drillable: boolean;
  onHover: (id: string | null) => void;
  onOpen: () => void;
}) {
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
        >
          <span
            className="h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ backgroundColor: slice.color }}
          />
          <span className="min-w-0 flex-1 truncate text-sm text-[#1f3d4d]">
            {slice.name}
          </span>
          <span className="shrink-0 text-xs tabular-nums text-[#5c6b73]">
            {formatMillions(slice.amountMillions)}
            {percent != null ? ` · ${formatPercent(percent)}` : ""}
          </span>
        </button>
      ) : (
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <span
            className="h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ backgroundColor: slice.color }}
          />
          <span className="min-w-0 flex-1 truncate text-sm text-[#1f3d4d]">
            {slice.name}
          </span>
          <span className="shrink-0 text-xs tabular-nums text-[#5c6b73]">
            {formatMillions(slice.amountMillions)}
            {percent != null ? ` · ${formatPercent(percent)}` : ""}
          </span>
        </div>
      )}
      <InfoTip label={`Sources for ${slice.name}`} align="right">
        {slice.code ? (
          <p className="mb-1 text-[11px] text-[#8a7358]">{slice.code}</p>
        ) : null}
        <p className="mb-2 text-xs leading-5 text-[#5c6b73]">{slice.description}</p>
        <SourceLinks sources={slice.sources} />
      </InfoTip>
    </li>
  );
}

export default function SpendExplorer() {
  const [path, setPath] = useState<string[]>([]);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const current = useMemo(() => nodeAtPath(federalBudget, path), [path]);

  if (!current.children) {
    throw new Error(`Explorer landed on "${current.id}" with no children to chart`);
  }

  const positives = positiveChildren(current);
  const offsets = offsetChildren(current);
  const slices = positives.length > 0 ? pieSlices(positives) : [];
  const crumbs = [
    { id: federalBudget.id, name: "All", depth: 0 },
    ...path.map((id, index) => {
      const node = nodeAtPath(federalBudget, path.slice(0, index + 1));
      return { id, name: node.name, depth: index + 1 };
    }),
  ];
  const drilled = path.length > 0;

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
      <header className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-[#1f3d4d] sm:text-3xl">
          My Tax Spend
        </h1>
        <div className="flex items-center gap-2">
          <InfoTip label={`About ${current.name}`}>
            {current.code ? (
              <p className="mb-1 text-[11px] text-[#8a7358]">{current.code}</p>
            ) : null}
            <p className="mb-2 text-xs leading-5 text-[#5c6b73]">{current.description}</p>
            <SourceLinks sources={current.sources} />
          </InfoTip>
          <UpdateStamp />
        </div>
      </header>

      <nav aria-label="Spending path" className="flex flex-wrap items-center gap-2 text-sm">
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

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_16.5rem]">
        <section
          className={`relative rounded-3xl border border-[#eadfce] bg-white p-3 sm:p-6 ${drilled ? "sm:pr-[12rem]" : ""}`}
        >
          {drilled ? (
            <div className="mb-3 flex justify-end sm:absolute sm:right-4 sm:top-4 sm:z-20 sm:mb-0">
              <ContextPie section={current} hoveredId={hoveredId} />
            </div>
          ) : null}
          <DrilldownPie
            key={current.id}
            node={current}
            hoveredId={hoveredId}
            onHover={setHoveredId}
            onSelect={(id) => {
              setHoveredId(null);
              setPath([...path, id]);
            }}
          />
        </section>

        <aside className="min-w-0">
          <p className="mb-2 truncate text-sm font-semibold text-[#1f3d4d]">
            {current.name}
          </p>
          {slices.length > 0 ? (
            <ul className="flex flex-col">
              {slices.map((slice) => (
                <SliceRow
                  key={slice.id}
                  slice={slice}
                  percent={slice.percent}
                  active={hoveredId === slice.id}
                  drillable={hasChildren(slice)}
                  onHover={setHoveredId}
                  onOpen={() => {
                    setHoveredId(null);
                    setPath([...path, slice.id]);
                  }}
                />
              ))}
            </ul>
          ) : null}
          {offsets.length > 0 ? (
            <details className="mt-2">
              <summary className="cursor-pointer text-xs text-[#8a7358]">Offsets</summary>
              <ul className="mt-1 flex flex-col">
                {offsets.map((slice) => (
                  <SliceRow
                    key={slice.id}
                    slice={slice}
                    active={hoveredId === slice.id}
                    drillable={hasChildren(slice)}
                    onHover={setHoveredId}
                    onOpen={() => {
                      setHoveredId(null);
                      setPath([...path, slice.id]);
                    }}
                  />
                ))}
              </ul>
            </details>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
