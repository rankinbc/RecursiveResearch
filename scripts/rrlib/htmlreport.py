"""Turn a knowledge base into one self-contained HTML page a person can read and share."""
import json
from pathlib import Path

from .mdlite import REL, badge, esc, inline, render, slug
from .provenance import TIERS
from .scorecard import OVERVIEW, scorecard
from .store import RRError, load_plan, read_json, read_text, today, write_text
from .verify import is_checked

# fields that describe how a value is supported; shown as a badge, not as columns
SUPPORT = ("tier", "quote", "source", "source_url", "source_file", "verified", "verify_note", "downgraded_from")
SEGMENTS = (("verified", "PRIMARY, verified at source", "s-verified"),
            ("unverified_primary", "PRIMARY, not yet checked", "s-unchecked"),
            ("EXPERT", "EXPERT", "s-expert"), ("SECONDARY", "SECONDARY", "s-secondary"),
            ("INFERRED", "INFERRED", "s-inferred"), ("OBSERVED", "OBSERVED", "s-observed"),
            ("UNKNOWN", "UNKNOWN", "s-unknown"))

CSS = """
:root{--bg:#f6f8fa;--panel:#fff;--line:#d8dee4;--text:#1f2328;--muted:#59636e;--accent:#0969da;
--primary:#1a7f37;--primary-bg:#dafbe1;--expert:#0550ae;--expert-bg:#ddf4ff;--secondary:#6639ba;
--secondary-bg:#f3e8ff;--inferred:#7d4e00;--inferred-bg:#fff4c2;--observed:#a04100;--observed-bg:#ffe6d1;
--unknown:#59636e;--unknown-bg:#e7ebef;--conflict:#b3261e;--conflict-bg:#ffe3e0;
--f-primary:#2da44e;--f-expert:#218bff;--f-secondary:#a475f9;--f-inferred:#d4a72c;--f-observed:#e16f24;--f-unknown:#afb8c1}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--panel:#151b23;--line:#2f353d;--text:#e6edf3;
--muted:#9198a1;--accent:#58a6ff;--primary:#56d364;--primary-bg:#12301c;--expert:#79c0ff;--expert-bg:#10294a;
--secondary:#d2a8ff;--secondary-bg:#2a1a45;--inferred:#e3b341;--inferred-bg:#3a2d08;--observed:#ffa657;
--observed-bg:#3d1f05;--unknown:#9198a1;--unknown-bg:#262c34;--conflict:#ff7b72;--conflict-bg:#3c1614;
--f-primary:#3fb950;--f-expert:#58a6ff;--f-secondary:#bc8cff;--f-inferred:#d29922;--f-observed:#f0883e;--f-unknown:#6e7681}}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.layout{display:grid;grid-template-columns:250px minmax(0,1fr);max-width:1280px;margin:0 auto}
nav{position:sticky;top:0;align-self:start;height:100vh;overflow:auto;padding:28px 18px;border-right:1px solid var(--line)}
nav .brand{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:6px}
nav .subject{font-weight:650;font-size:17px;line-height:1.3;margin-bottom:22px}
nav a{display:block;padding:5px 10px;border-radius:6px;color:var(--text);font-size:14px}
nav a.sub{padding-left:22px;color:var(--muted);font-size:13px}
nav a:hover,nav a.on{background:var(--panel);text-decoration:none}
nav a.on{box-shadow:inset 2px 0 0 var(--accent)}
nav .group{margin:16px 0 4px 10px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
main{padding:36px 40px 80px;min-width:0}
header h1{font-size:30px;line-height:1.2;margin:0 0 8px}
header .goal{font-size:17px;color:var(--muted);margin:0 0 6px;max-width:70ch}
header .meta{font-size:13px;color:var(--muted)}
section{margin-top:46px}
section>h2{font-size:21px;margin:0 0 4px;padding-bottom:8px;border-bottom:1px solid var(--line)}
section>.lead{color:var(--muted);margin:8px 0 18px;max-width:75ch}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.tile .num{font-size:30px;font-weight:650;line-height:1.1}
.tile .label{font-size:13px;color:var(--muted);margin-top:4px}
.tile.good .num{color:var(--primary)}.tile.warn .num{color:var(--conflict)}
.bar{display:flex;height:12px;border-radius:6px;overflow:hidden;background:var(--unknown-bg);min-width:120px}
.bar.big{height:18px;margin:6px 0 10px}
.bar span{display:block;height:100%}
.s-verified{background:var(--f-primary)}.s-expert{background:var(--f-expert)}.s-secondary{background:var(--f-secondary)}
.s-inferred{background:var(--f-inferred)}.s-observed{background:var(--f-observed)}.s-unknown{background:var(--f-unknown)}
.s-unchecked{background:repeating-linear-gradient(45deg,var(--f-primary) 0 4px,var(--primary-bg) 4px 8px)}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--muted);margin-bottom:8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:12px 0;background:var(--panel)}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);background:var(--bg);font-weight:600}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.scroll{overflow-x:auto}
.tier{display:inline-block;font-size:10.5px;font-weight:650;letter-spacing:.05em;padding:1px 6px;border-radius:999px;
vertical-align:1px;white-space:nowrap;border:1px solid transparent}
a.tier:hover{text-decoration:none;filter:brightness(1.08)}
.t-primary{color:var(--primary);background:var(--primary-bg)}
.t-primary.unchecked{background:transparent;border-color:var(--primary);border-style:dashed}
.t-expert{color:var(--expert);background:var(--expert-bg)}.t-secondary{color:var(--secondary);background:var(--secondary-bg)}
.t-inferred{color:var(--inferred);background:var(--inferred-bg)}.t-observed{color:var(--observed);background:var(--observed-bg)}
.t-unknown{color:var(--unknown);background:var(--unknown-bg)}
.conflict{color:var(--conflict);background:var(--conflict-bg);font-size:10.5px;font-weight:700;letter-spacing:.05em;
padding:1px 6px;border-radius:4px}
.chip{display:inline-block;font-size:12px;padding:1px 8px;border-radius:999px;border:1px solid var(--line);color:var(--muted)}
.chip.open{color:var(--accent);border-color:var(--accent)}.chip.closed{color:var(--primary);border-color:var(--primary)}
.branch{margin-top:30px}
.branch>h3{font-size:18px;margin:0 0 4px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.branch .why{font-size:13px;color:var(--muted);margin:0 0 10px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:12px 0;overflow:hidden}
.card>.path{font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--muted);padding:8px 16px;
border-bottom:1px solid var(--line);background:var(--bg)}
.card>.body{padding:6px 18px 14px}
.body h3,.body h4,.body h5,.body h6{margin:18px 0 6px;line-height:1.3}
.body h3{font-size:17px}.body h4{font-size:15px}.body h5,.body h6{font-size:14px;color:var(--muted)}
.body p{margin:8px 0;max-width:80ch}
.body ul,.body ol{padding-left:22px;margin:8px 0}
.body li{margin:3px 0}
li.open,li.done{list-style:none;margin-left:-20px}
.box{display:inline-block;width:14px;height:14px;border:1.5px solid var(--muted);border-radius:3px;margin-right:8px;
vertical-align:-2px;font-size:10px;line-height:11px;text-align:center}
li.done{color:var(--muted)}li.done .box{background:var(--primary);border-color:var(--primary);color:var(--panel)}
code{font:13px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--unknown-bg);padding:1px 5px;border-radius:4px}
pre{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:12px 14px;overflow:auto}
pre code{background:none;padding:0}
blockquote{margin:8px 0;padding:2px 14px;border-left:3px solid var(--line);color:var(--muted)}
td.cell{position:relative}
td.cell.t-primary,td.cell.t-expert,td.cell.t-secondary,td.cell.t-inferred,td.cell.t-observed,td.cell.t-unknown{
background:var(--panel);box-shadow:inset 3px 0 0 currentColor}
td.cell span.v{color:var(--text)}
td.cell a.src{margin-left:6px;font-weight:700;color:var(--primary)}
.caption{font-size:13px;color:var(--muted);margin:10px 0 0}
details>summary{cursor:pointer;color:var(--accent);padding:8px 0;font-weight:600}
.empty{color:var(--muted);font-style:italic}
footer{margin-top:60px;padding-top:16px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}
@media (max-width:860px){.layout{grid-template-columns:1fr}nav{position:static;height:auto;border-right:0;
border-bottom:1px solid var(--line)}main{padding:24px 18px 60px}}
@media print{nav{display:none}.layout{display:block}details>*{display:block}}
"""

