import usOutlays from "@/data/federal-outlays.json";
import usReceipts from "@/data/federal-receipts.json";
import caOutlays from "@/data/canada-federal-outlays.json";
import caReceipts from "@/data/canada-federal-receipts.json";
import type { CountryId } from "@/lib/jurisdiction";
import { assertTreeTotals, type BudgetDataset, type GdpSeries } from "@/lib/spend";

export const outlaysDataset = usOutlays as BudgetDataset;
export const receiptsDataset = usReceipts as BudgetDataset;
export const canadaOutlaysDataset = caOutlays as BudgetDataset;
export const canadaReceiptsDataset = caReceipts as BudgetDataset;

function validatePair(outlays: BudgetDataset, receipts: BudgetDataset, label: string) {
  assertTreeTotals(outlays.root);
  assertTreeTotals(receipts.root);

  if (outlays.omb.fiscalYear !== receipts.omb.fiscalYear) {
    throw new Error(
      `${label}: fiscal years do not match: outlays FY ${outlays.omb.fiscalYear} vs receipts FY ${receipts.omb.fiscalYear}`,
    );
  }
  if (outlays.omb.status !== receipts.omb.status) {
    throw new Error(
      `${label}: status does not match: outlays "${outlays.omb.status}" vs receipts "${receipts.omb.status}"`,
    );
  }
  if (!outlays.gdp) {
    throw new Error(`${label}: outlays dataset is missing GDP`);
  }
  if (outlays.gdp.fiscalYear !== outlays.omb.fiscalYear) {
    throw new Error(
      `${label}: GDP fiscal year ${outlays.gdp.fiscalYear} does not match outlays FY ${outlays.omb.fiscalYear}`,
    );
  }
}

validatePair(outlaysDataset, receiptsDataset, "US");
validatePair(canadaOutlaysDataset, canadaReceiptsDataset, "Canada");

export type CountryBudget = {
  outlays: BudgetDataset;
  receipts: BudgetDataset;
  gdp: GdpSeries;
  spending: BudgetDataset["root"];
  revenue: BudgetDataset["root"];
  comparisonFiscalYear: number;
  comparisonFiscalYearLabel: string;
  comparisonStatus: string;
};

export function budgetFor(countryId: CountryId): CountryBudget {
  if (countryId === "ca") {
    const gdp = canadaOutlaysDataset.gdp;
    if (!gdp) throw new Error("Canada outlays dataset is missing GDP");
    return {
      outlays: canadaOutlaysDataset,
      receipts: canadaReceiptsDataset,
      gdp,
      spending: canadaOutlaysDataset.root,
      revenue: canadaReceiptsDataset.root,
      comparisonFiscalYear: canadaOutlaysDataset.omb.fiscalYear,
      comparisonFiscalYearLabel:
        (canadaOutlaysDataset.omb as { fiscalYearLabel?: string }).fiscalYearLabel ??
        String(canadaOutlaysDataset.omb.fiscalYear),
      comparisonStatus: canadaOutlaysDataset.omb.status,
    };
  }

  const gdp = outlaysDataset.gdp;
  if (!gdp) throw new Error("US outlays dataset is missing GDP");
  return {
    outlays: outlaysDataset,
    receipts: receiptsDataset,
    gdp,
    spending: outlaysDataset.root,
    revenue: receiptsDataset.root,
    comparisonFiscalYear: outlaysDataset.omb.fiscalYear,
    comparisonFiscalYearLabel: String(outlaysDataset.omb.fiscalYear),
    comparisonStatus: outlaysDataset.omb.status,
  };
}

/** Shared OMB comparison year used by Revenue vs Spending (US default). */
export const ombComparisonFiscalYear = outlaysDataset.omb.fiscalYear;
export const ombComparisonStatus = outlaysDataset.omb.status;

export const federalGdp: GdpSeries = outlaysDataset.gdp!;

/** @deprecated Prefer outlaysDataset — kept for existing imports. */
export const budgetDataset = outlaysDataset;

export const federalBudget = outlaysDataset.root;
export const federalRevenue = receiptsDataset.root;
