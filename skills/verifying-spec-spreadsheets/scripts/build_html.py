"""
build_html.py — Render the verification/enrichment results as a single
self-contained HTML report, from the SAME inputs as build_output.py:

    python build_html.py <source.xlsx> <payload.json> <out.html>
    python build_html.py --selftest

The HTML is a companion to (not a replacement for) the 5-sheet workbook: same
model, same payload, same leave-blank/flag discipline. What it adds over Excel:
clickable source URLs, old->new diffs on the Reconciled view (instead of a bare
amber cell), coverage badges, and instant filter/search/sort — in one file you
can email or open anywhere. No external assets (all CSS/JS inline), no
dependencies beyond openpyxl (via spec_model).

Views: Overview (stat tiles + per-division rollup) | Spec List | Reconciled
(Live) | Communities | Verification Report | Needs Research.

Color is never the only signal: every tinted row also carries its status /
confidence as text, matching the workbook's scheme (green=enriched/high,
orange=needs-research/medium, amber=reconciled-to-live, red=low/unverified).
"""
from __future__ import annotations

import datetime
import html
import json
import re
import sys

from spec_model import Community, FloorPlan, load_communities
from build_output import apply_enrichment, insert_new_communities, normalize_floorplan


# ---------------------------------------------------------------- reconciliation

FP_FIELDS = ("base_price", "unit_type", "sf", "stories", "garages", "lot_width", "product")
FP_LABELS = {"base_price": "price", "unit_type": "bed/bath", "sf": "SF",
             "stories": "stories", "garages": "garages", "lot_width": "lot width",
             "product": "product"}


def apply_overrides(c: Community, ov: dict):
    """Apply one community's reconciliation override; return (live_plans,
    scalars, changes). ``changes`` is a list of dicts {field, plan, old, new}
    describing every difference the override introduces, so the report can show
    old->new instead of a silent amber cell. Mirrors build_output's rules:
    ``floor_plans`` replaces the roster; ``rename_plan``/``price_override``
    patch single plans; scalar keys override cells."""
    changes = []
    scalars = {k: getattr(c, k) for k in ("latlong", "website", "delivery", "amenities", "hoa")}
    for k in scalars:
        if k in ov:
            changes.append({"field": k, "plan": None, "old": scalars[k], "new": ov[k]})
            scalars[k] = ov[k]

    if ov.get("floor_plans"):
        live = [FloorPlan(
            base_price=f.get("base_price"), plan=f.get("plan"), unit_type=f.get("unit_type"),
            lot_width=f.get("lot_width"), product=f.get("product"), sf=f.get("sf"),
            stories=f.get("stories"), garages=f.get("garages"),
            source=f.get("source"), confidence=f.get("confidence"),
        ) for f in ov["floor_plans"]]
        old_by_name = {fp.plan: fp for fp in c.floor_plans if fp.plan}
        new_names = {fp.plan for fp in live if fp.plan}
        for fp in live:
            old = old_by_name.get(fp.plan)
            if old is None:
                changes.append({"field": "plan added", "plan": fp.plan, "old": None, "new": fp.plan})
                continue
            for f in FP_FIELDS:
                a, b = getattr(old, f), getattr(fp, f)
                if a is not None and b is not None and str(a) != str(b):
                    changes.append({"field": FP_LABELS[f], "plan": fp.plan, "old": a, "new": b})
        for name in old_by_name:
            if name not in new_names:
                changes.append({"field": "plan removed", "plan": name, "old": name, "new": None})
        return live, scalars, changes

    live = [FloorPlan(**vars(fp)) for fp in c.floor_plans]
    rn = ov.get("rename_plan")
    if rn:
        for fp in live:
            if fp.plan == rn.get("from"):
                changes.append({"field": "plan renamed", "plan": rn.get("to"),
                                "old": rn.get("from"), "new": rn.get("to")})
                fp.plan = rn.get("to")
    po = ov.get("price_override")
    if po:
        for fp in live:
            if fp.plan == po.get("plan"):
                changes.append({"field": "price", "plan": fp.plan,
                                "old": fp.base_price, "new": po.get("value")})
                fp.base_price = po.get("value")
    return live, scalars, changes


