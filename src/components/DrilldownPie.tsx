"use client";

import { useId } from "react";
import {
  buildPieChart,
  formatMillions,
  formatPercent,
  hasChildren,
  pieSlicePath,
  type PieSlice,
  type SpendNode,
} from "@/lib/spend";

type DrilldownPieProps = {
  node: SpendNode;
  hoveredId: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
};

const SIZE = 520;
const CX = SIZE / 2;
const CY = SIZE / 2;
const RADIUS = 214;

export default function DrilldownPie({
  node,
  hoveredId,
  onHover,
  onSelect,
}: DrilldownPieProps) {
  const glowId = useId();
  const hatchId = useId();
  const chart = buildPieChart(node);
  const hovered =
    chart.legend.find((slice) => slice.id === hoveredId) ?? null;
  const hasOverlays = chart.overlays.length > 0;
  const hatchOnly = chart.slices.every((s) => s.isOffset);

  if (chart.legend.length === 0) {
    return (
      <div className="mx-auto flex min-h-[16rem] w-full max-w-[520px] items-center justify-center text-sm text-[#5c6b73]">
        No amounts to chart
      </div>
    );
  }

  return (
    <div className="relative mx-auto w-full max-w-[520px]">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        role="img"
        aria-label={node.name}
        className="h-auto w-full"
      >
        <defs>
          <filter id={glowId} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <pattern
            id={hatchId}
            width="8"
            height="8"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect width="8" height="8" fill="#f3ebe0" fillOpacity="0.55" />
            <line
              x1="0"
              y1="0"
              x2="0"
              y2="8"
              stroke="#8a7358"
              strokeWidth="2.5"
              strokeOpacity="0.9"
            />
          </pattern>
        </defs>

        {/* Solid spending wedges (or hatch-only base when parent is all offsets) */}
        {chart.slices.map((slice) => (
          <PieWedge
            key={slice.id}
            slice={slice}
            mode={slice.isOffset ? "hatch-base" : "solid"}
            hatchId={hatchId}
            glowId={glowId}
            hovered={hoveredId === slice.id}
            onHover={onHover}
            onSelect={onSelect}
          />
        ))}

        {/* Negative offsets slash on top of the spending pie — do not expand it */}
        {chart.overlays.map((slice) => (
          <PieWedge
            key={`overlay-${slice.id}`}
            slice={slice}
            mode="overlay"
            hatchId={hatchId}
            glowId={glowId}
            hovered={hoveredId === slice.id}
            onHover={onHover}
            onSelect={onSelect}
          />
        ))}

        <circle cx={CX} cy={CY} r={86} fill="#fbf8f2" />
        <text
          x={CX}
          y={CY - 8}
          textAnchor="middle"
          className="fill-[#1f3d4d]"
          style={{ fontSize: 13, fontWeight: 650 }}
        >
          {node.name.includes(",") ? node.name.split(",")[0] : node.name}
        </text>
        <text
          x={CX}
          y={CY + 14}
          textAnchor="middle"
          className="fill-[#5c6b73]"
          style={{ fontSize: 12 }}
        >
          {formatMillions(node.amountMillions)}
        </text>
      </svg>
      {hovered ? (
        <div className="pointer-events-none absolute left-1/2 top-2 z-10 -translate-x-1/2 rounded-lg bg-[#1f3d4d] px-3 py-1.5 text-center text-white shadow-lg">
          <p className="text-sm font-semibold">{hovered.name}</p>
          <p className="text-xs text-[#e8dcc8]">
            {formatMillions(hovered.amountMillions)} · {formatPercent(hovered.percent)}
            {hovered.isOffset ? " · offset" : ""}
          </p>
          <p className="mt-0.5 text-[10px] text-[#c4b59a]">
            {hasChildren(hovered) ? "Click to open" : "No further detail"}
          </p>
        </div>
      ) : null}
      {hasOverlays && !hatchOnly ? (
        <p className="mt-2 text-center text-[11px] text-[#8a7358]">
          Hatch overlays mark offsets cutting into the totals above — they reduce the net
          without adding pie slices.
        </p>
      ) : null}
    </div>
  );
}

function PieWedge({
  slice,
  mode,
  hatchId,
  glowId,
  hovered,
  onHover,
  onSelect,
}: {
  slice: PieSlice;
  mode: "solid" | "overlay" | "hatch-base";
  hatchId: string;
  glowId: string;
  hovered: boolean;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
}) {
  const drillable = hasChildren(slice);
  const radius = hovered && drillable ? 222 : RADIUS;
  const path = pieSlicePath(CX, CY, radius, slice.startAngle, slice.endAngle);

  return (
    <g
      className={drillable ? "cursor-pointer" : "cursor-default"}
      onMouseEnter={() => onHover(slice.id)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(slice.id)}
      onBlur={() => onHover(null)}
      onClick={() => {
        if (drillable) onSelect(slice.id);
      }}
      tabIndex={drillable ? 0 : -1}
      role={drillable ? "button" : undefined}
      aria-label={`${slice.name}, ${formatPercent(slice.percent)}, ${formatMillions(slice.amountMillions)}${slice.isOffset ? ", offset" : ""}${drillable ? ", has more detail" : ", no further detail"}`}
      onKeyDown={(event) => {
        if (!drillable) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(slice.id);
        }
      }}
    >
      {mode === "solid" ? (
        <path
          d={path}
          fill={slice.color}
          fillOpacity={drillable ? 1 : 0.78}
          stroke="#f7f3ec"
          strokeWidth={hovered ? (drillable ? 5 : 3) : 2}
          filter={hovered && drillable ? `url(#${glowId})` : undefined}
        />
      ) : null}
      {mode === "hatch-base" ? (
        <>
          <path d={path} fill={`url(#${hatchId})`} stroke="#d9cbb8" strokeWidth={hovered ? 5 : 2} />
          <path
            d={path}
            fill={slice.color}
            fillOpacity={drillable ? 0.28 : 0.2}
            stroke="#8a7358"
            strokeWidth={hovered ? 5 : 2}
            strokeDasharray={hovered ? undefined : "5 4"}
            filter={hovered && drillable ? `url(#${glowId})` : undefined}
          />
        </>
      ) : null}
      {mode === "overlay" ? (
        <>
          {/* Keep colored spending visible underneath; hatch slashes on top */}
          <path
            d={path}
            fill={`url(#${hatchId})`}
            fillOpacity={0.92}
            stroke="#8a7358"
            strokeWidth={hovered ? (drillable ? 4 : 2) : 1.5}
            strokeDasharray={hovered ? undefined : "4 3"}
            filter={hovered && drillable ? `url(#${glowId})` : undefined}
          />
        </>
      ) : null}
    </g>
  );
}
