"use client";

import { budgetDataset } from "@/data/budget";
import InfoTip from "@/components/InfoTip";
import { formatDollars, formatIsoDate, formatMillions } from "@/lib/spend";

export default function UpdateStamp() {
  const { omb, treasuryMts, generatedAt } = budgetDataset;

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium tracking-wide text-[#8a7358]">
        FY {omb.fiscalYear}
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
            OMB Table 3.2
          </a>{" "}
          FY {omb.fiscalYear} {omb.status}s
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
            Treasury MTS
          </a>
          : {treasuryMts.periodLabel}. Outlays {formatDollars(treasuryMts.netOutlays)}.
        </p>
        <p className="mt-2 text-[11px] text-[#8a7358]">
          Pulled {formatIsoDate(generatedAt)}.
        </p>
      </InfoTip>
    </div>
  );
}
