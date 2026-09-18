/**
 * Country + jurisdiction labels for the explorer.
 * USA and Canada federal datasets are live.
 */

export type JurisdictionLabels = {
  id: string;
  /** Short place name, e.g. "US Federal" */
  name: string;
  /** Mode toggle + headings */
  spending: string;
  revenue: string;
  /** Comparison strip column labels */
  spendingShort: string;
  revenueShort: string;
  /** GDP series label */
  gdp: string;
  /** Slice metric: share of this jurisdiction's total spending */
  ofSpending: string;
  /** Slice metric: share of this jurisdiction's GDP */
  ofGdp: string;
  /** Reconciliation / summary wording */
  grossSpending: string;
  netSpending: string;
  grossRevenue: string;
  netRevenue: string;
  spendingUnit: string;
  revenueUnit: string;
};

export type CountryId = "us" | "ca";

export type CountryConfig = {
  id: CountryId;
  name: string;
  /** Native / short label on the flag control */
  shortName: string;
  /** Whether budget data is loaded for this country */
  available: boolean;
  comingSoonMessage?: string;
  federal: JurisdictionLabels;
};

export const US_FEDERAL: JurisdictionLabels = {
  id: "us-federal",
  name: "US Federal",
  spending: "US Federal Spending",
  revenue: "US Federal Revenue",
  spendingShort: "US Federal Spending",
  revenueShort: "US Federal Revenue",
  gdp: "US GDP",
  ofSpending: "of US federal spending",
  ofGdp: "of US GDP",
  grossSpending: "Gross US federal spending",
  netSpending: "Net US federal spending",
  grossRevenue: "Gross US federal revenue",
  netRevenue: "Net US federal revenue",
  spendingUnit: "US federal spending",
  revenueUnit: "US federal revenue",
};

export const CA_FEDERAL: JurisdictionLabels = {
  id: "ca-federal",
  name: "Canadian Federal",
  spending: "Canadian Federal Spending",
  revenue: "Canadian Federal Revenue",
  spendingShort: "Canadian Federal Spending",
  revenueShort: "Canadian Federal Revenue",
  gdp: "Canadian GDP",
  ofSpending: "of Canadian federal spending",
  ofGdp: "of Canadian GDP",
  grossSpending: "Gross Canadian federal spending",
  netSpending: "Net Canadian federal spending",
  grossRevenue: "Gross Canadian federal revenue",
  netRevenue: "Net Canadian federal revenue",
  spendingUnit: "Canadian federal spending",
  revenueUnit: "Canadian federal revenue",
};

export const COUNTRIES: CountryConfig[] = [
  {
    id: "us",
    name: "United States",
    shortName: "USA",
    available: true,
    federal: US_FEDERAL,
  },
  {
    id: "ca",
    name: "Canada",
    shortName: "Canada",
    available: true,
    federal: CA_FEDERAL,
  },
];

export const DEFAULT_COUNTRY_ID: CountryId = "us";

export function getCountry(id: CountryId): CountryConfig {
  const country = COUNTRIES.find((entry) => entry.id === id);
  if (!country) {
    throw new Error(`Unknown country id: ${id}`);
  }
  return country;
}
