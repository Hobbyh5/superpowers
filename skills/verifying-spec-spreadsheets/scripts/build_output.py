"""
build_output.py — Rebuild the spec workbook from the parsed model plus a
verification/enrichment payload, producing a clean, un-merged, auditable output.

Input:
  - source workbook (original .xlsx)
  - a JSON payload describing per-community verification results and enrichment
    (see PAYLOAD SHAPE below)

Output workbook has four sheets:
  1. "Spec List"          flat, one row per floor plan, division+property repeated,
                          with added Source / Confidence / Verified / Notes columns
  2. "Communities"        one row per community + status (complete/enriched/needs_research)
  3. "Verification Report" results of checking already-populated communities
  4. "Needs Research"     blanks that could not be filled, with the missing fields

PAYLOAD SHAPE (JSON):
{
  "enrichments": {
     "<src_row>": {
        "latlong": {"value": "33.17, -84.91", "source": "https://...", "confidence": "medium"} | null,
        "website": {"value": "https://...", "source": "...", "confidence": "high"} | null,
        "delivery": {"value": "Active", "source": "...", "confidence": "high"} | null,
        "amenities": {"value": "...", "source": "...", "confidence": "high"} | null,
        "hoa": {"value": "...", "source": "...", "confidence": "medium"} | null,
        "builder_brand": "Coventry Homes",          # optional note
        "floor_plans": [
           {"plan": "Aspen", "unit_type": "3 Bed / 2.5 Bath", "base_price": 249990,
            "sf": 1579, "stories": 2, "garages": 2, "lot_width": null, "product": "Townhome",
            "source": "https://...", "confidence": "high"}
        ],
        "notes": "Free-text flags; what was left blank and why."
     }
  },
  "verifications": {
     "<src_row>": {
        "website_ok": "yes|no|blocked",
        "latlong_plausible": "yes|no|unconfirmed",
        "plans_checked": "consistent|discrepancy|unconfirmed",
        "discrepancies": "free text",
        "source": "https://..."
     }
  }
}

Only HIGH/MEDIUM-confidence, sourced values should appear in enrichments. Anything
inferred or unconfirmed must be left out (left blank) and described in "notes" so it
lands on the Needs Research sheet. Never fabricate.
"""
from __future__ import annotations

import json
import sys

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from spec_model import load_communities, FloorPlan

FLAT_HEADERS = [
    "Division", "Property Name", "Product Type", "Lat/Long", "Website",
    "Delivery Date", "Base Retail Price", "Floor Plan", "Unit Type (Bed/Bath)",
    "Lot Width", "SF", "Stories", "Garages", "Amenities", "HOA / Sub HOA",
    "Status", "Confidence", "Source",
]

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=10)
ENRICHED_FILL = PatternFill("solid", fgColor="E2EFDA")   # green-ish = newly added
FLAG_FILL = PatternFill("solid", fgColor="FCE4D6")       # orange-ish = needs research
THIN = Side(style="thin", color="D9D9D9")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# Separators on the flat Spec List: thin blue between properties, thick blue between divisions.
PROP_BLUE = Side(style="thin", color="2E75B6")
DIV_BLUE = Side(style="thick", color="1F4E78")


