import budget from "@/data/federal-outlays.json";
import { assertTreeTotals, type BudgetDataset } from "@/lib/spend";

export const budgetDataset = budget as BudgetDataset;

assertTreeTotals(budgetDataset.root);

export const federalBudget = budgetDataset.root;