JS = """
(function(){var links=[].slice.call(document.querySelectorAll('nav a[href^="#"]'));
var byId={};links.forEach(function(a){byId[a.getAttribute('href').slice(1)]=a});
if(!('IntersectionObserver' in window))return;
var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){
links.forEach(function(a){a.classList.remove('on')});var a=byId[e.target.id];if(a)a.classList.add('on')}})},
{rootMargin:'-10% 0px -80% 0px'});
Object.keys(byId).forEach(function(id){var el=document.getElementById(id);if(el)io.observe(el)})})();
"""


def _bar(card, big=False):
    total = card["claims"]
    if not total:
        return '<div class="bar"></div>'
    spans = []
    for key, label, css in SEGMENTS:
        n = card[key] if key in card and not key.isupper() else card["tiers"].get(key, 0)
        if n:
            spans.append(f'<span class="{css}" style="width:{100 * n / total:.2f}%" title="{esc(label)}: {n}"></span>')
    return f'<div class="bar{" big" if big else ""}">{"".join(spans)}</div>'


def _status_chip(status):
    return f'<span class="chip {esc(status.split()[0])}">{esc(status)}</span>' if status else ""


def _scorecard_section(card):
    o = card["overall"]
    closed = sum(1 for b in card["branches"] if b["status"] == "closed")
    started = sum(1 for b in card["branches"] if b["status"] in ("open", "closed"))
    tiles = [("", o["claims"], "Claims"), ("good", o["verified"], "Verified at source"),
             ("", o["unknowns_open"], "Open unknowns"), ("warn" if o["conflicts"] else "", o["conflicts"], "Conflicts"),
             ("", f"{closed}/{started}" if started else "0", "Branches closed")]
    html_tiles = "".join(f'<div class="tile {css}"><div class="num">{esc(num)}</div>\n'
                         f'<div class="label">{label}</div></div>' for css, num, label in tiles)
    legend = "".join(f'<span><i class="{css}"></i>{esc(label)}</span>' for _, label, css in SEGMENTS)

    def row(name, part, status="", link=None):
        label = f'<a href="#{esc(link)}">{esc(name)}</a>' if link else esc(name)
        return (f'<tr><td>{label}</td><td>{_bar(part)}</td><td class="n">{part["claims"]}</td>'
                f'<td class="n">{part["verified"]}</td><td class="n">{part["unknowns_open"]}</td>'
                f'<td class="n">{part["conflicts"]}</td><td>{_status_chip(status)}</td></tr>')

    rows = [row("Survey", card["survey"], link="survey")] if card["survey"]["claims"] else []
    rows += [row(f"Catalogue: {t['name']} ({t['instances']})", t, link="c-" + slug(t["type"]))
             for t in card["catalogue"]]
    rows += [row("Tree overview" if b["branch"] == OVERVIEW else b["branch"], b, b["status"],
                 link="b-" + slug(b["branch"])) for b in card["branches"]]
    table = ('<div class="scroll"><table><thead><tr><th>Part</th><th>Support</th><th>Claims</th><th>Verified</th>'
             '<th>Open unknowns</th><th>Conflicts</th><th>Status</th></tr></thead><tbody>'
             + "".join(rows) + "</tbody></table></div>") if rows else ""
    note = ""
    if o["unverified_primary"]:
        note = (f'<p class="caption">{o["unverified_primary"]} PRIMARY claims are in files changed since the last '
                f'check, so they are shown as unchecked. Run <code>verify</code> to check them.</p>')
    return (f'<section id="scorecard"><h2>Scorecard</h2>'
            f'<p class="lead">Every claim carries a tier. <strong>Verified at source</strong> means the script '
            f'opened the cited page and found the quoted words there.</p>'
            f'<div class="tiles">{html_tiles}</div>{_bar(o, big=True)}<div class="legend">{legend}</div>'
            f'{table}{note}</section>')


