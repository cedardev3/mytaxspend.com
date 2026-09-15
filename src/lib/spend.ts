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

export type BudgetDataset = {
  generatedAt: string;
  omb: {
    table: string;
    title: string;
    fiscalYear: number;
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
  };
  treasuryMts: {
    recordDate: string;
    fiscalYear: number;
    periodLabel: string;
    receipts: number;
    netOutlays: number;
    functions: Array<{
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

export type PieSlice = SpendNode & {
  startAngle: number;
  endAngle: number;
  percent: number;
};

export function hasChildren(node: SpendNode): boolean {
  return Boolean(node.children && node.children.length > 0);
}

export function positiveChildren(node: SpendNode): SpendNode[] {
  return (node.children ?? []).filter((child) => child.amountMillions > 0);
}

export function offsetChildren(node: SpendNode): SpendNode[] {
  return (node.children ?? []).filter((child) => child.amountMillions <= 0);
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

export function pieSlices(nodes: SpendNode[]): PieSlice[] {
  const total = nodes.reduce((sum, node) => sum + node.amountMillions, 0);
  if (total <= 0) {
    throw new Error("Cannot build pie slices from a zero or negative total");
  }

  let startAngle = -Math.PI / 2;
  return nodes.map((node) => {
    const sweep = (node.amountMillions / total) * Math.PI * 2;
    const slice: PieSlice = {
      ...node,
      startAngle,
      endAngle: startAngle + sweep,
      percent: node.amountMillions / total,
    };
    startAngle += sweep;
    return slice;
  });
}

export function childWedgeInParentSlice(
  parentSlice: PieSlice,
  parent: SpendNode,
  childId: string,
): { startAngle: number; endAngle: number } | null {
  const siblings = positiveChildren(parent);
  const parentPositive = siblings.reduce((sum, child) => sum + child.amountMillions, 0);
  if (parentPositive <= 0) return null;

  const parentSweep = parentSlice.endAngle - parentSlice.startAngle;
  let cursor = parentSlice.startAngle;
  for (const sibling of siblings) {
    const sweep = (sibling.amountMillions / parentPositive) * parentSweep;
    if (sibling.id === childId) {
      return { startAngle: cursor, endAngle: cursor + sweep };
    }
    cursor += sweep;
  }
  return null;
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
