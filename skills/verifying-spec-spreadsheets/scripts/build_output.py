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

from spec_model import load_communities, FloorPlan, Community

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
RECON_FILL = PatternFill("solid", fgColor="FFE699")      # amber = overwritten to live data
THIN = Side(style="thin", color="D9D9D9")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# Separators on the flat Spec List: thin blue between properties, thick blue between divisions.
PROP_BLUE = Side(style="thin", color="2E75B6")
DIV_BLUE = Side(style="thick", color="1F4E78")
COL_SEP = Side(style="thin", color="BDD7EE")   # light blue vertical gridline between columns


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


def insert_new_communities(communities, payload):
    """Insert brand-new communities (not present as source rows) from payload.

    Each entry may carry an ``after_row`` (place it right after the community with
    that src_row; appended at the end if not found) plus the same fields as an
    enrichment. Values are sourced; nothing is fabricated here.
    """
    for nc in payload.get("new_communities", []):
        fps = [FloorPlan(
            base_price=f.get("base_price"), plan=f.get("plan"),
            unit_type=f.get("unit_type"), lot_width=f.get("lot_width"),
            product=f.get("product"), sf=f.get("sf"), stories=f.get("stories"),
            garages=f.get("garages"), source=f.get("source"),
            confidence=f.get("confidence"),
        ) for f in nc.get("floor_plans", [])]
        comm = Community(
            src_row=nc.get("src_row", "NEW"), division=nc.get("division"),
            property_name=nc.get("property_name"), type=nc.get("type"),
            latlong=_v(nc.get("latlong")), website=_v(nc.get("website")),
            delivery=_v(nc.get("delivery")), amenities=_v(nc.get("amenities")),
            hoa=_v(nc.get("hoa")), floor_plans=fps, notes=nc.get("notes"),
            source=(fps[0].source if fps else None),
        )
        comm.status = "needs_research" if comm.is_blank() else "enriched"
        after = nc.get("after_row")
        idx = len(communities)
        if after is not None:
            for j, c in enumerate(communities):
                if c.src_row == after:
                    idx = j + 1
                    break
        communities.insert(idx, comm)
    return communities


def _fp_from_dict(f):
    return FloorPlan(
        base_price=f.get("base_price"), plan=f.get("plan"),
        unit_type=f.get("unit_type"), lot_width=f.get("lot_width"),
        product=f.get("product"), sf=f.get("sf"), stories=f.get("stories"),
        garages=f.get("garages"), source=f.get("source"), confidence=f.get("confidence"),
    )


