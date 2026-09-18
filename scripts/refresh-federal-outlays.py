"""
Pull official federal outlay figures and write src/data/federal-outlays.json.

Sources:
  - OMB Historical Table 3.2 (function and subfunction actuals) via GovInfo
  - OMB Public Budget Database DB-2 (agency / bureau / account under subfunctions)
  - Treasury Fiscal Data Monthly Treasury Statement Table 9 (latest FYTD)

Run: python scripts/refresh-federal-outlays.py
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
    PDB_OUTLAYS_XLSX_URL,
    PDB_ZIP_URL,
    enrich_outlay_tree,
    load_pdb_outlay_sheet,
    parse_outlay_entries,
)

OUT_PATH = ROOT / "src" / "data" / "federal-outlays.json"

OMB_ZIP_URL = "https://www.govinfo.gov/content/pkg/BUDGET-2027-TAB/zip/BUDGET-2027-TAB.zip"
OMB_TABLE_PATH = "BUDGET-2027-TAB/xls/BUDGET-2027-TAB-4-2.xlsx"
OMB_GDP_TABLE_PATH = "BUDGET-2027-TAB/xls/BUDGET-2027-TAB-11-1.xlsx"
OMB_XLSX_URL = "https://www.govinfo.gov/content/pkg/BUDGET-2027-TAB/xls/BUDGET-2027-TAB-4-2.xlsx"
OMB_GDP_XLSX_URL = "https://www.govinfo.gov/content/pkg/BUDGET-2027-TAB/xls/BUDGET-2027-TAB-11-1.xlsx"
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

FUNCTION_COLORS = {
    "050": "#c45c26",
    "150": "#2a6f97",
    "250": "#6b5b95",
    "270": "#b8860b",
    "300": "#4a7c59",
    "350": "#8a9a3a",
    "370": "#7a6a58",
    "400": "#5c6b73",
    "450": "#3b6d9a",
    "500": "#c4922a",
    "550": "#2f7d6d",
    "570": "#1f6f62",
    "600": "#3b6d9a",
    "650": "#245d82",
    "700": "#4a7c59",
    "750": "#5c4a6b",
    "800": "#7a6a58",
    "900": "#6b5b95",
    "920": "#9a8a78",
    "950": "#8a7060",
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
    if text in {"", "..........", "N/A", "None"}:
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


def omb_sources() -> list[dict[str, str]]:
    return [
        {
            "label": "OMB Historical Table 3.2, FY 2025 actual outlays",
            "url": OMB_HISTORICAL_TABLES_URL,
        },
        {
            "label": "FY 2027 Historical Tables (GovInfo)",
            "url": OMB_DETAILS_URL,
        },
        {
            "label": "Table 3.2 spreadsheet",
            "url": OMB_XLSX_URL,
        },
    ]


def treasury_function_url(record_date: str, name: str) -> str:
    return (
        f"{TREASURY_TABLE9_URL}"
        f"?filter=record_date:eq:{record_date},classification_desc:eq:{urllib.parse.quote(name)}"
        "&fields=record_date,classification_desc,current_fytd_rcpt_outly_amt,src_line_nbr"
        "&page[size]=1"
    )


def parse_omb_gdp(rows: dict[int, dict[int, str]], fiscal_year: int) -> dict:
    """Table 10.1: years are rows; column 2 is GDP in billions of dollars."""
    for r in sorted(rows):
        fy_raw = str(rows[r].get(1, "")).strip()
        try:
            fy = int(float(fy_raw))
        except ValueError:
            continue
        if fy != fiscal_year:
            continue
        gdp_billions = parse_millions(rows[r].get(2))
        if gdp_billions is None:
            raise RuntimeError(f"Table 10.1 missing GDP for FY {fiscal_year}")
        return {
            "fiscalYear": fiscal_year,
            "status": "actual",
            "table": "10.1",
            "title": "Gross Domestic Product and Deflators Used in the Historical Tables",
            "units": "billions of dollars",
            "amountBillions": gdp_billions,
            "amountMillions": gdp_billions * 1000.0,
            "spreadsheetUrl": OMB_GDP_XLSX_URL,
            "historicalTablesUrl": OMB_HISTORICAL_TABLES_URL,
            "detailsUrl": OMB_DETAILS_URL,
        }
    raise RuntimeError(f"Table 10.1 has no row for FY {fiscal_year}")


def parse_omb_table(rows: dict[int, dict[int, str]], fiscal_year: int) -> dict:
    header = rows[3]
    years: dict[int, int] = {}
    for col, val in header.items():
        if col <= 1:
            continue
        try:
            years[int(float(val))] = col
        except ValueError:
            continue
    if fiscal_year not in years:
        raise RuntimeError(f"OMB Table 3.2 has no actual-year column for {fiscal_year}")
    year_col = years[fiscal_year]

    functions: list[dict] = []
    current: dict | None = None
    root_total = None
    on_budget = None
    off_budget = None

    function_header = re.compile(r"^(\d{3})\s+(.+):$")
    coded_line = re.compile(r"^(\d{3})\s+(.+)$")
    total_line = re.compile(r"^Total,\s+(.+)$")

    def close_function(function: dict, collected: list[dict]) -> None:
        if "amountMillions" not in function:
            if not function["children"]:
                return
            function["amountMillions"] = sum(child["amountMillions"] for child in function["children"])
        collected.append(function)

    for r in sorted(rows):
        label = str(rows[r].get(1, "")).strip()
        amount = parse_millions(rows[r].get(year_col))

        if label == "Total outlays":
            root_total = amount
            continue
        if current is None and label == "(On-budget)":
            on_budget = amount
            continue
        if current is None and label == "(Off-budget)":
            off_budget = amount
            continue

        header_match = function_header.match(label)
        if header_match:
            code = header_match.group(1)
            if code not in FUNCTION_COLORS:
                continue
            if current is not None:
                close_function(current, functions)
            current = {
                "code": code,
                "name": header_match.group(2).strip(),
                "children": [],
            }
            continue

        if current is None:
            continue

        if label.startswith("(") or "Subtotal" in label:
            continue

        total_match = total_line.match(label)
        if total_match:
            if amount is None:
                current = None
                continue
            current["amountMillions"] = amount
            functions.append(current)
            current = None
            continue

        if amount is None:
            continue

        coded = coded_line.match(label)
        if coded and not label.endswith(":"):
            code, name = coded.group(1), coded.group(2).strip()
            current["children"].append(
                {
                    "code": code,
                    "name": name,
                    "amountMillions": amount,
                }
            )
            continue

        current["children"].append(
            {
                "name": label,
                "amountMillions": amount,
            }
        )

    if current is not None:
        close_function(current, functions)

    if root_total is None:
        raise RuntimeError("OMB Table 3.2 is missing the Total outlays row")

    child_total = round(sum(fn["amountMillions"] for fn in functions), 1)
    if child_total != round(root_total, 1):
        raise RuntimeError(
            f"OMB function totals {child_total} do not equal Total outlays {root_total}"
        )

    return {
        "amountMillions": root_total,
        "onBudgetMillions": on_budget,
        "offBudgetMillions": off_budget,
        "functions": functions,
    }


def build_node(fn: dict, treasury: dict) -> dict:
    code = fn["code"]
    color = FUNCTION_COLORS[code]
    sources = omb_sources()
    treasury_match = next(
        (item for item in treasury["functions"] if item["name"] == fn["name"]),
        None,
    )
    if treasury_match:
        sources.append(
            {
                "label": f"Treasury MTS Table 9, {treasury['periodLabel']}",
                "url": treasury_match["apiUrl"],
            }
        )
        sources.append(
            {
                "label": "Monthly Treasury Statement dataset",
                "url": TREASURY_DATASET_URL,
            }
        )

    children = []
    for index, child in enumerate(fn["children"]):
        child_id = slug(f"{code}-{child.get('code', '')}-{child['name']}")
        child_sources = omb_sources()
        child_node = {
            "id": child_id,
            "name": child["name"],
            "amountMillions": child["amountMillions"],
            "color": mix_hex(color, "#ffffff" if index % 2 == 0 else "#1f3d4d", 0.18),
            "description": (
                f"OMB subfunction {child['code']}, {child['name']}."
                if child.get("code")
                else f"OMB Table 3.2 line under function {code}: {child['name']}."
            ),
            "sources": child_sources,
        }
        if child.get("code"):
            child_node["code"] = child["code"]
        children.append(child_node)

    child_sum = round(sum(child["amountMillions"] for child in children), 1)
    parent_amount = round(fn["amountMillions"], 1)
    if children and child_sum != parent_amount:
        raise RuntimeError(
            f"Function {code} amount {parent_amount} != children {child_sum}"
        )

    node = {
        "id": slug(f"{code}-{fn['name']}"),
        "name": fn["name"],
        "code": code,
        "amountMillions": fn["amountMillions"],
        "color": color,
        "description": f"OMB budget function {code}: {fn['name']}. FY 2025 actual outlays.",
        "sources": sources,
    }
    if children:
        node["children"] = children
    return node


def latest_treasury() -> dict:
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
    # Table 9 has two Totals; first is receipts, second is outlays.
    if len(totals) != 2:
        raise RuntimeError(f"Expected two Table 9 Total rows, got {len(totals)}")
    receipts_total = totals[0]["current_fytd_rcpt_outly_amt"]
    outlays_total = totals[1]["current_fytd_rcpt_outly_amt"]

    functions = []
    in_outlays = False
    for row in table:
        if row["classification_desc"] == "Net Outlays":
            in_outlays = True
            continue
        if not in_outlays:
            continue
        if row["classification_desc"] == "Total":
            break
        amount = row["current_fytd_rcpt_outly_amt"]
        if amount in {None, "null"}:
            continue
        functions.append(
            {
                "name": row["classification_desc"],
                "amount": float(amount),
                "apiUrl": treasury_function_url(record_date, row["classification_desc"]),
            }
        )

    month = datetime.strptime(record_date, "%Y-%m-%d").strftime("%B %d, %Y")
    fiscal_year = int(latest["record_fiscal_year"])
    return {
        "recordDate": record_date,
        "fiscalYear": fiscal_year,
        "periodLabel": f"FY {fiscal_year} through {month}",
        "receipts": float(receipts_total),
        "netOutlays": float(outlays_total),
        "functions": functions,
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


def main() -> None:
    zip_bytes = fetch(OMB_ZIP_URL)
    with zipfile.ZipFile(BytesIO(zip_bytes)) as z:
        xlsx = z.read(OMB_TABLE_PATH)
        gdp_xlsx = z.read(OMB_GDP_TABLE_PATH)
    rows = parse_xlsx_sheet(xlsx)
    omb = parse_omb_table(rows, 2025)
    gdp = parse_omb_gdp(parse_xlsx_sheet(gdp_xlsx), 2025)
    issued = mods_issued(zip_bytes)
    treasury = latest_treasury()

    children = [build_node(fn, treasury) for fn in omb["functions"]]

    payload = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "omb": {
            "table": "3.2",
            "title": "Outlays by Function and Subfunction",
            "fiscalYear": 2025,
            "status": "actual",
            "units": "millions of dollars",
            "publication": "Budget of the United States Government, Fiscal Year 2027",
            "dateIssued": issued,
            "zipUrl": OMB_ZIP_URL,
            "spreadsheetUrl": OMB_XLSX_URL,
            "detailsUrl": OMB_DETAILS_URL,
            "historicalTablesUrl": OMB_HISTORICAL_TABLES_URL,
            "amountMillions": omb["amountMillions"],
            "onBudgetMillions": omb["onBudgetMillions"],
            "offBudgetMillions": omb["offBudgetMillions"],
        },
        "gdp": gdp,
        "treasuryMts": treasury,
        "root": {
            "id": "us-federal-outlays",
            "name": "US Federal Spending",
            "amountMillions": omb["amountMillions"],
            "color": "#1f3d4d",
            "description": (
                "FY 2025 actual US Federal Spending from OMB Historical Table 3.2, "
                "with agency/bureau/account detail from the Public Budget Database. "
                "Click a category to dig deeper."
            ),
            "sources": omb_sources(),
            "children": children,
        },
    }

    outlay_sheet = load_pdb_outlay_sheet()
    pdb_entries = parse_outlay_entries(outlay_sheet, 2025)
    enrich_stats = enrich_outlay_tree(payload["root"], pdb_entries, 2025)
    payload["publicBudgetDatabase"] = {
        "zipUrl": PDB_ZIP_URL,
        "detailsUrl": PDB_DETAILS_URL,
        "outlaysSpreadsheetUrl": PDB_OUTLAYS_XLSX_URL,
        "units": "thousands of dollars in source file; converted to millions here",
        "enrichedLeaves": enrich_stats["enriched"],
        "skippedLeaves": enrich_stats["skipped"],
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"OMB FY 2025 total outlays: {omb['amountMillions']} million")
    print(f"OMB FY 2025 GDP: {gdp['amountBillions']} billion")
    print(f"Treasury {treasury['periodLabel']} net outlays: {treasury['netOutlays']}")
    print(
        f"Public DB enrichment: {enrich_stats['enriched']} leaves expanded, "
        f"{enrich_stats['skipped']} left as Table 3.2 leaves"
    )


if __name__ == "__main__":
    main()