# ---------------------------------------------------------------- formatting

def esc(v) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime.datetime):
        v = v.date().isoformat()
    return html.escape(str(v))


def money(v) -> str:
    if isinstance(v, (int, float)):
        return f"${v:,.0f}"
    return esc(v)


def link(url) -> str:
    if not url:
        return ""
    u = str(url)
    if not u.lower().startswith("http"):
        return esc(u)
    label = re.sub(r"^https?://(www\.)?", "", u).rstrip("/")
    if len(label) > 42:
        label = label[:40] + "…"
    return f'<a href="{esc(u)}" target="_blank" rel="noopener">{esc(label)}</a>'


def maplink(latlong) -> str:
    if not latlong:
        return ""
    s = str(latlong)
    m = re.search(r"(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)", s)
    if not m:
        return esc(s)
    return (f'<a href="https://www.google.com/maps?q={m.group(1)},{m.group(2)}"'
            f' target="_blank" rel="noopener">{esc(s)}</a>')


def badge(kind: str, label: str) -> str:
    """A status chip: colored dot + text. Text always carries the meaning."""
    return f'<span class="badge b-{kind}"><span class="dot"></span>{esc(label)}</span>'


STATUS_BADGE = {"complete": ("ok", "complete"), "enriched": ("ok", "enriched"),
                "needs_research": ("warn", "needs research"), "blank": ("bad", "blank")}
CONF_BADGE = {"high": "ok", "medium": "warn", "low": "bad"}


def status_badge(status) -> str:
    kind, label = STATUS_BADGE.get(status or "", ("muted", status or ""))
    return badge(kind, label) if label else ""


def conf_badge(conf) -> str:
    if not conf:
        return ""
    return badge(CONF_BADGE.get(conf, "muted"), conf)


def coverage_badge(cov) -> str:
    """Parse a coverage string ("40' 5/5; 50' 12/12 = 17/17 OK" / "6/10 INCOMPLETE — ...").
    Bad when it says INCOMPLETE or the final captured/stated pair falls short."""
    if not cov:
        return ""
    s = str(cov)
    pairs = re.findall(r"(\d+)\s*/\s*(\d+)", s)
    short = pairs and int(pairs[-1][0]) < int(pairs[-1][1])
    bad = "INCOMPLETE" in s.upper() or short
    return badge("bad" if bad else "ok", s)


def diff_cell(old, new, fmt=esc) -> str:
    return f'<span class="old">{fmt(old) or "—"}</span><span class="arr">→</span>{fmt(new) or "—"}'


def tr(cells, row_class="", data: dict | None = None) -> str:
    attrs = f' class="{row_class}"' if row_class else ""
    for k, v in (data or {}).items():
        attrs += f' data-{k}="{esc(v).lower()}"'
    return f"<tr{attrs}>" + "".join(cells) + "</tr>"


def td(content, sort=None, cls="") -> str:
    a = f' class="{cls}"' if cls else ""
    if sort is not None:
        a += f' data-sort="{esc(sort)}"'
    return f"<td{a}>{content}</td>"


def table(view_id, headers, rows, num_cols=()) -> str:
    ths = "".join(
        f'<th{" class=num" if i in num_cols else ""} data-col="{i}">{esc(h)}'
        f'<span class="sort-ind"></span></th>'
        for i, h in enumerate(headers))
    return (f'<div class="tablewrap"><table id="t-{view_id}">'
            f"<thead><tr>{ths}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")


# ---------------------------------------------------------------- views