def build_reconciled_sheet(wb, communities, payload):
    """Emit a 'Reconciled (Live)' tab (inserted right after Spec List) when the
    payload carries a ``reconciliation`` section. The Spec List keeps your original
    values; THIS tab is where the builder's current data wins.

    payload["reconciliation"] = {
      "uncolor_spec_list": true,            # optional; move all color onto this tab
      "overrides": {
        "<src_row or property name>": {
          "floor_plans": [ {plan, unit_type, base_price, sf, stories, garages,
                            lot_width, product, source, confidence}, ... ],  # replace roster
          "latlong": "..", "website": "..", "delivery": "..",               # scalar cell overrides
          "amenities": "..", "hoa": "..",
          "price_override": {"plan": "Jordan", "value": 241990},            # single-plan price
          "rename_plan": {"from": "Kingston", "to": "Kinston"},             # fix a plan name
          "note": "Why it changed / what was kept original."
        }
      }
    }

    Rules mirror the rest of the skill: only put SOURCED live values here. A full
    roster replacement tints the whole community block amber; a scalar/plan override
    tints just the changed cell. Communities with no override keep their Spec-List
    status color (green=enriched, orange=needs research). Anything left blank stays
    blank — never fabricate to fill the live tab.
    """
    recon = payload.get("reconciliation")
    if recon is None:   # emit the tab whenever the key is present (even {} -> live mirror)
        return
    overrides = recon.get("overrides", {}) or {}
    ov_by_row = {str(k): v for k, v in overrides.items()}

    headers = FLAT_HEADERS + ["Reconciliation Note"]
    ncol = len(headers)
    ws = wb.create_sheet("Reconciled (Live)")
    ws.append(headers)
    prop_boundaries = []
    div_boundaries = []
    prev_division = None
    first_block = True
    for c in communities:
        ov = ov_by_row.get(str(c.src_row)) or overrides.get(c.property_name) or {}
        note = ov.get("note")
        roster = bool(ov.get("floor_plans"))
        if roster:
            plans = [_fp_from_dict(f) for f in ov["floor_plans"]]
        else:
            # copy so plan-level overrides don't mutate the Spec List model objects
            plans = [FloorPlan(**vars(fp)) for fp in c.floor_plans]
        latlong = ov.get("latlong", c.latlong)
        website = ov.get("website", c.website)
        delivery = ov.get("delivery", c.delivery)
        amenities = ov.get("amenities", c.amenities)
        hoa = ov.get("hoa", c.hoa)
        scalar_amber = {col for key, col in
                        (("latlong", 4), ("website", 5), ("delivery", 6),
                         ("amenities", 14), ("hoa", 15)) if key in ov}
        plan_amber = {}  # plan index -> set(column)
        if not roster:
            rn = ov.get("rename_plan")
            if rn:
                for idx, fp in enumerate(plans):
                    if fp.plan == rn.get("from"):
                        fp.plan = rn.get("to")
                        plan_amber.setdefault(idx, set()).add(8)
            po = ov.get("price_override")
            if po:
                for idx, fp in enumerate(plans):
                    if fp.plan == po.get("plan"):
                        fp.base_price = po.get("value")
                        plan_amber.setdefault(idx, set()).add(7)
        rows = plans if plans else [FloorPlan()]
        for fp in rows:
            normalize_floorplan(fp)
        for i, fp in enumerate(rows):
            if i == 0 and not first_block:
                start_row = ws.max_row + 1
                (div_boundaries if c.division != prev_division
                 else prop_boundaries).append(start_row)
            first_block = False
            ws.append([
                c.division if i == 0 else None,
                c.property_name if i == 0 else None,
                fp.product,
                latlong if i == 0 else None,
                website if i == 0 else None,
                delivery if i == 0 else None,
                fp.base_price, fp.plan, fp.unit_type, fp.lot_width,
                fp.sf, fp.stories, fp.garages,
                amenities if i == 0 else None,
                hoa if i == 0 else None,
                c.status if i == 0 else None,
                fp.confidence, fp.source,
                note if i == 0 else None,
            ])
            r = ws.max_row
            price_cell = ws.cell(row=r, column=7)
            if isinstance(price_cell.value, (int, float)):
                price_cell.number_format = '"$"#,##0'
            if roster:
                for cc in range(1, ncol + 1):
                    ws.cell(row=r, column=cc).fill = RECON_FILL
            else:
                if c.status == "enriched" and (fp.source or fp.confidence):
                    for cc in range(1, ncol + 1):
                        ws.cell(row=r, column=cc).fill = ENRICHED_FILL
                elif c.status == "needs_research" and i == 0:
                    for cc in range(1, ncol + 1):
                        ws.cell(row=r, column=cc).fill = FLAG_FILL
                if i == 0:
                    for cc in scalar_amber:
                        ws.cell(row=r, column=cc).fill = RECON_FILL
                for cc in plan_amber.get(i, ()):
                    ws.cell(row=r, column=cc).fill = RECON_FILL
            if i == 0 and note:
                ws.cell(row=r, column=ncol).alignment = Alignment(wrap_text=True, vertical="top")
        prev_division = c.division

    _style_header(ws, ncol)
    ws.freeze_panes = "A2"
    widths = [14, 28, 13, 22, 46, 13, 14, 18, 18, 10, 8, 8, 9, 30, 24, 15, 11, 46, 60]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
    ws.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(ncol)}{ws.max_row}"
    for r in range(1, ws.max_row + 1):
        for cc in range(1, ncol + 1):
            b = ws.cell(row=r, column=cc).border
            ws.cell(row=r, column=cc).border = Border(left=COL_SEP, right=COL_SEP,
                                                       top=b.top, bottom=b.bottom)

    def _tb(row_idx, side):
        for cc in range(1, ncol + 1):
            b = ws.cell(row=row_idx, column=cc).border
            ws.cell(row=row_idx, column=cc).border = Border(top=side, left=b.left,
                                                            right=b.right, bottom=b.bottom)
    for r in prop_boundaries:
        _tb(r, PROP_BLUE)
    for r in div_boundaries:
        _tb(r, DIV_BLUE)
    # Place the tab right after Spec List (index 1).
    wb._sheets.remove(ws)
    wb._sheets.insert(1, ws)


