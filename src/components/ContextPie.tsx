"use client";

import { useId } from "react";
import { federalBudget } from "@/data/budget";
import {
  childWedgeInParentSlice,
  formatMillions,
  formatPercent,
  pieSlicePath,
  pieSlices,
  positiveChildren,
  shareOf,
  totalPositive,
  type SpendNode,
} from "@/lib/spend";

type ContextPieProps = {
  section: SpendNode;
  hoveredId: string | null;
};

const SIZE = 168;
const CX = SIZE / 2;
const CY = SIZE / 2;
const RADIUS = 72;
const GLOW_RADIUS = 76;

export default function ContextPie({ section, hoveredId }: ContextPieProps) {
  const glowId = useId();
  const rootSlices = pieSlices(positiveChildren(federalBudget));
  const total = totalPositive(federalBudget);
  const sectionSlice = rootSlices.find((slice) => slice.id === section.id);
  const hovered = section.children?.find((child) => child.id === hoveredId);
  const glowWedge =
    sectionSlice && hovered && hovered.amountMillions > 0
      ? childWedgeInParentSlice(sectionSlice, section, hovered.id)
      : null;

  return (
    <div className="w-[10.5rem]">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        role="img"
        aria-label={`Share of total outlays: ${section.name}`}
        className="h-auto w-full"
      >
        <defs>
          <filter id={glowId} x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="3.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        {rootSlices.map((slice) => {
          const isSection = slice.id === section.id;
          return (
            <path
              key={slice.id}
              d={pieSlicePath(CX, CY, RADIUS, slice.startAngle, slice.endAngle)}
              fill={slice.color}
              fillOpacity={isSection ? (glowWedge ? 0.45 : 1) : 0.18}
              stroke="#f7f3ec"
              strokeWidth={isSection ? 2 : 1}
            />
          );
        })}
        {glowWedge ? (
          <path
            d={pieSlicePath(
              CX,
              CY,
              GLOW_RADIUS,
              glowWedge.startAngle,
              glowWedge.endAngle,
            )}
            fill={hovered?.color}
            stroke="#fff8ee"
            strokeWidth={3}
            filter={`url(#${glowId})`}
          />
        ) : null}
        <circle cx={CX} cy={CY} r={28} fill="#fbf8f2" />
        <text
          x={CX}
          y={CY + 4}
          textAnchor="middle"
          className="fill-[#1f3d4d]"
          style={{ fontSize: 11, fontWeight: 700 }}
        >
          {formatPercent(
            shareOf(
              hovered && hovered.amountMillions > 0
                ? hovered.amountMillions
                : section.amountMillions,
              total,
            ),
          )}
        </text>
      </svg>
      <p className="mt-1 text-center text-[11px] leading-4 text-[#5c6b73]">
        {hovered && hovered.amountMillions > 0 ? hovered.name : section.name}
        <span className="block text-[#1f3d4d]">
          {formatMillions(
            hovered && hovered.amountMillions > 0
              ? hovered.amountMillions
              : section.amountMillions,
          )}
        </span>
      </p>
    </div>
  );
}