def spec_rows(communities, recon_by_row=None, live=False, uncolor=False):
    """Rows for Spec List (live=False) or Reconciled (live=True). ``uncolor``
    mirrors the payload's ``uncolor_spec_list``: status badges stay, row tints
    move to the Reconciled view."""
    rows = []
    for c in communities:
        ov = (recon_by_row or {}).get(str(c.src_row)) or (recon_by_row or {}).get(c.property_name)
        if live and ov:
            plans, scalars, changes = apply_overrides(c, ov)
            note = ov.get("note")
        else:
            plans = [FloorPlan(**vars(fp)) for fp in c.floor_plans]
            scalars = {k: getattr(c, k) for k in ("latlong", "website", "delivery", "amenities", "hoa")}
            changes, note = [], None
        changed_scalar = {ch["field"] for ch in changes if ch["plan"] is None}
        by_plan = {}
        for ch in changes:
            if ch["plan"]:
                by_plan.setdefault(ch["plan"], []).append(ch)
        old_scalars = {ch["field"]: ch["old"] for ch in changes if ch["plan"] is None}

        plans = plans or [FloorPlan()]
        for fp in plans:
            normalize_floorplan(fp)
        for i, fp in enumerate(plans):
            first = i == 0
            plan_changes = by_plan.get(fp.plan, [])
            changed_fields = {ch["field"] for ch in plan_changes}
            row_cls = []
            if not uncolor:
                if c.status == "enriched" and (fp.source or fp.confidence):
                    row_cls.append("r-enriched")
                elif c.status == "needs_research" and first:
                    row_cls.append("r-flag")
            if plan_changes or (first and changed_scalar):
                row_cls.append("r-recon")

            def sc(key, fmt=esc):
                if not first:
                    return ""
                if key in changed_scalar:
                    return diff_cell(old_scalars.get(key), scalars[key], fmt)
                return fmt(scalars[key])

            def pc(field_label, value, fmt=esc, sort=None):
                for ch in plan_changes:
                    if ch["field"] == field_label:
                        return td(diff_cell(ch["old"], ch["new"], fmt), sort=sort, cls="chg")
                return td(fmt(value), sort=sort)

            added = any(ch["field"] == "plan added" for ch in plan_changes)
            plan_html = esc(fp.plan)
            if added:
                plan_html += ' <span class="tag">new</span>'
            for ch in plan_changes:
                if ch["field"] == "plan renamed":
                    plan_html = diff_cell(ch["old"], ch["new"])
            cells = [
                td(esc(c.division) if first else ""),
                td(esc(c.property_name) if first else ""),
                td(esc(fp.product)),
                td(sc("latlong", maplink)),
                td(sc("website", link)),
                td(sc("delivery")),
                pc("price", fp.base_price, money, sort=fp.base_price or 0),
                td(plan_html, cls="chg" if added else ""),
                pc("bed/bath", fp.unit_type),
                td(esc(fp.lot_width)),
                pc("SF", fp.sf, esc, sort=fp.sf or 0),
                pc("stories", fp.stories),
                pc("garages", fp.garages),
                td(sc("amenities"), cls="wrap"),
                td(sc("hoa")),
                td(status_badge(c.status) if first else ""),
                td(conf_badge(fp.confidence)),
                td(link(fp.source)),
            ]
            if live:
                cells.append(td(esc(note) if first else "", cls="wrap"))
            rows.append(tr(cells, " ".join(row_cls), {
                "division": c.division or "", "status": c.status or "",
                "confidence": fp.confidence or "", "property": c.property_name or ""}))
        # removed plans (live view): show struck-through so the retirement is visible
        if live:
            for ch in changes:
                if ch["field"] == "plan removed":
                    rows.append(tr([
                        td(""), td(""), td(""), td(""), td(""), td(""), td(""),
                        td(f'<span class="old">{esc(ch["plan"])}</span> <span class="tag t-bad">retired</span>'),
                        td(""), td(""), td("", sort=0), td(""), td(""), td(""), td(""),
                        td(""), td(""), td(""), td("plan no longer offered by builder"),
                    ], "r-recon", {"division": c.division or "", "status": c.status or "",
                                   "confidence": "", "property": c.property_name or ""}))
    return rows


SPEC_HEADERS = ["Division", "Property", "Product", "Lat/Long", "Website", "Delivery",
                "Base Price", "Floor Plan", "Bed/Bath", "Lot", "SF", "Stories",
                "Garages", "Amenities", "HOA", "Status", "Conf.", "Source"]