def build(src_path, out_path, payload):
    communities = load_communities(src_path)
    apply_enrichment(communities, payload)
    insert_new_communities(communities, payload)
    verifications = {int(k): v for k, v in payload.get("verifications", {}).items()}
    # Optional per-community plan-coverage strings ({src_row: "40' 5/5; 50' 12/12 = 17/17"}).
    # Surfaced on the Communities sheet so collection completeness is visible and filterable.
    coverage_map = {str(k): v for k, v in payload.get("coverage", {}).items()}
    # When a reconciliation tab is requested, the Spec List can be left uncolored
    # so all color (enriched/flagged/overwritten) lives on the Reconciled tab.
    uncolor = bool((payload.get("reconciliation") or {}).get("uncolor_spec_list"))

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
            if not uncolor:
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

    # Vertical gridlines between every column (header + data), preserving any
    # top/bottom borders set elsewhere.
    for r in range(1, ws.max_row + 1):
        for cc in range(1, len(FLAT_HEADERS) + 1):
            cell = ws.cell(row=r, column=cc)
            b = cell.border
            cell.border = Border(left=COL_SEP, right=COL_SEP, top=b.top, bottom=b.bottom)

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
                "Plan Coverage (captured/stated)", "Missing Fields", "Builder/Source Notes"])
    for c in communities:
        ws2.append([c.src_row, c.division, c.property_name, c.status,
                    len([fp for fp in c.floor_plans if not fp.is_empty()]),
                    coverage_map.get(str(c.src_row), ""),
                    ", ".join(c.missing_fields()), c.notes or ""])
        if c.status == "enriched":
            for cc in range(1, 9):
                ws2.cell(row=ws2.max_row, column=cc).fill = ENRICHED_FILL
        elif c.status == "needs_research":
            for cc in range(1, 9):
                ws2.cell(row=ws2.max_row, column=cc).fill = FLAG_FILL
    _style_header(ws2, 8)
    ws2.freeze_panes = "A2"
    for i, w in enumerate([8, 14, 30, 16, 13, 30, 28, 50], 1):
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

    # ---- Optional Sheet: Reconciled (Live) ----
    # Built only when payload has a "reconciliation" section; inserted right after
    # the Spec List. Leaves Spec List untouched; applies live overrides here.
    build_reconciled_sheet(wb, communities, payload)

    wb.save(out_path)
    # Console summary
    n_enriched = sum(1 for c in communities if c.status == "enriched")
    n_needs = sum(1 for c in communities if c.status == "needs_research")
    recon = "Reconciled (Live)" in wb.sheetnames
    print(f"Wrote {out_path}")
    print(f"  communities: {len(communities)} | enriched: {n_enriched} | "
          f"needs_research: {n_needs} | verifications: {len(verifications)} | "
          f"reconciled_tab: {recon}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: python build_output.py <source.xlsx> <payload.json> <out.xlsx>")
        raise SystemExit(2)
    src, payload_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(payload_path) as fh:
        payload = json.load(fh)
    build(src, out, payload)
