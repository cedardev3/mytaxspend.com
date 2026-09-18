"""
Pull official federal receipt figures and write src/data/federal-receipts.json.

Sources:
  - OMB Historical Table 2.1 (receipts by source) via GovInfo
  - OMB Historical Table 2.4 (social insurance + excise detail)
  - OMB Historical Table 2.5 (other receipts detail)
  - OMB Public Budget Database DB-3 (agency / account under receipt lines)
  - Treasury Fiscal Data Monthly Treasury Statement Table 9 (latest FYTD receipts)

Run: python scripts/refresh-federal-receipts.py
"""

from __future__ import annotations

import json
import re
import ssl
import sys
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from public_budget_db import (  # noqa: E402
    PDB_DETAILS_URL,
    PDB_RECEIPTS_XLSX_URL,
    PDB_ZIP_URL,
    enrich_receipt_tree,
    load_pdb_receipt_sheet,
    parse_receipt_entries,
)

OUT_PATH = ROOT / "src" / "data" / "federal-receipts.json"

OMB_ZIP_URL = "https://www.govinfo.gov/content/pkg/BUDGET-2027-TAB/zip/BUDGET-2027-TAB.zip"
OMB_TABLE_2_1_PATH = "BUDGET-2027-TAB/xls/BUDGET-2027-TAB-3-1.xlsx"
OMB_TABLE_2_4_PATH = "BUDGET-2027-TAB/xls/BUDGET-2027-TAB-3-4.xlsx"
OMB_TABLE_2_5_PATH = "BUDGET-2027-TAB/xls/BUDGET-2027-TAB-3-5.xlsx"
OMB_TABLE_2_1_URL = "https://www.govinfo.gov/content/pkg/BUDGET-2027-TAB/xls/BUDGET-2027-TAB-3-1.xlsx"
OMB_TABLE_2_4_URL = "https://www.govinfo.gov/content/pkg/BUDGET-2027-TAB/xls/BUDGET-2027-TAB-3-4.xlsx"
OMB_TABLE_2_5_URL = "https://www.govinfo.gov/content/pkg/BUDGET-2027-TAB/xls/BUDGET-2027-TAB-3-5.xlsx"
OMB_DETAILS_URL = "https://www.govinfo.gov/app/details/BUDGET-2027-TAB"
OMB_HISTORICAL_TABLES_URL = (
    "https://www.whitehouse.gov/omb/information-resources/budget/historical-tables/"
)
TREASURY_TABLE9_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_9"
)
TREASURY_DATASET_URL = (
    "https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/"
    "summary-of-receipts-by-source-and-outlays-by-function-of-the-u-s-government/"
)

SSML = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MODS = {"m": "http://www.loc.gov/mods/v3"}

FISCAL_YEAR = 2025

SOURCE_COLORS = {
    "individual-income-taxes": "#2a6f97",
    "corporation-income-taxes": "#245d82",
    "social-insurance-and-retirement-receipts": "#2f7d6d",
    "excise-taxes": "#c4922a",
    "other-receipts": "#7a6a58",
}

CTX = ssl.create_default_context()


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mytaxspend.com budget refresh"})
    with urllib.request.urlopen(req, context=CTX, timeout=120) as resp:
        return resp.read()


def fetch_json(url: str) -> dict:
    return json.loads(fetch(url).decode("utf-8"))


def colrow(cell_ref: str) -> tuple[int, int]:
    col = "".join(ch for ch in cell_ref if ch.isalpha())
    row = int("".join(ch for ch in cell_ref if ch.isdigit()))
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch.upper()) - 64)
    return n, row


def parse_xlsx_sheet(data: bytes) -> dict[int, dict[int, str]]:
    with zipfile.ZipFile(BytesIO(data)) as z:
        ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
        strings = []
        for si in ss.findall("a:si", SSML):
            strings.append("".join(t.text or "" for t in si.findall(".//a:t", SSML)))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        rows: dict[int, dict[int, str]] = {}
        for c in sheet.findall(".//a:c", SSML):
            ref = c.get("r")
            if not ref:
                continue
            col, row = colrow(ref)
            v = c.find("a:v", SSML)
            if v is None or v.text is None:
                continue
            val = strings[int(v.text)] if c.get("t") == "s" else v.text
            rows.setdefault(row, {})[col] = val
        return rows


