"use client";

import InfoTip from "@/components/InfoTip";
import {
  formatDollars,
  formatIsoDate,
  formatMillions,
  type BudgetDataset,
  type BudgetMode,
} from "@/lib/spend";

type UpdateStampProps = {
  dataset: BudgetDataset;
  mode: BudgetMode;
};

export default function UpdateStamp({ dataset, mode }: UpdateStampProps) {
  const { omb, treasuryMts, generatedAt } = dataset;
  const fyLabel = omb.fiscalYearLabel ?? String(omb.fiscalYear);
  const pieLabel = omb.title || `Table ${omb.table}`;
  const isUsOmnibased = omb.publication.toLowerCase().includes("united states");
  const treasuryFigure =
    mode === "spending"
      ? `Outlays ${formatDollars(treasuryMts.netOutlays)}`
      : `Receipts ${formatDollars(treasuryMts.receipts)}`;
  const contextLabel = isUsOmnibased ? "Treasury MTS" : "Context series";

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium tracking-wide text-[#8a7358]">
        FY {fyLabel}
      </span>
      <InfoTip label="Data sources and last updated" align="right">
        <p className="text-[10px] font-semibold tracking-[0.14em] text-[#8a7358] uppercase">
          Last updated
        </p>
        <p className="mt-2 text-xs leading-5 text-[#1f3d4d]">
          Pie:{" "}
          <a
            href={omb.historicalTablesUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#2a6f97] underline-offset-2 hover:underline"
          >
            {pieLabel}
          </a>{" "}
          FY {fyLabel} {omb.status}
          {omb.dateIssued ? `, ${formatIsoDate(omb.dateIssued)}` : ""}.{" "}
          {formatMillions(omb.amountMillions)}.
        </p>
        <p className="mt-2 text-xs leading-5 text-[#5c6b73]">
          <a
            href={treasuryMts.datasetUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#2a6f97] underline-offset-2 hover:underline"
          >
            {contextLabel}
          </a>
          : {treasuryMts.periodLabel}
          {isUsOmnibased
            ? " (FYTD context only — not used in the pie or federal revenue/spending comparison). "
            : " (annual context). "}
          {treasuryFigure}.
        </p>
        <p className="mt-2 text-[11px] text-[#8a7358]">
          Pulled {formatIsoDate(generatedAt)}.
        </p>
      </InfoTip>
    </div>
  );
}