def _style_header(ws, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=1, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def _v(field):
    """Unwrap a {value,source,confidence} dict or return as-is."""
    if isinstance(field, dict):
        return field.get("value")
    return field


PRODUCT_KEYWORDS = {
    "single family", "single-family", "townhome", "town home", "paired",
    "duplex", "villa", "condo", "row", "sfd", "th",
}


def normalize_floorplan(fp):
    """Keep Unit Type strictly bed/bath; move any product-type text to Product.

    Some sources put "Single Family"/"Townhome" in the bed/bath slot. If the
    unit_type isn't a real bed/bath string (no "bed"), treat it as a product type.
    """
    ut = (fp.unit_type or "").strip()
    if ut and "bed" not in ut.lower():
        if ut.lower() in PRODUCT_KEYWORDS or "/" not in ut:
            if not fp.product:
                fp.product = ut
            fp.unit_type = None
    return fp


def apply_enrichment(communities, payload):
    enr = {int(k): v for k, v in payload.get("enrichments", {}).items()}
    for c in communities:
        e = enr.get(c.src_row)
        if not e:
            continue
        changed = False
        for key in ("latlong", "website", "delivery", "amenities", "hoa"):
            if e.get(key) and not getattr(c, key):
                setattr(c, key, _v(e[key]))
                changed = True
        if e.get("floor_plans"):
            for fpd in e["floor_plans"]:
                c.floor_plans.append(FloorPlan(
                    base_price=fpd.get("base_price"), plan=fpd.get("plan"),
                    unit_type=fpd.get("unit_type"), lot_width=fpd.get("lot_width"),
                    product=fpd.get("product"), sf=fpd.get("sf"),
                    stories=fpd.get("stories"), garages=fpd.get("garages"),
                    source=fpd.get("source"), confidence=fpd.get("confidence"),
                ))
            changed = True
        c.source = e.get("floor_plans", [{}])[0].get("source") if e.get("floor_plans") else None
        c.notes = e.get("notes")
        # Recompute status
        if changed:
            c.status = "needs_research" if c.is_blank() else "enriched"
        if e.get("notes") and c.is_blank():
            c.status = "needs_research"
    return communities


def build(src_path, out_path, payload):
    communities = load_communities(src_path)
    apply_enrichment(communities, payload)
    verifications = {int(k): v for k, v in payload.get("verifications", {}).items()}

    wb = openpyxl.Workbook()

    # ---- Sheet 1: flat Spec List ----
    ws = wb.active
    ws.title = "Spec List"
    ws.append(FLAT_HEADERS)
    prop_boundaries = []   # output rows that begin a new property
    div_boundaries = []    # output rows that begin a new division
    prev_division = None
    first_block = True
    for c in communities:
        rows = c.floor_plans if c.floor_plans else [FloorPlan()]
        for fp in rows:
            normalize_floorplan(fp)
        for i, fp in enumerate(rows):
            if i == 0 and not first_block:
                start_row = ws.max_row + 1
                if c.division != prev_division:
                    div_boundaries.append(start_row)
                else:
                    prop_boundaries.append(start_row)
            first_block = False
            row = [
                c.division if i == 0 else None,
                c.property_name if i == 0 else None,
                fp.product,
                c.latlong if i == 0 else None,
                c.website if i == 0 else None,
                c.delivery if i == 0 else None,
                fp.base_price, fp.plan, fp.unit_type, fp.lot_width,
                fp.sf, fp.stories, fp.garages,
                c.amenities if i == 0 else None,
                c.hoa if i == 0 else None,
                c.status if i == 0 else None,
                fp.confidence,
                fp.source,
            ]
            ws.append(row)
            r = ws.max_row
            # Show Base Retail Price as currency ($363,990) while keeping it numeric.
            price_cell = ws.cell(row=r, column=7)
            if isinstance(price_cell.value, (int, float)):
                price_cell.number_format = '"$"#,##0'
            if c.status == "enriched" and (fp.source or fp.confidence):
                for cc in range(1, len(FLAT_HEADERS) + 1):
                    ws.cell(row=r, column=cc).fill = ENRICHED_FILL
            elif c.status == "needs_research" and i == 0:
                for cc in range(1, len(FLAT_HEADERS) + 1):
                    ws.cell(row=r, column=cc).fill = FLAG_FILL
        prev_division = c.division
    _style_header(ws, len(FLAT_HEADERS))
    ws.freeze_panes = "A2"
    widths = [14, 28, 13, 22, 46, 13, 14, 18, 18, 10, 8, 8, 9, 30, 24, 15, 11, 46]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    # Excel autofilter (dropdowns on every column, incl. Division, Property Name,
    # Product Type, Lot Width, Stories, Garages, Floor Plan).
    ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(FLAT_HEADERS))}{ws.max_row}"

    # Separator borders: thin blue between properties, thick blue between divisions.
    # Applied as a top border across the row that begins each new block.
    def _top_border(row_idx, side):
        for cc in range(1, len(FLAT_HEADERS) + 1):
            cell = ws.cell(row=row_idx, column=cc)
            b = cell.border
            cell.border = Border(top=side, left=b.left, right=b.right, bottom=b.bottom)

    for r in prop_boundaries:
        _top_border(r, PROP_BLUE)
    for r in div_boundaries:   # division wins over property where both could apply
        _top_border(r, DIV_BLUE)

    # ---- Sheet 2: Communities ----
    ws2 = wb.create_sheet("Communities")
    ws2.append(["Src Row", "Division", "Property Name", "Status", "# Floor Plans",
                "Missing Fields", "Builder/Source Notes"])
    for c in communities:
        ws2.append([c.src_row, c.division, c.property_name, c.status,
                    len([fp for fp in c.floor_plans if not fp.is_empty()]),
                    ", ".join(c.missing_fields()), c.notes or ""])
        if c.status == "enriched":
            for cc in range(1, 8):
                ws2.cell(row=ws2.max_row, column=cc).fill = ENRICHED_FILL
        elif c.status == "needs_research":
            for cc in range(1, 8):
                ws2.cell(row=ws2.max_row, column=cc).fill = FLAG_FILL
    _style_header(ws2, 7)
    ws2.freeze_panes = "A2"
    for i, w in enumerate([8, 14, 30, 16, 13, 28, 50], 1):
        ws2.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    # ---- Sheet 3: Verification Report ----
    ws3 = wb.create_sheet("Verification Report")
    ws3.append(["Src Row", "Division", "Property Name", "Website OK",
                "Lat/Long Plausible", "Plans Checked", "Discrepancies", "Source"])
    by_row = {c.src_row: c for c in communities}
    for row, v in sorted(verifications.items()):
        c = by_row.get(row)
        ws3.append([row, c.division if c else "", c.property_name if c else "",
                    v.get("website_ok", ""), v.get("latlong_plausible", ""),
                    v.get("plans_checked", ""), v.get("discrepancies", ""),
                    v.get("source", "")])
    _style_header(ws3, 8)
    ws3.freeze_panes = "A2"
    for i, w in enumerate([8, 14, 30, 12, 16, 16, 44, 46], 1):
        ws3.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    # ---- Sheet 4: Needs Research ----
    ws4 = wb.create_sheet("Needs Research")
    ws4.append(["Src Row", "Division", "Property Name", "Status", "Missing Fields",
                "Why / What was checked"])
    for c in communities:
        missing = c.missing_fields()
        # Surface anything still incomplete: untouched blanks AND partially-enriched
        # communities that still have gaps (e.g. lat/long left blank, plans not found).
        if missing or c.status == "needs_research":
            ws4.append([c.src_row, c.division, c.property_name, c.status,
                        ", ".join(missing),
                        c.notes or "Not yet researched — no data gathered."])
            for cc in range(1, 7):
                ws4.cell(row=ws4.max_row, column=cc).fill = FLAG_FILL
    _style_header(ws4, 5)
    ws4.freeze_panes = "A2"
    for i, w in enumerate([8, 14, 30, 16, 28, 70], 1):
        ws4.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    wb.save(out_path)
    # Console summary
    n_enriched = sum(1 for c in communities if c.status == "enriched")
    n_needs = sum(1 for c in communities if c.status == "needs_research")
    print(f"Wrote {out_path}")
    print(f"  communities: {len(communities)} | enriched: {n_enriched} | "
          f"needs_research: {n_needs} | verifications: {len(verifications)}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: python build_output.py <source.xlsx> <payload.json> <out.xlsx>")
        raise SystemExit(2)
    src, payload_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(payload_path) as fh:
        payload = json.load(fh)
    build(src, out, payload)
