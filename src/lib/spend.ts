export type SourceLink = {
  label: string;
  url: string;
};

export type SpendNode = {
  id: string;
  name: string;
  code?: string;
  amountMillions: number;
  color: string;
  description: string;
  sources: SourceLink[];
  children?: SpendNode[];
};

export type GdpSeries = {
  fiscalYear: number;
  status: string;
  table: string;
  title: string;
  units: string;
  amountBillions: number;
  amountMillions: number;
  spreadsheetUrl: string;
  historicalTablesUrl: string;
  detailsUrl: string;
};

export type BudgetDataset = {
  generatedAt: string;
  omb: {
    table: string;
    title: string;
    fiscalYear: number;
    /** Optional display label (e.g. Canadian "2024-25"). */
    fiscalYearLabel?: string;
    status: string;
    units: string;
    publication: string;
    dateIssued: string | null;
    zipUrl: string;
    spreadsheetUrl: string;
    detailsUrl: string;
    historicalTablesUrl: string;
    amountMillions: number;
    onBudgetMillions: number;
    offBudgetMillions: number;
    tables?: Record<string, string>;
  };
  /** Present on the outlays dataset (OMB Table 10.1). */
  gdp?: GdpSeries;
  /** Optional interest-vs-defense snapshot for comparison strip. */
  highlights?: {
    interest: {
      name: string;
      amountMillions: number;
      nodeId?: string;
      note?: string;
    };
    defense: {
      name: string;
      amountMillions: number;
      nodeId?: string;
      note?: string;
    };
  };
  treasuryMts: {
    recordDate: string;
    fiscalYear: number;
    periodLabel: string;
    receipts: number;
    netOutlays: number;
    /** Outlay functions (spending dataset). */
    functions?: Array<{
      name: string;
      amount: number;
      apiUrl: string;
    }>;
    /** Receipt sources (revenue dataset). */
    sources?: Array<{
      name: string;
      amount: number;
      apiUrl: string;
    }>;
    queryUrl: string;
    datasetUrl: string;
    latestRecordQueryUrl: string;
  };
  root: SpendNode;
};

export type BudgetMode = "spending" | "revenue";

export type PieSlice = SpendNode & {
  startAngle: number;
  endAngle: number;
  /** Share used for labels: of parent net when parent > 0, else of gross |children|. */
  percent: number;
  isOffset: boolean;
};

export type PieChartModel = {
  /** Solid wedges — positive outlays only (or hatch-only when the parent has no positives). */
  slices: PieSlice[];
  /** Negative outlays drawn on top of the positive pie (do not expand geometry). */
  overlays: PieSlice[];
  /** Sidebar / legend order matches the source tree. */
  legend: PieSlice[];
};

export function hasChildren(node: SpendNode): boolean {
  return Boolean(node.children && node.children.length > 0);
}

export function positiveChildren(node: SpendNode): SpendNode[] {
  return (node.children ?? []).filter((child) => child.amountMillions > 0);
}

export function offsetChildren(node: SpendNode): SpendNode[] {
  return (node.children ?? []).filter((child) => child.amountMillions < 0);
}

/** Children that contribute a wedge or overlay (non-zero outlays). Preserves source order. */
export function chartChildren(node: SpendNode): SpendNode[] {
  return (node.children ?? []).filter((child) => child.amountMillions !== 0);
}

export function totalPositive(node: SpendNode): number {
  return positiveChildren(node).reduce((sum, child) => sum + child.amountMillions, 0);
}

export function shareOf(amountMillions: number, totalMillions: number): number {
  if (totalMillions <= 0) {
    throw new Error("Cannot compute a share against a non-positive total");
  }
  return amountMillions / totalMillions;
}

/** Share of a parent net total. Null when the parent is zero or a net offset. */
export function shareOfParent(
  amountMillions: number,
  parentAmountMillions: number,
): number | null {
  if (parentAmountMillions <= 0) return null;
  return amountMillions / parentAmountMillions;
}

export function totalOffsets(node: SpendNode): number {
  return offsetChildren(node).reduce((sum, child) => sum + child.amountMillions, 0);
}

export type OffsetLineSummary = {
  id: string;
  name: string;
  /** Negative outlay amount (millions). */
  amountMillions: number;
  /** Positive outlay remaining on this line after the offset — 0 when the line is fully negative. */
  remainingMillions: number;
  percentOfGross: number | null;
  percentOfNet: number | null;
};

