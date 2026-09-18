"""
Build Canadian federal spending + revenue trees (2 layers deep) and write:
  src/data/canada-federal-outlays.json
  src/data/canada-federal-receipts.json

Sources (FY 2024-25 actuals):
  - Public Accounts of Canada revenues/expenses CSV (Receiver General)
  - Finance Canada Fiscal Reference Tables (October 2025) for spending category detail
  - Statistics Canada / FRT-implied GDP for share-of-GDP comparisons

Run: python scripts/refresh-canada-federal.py
"""

from __future__ import annotations

import csv
import json
import re
import ssl
import urllib.request
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTLAYS_PATH = ROOT / "src" / "data" / "canada-federal-outlays.json"
RECEIPTS_PATH = ROOT / "src" / "data" / "canada-federal-receipts.json"

PUBLIC_ACCOUNTS_URL = (
    "https://donnees-data.tpsgc-pwgsc.gc.ca/ba1/revenuesdeficit/revenuesdeficit-2025.csv"
)
PUBLIC_ACCOUNTS_DATASET = (
    "https://open.canada.ca/data/en/dataset/2599fe61-0e6e-40b9-958a-f56dd7f1fa09"
)
FRT_PAGE_URL = (
    "https://www.canada.ca/en/department-finance/services/publications/"
    "fiscal-reference-tables/2025.html"
)
FRT_PDF_URL = "https://www.canada.ca/content/dam/fin/publications/frt-trf/2025/frt-trf-25-eng.pdf"

FISCAL_YEAR_LABEL = "2024-25"
FISCAL_YEAR = 2025  # ending year, parallel to US FY labeling
STATUS = "actual"

# FRT Table 7 / 10 / 11 / 12 / 13 — FY 2024-25 (millions of dollars).
FRT_SPENDING = {
    "major_transfers_persons": {
        "name": "Major transfers to persons",
        "amount": 131579.0,
        "children": [
            {"name": "Old Age Security benefits", "amount": 80294.0},
            {"name": "Children's benefits", "amount": 28574.0},
            {"name": "Employment Insurance", "amount": 24880.0},
            {"name": "Relief for heating expenses", "amount": -2169.0},
        ],
    },
    "major_transfers_provinces": {
        "name": "Major transfers to provinces, territories and municipalities",
        "amount": 105101.0,
        "children": [
            {"name": "Canada Health Transfer", "amount": 68979.0},
            {"name": "Fiscal arrangements", "amount": 30457.0},
            {"name": "Canada-wide early learning and child care", "amount": 6639.0},
            {"name": "Other", "amount": 6568.0},
            {"name": "Quebec Abatement", "amount": -7542.0},
        ],
    },
    "other_transfer_payments": {
        "name": "Other transfer payments",
        "amount": 15595.0,
        "children": [],
    },
    "direct_program": {
        "name": "Direct program expenses",
        "amount": 237594.0,
        "children": [
            {"name": "Other transfer payments", "amount": 107140.0},
            {"name": "Other direct program expenses", "amount": 130454.0},
        ],
    },
    "pollution_pricing": {
        "name": "Pollution pricing proceeds returned to Canadians",
        "amount": 4020.0,
        "children": [],
    },
    "public_debt": {
        "name": "Public debt charges",
        "amount": 53410.0,
        # L2 filled from Public Accounts CSV (sums to 53410).
        "children": None,
    },
}

# FRT Table 1: budgetary deficit -36,348 is -1.2% of GDP → GDP ≈ 3,029 billion.
CANADA_GDP_BILLIONS = 3029.0

CTX = ssl.create_default_context()

COLORS = [
    "#c45c26",
    "#2a6f97",
    "#2f7d6d",
    "#c4922a",
    "#5c6b73",
    "#6b5b95",
    "#4a7c59",
    "#245d82",
    "#7a6a58",
    "#3b6d9a",
]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mytaxspend.com canada refresh"})
    with urllib.request.urlopen(req, context=CTX, timeout=120) as resp:
        return resp.read()


def slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:96]


def mix_hex(color: str, toward: str, t: float) -> str:
    def parts(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    a = parts(color)
    b = parts(toward)
    mixed = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def round1(value: float) -> float:
    return round(value, 1)


def assert_sum(label: str, total: float, parts: list[float]) -> None:
    got = round1(sum(parts))
    want = round1(total)
    if got != want:
        raise RuntimeError(f"{label}: parts sum {got} != total {want}")


def sources_pa() -> list[dict[str, str]]:
    return [
        {
            "label": f"Public Accounts of Canada, FY {FISCAL_YEAR_LABEL}",
            "url": PUBLIC_ACCOUNTS_DATASET,
        },
        {"label": "Revenues / expenses CSV", "url": PUBLIC_ACCOUNTS_URL},
    ]


def sources_frt() -> list[dict[str, str]]:
    return [
        {
            "label": f"Fiscal Reference Tables, October 2025 (FY {FISCAL_YEAR_LABEL})",
            "url": FRT_PAGE_URL,
        },
        {"label": "FRT PDF", "url": FRT_PDF_URL},
    ]


def leaf(
    *,
    node_id: str,
    name: str,
    amount: float,
    color: str,
    description: str,
    sources: list[dict[str, str]],
) -> dict:
    return {
        "id": node_id,
        "name": name,
        "amountMillions": round1(amount),
        "color": color,
        "description": description,
        "sources": sources,
    }


def branch(
    *,
    node_id: str,
    name: str,
    amount: float,
    color: str,
    description: str,
    sources: list[dict[str, str]],
    children: list[dict],
) -> dict:
    if children:
        assert_sum(name, amount, [c["amountMillions"] for c in children])
    node = {
        "id": node_id,
        "name": name,
        "amountMillions": round1(amount),
        "color": color,
        "description": description,
        "sources": sources,
    }
    if children:
        node["children"] = children
    return node


def parse_amount(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = str(raw).replace(",", "").strip()
    if text in {"", "N/A", "n/a", ".."}:
        return None
    return float(text)


def load_public_accounts() -> list[dict]:
    text = fetch(PUBLIC_ACCOUNTS_URL).decode("utf-8-sig")
    return list(csv.DictReader(StringIO(text)))


def public_debt_children(rows: list[dict]) -> list[dict]:
    """Aggregate Public Accounts public-debt lines to Type-detail2 (2nd layer)."""
    buckets: dict[str, float] = {}
    for row in rows:
        if row.get("Account_Compte_eng") != "Expenses":
            continue
        if (row.get("Type-detail_eng") or "") != "Public debt charges":
            continue
        amount = parse_amount(row.get("2024/2025"))
        if amount is None:
            continue
        label = (row.get("Type-detail2_eng") or "").strip() or "Other public debt charges"
        # Normalize encoding artifacts
        label = label.replace("\ufffd", "-")
        buckets[label] = buckets.get(label, 0.0) + amount

    color = COLORS[5]
    children = []
    for index, (name, amount) in enumerate(
        sorted(buckets.items(), key=lambda item: -abs(item[1]))
    ):
        children.append(
            leaf(
                node_id=slug(f"ca-debt-{name}"),
                name=name,
                amount=amount,
                color=mix_hex(color, "#ffffff" if index % 2 == 0 else "#1f3d4d", 0.16),
                description=(
                    f"Public Accounts FY {FISCAL_YEAR_LABEL}: public debt charges — {name}."
                ),
                sources=sources_pa(),
            )
        )
    assert_sum("Public debt charges", FRT_SPENDING["public_debt"]["amount"], [c["amountMillions"] for c in children])
    return children


def build_spending_tree(rows: list[dict]) -> dict:
    frt = sources_frt()
    pa = sources_pa()
    children: list[dict] = []

    order = [
        "major_transfers_persons",
        "major_transfers_provinces",
        "other_transfer_payments",
        "direct_program",
        "pollution_pricing",
        "public_debt",
    ]
    for index, key in enumerate(order):
        spec = FRT_SPENDING[key]
        color = COLORS[index % len(COLORS)]
        if key == "public_debt":
            kids = public_debt_children(rows)
            src = frt + pa[1:]
            desc = (
                f"Finance Canada Fiscal Reference Tables, FY {FISCAL_YEAR_LABEL}. "
                "Public debt charge detail from Public Accounts."
            )
        elif spec["children"]:
            kids = []
            for j, child in enumerate(spec["children"]):
                kids.append(
                    leaf(
                        node_id=slug(f"ca-{key}-{child['name']}"),
                        name=child["name"],
                        amount=child["amount"],
                        color=mix_hex(color, "#ffffff" if j % 2 == 0 else "#1f3d4d", 0.16),
                        description=(
                            f"Fiscal Reference Tables FY {FISCAL_YEAR_LABEL}: "
                            f"{spec['name']} — {child['name']}."
                        ),
                        sources=frt,
                    )
                )
            src = frt
            desc = f"Fiscal Reference Tables FY {FISCAL_YEAR_LABEL}: {spec['name']}."
        else:
            kids = []
            src = frt
            desc = f"Fiscal Reference Tables FY {FISCAL_YEAR_LABEL}: {spec['name']}."

        children.append(
            branch(
                node_id=slug(f"ca-{spec['name']}"),
                name=spec["name"],
                amount=spec["amount"],
                color=color,
                description=desc,
                sources=src,
                children=kids,
            )
        )

    total = sum(spec["amount"] for spec in (FRT_SPENDING[k] for k in order))
    assert_sum("Canadian federal spending", total, [c["amountMillions"] for c in children])

    return branch(
        node_id="ca-federal-outlays",
        name="Canadian Federal Spending",
        amount=total,
        color="#1f3d4d",
        description=(
            f"FY {FISCAL_YEAR_LABEL} actual Canadian federal expenses from Finance Canada "
            "Fiscal Reference Tables (2 layers). Click a category to open its components."
        ),
        sources=frt,
        children=children,
    )


def build_revenue_tree(rows: list[dict]) -> dict:
    """Two layers from Public Accounts revenue lines."""
    pa = sources_pa()

    def amount_of(row: dict) -> float:
        value = parse_amount(row.get("2024/2025"))
        if value is None:
            raise RuntimeError(f"Missing amount for {row}")
        return value

    revenue_rows = [r for r in rows if r.get("Account_Compte_eng") == "Revenues"]

    # Tax revenues — flatten meaningful L2 categories.
    personal = corporate = non_resident = 0.0
    gst = energy = customs = other_excise = 0.0
    for row in revenue_rows:
        d1 = row.get("Type-detail_eng") or ""
        d2 = row.get("Type-detail2_eng") or ""
        d3 = row.get("Type-detail3_eng") or ""
        d4 = row.get("Type-detail4_eng") or ""
        if d1 != "Tax revenues":
            continue
        amt = amount_of(row)
        if d2 == "Income tax revenues":
            if d3 == "Personal":
                personal += amt
            elif d3 == "Corporate":
                corporate += amt
            elif d3 == "Non-resident":
                non_resident += amt
        elif d2 == "Other taxes and duties":
            if d3 == "Goods and services tax":
                gst += amt
            elif d3 == "Energy taxes":
                energy += amt
            elif d3 == "Customs import duties":
                customs += amt
            elif d3 == "Other excise taxes and duties":
                other_excise += amt

    tax_children_spec = [
        ("Personal income tax", personal),
        ("Corporate income tax", corporate),
        ("Non-resident income tax", non_resident),
        ("Goods and services tax", gst),
        ("Energy taxes", energy),
        ("Customs import duties", customs),
        ("Other excise taxes and duties", other_excise),
    ]
    tax_total = sum(a for _, a in tax_children_spec)
    tax_color = COLORS[0]
    tax_children = [
        leaf(
            node_id=slug(f"ca-tax-{name}"),
            name=name,
            amount=amount,
            color=mix_hex(tax_color, "#ffffff" if i % 2 == 0 else "#1f3d4d", 0.16),
            description=f"Public Accounts FY {FISCAL_YEAR_LABEL}: {name}.",
            sources=pa,
        )
        for i, (name, amount) in enumerate(tax_children_spec)
    ]

    ei = next(
        amount_of(r)
        for r in revenue_rows
        if (r.get("Type-detail_eng") or "") == "Employment insurance premiums"
    )
    pollution = next(
        amount_of(r)
        for r in revenue_rows
        if (r.get("Type-detail_eng") or "") == "Pollution pricing proceeds"
    )

    # Other revenues — group by Type-detail2.
    other_buckets: dict[str, float] = {}
    for row in revenue_rows:
        if (row.get("Type-detail_eng") or "") != "Other revenues":
            continue
        label = (row.get("Type-detail2_eng") or "Other").strip()
        other_buckets[label] = other_buckets.get(label, 0.0) + amount_of(row)
    other_total = sum(other_buckets.values())
    other_color = COLORS[3]
    other_children = [
        leaf(
            node_id=slug(f"ca-other-rev-{name}"),
            name=name,
            amount=amount,
            color=mix_hex(other_color, "#ffffff" if i % 2 == 0 else "#1f3d4d", 0.16),
            description=f"Public Accounts FY {FISCAL_YEAR_LABEL}: {name}.",
            sources=pa,
        )
        for i, (name, amount) in enumerate(
            sorted(other_buckets.items(), key=lambda item: -abs(item[1]))
        )
    ]

    children = [
        branch(
            node_id="ca-tax-revenues",
            name="Tax revenues",
            amount=tax_total,
            color=tax_color,
            description=f"Public Accounts FY {FISCAL_YEAR_LABEL}: Tax revenues.",
            sources=pa,
            children=tax_children,
        ),
        leaf(
            node_id="ca-employment-insurance-premiums",
            name="Employment insurance premiums",
            amount=ei,
            color=COLORS[1],
            description=f"Public Accounts FY {FISCAL_YEAR_LABEL}: Employment insurance premiums.",
            sources=pa,
        ),
        leaf(
            node_id="ca-pollution-pricing-proceeds",
            name="Pollution pricing proceeds",
            amount=pollution,
            color=COLORS[2],
            description=f"Public Accounts FY {FISCAL_YEAR_LABEL}: Pollution pricing proceeds.",
            sources=pa,
        ),
        branch(
            node_id="ca-other-revenues",
            name="Other revenues",
            amount=other_total,
            color=other_color,
            description=f"Public Accounts FY {FISCAL_YEAR_LABEL}: Other revenues.",
            sources=pa,
            children=other_children,
        ),
    ]
    total = tax_total + ei + pollution + other_total
    assert_sum("Canadian federal revenue", total, [c["amountMillions"] for c in children])

    return branch(
        node_id="ca-federal-receipts",
        name="Canadian Federal Revenue",
        amount=total,
        color="#1f3d4d",
        description=(
            f"FY {FISCAL_YEAR_LABEL} actual Canadian federal revenues from the Public Accounts "
            "of Canada (2 layers). Click a source to open its components."
        ),
        sources=pa,
        children=children,
    )


def dataset_shell(
    *,
    root: dict,
    table: str,
    title: str,
    spreadsheet_url: str,
    historical_url: str,
    extra: dict | None = None,
) -> dict:
    payload = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "omb": {
            "table": table,
            "title": title,
            "fiscalYear": FISCAL_YEAR,
            "fiscalYearLabel": FISCAL_YEAR_LABEL,
            "status": STATUS,
            "units": "millions of dollars",
            "publication": "Public Accounts of Canada / Fiscal Reference Tables",
            "dateIssued": None,
            "zipUrl": spreadsheet_url,
            "spreadsheetUrl": spreadsheet_url,
            "detailsUrl": historical_url,
            "historicalTablesUrl": historical_url,
            "amountMillions": root["amountMillions"],
            "onBudgetMillions": root["amountMillions"],
            "offBudgetMillions": 0.0,
        },
        "treasuryMts": {
            "recordDate": f"{FISCAL_YEAR}-03-31",
            "fiscalYear": FISCAL_YEAR,
            "periodLabel": f"FY {FISCAL_YEAR_LABEL} annual (Public Accounts)",
            "receipts": root["amountMillions"] * 1_000_000
            if "Revenue" in root["name"]
            else 0.0,
            "netOutlays": root["amountMillions"] * 1_000_000
            if "Spending" in root["name"]
            else 0.0,
            "queryUrl": spreadsheet_url,
            "datasetUrl": historical_url,
            "latestRecordQueryUrl": spreadsheet_url,
        },
        "root": root,
    }
    if extra:
        payload.update(extra)
    return payload


def main() -> None:
    rows = load_public_accounts()
    spending_root = build_spending_tree(rows)
    revenue_root = build_revenue_tree(rows)

    # Cross-check Public Accounts revenue total vs FRT.
    pa_revenue = sum(
        parse_amount(r.get("2024/2025")) or 0.0
        for r in rows
        if r.get("Account_Compte_eng") == "Revenues"
    )
    if round1(pa_revenue) != round1(revenue_root["amountMillions"]):
        raise RuntimeError("Revenue tree total does not match Public Accounts CSV sum")

    outlays = dataset_shell(
        root=spending_root,
        table="FRT 7 / 10–13",
        title="Federal expenses by major category (Fiscal Reference Tables)",
        spreadsheet_url=FRT_PDF_URL,
        historical_url=FRT_PAGE_URL,
        extra={
            "gdp": {
                "fiscalYear": FISCAL_YEAR,
                "status": STATUS,
                "table": "FRT Table 1 / 2",
                "title": "Canadian GDP (implied from budgetary balance as % of GDP)",
                "units": "billions of dollars",
                "amountBillions": CANADA_GDP_BILLIONS,
                "amountMillions": CANADA_GDP_BILLIONS * 1000.0,
                "spreadsheetUrl": FRT_PDF_URL,
                "historicalTablesUrl": FRT_PAGE_URL,
                "detailsUrl": FRT_PAGE_URL,
            },
            "publicAccounts": {
                "url": PUBLIC_ACCOUNTS_URL,
                "datasetUrl": PUBLIC_ACCOUNTS_DATASET,
                "expenseMillions": sum(
                    parse_amount(r.get("2024/2025")) or 0.0
                    for r in rows
                    if r.get("Account_Compte_eng") == "Expenses"
                ),
            },
        },
    )
    # Fix treasury figures for spending dataset.
    outlays["treasuryMts"]["netOutlays"] = spending_root["amountMillions"] * 1_000_000
    outlays["treasuryMts"]["receipts"] = revenue_root["amountMillions"] * 1_000_000

    receipts = dataset_shell(
        root=revenue_root,
        table="Public Accounts",
        title="Federal revenues by source (Public Accounts of Canada)",
        spreadsheet_url=PUBLIC_ACCOUNTS_URL,
        historical_url=PUBLIC_ACCOUNTS_DATASET,
    )
    receipts["treasuryMts"]["receipts"] = revenue_root["amountMillions"] * 1_000_000
    receipts["treasuryMts"]["netOutlays"] = spending_root["amountMillions"] * 1_000_000

    OUTLAYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTLAYS_PATH.write_text(json.dumps(outlays, indent=2) + "\n", encoding="utf-8")
    RECEIPTS_PATH.write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTLAYS_PATH}")
    print(f"Wrote {RECEIPTS_PATH}")
    print(f"FY {FISCAL_YEAR_LABEL} spending: {spending_root['amountMillions']} million")
    print(f"FY {FISCAL_YEAR_LABEL} revenue: {revenue_root['amountMillions']} million")
    print(
        f"Deficit: {round1(revenue_root['amountMillions'] - spending_root['amountMillions'])} million"
    )


if __name__ == "__main__":
    main()
