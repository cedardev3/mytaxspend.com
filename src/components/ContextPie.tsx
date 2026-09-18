"use client";

import { useId } from "react";
import {
  buildPieChart,
  childWedgeInParentSlice,
  formatMillions,
  formatPercent,
  pieSlicePath,
  shareOf,
  type SpendNode,
} from "@/lib/spend";

type ContextPieProps = {
  root: SpendNode;
  section: SpendNode;
  hoveredId: string | null;
  totalLabel: string;
};

const SIZE = 168;
const CX = SIZE / 2;
const CY = SIZE / 2;
const RADIUS = 72;
const GLOW_RADIUS = 76;

export default function ContextPie({ root, section, hoveredId, totalLabel }: ContextPieProps) {
  const glowId = useId();
  const hatchId = useId();
  const federalNet = root.amountMillions;
  const chart = buildPieChart(root);
  const sectionSlice =
    chart.slices.find((slice) => slice.id === section.id) ??
    chart.overlays.find((slice) => slice.id === section.id);
  const hovered = section.children?.find((child) => child.id === hoveredId);
  const glowWedge =
    sectionSlice && hovered && !sectionSlice.isOffset
      ? childWedgeInParentSlice(sectionSlice, section, hovered.id)
      : null;

  const focusAmount =
    hovered != null ? hovered.amountMillions : section.amountMillions;
  const focusName = hovered != null ? hovered.name : section.name;
  const focusPercent = shareOf(focusAmount, federalNet);
  const focusIsOffset = focusAmount < 0;

  return (
    <div className="w-[10.5rem]">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        role="img"
        aria-label={`Share of ${totalLabel}: ${section.name}`}
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
          <pattern
            id={hatchId}
            width="6"
            height="6"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect width="6" height="6" fill="#f3ebe0" fillOpacity="0.55" />
            <line
              x1="0"
              y1="0"
              x2="0"
              y2="6"
              stroke="#8a7358"
              strokeWidth="2"
              strokeOpacity="0.85"
            />
          </pattern>
        </defs>
        {chart.slices.map((slice) => {
          const isSection = slice.id === section.id;
          const path = pieSlicePath(CX, CY, RADIUS, slice.startAngle, slice.endAngle);
          const fillOpacity = isSection ? (glowWedge ? 0.45 : 1) : 0.18;
          if (slice.isOffset) {
            return (
              <g key={slice.id}>
                <path d={path} fill={`url(#${hatchId})`} fillOpacity={fillOpacity} />
                <path
                  d={path}
                  fill={slice.color}
                  fillOpacity={0.22 * fillOpacity}
                  stroke="#d9cbb8"
                  strokeWidth={isSection ? 2 : 1}
                />
              </g>
            );
          }
          return (
            <path
              key={slice.id}
              d={path}
              fill={slice.color}
              fillOpacity={fillOpacity}
              stroke="#f7f3ec"
              strokeWidth={isSection ? 2 : 1}
            />
          );
        })}
        {chart.overlays.map((slice) => {
          const isSection = slice.id === section.id;
          const path = pieSlicePath(CX, CY, RADIUS, slice.startAngle, slice.endAngle);
          return (
            <path
              key={`overlay-${slice.id}`}
              d={path}
              fill={`url(#${hatchId})`}
              fillOpacity={isSection ? 0.95 : 0.35}
              stroke="#8a7358"
              strokeWidth={isSection ? 2 : 1}
              strokeDasharray="3 2"
            />
          );
        })}
        {glowWedge && hovered ? (
          hovered.amountMillions < 0 ? (
            <path
              d={pieSlicePath(
                CX,
                CY,
                GLOW_RADIUS,
                glowWedge.startAngle,
                glowWedge.endAngle,
              )}
              fill={`url(#${hatchId})`}
              stroke="#8a7358"
              strokeWidth={2}
              filter={`url(#${glowId})`}
            />
          ) : (
            <path
              d={pieSlicePath(
                CX,
                CY,
                GLOW_RADIUS,
                glowWedge.startAngle,
                glowWedge.endAngle,
              )}
              fill={hovered.color}
              stroke="#fff8ee"
              strokeWidth={3}
              filter={`url(#${glowId})`}
            />
          )
        ) : null}
        <circle cx={CX} cy={CY} r={28} fill="#fbf8f2" />
        <text
          x={CX}
          y={CY + 4}
          textAnchor="middle"
          className="fill-[#1f3d4d]"
          style={{ fontSize: 11, fontWeight: 700 }}
        >
          {formatPercent(focusPercent)}
        </text>
      </svg>
      <p className="mt-1 text-center text-[11px] leading-4 text-[#5c6b73]">
        {focusName}
        <span className={`block ${focusIsOffset ? "text-[#8a7358]" : "text-[#1f3d4d]"}`}>
          {formatMillions(focusAmount)}
          {focusIsOffset ? " offset" : ""}
        </span>
      </p>
    </div>
  );
}