export type BudgetSummary = {
  name: string;
  /** Sum of positive child outlays (gross spending in this category). */
  grossMillions: number;
  /** Sum of negative child outlays (≤ 0). */
  offsetMillions: number;
  /** Parent net total (gross + offsets). */
  netMillions: number;
  /** net - gross; negative means reduced, positive means expanded. */
  deltaMillions: number;
  /** 'reduced' | 'expanded' | 'unchanged' */
  effect: "reduced" | "expanded" | "unchanged";
  offsets: OffsetLineSummary[];
};

export function summarizeBudget(node: SpendNode): BudgetSummary {
  const grossMillions = totalPositive(node);
  const offsetMillions = totalOffsets(node);
  const netMillions = node.amountMillions;
  const deltaMillions = netMillions - grossMillions;
  const effect: BudgetSummary["effect"] =
    deltaMillions < -0.05 ? "reduced" : deltaMillions > 0.05 ? "expanded" : "unchanged";

  const offsets: OffsetLineSummary[] = offsetChildren(node).map((child) => ({
    id: child.id,
    name: child.name,
    amountMillions: child.amountMillions,
    // OMB lines are signed net figures: a negative subfunction has no positive remainder.
    remainingMillions: Math.max(0, child.amountMillions),
    percentOfGross: grossMillions > 0 ? child.amountMillions / grossMillions : null,
    percentOfNet: shareOfParent(child.amountMillions, netMillions),
  }));

  return {
    name: node.name,
    grossMillions,
    offsetMillions,
    netMillions,
    deltaMillions,
    effect,
    offsets,
  };
}

export function grossAbsTotal(nodes: SpendNode[]): number {
  return nodes.reduce((sum, node) => sum + Math.abs(node.amountMillions), 0);
}

/**
 * Label percent for a child under `parent`.
 * Prefer share of parent net; if parent is a net offset, use signed share of gross |children|.
 */
export function displayPercent(child: SpendNode, parent: SpendNode): number {
  const ofNet = shareOfParent(child.amountMillions, parent.amountMillions);
  if (ofNet != null) return ofNet;
  const gross = grossAbsTotal(chartChildren(parent));
  if (gross <= 0) {
    throw new Error(`Cannot compute display percent under "${parent.id}"`);
  }
  return child.amountMillions / gross;
}

export function assertTreeTotals(node: SpendNode): void {
  if (!node.children || node.children.length === 0) return;
  const childTotal = node.children.reduce(
    (sum, child) => sum + child.amountMillions,
    0,
  );
  if (Math.round(childTotal * 10) !== Math.round(node.amountMillions * 10)) {
    throw new Error(
      `"${node.id}" amount ${node.amountMillions} does not equal child total ${childTotal}`,
    );
  }
  for (const child of node.children) {
    assertTreeTotals(child);
  }
}

export function nodeAtPath(root: SpendNode, path: string[]): SpendNode {
  let node = root;
  for (const id of path) {
    if (!node.children) {
      throw new Error(`Path id "${id}" requested but "${node.id}" has no children`);
    }
    const next = node.children.find((child) => child.id === id);
    if (!next) {
      throw new Error(`No child "${id}" under "${node.id}"`);
    }
    node = next;
  }
  return node;
}

/**
 * Build the pie model for a parent node.
 *
 * - Positive outlays become solid wedges that fill the circle (relative to each other).
 * - Negative outlays become hatched overlays on top of those wedges — they slash the
 *   spending visually without expanding the pie.
 * - Parents with only offsets render hatch-only wedges (no solid base).
 */
export function buildPieChart(parent: SpendNode): PieChartModel {
  const positives = positiveChildren(parent);
  const offsets = offsetChildren(parent);
  const positiveTotal = positives.reduce((sum, n) => sum + n.amountMillions, 0);

  let slices: PieSlice[] = [];
  let overlays: PieSlice[] = [];

  if (positives.length > 0 && positiveTotal > 0) {
    let cursor = -Math.PI / 2;
    slices = positives.map((node) => {
      const sweep = (node.amountMillions / positiveTotal) * Math.PI * 2;
      const slice: PieSlice = {
        ...node,
        startAngle: cursor,
        endAngle: cursor + sweep,
        percent: displayPercent(node, parent),
        isOffset: false,
      };
      cursor += sweep;
      return slice;
    });

    // Overlays sit on top of the positive pie. Arc length = |offset| / positiveTotal,
    // capped so stacked overlays never exceed a full turn.
    let overlayCursor = -Math.PI / 2;
    let remaining = Math.PI * 2;
    for (const node of offsets) {
      if (remaining <= 1e-9) break;
      const raw = (Math.abs(node.amountMillions) / positiveTotal) * Math.PI * 2;
      const sweep = Math.min(raw, remaining);
      overlays.push({
        ...node,
        startAngle: overlayCursor,
        endAngle: overlayCursor + sweep,
        percent: displayPercent(node, parent),
        isOffset: true,
      });
      overlayCursor += sweep;
      remaining -= sweep;
    }
  } else if (offsets.length > 0) {
    const absTotal = grossAbsTotal(offsets);
    let cursor = -Math.PI / 2;
    slices = offsets.map((node) => {
      const sweep = (Math.abs(node.amountMillions) / absTotal) * Math.PI * 2;
      const slice: PieSlice = {
        ...node,
        startAngle: cursor,
        endAngle: cursor + sweep,
        percent: displayPercent(node, parent),
        isOffset: true,
      };
      cursor += sweep;
      return slice;
    });
  }

  const byId = new Map<string, PieSlice>();
  for (const slice of [...slices, ...overlays]) {
    byId.set(slice.id, slice);
  }
  const legend = chartChildren(parent)
    .map((child) => byId.get(child.id))
    .filter((slice): slice is PieSlice => slice != null);

  return { slices, overlays, legend };
}