def parse_millions(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if text in {"", "..........", "N/A", "None", "*"}:
        return None
    return float(text)


def slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def mix_hex(color: str, toward: str, t: float) -> str:
    def parts(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    a = parts(color)
    b = parts(toward)
    mixed = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def omb_sources(primary_label: str, spreadsheet_url: str) -> list[dict[str, str]]:
    return [
        {
            "label": primary_label,
            "url": OMB_HISTORICAL_TABLES_URL,
        },
        {
            "label": "FY 2027 Historical Tables (GovInfo)",
            "url": OMB_DETAILS_URL,
        },
        {
            "label": "Spreadsheet",
            "url": spreadsheet_url,
        },
    ]


def assert_sum(label: str, total: float, parts: list[float]) -> None:
    got = round(sum(parts), 1)
    want = round(total, 1)
    if got != want:
        raise RuntimeError(f"{label}: parts sum {got} != total {want}")


def parse_table_2_1(rows: dict[int, dict[int, str]], fiscal_year: int) -> dict:
    """Years are rows; major receipt categories are columns."""
    for r in sorted(rows):
        fy_raw = str(rows[r].get(1, "")).strip()
        try:
            fy = int(float(fy_raw))
        except ValueError:
            continue
        if fy != fiscal_year:
            continue
        individual = parse_millions(rows[r].get(2))
        corporate = parse_millions(rows[r].get(3))
        social = parse_millions(rows[r].get(4))
        social_on = parse_millions(rows[r].get(5))
        social_off = parse_millions(rows[r].get(6))
        excise = parse_millions(rows[r].get(7))
        other = parse_millions(rows[r].get(8))
        total = parse_millions(rows[r].get(9))
        on_budget = parse_millions(rows[r].get(10))
        off_budget = parse_millions(rows[r].get(11))
        if None in {individual, corporate, social, excise, other, total}:
            raise RuntimeError(f"Table 2.1 missing values for FY {fiscal_year}")
        assert_sum(
            "Table 2.1 major sources",
            total,  # type: ignore[arg-type]
            [individual, corporate, social, excise, other],  # type: ignore[list-item]
        )
        return {
            "amountMillions": total,
            "onBudgetMillions": on_budget,
            "offBudgetMillions": off_budget,
            "individualIncomeTaxes": individual,
            "corporationIncomeTaxes": corporate,
            "socialInsurance": social,
            "socialInsuranceOnBudget": social_on,
            "socialInsuranceOffBudget": social_off,
            "exciseTaxes": excise,
            "otherReceipts": other,
        }
    raise RuntimeError(f"Table 2.1 has no row for FY {fiscal_year}")


def parse_table_2_5(rows: dict[int, dict[int, str]], fiscal_year: int) -> dict:
    for r in sorted(rows):
        fy_raw = str(rows[r].get(1, "")).strip()
        try:
            fy = int(float(fy_raw))
        except ValueError:
            continue
        if fy != fiscal_year:
            continue
        total = parse_millions(rows[r].get(2))
        estate = parse_millions(rows[r].get(3))
        customs = parse_millions(rows[r].get(4))
        misc_total = parse_millions(rows[r].get(5))
        fed_reserve = parse_millions(rows[r].get(6)) or 0.0
        all_other = parse_millions(rows[r].get(7)) or 0.0
        if None in {total, estate, customs, misc_total}:
            raise RuntimeError(f"Table 2.5 missing values for FY {fiscal_year}")
        assert_sum("Table 2.5 other receipts", total, [estate, customs, misc_total])  # type: ignore
        assert_sum("Table 2.5 miscellaneous", misc_total, [fed_reserve, all_other])  # type: ignore
        return {
            "amountMillions": total,
            "estateAndGiftTaxes": estate,
            "customsDutiesAndFees": customs,
            "miscellaneousReceipts": misc_total,
            "federalReserveDeposits": fed_reserve,
            "miscellaneousAllOther": all_other,
        }
    raise RuntimeError(f"Table 2.5 has no row for FY {fiscal_year}")


def parse_table_2_4(rows: dict[int, dict[int, str]], fiscal_year: int) -> dict:
    """Years are columns; receipt lines are rows with hierarchical labels."""
    header = rows[3]
    years: dict[int, int] = {}
    for col, val in header.items():
        try:
            years[int(float(val))] = col
        except ValueError:
            continue
    if fiscal_year not in years:
        raise RuntimeError(f"Table 2.4 has no column for FY {fiscal_year}")
    year_col = years[fiscal_year]

    amounts: dict[str, float] = {}
    for r in sorted(rows):
        label = str(rows[r].get(1, "")).strip()
        amount = parse_millions(rows[r].get(year_col))
        if label and amount is not None:
            amounts[label] = amount

    social_total = amounts["Total, Social Insurance and Retirement Receipts (1)"]
    employment_total = amounts["Total (1)"]  # employment and general retirement total
    unemployment_total = amounts["Total"]  # first Total after unemployment — ambiguous

    # Re-walk with state machine for unambiguous section totals / leaves.
    section = None
    subsection = None
    employment_children: list[dict] = []
    unemployment_children: list[dict] = []
    other_retirement_children: list[dict] = []
    federal_excise: list[dict] = []
    trust_excise: list[dict] = []
    employment_total_amt = None
    unemployment_total_amt = None
    other_retirement_total_amt = None
    social_total_amt = None
    federal_excise_total = None
    trust_excise_total = None
    excise_total_amt = None

    for r in sorted(rows):
        label = str(rows[r].get(1, "")).strip()
        amount = parse_millions(rows[r].get(year_col))
        if not label:
            continue

        if label == "Employment and general retirement:":
            section = "employment"
            subsection = None
            continue
        if label == "Unemployment insurance:":
            section = "unemployment"
            subsection = None
            continue
        if label == "Other retirement:":
            section = "other_retirement"
            subsection = None
            continue
        if label.startswith("Total, Social Insurance"):
            social_total_amt = amount
            section = None
            continue
        if label == "Excise Taxes":
            section = "excise"
            subsection = None
            continue
        if label == "Federal funds:" and section == "excise":
            subsection = "federal_excise"
            continue
        if label == "Trust funds:" and section == "excise":
            subsection = "trust_excise"
            continue
        if label.startswith("Total, Excise"):
            excise_total_amt = amount
            section = None
            subsection = None
            continue

        if label.endswith(":") and amount is None:
            subsection = label[:-1]
            continue

        if label == "Total" or label.startswith("Total ("):
            if section == "employment":
                employment_total_amt = amount
            elif section == "unemployment":
                unemployment_total_amt = amount
            elif section == "other_retirement":
                other_retirement_total_amt = amount
            elif subsection == "federal_excise":
                federal_excise_total = amount
            elif subsection == "trust_excise":
                trust_excise_total = amount
            continue

        if amount is None:
            continue
        if label in {"Federal funds"} and amount is None:
            continue

        # Skip blank federal-funds placeholders under social insurance.
        if label == "Federal funds":
            continue

        item = {"name": label, "amountMillions": amount}
        if section == "employment":
            employment_children.append(item)
        elif section == "unemployment":
            unemployment_children.append(item)
        elif section == "other_retirement":
            other_retirement_children.append(item)
        elif subsection == "federal_excise":
            federal_excise.append(item)
        elif subsection == "trust_excise":
            trust_excise.append(item)

    if None in {
        employment_total_amt,
        unemployment_total_amt,
        other_retirement_total_amt,
        social_total_amt,
        federal_excise_total,
        trust_excise_total,
        excise_total_amt,
    }:
        raise RuntimeError("Table 2.4 is missing one or more section totals")

    assert_sum(
        "employment and general retirement",
        employment_total_amt,  # type: ignore
        [c["amountMillions"] for c in employment_children],
    )
    assert_sum(
        "unemployment insurance",
        unemployment_total_amt,  # type: ignore
        [c["amountMillions"] for c in unemployment_children],
    )
    assert_sum(
        "other retirement",
        other_retirement_total_amt,  # type: ignore
        [c["amountMillions"] for c in other_retirement_children],
    )
    assert_sum(
        "social insurance",
        social_total_amt,  # type: ignore
        [employment_total_amt, unemployment_total_amt, other_retirement_total_amt],  # type: ignore
    )
    assert_sum(
        "federal excise",
        federal_excise_total,  # type: ignore
        [c["amountMillions"] for c in federal_excise],
    )
    assert_sum(
        "trust excise",
        trust_excise_total,  # type: ignore
        [c["amountMillions"] for c in trust_excise],
    )
    assert_sum(
        "excise taxes",
        excise_total_amt,  # type: ignore
        [federal_excise_total, trust_excise_total],  # type: ignore
    )

    return {
        "socialInsuranceTotal": social_total_amt,
        "employment": {
            "amountMillions": employment_total_amt,
            "children": employment_children,
        },
        "unemployment": {
            "amountMillions": unemployment_total_amt,
            "children": unemployment_children,
        },
        "otherRetirement": {
            "amountMillions": other_retirement_total_amt,
            "children": other_retirement_children,
        },
        "exciseTotal": excise_total_amt,
        "federalExcise": {
            "amountMillions": federal_excise_total,
            "children": federal_excise,
        },
        "trustExcise": {
            "amountMillions": trust_excise_total,
            "children": trust_excise,
        },
    }


def leaf_node(
    *,
    node_id: str,
    name: str,
    amount: float,
    color: str,
    description: str,
    sources: list[dict[str, str]],
    code: str | None = None,
) -> dict:
    node = {
        "id": node_id,
        "name": name,
        "amountMillions": amount,
        "color": color,
        "description": description,
        "sources": sources,
    }
    if code:
        node["code"] = code
    return node


def branch_node(
    *,
    node_id: str,
    name: str,
    amount: float,
    color: str,
    description: str,
    sources: list[dict[str, str]],
    children: list[dict],
) -> dict:
    child_sum = round(sum(c["amountMillions"] for c in children), 1)
    if children and child_sum != round(amount, 1):
        raise RuntimeError(f"{name}: children {child_sum} != parent {round(amount, 1)}")
    return {
        "id": node_id,
        "name": name,
        "amountMillions": amount,
        "color": color,
        "description": description,
        "sources": sources,
        "children": children,
    }


def colorize_children(parent_color: str, items: list[dict], sources: list[dict[str, str]], desc_prefix: str) -> list[dict]:
    children = []
    for index, item in enumerate(items):
        children.append(
            leaf_node(
                node_id=slug(f"{desc_prefix}-{item['name']}"),
                name=item["name"],
                amount=item["amountMillions"],
                color=mix_hex(parent_color, "#ffffff" if index % 2 == 0 else "#1f3d4d", 0.18),
                description=f"{desc_prefix}: {item['name']}.",
                sources=sources,
            )
        )
    return children


def latest_treasury_receipts() -> dict:
    latest_url = (
        f"{TREASURY_TABLE9_URL}?sort=-record_date&page[size]=1"
        "&fields=record_date,record_fiscal_year,record_calendar_month"
    )
    latest = fetch_json(latest_url)["data"][0]
    record_date = latest["record_date"]
    table_url = (
        f"{TREASURY_TABLE9_URL}?filter=record_date:eq:{record_date}"
        "&sort=src_line_nbr&page[size]=200"
    )
    table = fetch_json(table_url)["data"]
    totals = [row for row in table if row["classification_desc"] == "Total"]
    if len(totals) != 2:
        raise RuntimeError(f"Expected two Table 9 Total rows, got {len(totals)}")
    receipts_total = float(totals[0]["current_fytd_rcpt_outly_amt"])
    outlays_total = float(totals[1]["current_fytd_rcpt_outly_amt"])

    sources: list[dict] = []
    for row in table:
        name = row["classification_desc"]
        if name == "Net Outlays":
            break
        if name in {"Receipts", "Total"} or name.endswith(":"):
            continue
        amount = row["current_fytd_rcpt_outly_amt"]
        if amount in {None, "null"}:
            continue
        sources.append(
            {
                "name": name,
                "amount": float(amount),
                "apiUrl": (
                    f"{TREASURY_TABLE9_URL}"
                    f"?filter=record_date:eq:{record_date},classification_desc:eq:{urllib.parse.quote(name)}"
                    "&fields=record_date,classification_desc,current_fytd_rcpt_outly_amt,src_line_nbr"
                    "&page[size]=1"
                ),
            }
        )

    month = datetime.strptime(record_date, "%Y-%m-%d").strftime("%B %d, %Y")
    fiscal_year = int(latest["record_fiscal_year"])
    return {
        "recordDate": record_date,
        "fiscalYear": fiscal_year,
        "periodLabel": f"FY {fiscal_year} through {month}",
        "receipts": receipts_total,
        "netOutlays": outlays_total,
        "sources": sources,
        "queryUrl": table_url,
        "datasetUrl": TREASURY_DATASET_URL,
        "latestRecordQueryUrl": latest_url,
    }


def mods_issued(zip_bytes: bytes) -> str | None:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
        if "BUDGET-2027-TAB/mods.xml" not in z.namelist():
            return None
        root = ET.fromstring(z.read("BUDGET-2027-TAB/mods.xml"))
        issued = root.find(".//m:dateIssued", MODS)
        return issued.text if issued is not None else None


def build_tree(t21: dict, t24: dict, t25: dict) -> dict:
    src_21 = omb_sources(
        f"OMB Historical Table 2.1, FY {FISCAL_YEAR} actual receipts",
        OMB_TABLE_2_1_URL,
    )
    src_24 = omb_sources(
        f"OMB Historical Table 2.4, FY {FISCAL_YEAR} actual receipts",
        OMB_TABLE_2_4_URL,
    )
    src_25 = omb_sources(
        f"OMB Historical Table 2.5, FY {FISCAL_YEAR} actual receipts",
        OMB_TABLE_2_5_URL,
    )

    individual = leaf_node(
        node_id="individual-income-taxes",
        name="Individual Income Taxes",
        amount=t21["individualIncomeTaxes"],
        color=SOURCE_COLORS["individual-income-taxes"],
        description=f"OMB Table 2.1: Individual Income Taxes. FY {FISCAL_YEAR} actual receipts.",
        sources=src_21,
    )
    corporate = leaf_node(
        node_id="corporation-income-taxes",
        name="Corporation Income Taxes",
        amount=t21["corporationIncomeTaxes"],
        color=SOURCE_COLORS["corporation-income-taxes"],
        description=f"OMB Table 2.1: Corporation Income Taxes. FY {FISCAL_YEAR} actual receipts.",
        sources=src_21,
    )

    social_color = SOURCE_COLORS["social-insurance-and-retirement-receipts"]
    social = branch_node(
        node_id="social-insurance-and-retirement-receipts",
        name="Social Insurance and Retirement Receipts",
        amount=t21["socialInsurance"],
        color=social_color,
        description=(
            f"OMB Tables 2.1 and 2.4: Social Insurance and Retirement Receipts. "
            f"FY {FISCAL_YEAR} actual receipts."
        ),
        sources=src_21 + src_24[1:],
        children=[
            branch_node(
                node_id="employment-and-general-retirement",
                name="Employment and general retirement",
                amount=t24["employment"]["amountMillions"],
                color=mix_hex(social_color, "#ffffff", 0.12),
                description="OMB Table 2.4: Employment and general retirement.",
                sources=src_24,
                children=colorize_children(
                    social_color,
                    t24["employment"]["children"],
                    src_24,
                    "OMB Table 2.4 employment and general retirement",
                ),
            ),
            branch_node(
                node_id="unemployment-insurance",
                name="Unemployment insurance",
                amount=t24["unemployment"]["amountMillions"],
                color=mix_hex(social_color, "#1f3d4d", 0.12),
                description="OMB Table 2.4: Unemployment insurance.",
                sources=src_24,
                children=colorize_children(
                    social_color,
                    t24["unemployment"]["children"],
                    src_24,
                    "OMB Table 2.4 unemployment insurance",
                ),
            ),
            branch_node(
                node_id="other-retirement",
                name="Other retirement",
                amount=t24["otherRetirement"]["amountMillions"],
                color=mix_hex(social_color, "#ffffff", 0.22),
                description="OMB Table 2.4: Other retirement.",
                sources=src_24,
                children=colorize_children(
                    social_color,
                    t24["otherRetirement"]["children"],
                    src_24,
                    "OMB Table 2.4 other retirement",
                ),
            ),
        ],
    )

    excise_color = SOURCE_COLORS["excise-taxes"]
    if round(t24["exciseTotal"], 1) != round(t21["exciseTaxes"], 1):
        raise RuntimeError("Table 2.4 excise total does not match Table 2.1")
    excise = branch_node(
        node_id="excise-taxes",
        name="Excise Taxes",
        amount=t21["exciseTaxes"],
        color=excise_color,
        description=f"OMB Tables 2.1 and 2.4: Excise Taxes. FY {FISCAL_YEAR} actual receipts.",
        sources=src_21 + src_24[1:],
        children=[
            branch_node(
                node_id="excise-federal-funds",
                name="Federal funds",
                amount=t24["federalExcise"]["amountMillions"],
                color=mix_hex(excise_color, "#ffffff", 0.12),
                description="OMB Table 2.4: Federal-fund excise taxes.",
                sources=src_24,
                children=colorize_children(
                    excise_color,
                    t24["federalExcise"]["children"],
                    src_24,
                    "OMB Table 2.4 federal-fund excise",
                ),
            ),
            branch_node(
                node_id="excise-trust-funds",
                name="Trust funds",
                amount=t24["trustExcise"]["amountMillions"],
                color=mix_hex(excise_color, "#1f3d4d", 0.12),
                description="OMB Table 2.4: Trust-fund excise taxes.",
                sources=src_24,
                children=colorize_children(
                    excise_color,
                    t24["trustExcise"]["children"],
                    src_24,
                    "OMB Table 2.4 trust-fund excise",
                ),
            ),
        ],
    )

    other_color = SOURCE_COLORS["other-receipts"]
    if round(t25["amountMillions"], 1) != round(t21["otherReceipts"], 1):
        raise RuntimeError("Table 2.5 other total does not match Table 2.1")
    other = branch_node(
        node_id="other-receipts",
        name="Other Receipts",
        amount=t21["otherReceipts"],
        color=other_color,
        description=f"OMB Tables 2.1 and 2.5: Other Receipts. FY {FISCAL_YEAR} actual receipts.",
        sources=src_21 + src_25[1:],
        children=[
            leaf_node(
                node_id="estate-and-gift-taxes",
                name="Estate and Gift Taxes",
                amount=t25["estateAndGiftTaxes"],
                color=mix_hex(other_color, "#ffffff", 0.12),
                description="OMB Table 2.5: Estate and Gift Taxes.",
                sources=src_25,
            ),
            leaf_node(
                node_id="customs-duties-and-fees",
                name="Customs Duties and Fees",
                amount=t25["customsDutiesAndFees"],
                color=mix_hex(other_color, "#1f3d4d", 0.12),
                description="OMB Table 2.5: Customs Duties and Fees.",
                sources=src_25,
            ),
            branch_node(
                node_id="miscellaneous-receipts",
                name="Miscellaneous Receipts",
                amount=t25["miscellaneousReceipts"],
                color=mix_hex(other_color, "#ffffff", 0.22),
                description="OMB Table 2.5: Miscellaneous Receipts.",
                sources=src_25,
                children=[
                    leaf_node(
                        node_id="federal-reserve-deposits",
                        name="Federal Reserve Deposits",
                        amount=t25["federalReserveDeposits"],
                        color=mix_hex(other_color, "#ffffff", 0.3),
                        description="OMB Table 2.5: Federal Reserve Deposits.",
                        sources=src_25,
                    ),
                    leaf_node(
                        node_id="miscellaneous-all-other",
                        name="All Other",
                        amount=t25["miscellaneousAllOther"],
                        color=mix_hex(other_color, "#1f3d4d", 0.22),
                        description="OMB Table 2.5: All other miscellaneous receipts.",
                        sources=src_25,
                    ),
                ],
            ),
        ],
    )

    children = [individual, corporate, social, excise, other]
    assert_sum(
        "root receipts",
        t21["amountMillions"],
        [c["amountMillions"] for c in children],
    )

    return {
        "id": "us-federal-receipts",
        "name": "US Federal Revenue",
        "amountMillions": t21["amountMillions"],
        "color": "#1f3d4d",
        "description": (
            f"FY {FISCAL_YEAR} actual US Federal Revenue from OMB Historical Tables 2.1, 2.4, and 2.5, "
            "with agency/account detail from the Public Budget Database. "
            "Click a source to dig deeper."
        ),
        "sources": src_21,
        "children": children,
    }


def main() -> None:
    zip_bytes = fetch(OMB_ZIP_URL)
    with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
        t21 = parse_table_2_1(parse_xlsx_sheet(z.read(OMB_TABLE_2_1_PATH)), FISCAL_YEAR)
        t24 = parse_table_2_4(parse_xlsx_sheet(z.read(OMB_TABLE_2_4_PATH)), FISCAL_YEAR)
        t25 = parse_table_2_5(parse_xlsx_sheet(z.read(OMB_TABLE_2_5_PATH)), FISCAL_YEAR)
    issued = mods_issued(zip_bytes)
    treasury = latest_treasury_receipts()
    root = build_tree(t21, t24, t25)

    if round(t24["socialInsuranceTotal"], 1) != round(t21["socialInsurance"], 1):
        raise RuntimeError("Table 2.4 social insurance total does not match Table 2.1")

    receipt_sheet = load_pdb_receipt_sheet()
    pdb_entries = parse_receipt_entries(receipt_sheet, FISCAL_YEAR)
    enrich_stats = enrich_receipt_tree(root, pdb_entries, FISCAL_YEAR)

    payload = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "omb": {
            "table": "2.1 / 2.4 / 2.5",
            "title": "Receipts by Source (with detail)",
            "fiscalYear": FISCAL_YEAR,
            "status": "actual",
            "units": "millions of dollars",
            "publication": "Budget of the United States Government, Fiscal Year 2027",
            "dateIssued": issued,
            "zipUrl": OMB_ZIP_URL,
            "spreadsheetUrl": OMB_TABLE_2_1_URL,
            "detailsUrl": OMB_DETAILS_URL,
            "historicalTablesUrl": OMB_HISTORICAL_TABLES_URL,
            "amountMillions": t21["amountMillions"],
            "onBudgetMillions": t21["onBudgetMillions"],
            "offBudgetMillions": t21["offBudgetMillions"],
            "tables": {
                "2.1": OMB_TABLE_2_1_URL,
                "2.4": OMB_TABLE_2_4_URL,
                "2.5": OMB_TABLE_2_5_URL,
            },
        },
        "publicBudgetDatabase": {
            "zipUrl": PDB_ZIP_URL,
            "detailsUrl": PDB_DETAILS_URL,
            "receiptsSpreadsheetUrl": PDB_RECEIPTS_XLSX_URL,
            "units": "thousands of dollars in source file; converted to millions here",
            "enrichedLeaves": enrich_stats["enriched"],
            "skippedLeaves": enrich_stats["skipped"],
        },
        "treasuryMts": treasury,
        "root": root,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"OMB FY {FISCAL_YEAR} total receipts: {t21['amountMillions']} million")
    print(f"Treasury {treasury['periodLabel']} receipts: {treasury['receipts']}")
    print(
        f"Public DB enrichment: {enrich_stats['enriched']} leaves expanded, "
        f"{enrich_stats['skipped']} left as Historical Table leaves"
    )


if __name__ == "__main__":
    main()
