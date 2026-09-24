"use client";

import { useId } from "react";
import {
  abbreviateDisplayName,
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
/** Mid-ring for on-slice labels (outside the center hole, inside the rim). */
const LABEL_RADIUS = 152;
/** Minimum wedge sweep (radians) before attempting an on-slice label. */
const MIN_LABEL_SWEEP = 0.38;

/** Exact-name shorthand for on-pie labels (full names stay in list / hover). */
const PIE_SHORT_LABELS: Record<string, string> = {
  // US spending (OMB functions)
  "National Defense": "Defense",
  "Net Interest": "Interest",
  "International Affairs": "International",
  "General Science, Space, and Technology": "Science & Space",
  "Natural Resources and Environment": "Nat. Resources",
  "Commerce and Housing Credit": "Commerce",
  "Community and Regional Development": "Community",
  "Education, Training, Employment, and Social Services": "Education",
  "Income Security": "Income Sec.",
  "Social Security": "Soc. Security",
  "Veterans Benefits and Services": "Veterans",
  "Administration of Justice": "Justice",
  "General Government": "Gov't",
  "Undistributed Offsetting Receipts": "Offsets",
  // US revenue
  "Individual Income Taxes": "Individual",
  "Corporation Income Taxes": "Corporate",
  "Social Insurance and Retirement Receipts": "Soc. Insurance",
  "Excise Taxes": "Excise",
  "Other Receipts": "Other",
  // US common subfunctions / accounts
  "Military Personnel": "Personnel",
  "Operation and Maintenance": "O&M",
  "Research, Development, Test, and Evaluation": "RDT&E",
  "Military Construction": "Construction",
  "Family Housing": "Housing",
  "Atomic energy defense activities": "Atomic energy",
  "Interest on Treasury debt securities (gross)": "Treasury debt",
  "Interest received by on-budget trust funds": "On-budget TF",
  "Interest received by off-budget trust funds": "Off-budget TF",
  "Other interest": "Other interest",
  "Other investment income": "Other income",
  "Health care services": "Health care",
  "Health research and training": "Research",
  "Consumer and occupational health and safety": "Safety",
  "Federal employee retirement and disability": "Fed. retirement",
  "General retirement and disability insurance (excluding social security)": "Retirement",
  "Unemployment compensation": "Unemployment",
  "Housing assistance": "Housing",
  "Food and nutrition assistance": "Food aid",
  "Other income security": "Other",
  // Canada spending (FRT)
  "Major transfers to persons": "Persons",
  "Major transfers to provinces, territories and municipalities": "Provinces",
  "Other transfer payments": "Other transfers",
  "Direct program expenses": "Direct program",
  "Pollution pricing proceeds returned to Canadians": "Pollution return",
  "Public debt charges": "Debt charges",
  "Other direct program expenses": "Other direct",
  "Old Age Security benefits": "OAS",
  "Children's benefits": "Children",
  "Employment Insurance": "EI",
  "Relief for heating expenses": "Heating",
  "Canada Health Transfer": "Health transfer",
  "Fiscal arrangements": "Fiscal arr.",
  "Canada-wide early learning and child care": "Child care",
  "Quebec Abatement": "QC Abatement",
  "Provision for valuation and other items": "Valuation",
  "Consolidation and other adjustments": "Consolidation",
  // Canada revenue
  "Tax revenues": "Tax",
  "Employment insurance premiums": "EI premiums",
  "Pollution pricing proceeds": "Pollution",
  "Other revenues": "Other",
  "Income tax revenues": "Income tax",
  "Other taxes and duties": "Other taxes",
  "Goods and services tax": "GST",
  "Energy taxes": "Energy",
  "Customs import duties": "Customs",
  "Other excise taxes and duties": "Excise",
  "Personal": "Personal",
  "Corporate": "Corporate",
  "Non-resident": "Non-resident",
};

function shortPieLabel(name: string): string {
  const mapped = PIE_SHORT_LABELS[name];
  if (mapped) return abbreviateDisplayName(mapped);

  let short = name;
  short = short.replace(/^National\s+/i, "");
  short = short.replace(/^Net\s+/i, "");
  short = short.replace(/\s+Benefits and Services$/i, "");
  short = short.replace(/\s+and Services$/i, "");
  short = short.replace(/\s+expenses$/i, "");
  short = short.replace(/\s+revenues$/i, "");
  short = short.replace(/\s+Receipts$/i, "");
  short = short.replace(/\s+Taxes$/i, "");
  if (short !== name && short.length >= 3) return abbreviateDisplayName(short);
  return abbreviateDisplayName(name);
}

function polarPoint(radius: number, angle: number) {
  return {
    x: CX + radius * Math.cos(angle),
    y: CY + radius * Math.sin(angle),
  };
}

/** Truncate a sector name so it roughly fits the available SVG width. */
function truncateLabel(name: string, maxWidth: number, fontSize: number): string {
  const avgChar = fontSize * 0.56;
  const maxChars = Math.floor(maxWidth / avgChar);
  if (maxChars < 4) return "";
  if (name.length <= maxChars) return name;
  return `${name.slice(0, Math.max(3, maxChars - 1)).trimEnd()}…`;
}

function sliceLabel(slice: PieSlice): {
  x: number;
  y: number;
  text: string;
  fontSize: number;
} | null {
  const sweep = slice.endAngle - slice.startAngle;
  if (sweep < MIN_LABEL_SWEEP) return null;

  const mid = (slice.startAngle + slice.endAngle) / 2;
  const { x, y } = polarPoint(LABEL_RADIUS, mid);
  const fontSize = sweep > 0.75 ? 12 : sweep > 0.5 ? 11 : 10;
  // Arc length at the label ring, with margin so text stays inside the wedge.
  const maxWidth = Math.min(sweep * LABEL_RADIUS * 0.78, 128);
  const text = truncateLabel(shortPieLabel(slice.name), maxWidth, fontSize);
  if (!text) return null;
  return { x, y, text, fontSize };
}

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
  const labels = chart.slices
    .map((slice) => {
      const label = sliceLabel(slice);
      return label ? { id: slice.id, ...label } : null;
    })
    .filter((label): label is NonNullable<typeof label> => label != null);

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
          {shortPieLabel(
            node.name.includes(",") ? node.name.split(",")[0]! : node.name,
          )}
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

        {/* On-slice names for wedges large enough — readable without hover on mobile */}
        <g aria-hidden="true" style={{ pointerEvents: "none" }}>
          {labels.map((label) => (
            <text
              key={`label-${label.id}`}
              x={label.x}
              y={label.y}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="#fbf8f2"
              stroke="#1f3d4d"
              strokeWidth={3.5}
              strokeLinejoin="round"
              paintOrder="stroke fill"
              style={{ fontSize: label.fontSize, fontWeight: 650 }}
            >
              {label.text}
            </text>
          ))}
        </g>
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