def build_report(communities, payload, generated=None) -> str:
    recon = payload.get("reconciliation") or {}
    overrides = {str(k): v for k, v in (recon.get("overrides") or {}).items()}
    verifications = {int(k): v for k, v in payload.get("verifications", {}).items()}
    coverage_map = {str(k): v for k, v in payload.get("coverage", {}).items()}
    by_row = {c.src_row: c for c in communities}

    n_plans = sum(len([fp for fp in c.floor_plans if not fp.is_empty()]) for c in communities)
    n_enriched = sum(1 for c in communities if c.status == "enriched")
    n_needs = sum(1 for c in communities if c.status == "needs_research")
    n_over = sum(1 for c in communities
                 if str(c.src_row) in overrides or (c.property_name or "") in overrides)
    covs = [coverage_map.get(str(c.src_row)) for c in communities]
    n_cov_bad = sum(1 for s in covs if s and ("INCOMPLETE" in str(s).upper()
                    or (lambda p: p and int(p[-1][0]) < int(p[-1][1]))(re.findall(r"(\d+)\s*/\s*(\d+)", str(s)))))

    tiles = [
        ("Communities", len(communities)),
        ("Floor plans", n_plans),
        ("Enriched", n_enriched),
        ("Needs research", n_needs),
        ("Verified (populated)", len(verifications)),
        ("Live overrides", n_over),
        ("Coverage shortfalls", n_cov_bad),
    ]
    tiles_html = "".join(
        f'<div class="tile"><div class="tlabel">{esc(l)}</div><div class="tvalue">{v:,}</div></div>'
        for l, v in tiles)

    # per-division rollup
    divs: dict = {}
    for c in communities:
        d = divs.setdefault(c.division or "—", dict(total=0, plans=0, enriched=0, needs=0))
        d["total"] += 1
        d["plans"] += len([fp for fp in c.floor_plans if not fp.is_empty()])
        d["enriched"] += c.status == "enriched"
        d["needs"] += c.status == "needs_research"
    div_rows = [tr([td(esc(name)), td(d["total"], sort=d["total"]), td(d["plans"], sort=d["plans"]),
                    td(d["enriched"], sort=d["enriched"]),
                    td(f'<span class="b-warn"><b>{d["needs"]}</b></span>' if d["needs"] else "0",
                       sort=d["needs"])])
                for name, d in divs.items()]
    overview = (f'<div class="tiles">{tiles_html}</div>'
                + table("overview", ["Division", "Communities", "Plans", "Enriched", "Needs research"],
                        div_rows, num_cols=(1, 2, 3, 4)))

    uncolor = bool(recon.get("uncolor_spec_list"))
    spec = table("spec", SPEC_HEADERS, spec_rows(communities, uncolor=uncolor), num_cols=(6, 10))
    reconciled = table("recon", SPEC_HEADERS + ["Reconciliation Note"],
                       spec_rows(communities, overrides, live=True), num_cols=(6, 10))

    comm_rows = [tr([
        td(c.src_row, sort=c.src_row if isinstance(c.src_row, int) else 0),
        td(esc(c.division)), td(esc(c.property_name)), td(status_badge(c.status)),
        td(len([fp for fp in c.floor_plans if not fp.is_empty()])),
        td(coverage_badge(coverage_map.get(str(c.src_row)))),
        td(esc(", ".join(c.missing_fields()))), td(esc(c.notes), cls="wrap"),
    ], "", {"division": c.division or "", "status": c.status or "",
            "property": c.property_name or ""}) for c in communities]
    comms = table("comms", ["Row", "Division", "Property", "Status", "# Plans",
                            "Plan coverage (captured/stated)", "Missing fields", "Notes"],
                  comm_rows, num_cols=(0, 4))

    VOK = {"yes": "ok", "consistent": "ok", "no": "bad", "discrepancy": "bad",
           "blocked": "warn", "unconfirmed": "warn"}
    ver_rows = []
    for row, v in sorted(verifications.items()):
        c = by_row.get(row)
        ver_rows.append(tr([
            td(row, sort=row),
            td(esc(c.division if c else "")), td(esc(c.property_name if c else "")),
            td(badge(VOK.get(v.get("website_ok", ""), "muted"), v.get("website_ok", "")) if v.get("website_ok") else ""),
            td(badge(VOK.get(v.get("latlong_plausible", ""), "muted"), v.get("latlong_plausible", "")) if v.get("latlong_plausible") else ""),
            td(badge(VOK.get(v.get("plans_checked", ""), "muted"), v.get("plans_checked", "")) if v.get("plans_checked") else ""),
            td(esc(v.get("discrepancies", "")), cls="wrap"), td(link(v.get("source"))),
        ], "", {"division": (c.division if c else "") or "",
                "property": (c.property_name if c else "") or ""}))
    verify = table("verify", ["Row", "Division", "Property", "Website", "Lat/Long",
                              "Plans", "Discrepancies", "Source"], ver_rows, num_cols=(0,))

    needs_rows = []
    for c in communities:
        missing = c.missing_fields()
        if missing or c.status == "needs_research":
            needs_rows.append(tr([
                td(c.src_row, sort=c.src_row if isinstance(c.src_row, int) else 0),
                td(esc(c.division)), td(esc(c.property_name)), td(status_badge(c.status)),
                td(esc(", ".join(missing))),
                td(esc(c.notes or "Not yet researched — no data gathered."), cls="wrap"),
            ], "r-flag", {"division": c.division or "", "status": c.status or "",
                          "property": c.property_name or ""}))
    needs = table("needs", ["Row", "Division", "Property", "Status", "Missing fields",
                            "Why / what was checked"], needs_rows, num_cols=(0,))

    views = [("overview", "Overview", overview), ("spec", "Spec List", spec),
             ("recon", "Reconciled (Live)", reconciled), ("comms", "Communities", comms),
             ("verify", "Verification Report", verify), ("needs", "Needs Research", needs)]
    tabs = "".join(f'<button class="tab" data-view="{vid}">{esc(label)}</button>'
                   for vid, label, _ in views)
    sections = "".join(f'<section class="view" id="v-{vid}">{body}</section>'
                       for vid, _, body in views)

    division_opts = "".join(f'<option value="{esc(d).lower()}">{esc(d)}</option>'
                            for d in sorted(divs))
    meta = payload.get("_meta", {})
    sub = " · ".join(x for x in [
        esc(meta.get("builder", "")),
        f"researched {esc(meta.get('research_date'))}" if meta.get("research_date") else "",
        f"report generated {esc(generated or datetime.date.today().isoformat())}"] if x)

    return HTML_TEMPLATE.replace("__TABS__", tabs).replace("__SECTIONS__", sections) \
        .replace("__DIVISIONS__", division_opts).replace("__SUBTITLE__", sub)


HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spec List Verification Report</title>
<style>
:root{
  --bg:#fcfcfb; --panel:#ffffff; --ink:#1a1a19; --ink2:#5f5e5a; --line:#e4e2dd;
  --ok:#0ca30c; --warn:#b97900; --bad:#d03b3b;
  --ok-bg:#e7f4e7; --warn-bg:#fdf2dc; --bad-bg:#fbe7e7; --recon-bg:#fdf6dd;
  --accent:#2e75b6;
}
@media (prefers-color-scheme: dark){:root{
  --bg:#1a1a19; --panel:#232322; --ink:#f0efec; --ink2:#a5a39d; --line:#3a3936;
  --ok:#4cc24c; --warn:#fab219; --bad:#e46262;
  --ok-bg:#213321; --warn-bg:#38300f; --bad-bg:#3a2222; --recon-bg:#37320f;
  --accent:#7ab3e0;
}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.45 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
header{padding:20px 24px 0}
h1{margin:0;font-size:20px;font-weight:650}
.sub{color:var(--ink2);margin:4px 0 14px;font-size:13px}
.tabs{display:flex;gap:2px;flex-wrap:wrap;padding:0 24px;border-bottom:1px solid var(--line)}
.tab{background:none;border:none;border-bottom:2px solid transparent;color:var(--ink2);
  padding:8px 12px;font:inherit;font-weight:600;cursor:pointer}
.tab.active{color:var(--ink);border-bottom-color:var(--accent)}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding:12px 24px}
.controls input,.controls select{background:var(--panel);color:var(--ink);
  border:1px solid var(--line);border-radius:6px;padding:6px 9px;font:inherit}
