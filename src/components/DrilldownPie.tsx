"use client";

import { useId } from "react";
import {
  formatMillions,
  formatPercent,
  hasChildren,
  pieSlicePath,
  pieSlices,
  positiveChildren,
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
  const chartNodes = positiveChildren(node);

  if (chartNodes.length === 0) {
    return (
      <div className="mx-auto flex min-h-[16rem] w-full max-w-[520px] items-center justify-center text-sm text-[#5c6b73]">
        Offset
      </div>
    );
  }

  const slices = pieSlices(chartNodes);
  const hovered = slices.find((slice) => slice.id === hoveredId);

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
        </defs>
        {slices.map((slice) => {
          const drillable = hasChildren(slice);
          const isHovered = hoveredId === slice.id;
          return (
            <path
              key={slice.id}
              d={pieSlicePath(CX, CY, isHovered ? 222 : RADIUS, slice.startAngle, slice.endAngle)}
              fill={slice.color}
              stroke="#f7f3ec"
              strokeWidth={isHovered ? 5 : 2}
              filter={isHovered ? `url(#${glowId})` : undefined}
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
              aria-label={`${slice.name}, ${formatPercent(slice.percent)}, ${formatMillions(slice.amountMillions)}`}
              onKeyDown={(event) => {
                if (!drillable) return;
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(slice.id);
                }
              }}
            />
          );
        })}
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
          </p>
        </div>
      ) : null}
    </div>
  );
}