export function pieSlices(parent: SpendNode): PieSlice[] {
  return buildPieChart(parent).legend;
}

export function childWedgeInParentSlice(
  parentSlice: PieSlice,
  parent: SpendNode,
  childId: string,
): { startAngle: number; endAngle: number } | null {
  const chart = buildPieChart(parent);
  const child =
    chart.slices.find((s) => s.id === childId) ??
    chart.overlays.find((s) => s.id === childId);
  if (!child) return null;

  const parentSweep = parentSlice.endAngle - parentSlice.startAngle;
  const full = Math.PI * 2;
  const childStart = child.startAngle + Math.PI / 2;
  const childEnd = child.endAngle + Math.PI / 2;
  const startFrac = ((((childStart % full) + full) % full) / full);
  const endFrac = ((((childEnd % full) + full) % full) / full);
  const startAngle = parentSlice.startAngle + startFrac * parentSweep;
  let endAngle = parentSlice.startAngle + endFrac * parentSweep;
  if (endAngle <= startAngle) {
    endAngle = startAngle + ((child.endAngle - child.startAngle) / full) * parentSweep;
  }
  return { startAngle, endAngle };
}

export function formatMillions(amountMillions: number): string {
  const sign = amountMillions < 0 ? "-" : "";
  const abs = Math.abs(amountMillions);
  if (abs >= 1_000_000) {
    return `${sign}$${trimZeros((abs / 1_000_000).toFixed(3))} trillion`;
  }
  if (abs >= 1_000) {
    const decimals = abs >= 100_000 ? 1 : 2;
    return `${sign}$${trimZeros((abs / 1_000).toFixed(decimals))} billion`;
  }
  return `${sign}$${abs.toLocaleString("en-US")} million`;
}

export function formatDollars(amount: number): string {
  return formatMillions(amount / 1_000_000);
}

export function formatPercent(percent: number): string {
  return `${(percent * 100).toFixed(1)}%`;
}

export function formatIsoDate(isoDate: string): string {
  const datePart = isoDate.slice(0, 10);
  const [year, month, day] = datePart.split("-").map(Number);
  if (!year || !month || !day) {
    throw new Error(`Invalid ISO date: ${isoDate}`);
  }
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function trimZeros(value: string): string {
  return value.replace(/\.?0+$/, "");
}

function polar(cx: number, cy: number, radius: number, angle: number) {
  return {
    x: cx + radius * Math.cos(angle),
    y: cy + radius * Math.sin(angle),
  };
}

export function pieSlicePath(
  cx: number,
  cy: number,
  radius: number,
  startAngle: number,
  endAngle: number,
): string {
  const sweep = endAngle - startAngle;
  if (sweep >= Math.PI * 2 - 1e-6) {
    return [
      `M ${cx} ${cy - radius}`,
      `A ${radius} ${radius} 0 1 1 ${cx} ${cy + radius}`,
      `A ${radius} ${radius} 0 1 1 ${cx} ${cy - radius}`,
      "Z",
    ].join(" ");
  }

  const start = polar(cx, cy, radius, startAngle);
  const end = polar(cx, cy, radius, endAngle);
  const largeArc = sweep > Math.PI ? 1 : 0;
  return [
    `M ${cx} ${cy}`,
    `L ${start.x} ${start.y}`,
    `A ${radius} ${radius} 0 ${largeArc} 1 ${end.x} ${end.y}`,
    "Z",
  ].join(" ");
}