.controls input{min-width:220px}
#count{color:var(--ink2);font-size:12.5px;margin-left:auto}
.view{display:none;padding:0 24px 32px}
.view.active{display:block}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0 18px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.tlabel{color:var(--ink2);font-size:12.5px}
.tvalue{font-size:30px;font-weight:600;margin-top:2px}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:13px}
th{position:sticky;top:0;background:var(--panel);text-align:left;font-weight:650;
  padding:8px 10px;border-bottom:2px solid var(--line);white-space:nowrap;cursor:pointer;user-select:none}
th.num,td[data-sort]{text-align:right;font-variant-numeric:tabular-nums}
.sort-ind{display:inline-block;width:1em;color:var(--accent)}
td{padding:6px 10px;border-bottom:1px solid var(--line);vertical-align:top;white-space:nowrap}
td.wrap{white-space:normal;min-width:260px;max-width:480px}
tr:last-child td{border-bottom:none}
a{color:var(--accent)}
.r-enriched td{background:var(--ok-bg)}
.r-flag td{background:var(--warn-bg)}
.r-recon td{background:var(--recon-bg)}
td.chg{background:var(--recon-bg);outline:1px solid var(--warn);outline-offset:-1px}
.old{text-decoration:line-through;color:var(--ink2)}
.arr{color:var(--ink2);margin:0 5px}
.badge{display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:600;white-space:nowrap}
.badge .dot{width:8px;height:8px;border-radius:50%;flex:none}
.b-ok{color:var(--ok)} .b-ok .dot{background:var(--ok)}
.b-warn{color:var(--warn)} .b-warn .dot{background:var(--warn)}
.b-bad{color:var(--bad)} .b-bad .dot{background:var(--bad)}
.b-muted{color:var(--ink2)} .b-muted .dot{background:var(--ink2)}
.tag{font-size:11px;font-weight:700;color:var(--ok);border:1px solid var(--ok);
  border-radius:4px;padding:0 4px;margin-left:4px}
.tag.t-bad{color:var(--bad);border-color:var(--bad)}
</style></head><body>
<header><h1>Spec List Verification Report</h1><div class="sub">__SUBTITLE__</div></header>
<nav class="tabs">__TABS__</nav>
<div class="controls">
  <input id="q" type="search" placeholder="Search property, plan, note…">
  <select id="f-division"><option value="">All divisions</option>__DIVISIONS__</select>
  <select id="f-status"><option value="">All statuses</option>
    <option value="complete">complete</option><option value="enriched">enriched</option>
    <option value="needs_research">needs research</option></select>
  <select id="f-confidence"><option value="">All confidence</option>
    <option value="high">high</option><option value="medium">medium</option>
    <option value="low">low</option></select>
  <span id="count"></span>
