"""Render a self-contained, clickable HTML Citation Explorer.

No external assets — inline CSS/JS. Every citation is a clickable deep link
(PDF page / slide / video timestamp / web URL / concept). Filter controls narrow
by kind and source type; the source explorer groups citations by resource.
"""

from __future__ import annotations

import html as _h

from ala.explorer.models import CitationIndex

_KIND_COLOR = {"chunk": "#4C72B0", "concept": "#8172B3", "web": "#DD8452"}
_TYPE_ICON = {"pdf": "📄", "slide": "📊", "video": "🎬", "notebook": "📓",
              "web": "🌐", "document": "📃", "concept": "🔗"}


def render(index: CitationIndex, *, title: str = "Citation Explorer") -> str:
    st = index.stats()
    kinds = sorted({n.kind for n in index.nodes})
    types = sorted({n.source_type for n in index.nodes})
    filt = ("".join(f'<button class="f" data-k="kind" data-v="{k}">{k}</button>' for k in kinds) +
            "".join(f'<button class="f" data-k="stype" data-v="{t}">{_TYPE_ICON.get(t,"•")} {t}</button>'
                    for t in types))
    cards = "\n".join(_card(n) for n in index.nodes)
    srcs = "\n".join(
        f'<li><b>{_h.escape(s.title[:60])}</b> <span class="muted">×{s.n_citations}</span>'
        + (f' <a href="{_h.escape(next((n.link for n in index.nodes if n.resource_id==s.resource_id and n.link), ""))}">open</a>'
           if s.resource_id else "") + "</li>"
        for s in index.sources()[:20])
    return _TEMPLATE.format(
        title=_h.escape(title), query=_h.escape(index.query),
        n=st["n_citations"], nsrc=st["n_sources"],
        resolvable=int(st["resolvable_rate"] * 100), loc=int(st["locator_coverage"] * 100),
        filters=filt, cards=cards, sources=srcs)


def _card(n) -> str:
    color = _KIND_COLOR.get(n.kind, "#937860")
    link = _h.escape(n.link)
    head = f'{_TYPE_ICON.get(n.source_type,"•")} <b>[{n.cid}]</b> {_h.escape(n.title[:70])}'
    loc = f'<span class="loc">{_h.escape(n.locator)}</span>' if n.locator else ""
    anchor = f'<a href="{link}" target="_blank">open ↗</a>' if n.resolvable and link else \
        '<span class="muted">unresolved</span>'
    conf = int(n.confidence * 100)
    return f'''<div class="card" data-kind="{n.kind}" data-stype="{n.source_type}" style="border-left:5px solid {color}">
  <div class="row">{head} {loc}</div>
  <div class="snip">{_h.escape(n.text[:240])}</div>
  <div class="row"><div class="bar"><i style="width:{conf}%;background:{color}"></i></div>
  <span class="muted">conf {n.confidence:.2f}</span> {anchor}</div>
</div>'''


_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f6f7f9;color:#222}}
 header{{background:#1f2937;color:#fff;padding:18px 26px}} header h1{{margin:0;font-size:19px}}
 .q{{opacity:.85;margin-top:4px}} .wrap{{display:flex;gap:20px;padding:20px 26px}}
 .main{{flex:3}} .side{{flex:1;min-width:220px}}
 .stats{{display:flex;gap:22px;margin:6px 26px 0;color:#cbd5e1;font-size:13px}}
 .filters{{margin:14px 0}} .f{{border:1px solid #cbd5e1;background:#fff;border-radius:16px;
   padding:5px 12px;margin:3px;cursor:pointer;font-size:13px}} .f.on{{background:#1f2937;color:#fff}}
 .card{{background:#fff;border-radius:10px;padding:12px 14px;margin:10px 0;box-shadow:0 1px 3px #0001}}
 .row{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}} .snip{{color:#555;margin:6px 0;font-size:14px}}
 .loc{{background:#eef2ff;color:#3730a3;border-radius:6px;padding:1px 8px;font-size:12px}}
 .bar{{flex:1;height:7px;background:#e5e7eb;border-radius:4px;overflow:hidden;max-width:200px}}
 .bar i{{display:block;height:100%}} .muted{{color:#94a3b8;font-size:12px}}
 a{{color:#2563eb;text-decoration:none;font-size:13px}} .side ul{{list-style:none;padding:0}}
 .side li{{background:#fff;border-radius:8px;padding:8px 10px;margin:6px 0;font-size:13px}}
</style></head><body>
<header><h1>🔎 {title}</h1><div class="q">{query}</div></header>
<div class="stats"><span>{n} citations</span><span>{nsrc} sources</span>
 <span>{resolvable}% resolvable</span><span>{loc}% located</span></div>
<div class="wrap"><div class="main">
 <div class="filters">{filters} <button class="f on" id="all">all</button></div>
 {cards}
</div><div class="side"><h3>Sources</h3><ul>{sources}</ul></div></div>
<script>
 const cards=[...document.querySelectorAll('.card')];let act={{}};
 function apply(){{cards.forEach(c=>{{let ok=Object.entries(act).every(([k,v])=>!v||c.dataset[k]===v);
   c.style.display=ok?'':'none';}});}}
 document.querySelectorAll('.f').forEach(b=>b.onclick=()=>{{
   if(b.id==='all'){{act={{}};document.querySelectorAll('.f').forEach(x=>x.classList.remove('on'));
     b.classList.add('on');return apply();}}
   document.getElementById('all').classList.remove('on');
   const k=b.dataset.k;act[k]=act[k]===b.dataset.v?'':b.dataset.v;
   document.querySelectorAll('.f[data-k="'+k+'"]').forEach(x=>x.classList.remove('on'));
   if(act[k])b.classList.add('on');apply();}});
</script></body></html>"""