def _support(entry, checked):
    tier = entry.get("tier")
    if tier not in TIERS:
        return ""
    if tier == "PRIMARY":
        return badge(tier, checked, entry.get("quote"), entry.get("source_url"))
    return badge(tier, note=entry.get("verify_note") or entry.get("source"))


def _value(value):
    if value is None:
        return '<span class="empty">not found</span>'
    if isinstance(value, (dict, list)):
        return f"<code>{esc(json.dumps(value, ensure_ascii=False))}</code>"
    return inline(str(value))


def _leaf(doc, checked):
    """Render a JSON leaf: its support line, then each table or value it holds."""
    if not isinstance(doc, dict):
        return f"<pre><code>{esc(json.dumps(doc, indent=2, ensure_ascii=False))}</code></pre>"
    parts = []
    meta = doc.get("_meta") if isinstance(doc.get("_meta"), dict) else {}
    if meta.get("provenance") in TIERS:
        support = _support({"tier": meta["provenance"], **{k: meta.get(k) for k in SUPPORT if k != "tier"}}, checked)
        source = f' &middot; {esc(meta["source"])}' if meta.get("source") else ""
        parts.append(f'<p class="caption">File as a whole: {support}{source}</p>')
    scalars = []
    for key, value in doc.items():
        if key == "_meta":
            continue
        rows = [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []
        if rows and len(rows) == len(value):
            columns = []
            for r in rows:
                columns += [k for k in r if k not in SUPPORT and k not in columns]
            tiered = any(r.get("tier") in TIERS for r in rows)
            head = "".join(f"<th>{esc(c)}</th>" for c in columns) + ("<th>Support</th>" if tiered else "")
            body = "".join(
                "<tr>" + "".join(f"<td>{_value(r.get(c))}</td>" for c in columns)
                + (f"<td>{_support(r, checked)}</td>" if tiered else "") + "</tr>" for r in rows)
            parts.append(f'<h4>{esc(key)}</h4><div class="scroll"><table><thead><tr>{head}</tr></thead>'
                         f'<tbody>{body}</tbody></table></div>')
        else:
            scalars.append((key, value))
    if scalars:
        body = "".join(f"<tr><th>{esc(k)}</th><td>{_value(v)}</td></tr>" for k, v in scalars)
        parts.append(f'<div class="scroll"><table><tbody>{body}</tbody></table></div>')
    return "".join(parts)


def _tree_section(ws, card):
    tree = Path(ws) / "knowledge" / "tree"
    if not card["branches"]:
        return ""
    status = {b["branch"]: b for b in card["branches"]}
    groups = {}
    for path in sorted(p for p in tree.rglob("*") if p.is_file() and p.suffix in (".md", ".json")):
        parts = path.relative_to(tree).parts
        groups.setdefault(parts[0] if len(parts) > 1 else OVERVIEW, []).append(path)
    out = ['<section id="tree"><h2>Knowledge tree</h2>'
           '<p class="lead">The deep layer, branch by branch. Each folder starts with an overview and ends with '
           'what is still unknown.</p>']
    for name in sorted(groups, key=lambda g: (g != OVERVIEW, g)):
        b = status.get(name, {})
        reasons = "; ".join(f"{c['branch']}: {c['reason']}" for c in b.get("closed", []))
        why = f'<p class="why">Closed: {esc(reasons)}</p>' if reasons else ""
        title = "Overview" if name == OVERVIEW else name
        out.append(f'<div class="branch" id="b-{esc(slug(name))}"><h3>{esc(title)} {_status_chip(b.get("status", ""))}'
                   f'</h3>{why}')
        # README first in each folder, then its leaves
        for path in sorted(groups[name], key=lambda p: (p.parent.as_posix(), p.name != "README.md", p.name)):
            rel = path.relative_to(tree).as_posix()
            checked = is_checked(ws, path)
            if path.suffix == ".md":
                body = render(read_text(path), checked, heading_offset=2, id_prefix=slug(rel) + "-")
            else:
                try:
                    body = _leaf(read_json(path), checked)
                except RRError as e:
                    body = f'<p class="empty">{esc(e)}</p>'
            out.append(f'<div class="card"><div class="path">{esc(rel)}</div><div class="body">{body}</div></div>')
        out.append("</div>")
    out.append("</section>")
    return "".join(out)


def _catalogue_section(ws, card):
    if not card["catalogue"]:
        return ""
    out = ['<section id="catalogue"><h2>Catalogue</h2>'
           '<p class="lead">Every instance of each kind of thing. The coloured edge of a cell is its tier, '
           'and a ✓ links to the passage that states it.</p>']
    for t in card["catalogue"]:
        path = Path(ws) / "knowledge" / "entities" / f"{t['type']}.json"
        doc = read_json(path)
        checked = is_checked(ws, path)
        entities = [e for e in doc.get("entities", []) if isinstance(e, dict) and isinstance(e.get("properties"), dict)]
        columns = []
        for e in entities:
            columns += [k for k in e["properties"] if k not in columns]
        rows = []
        for e in entities:
            given = e.get("provenance")
            evidence = e.get("evidence") if isinstance(e.get("evidence"), dict) else {}
            verified = e.get("verified") if isinstance(e.get("verified"), list) else []
            cells = [f"<td><strong>{esc(e.get('name', ''))}</strong></td>"]
            for c in columns:
                tier = given if isinstance(given, str) else (given or {}).get(c)
                css = f" t-{tier.lower()}" if tier in TIERS else ""
                claim = evidence.get(c) if isinstance(evidence.get(c), dict) else evidence
                mark, title = "", f' title="{esc(tier)}"' if tier in TIERS else ""
                if tier == "PRIMARY" and checked and c in verified and isinstance(claim.get("quote"), str):
                    url = str(claim.get("source_url") or "")
                    quote = f"“{esc(claim['quote'])}”"
                    title = f' title="PRIMARY, verified: {quote}"'
                    if url.lower().startswith(("http://", "https://")):
                        mark = f'<a class="src" href="{esc(url)}" {REL} title="{quote}">✓</a>'
                    else:
                        mark = f'<span class="src" title="{quote}">✓</span>'
                cells.append(f'<td class="cell{css}"{title}><span class="v">{_value(e["properties"].get(c))}</span>{mark}</td>')
            rows.append("<tr>" + "".join(cells) + "</tr>")
        head = "<th>Instance</th>" + "".join(f"<th>{esc(c)}</th>" for c in columns)
        out.append(f'<div class="branch" id="c-{esc(slug(t["type"]))}"><h3>{esc(t["name"])} '
                   f'<span class="chip">{t["instances"]} instances</span></h3>{_bar(t)}'
                   f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></div>')
    out.append("</section>")
    return "".join(out)


def _conflicts_section(ws):
    tree = Path(ws) / "knowledge" / "tree"
    items = []
    for path in sorted(tree.rglob("*.md")):
        checked = is_checked(ws, path)
        for line in read_text(path).splitlines():
            if "CONFLICT" in line:
                text = line.strip().lstrip("-*").strip()
                items.append(f'<li>{inline(text, checked)} <span class="chip">{esc(path.relative_to(tree).as_posix())}</span></li>')
    if not items:
        return ""
    return ('<section id="conflicts"><h2>Conflicts</h2><p class="lead">Places where sources of equal standing '
            'disagree. Both values were kept for you to decide.</p><div class="card"><div class="body"><ul>'
            + "".join(items) + "</ul></div></div></section>")


def _markdown_section(ws, name, anchor, title, lead, collapse=False):
    path = Path(ws) / "knowledge" / name
    if not path.is_file():
        return ""
    text = read_text(path)
    body = render(text, is_checked(ws, path), heading_offset=2, id_prefix=anchor + "-")
    if collapse:
        body = f'<details><summary>Read the full text ({text.count(chr(10)) + 1} lines)</summary>{body}</details>'
    return (f'<section id="{anchor}"><h2>{title}</h2><p class="lead">{lead}</p>'
            f'<div class="card"><div class="body">{body}</div></div></section>')


def build(ws):
    """Return (html, scorecard)."""
    ws = Path(ws)
    plan = load_plan(ws)
    card = scorecard(ws)
    sections = [_scorecard_section(card), _conflicts_section(ws), _tree_section(ws, card),
                _catalogue_section(ws, card),
                _markdown_section(ws, "spec.md", "survey", "Survey",
                                  "The broad overview written first. Use it to find your way; use the tree for "
                                  "anything exact.", collapse=True),
                _markdown_section(ws, "remaining_unknowns.md", "unknowns", "Remaining unknowns",
                                  "What was looked for and not found, and why each branch stopped.")]
    present = [s for s in sections if s]
    if not card["overall"]["claims"] and len(present) <= 1:
        present = ['<section id="scorecard"><h2>Scorecard</h2><p class="empty">No research yet. '
                   'Run the skill to plan and start it.</p></section>']

    nav = [('scorecard', 'Scorecard', False)]
    if 'id="conflicts"' in "".join(present):
        nav.append(("conflicts", "Conflicts", False))
    if card["branches"]:
        nav.append(("tree", "Knowledge tree", False))
        nav += [("b-" + slug(b["branch"]), "Overview" if b["branch"] == OVERVIEW else b["branch"], True)
                for b in sorted(card["branches"], key=lambda b: (b["branch"] != OVERVIEW, b["branch"]))]
    if card["catalogue"]:
        nav.append(("catalogue", "Catalogue", False))
        nav += [("c-" + slug(t["type"]), t["name"], True) for t in card["catalogue"]]
    for anchor, label in (("survey", "Survey"), ("unknowns", "Remaining unknowns")):
        if f'id="{anchor}"' in "".join(present):
            nav.append((anchor, label, False))
    links = "".join(f'<a class="{"sub" if sub else ""}" href="#{esc(a)}">{esc(label)}</a>' for a, label, sub in nav)

    goal = f'<p class="goal">{esc(plan["goal"])}</p>' if plan.get("goal") else ""
    page = (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(plan["subject"])}</title><style>{CSS}</style></head><body><div class="layout">'
            f'<nav><div class="brand">Research report</div><div class="subject">{esc(plan["subject"])}</div>{links}</nav>'
            f'<main><header><h1>{esc(plan["subject"])}</h1>{goal}'
            f'<div class="meta">Generated {esc(today())} by recursive-research</div></header>'
            f'{"".join(present)}'
            f'<footer>Tiers, strongest first: PRIMARY, EXPERT, SECONDARY, INFERRED, OBSERVED, UNKNOWN. '
            f'A PRIMARY claim marked ✓ was checked by a script against the page it cites.</footer>'
            f'</main></div><script>{JS}</script></body></html>\n')
    return page, card


def write_report(ws):
    page, card = build(ws)
    path = Path(ws) / "report.html"
    write_text(path, page)
    o = card["overall"]
    return {"file": path.as_posix(),
            "scorecard": {k: o[k] for k in ("claims", "verified", "unverified_primary", "unknowns_open", "conflicts")}}