</div>
__SECTIONS__
<script>
(function(){
  var tabs=[].slice.call(document.querySelectorAll('.tab'));
  var views=[].slice.call(document.querySelectorAll('.view'));
  var q=document.getElementById('q');
  var fDiv=document.getElementById('f-division'),fSt=document.getElementById('f-status'),
      fCf=document.getElementById('f-confidence'),count=document.getElementById('count');

  function activeTable(){var v=document.querySelector('.view.active');return v&&v.querySelector('table');}

  function show(id){
    tabs.forEach(function(t){t.classList.toggle('active',t.dataset.view===id);});
    views.forEach(function(v){v.classList.toggle('active',v.id==='v-'+id);});
    if(history.replaceState)history.replaceState(null,'','#'+id);
    applyFilters();
  }
  tabs.forEach(function(t){t.addEventListener('click',function(){show(t.dataset.view);});});

  // property blocks repeat division/status only on their first row; carry them
  // forward so filters keep whole blocks together.
  [].slice.call(document.querySelectorAll('tbody')).forEach(function(tb){
    var div='',st='',prop='';
    [].slice.call(tb.rows).forEach(function(r){
      if(r.dataset.property&&r.dataset.property!==prop){prop=r.dataset.property;div=r.dataset.division;st=r.dataset.status;}
      if(r.dataset.property!==undefined){r.dataset.division=div;r.dataset.status=st;}
    });
  });

  function applyFilters(){
    var t=activeTable(); if(!t)return;
    var needle=q.value.trim().toLowerCase(),dv=fDiv.value,st=fSt.value,cf=fCf.value;
    var shown=0,total=0,rows=[].slice.call(t.tBodies[0].rows);
    // group rows by property so a match shows the whole block
    var groups={},order=[];
    rows.forEach(function(r,i){
      var key=r.dataset.property!==undefined?(r.dataset.property||'row'+i):'row'+i;
      if(!groups[key]){groups[key]=[];order.push(key);}
      groups[key].push(r);
    });
    order.forEach(function(key){
      var g=groups[key];
      var r0=g[0];
      var okDiv=!dv||r0.dataset.division===dv;
      var okSt=!st||r0.dataset.status===st;
      var text=g.map(function(r){return r.textContent;}).join(' ').toLowerCase();
      var okQ=!needle||text.indexOf(needle)>=0;
      g.forEach(function(r){
        total++;
        var okCf=!cf||r.dataset.confidence===undefined||r.dataset.confidence===cf;
        var vis=okDiv&&okSt&&okQ&&okCf;
        r.style.display=vis?'':'none';
        if(vis)shown++;
      });
    });
    count.textContent=shown===total?total+' rows':shown+' of '+total+' rows';
  }
  [q,fDiv,fSt,fCf].forEach(function(el){el.addEventListener('input',applyFilters);});

  // sortable headers (numeric via data-sort, else text), stable-ish
  [].slice.call(document.querySelectorAll('th')).forEach(function(th){
    th.addEventListener('click',function(){
      var tbl=th.closest('table'),tb=tbl.tBodies[0],col=+th.dataset.col;
      var dir=th.dataset.dir==='asc'?'desc':'asc';
      [].slice.call(tbl.tHead.rows[0].cells).forEach(function(h){
        h.dataset.dir='';h.querySelector('.sort-ind').textContent='';});
      th.dataset.dir=dir;th.querySelector('.sort-ind').textContent=dir==='asc'?'▲':'▼';
      var rows=[].slice.call(tb.rows);
      function key(r){var c=r.cells[col];if(!c)return'';
        if(c.dataset.sort!==undefined)return parseFloat(c.dataset.sort)||0;
        return c.textContent.trim().toLowerCase();}
      rows.sort(function(a,b){var x=key(a),y=key(b);
        if(typeof x==='number'&&typeof y==='number')return dir==='asc'?x-y:y-x;
        x=String(x);y=String(y);return dir==='asc'?x.localeCompare(y):y.localeCompare(x);});
      rows.forEach(function(r){tb.appendChild(r);});
    });
  });

  var initial=location.hash.slice(1);
  show(document.getElementById('v-'+initial)?initial:'overview');
})();
</script></body></html>
"""


# ---------------------------------------------------------------- selftest

def _selftest():
    c1 = Community(src_row=5, division="Jacksonville", property_name="Amberly",
                   latlong="30.13, -81.77", website="https://dreamfindershomes.com/amberly/",
                   delivery="Active", hoa="$85/mo",
                   floor_plans=[FloorPlan(base_price=299990, plan="Boone",
                                          unit_type="3 Bed / 2 Bath", sf=1500, lot_width="40'",
                                          product="Single Family"),
                                FloorPlan(base_price=319990, plan="Caden",
                                          unit_type="4 Bed / 2 Bath", sf=1800, lot_width="40'",
                                          product="Single Family")])
    c2 = Community(src_row=9, division="Austin", property_name="Escondido 45'", status="blank")
    communities = [c1, c2]
    payload = {
        "_meta": {"builder": "Dream Finders Homes", "research_date": "2026-06-30"},
        "enrichments": {"9": {
            "website": {"value": "https://www.coventryhomes.com/escondido-45/",
                        "source": "https://www.coventryhomes.com/escondido-45/", "confidence": "high"},
            "floor_plans": [{"plan": "Muenster", "unit_type": "3 Bed / 2 Bath", "base_price": 274990,
                             "sf": 1644, "lot_width": "45'", "product": "Single Family",
                             "source": "https://www.coventryhomes.com/escondido-45/",
                             "confidence": "medium"}],
            "notes": "Lat/long blank — city-level only."}},
        "verifications": {"5": {"website_ok": "yes", "latlong_plausible": "yes",
                                "plans_checked": "discrepancy",
                                "discrepancies": "Boone now $305,990; Caden retired; Dylan added.",
                                "source": "https://dreamfindershomes.com/amberly-40/"}},
        "coverage": {"5": "40' 3/3 = 3/3 OK", "9": "45' 1/5 INCOMPLETE — 4 plans not captured"},
        "reconciliation": {"overrides": {"5": {
            "floor_plans": [
                {"plan": "Boone", "unit_type": "3 Bed / 2 Bath", "base_price": 305990, "sf": 1500,
                 "lot_width": "40'", "product": "Single Family",
                 "source": "https://dreamfindershomes.com/amberly-40/", "confidence": "high"},
                {"plan": "Dylan", "unit_type": "4 Bed / 3 Bath", "base_price": 342990, "sf": 2100,
                 "lot_width": "40'", "product": "Single Family",
                 "source": "https://dreamfindershomes.com/amberly-40/", "confidence": "high"}],
            "hoa": "$95/mo",
            "note": "Live roster 2026-06-30: Boone repriced, Caden retired, Dylan added; HOA raised."}}},
    }
    apply_enrichment(communities, payload)
    html_out = build_report(communities, payload, generated="2026-07-13")

    checks = [
        "Spec List Verification Report",
        "Amberly", "Escondido", "$299,990",             # original price kept on Spec List
        "$305,990",                                      # live price on Reconciled
        'class="old">$299,990',                          # old->new diff rendered
        "retired",                                       # removed plan visible
        ">new</span>",                                   # added plan tagged
        "INCOMPLETE",                                    # coverage badge text
        "needs research",                                # flag badge text
        "$85/mo", "$95/mo",                              # HOA old & new both present
        "prefers-color-scheme: dark",
    ]
    for needle in checks:
        assert needle in html_out, f"selftest: missing {needle!r}"
    assert "http-equiv" not in html_out
    ov = payload["reconciliation"]["overrides"]["5"]
    c1b = Community(src_row=5, property_name="Amberly", hoa="$85/mo",
                    floor_plans=[FloorPlan(base_price=299990, plan="Boone", sf=1500),
                                 FloorPlan(base_price=319990, plan="Caden", sf=1800)])
    live, scalars, changes = apply_overrides(c1b, ov)
    fields = sorted(ch["field"] for ch in changes)
    assert fields == ["hoa", "plan added", "plan removed", "price"], fields
    assert scalars["hoa"] == "$95/mo"
    assert len(live) == 2
    print("selftest OK —", len(html_out), "bytes of HTML,", len(changes), "diffed changes")


def main():
    if "--selftest" in sys.argv:
        _selftest()
        return
    if len(sys.argv) < 4:
        print("usage: python build_html.py <source.xlsx> <payload.json> <out.html>\n"
              "       python build_html.py --selftest")
        raise SystemExit(2)
    src, payload_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(payload_path) as fh:
        payload = json.load(fh)
    communities = load_communities(src)
    apply_enrichment(communities, payload)
    insert_new_communities(communities, payload)
    doc = build_report(communities, payload)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(doc)
    n_needs = sum(1 for c in communities if c.status == "needs_research")
    print(f"Wrote {out}")
    print(f"  communities: {len(communities)} | needs_research: {n_needs} | "
          f"views: Overview, Spec List, Reconciled (Live), Communities, "
          f"Verification Report, Needs Research")


if __name__ == "__main__":
    main()
