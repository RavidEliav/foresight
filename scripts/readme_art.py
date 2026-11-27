"""Phase 9: the README's art in the app's own look (docs/images): the banner (the sign-in
page's wordmark, whose "o" is the wafer logo), the pipeline, the deployment and the headline
results. Each is a small HTML page with the app's colours, fonts, die grid and glass cards
(app/ui.py), drawn by a browser at twice the size and saved as WebP with rounded corners.

    python scripts/readme_art.py [--out docs/images]
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from app import stepper, ui  # noqa: E402

WIDTH = 900  # GitHub shows a README about this wide; drawn at 2x
FONTS = ("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&"
         "family=Space+Grotesk:wght@500;600;700&display=swap")
CYAN, VIOLET, AMBER, GREEN = "#22D3EE", "#A78BFA", "#FBBF24", "#34D399"

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{fonts}">
<style>{app_css}</style>
<style>
html, body {{ margin: 0; background: transparent; }}
body {{ font-family: Inter, sans-serif; color: #DCE4F0; width: {width}px; }}
.frame {{ border-radius: 18px; overflow: hidden; padding: {pad};
  background:
    radial-gradient(520px 300px at 4% -10%, rgba(34,211,238,.18), transparent 62%),
    radial-gradient(480px 300px at 104% 6%, rgba(167,139,250,.16), transparent 58%),
    radial-gradient(420px 240px at 55% 112%, rgba(251,191,36,.07), transparent 60%),
    linear-gradient(rgba(148,163,184,.045) 1px, transparent 1px) 0 0 / 32px 32px,
    linear-gradient(90deg, rgba(148,163,184,.045) 1px, transparent 1px) 0 0 / 32px 32px,
    #070B14;
  border: 1px solid rgba(255,255,255,.08); }}
.glass {{ background: var(--fs-glass); border: 1px solid var(--fs-glass-border);
  border-top-color: var(--fs-glass-top); box-shadow: var(--fs-glass-shadow);
  border-radius: 16px; }}
.label {{ font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: #7DD3FC;
  font-weight: 600; }}
{extra}
</style></head><body><div class="frame">{body}</div></body></html>"""


def app_css() -> str:
    """The app's own style sheet (app/ui.py), without Streamlit's selectors mattering here."""
    return re.search(r"<style>(.*)</style>", ui.STYLE, re.S).group(1)


def icon(name: str, color: str = CYAN) -> str:
    """A stage's drawing from the New analysis page, in one colour, still."""
    css = stepper.BASE_CSS % (color, color) + stepper.DONE_CSS
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 44"><style>{css}</style>'
           f'{stepper.ART[name]}</svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def banner() -> tuple[str, str, str]:
    extra = """.fs-hero { padding: 6px 0 0 0; }
.fs-pitch { max-width: 600px; margin: 0 auto .9rem auto !important; text-wrap: balance; }
.fs-benefits { margin-bottom: 4px; }"""
    return ui.hero_html(), extra, "34px 40px 30px"


STAGES = [("ingest", "1 · Load and check", "Data Contract · no AI"),
          ("analyze", "2 · EDA and features", "AI data analyst"),
          ("model", "3 · Models", "AI data scientist"),
          ("investigate", "4 · Investigation", "AI investigator"),
          ("report", "5 · Report", "AI report writer")]
CHECK_AFTER = {"ingest", "analyze", "investigate"}


def pipeline() -> tuple[str, str, str]:
    tiles = []
    for i, (name, title, role) in enumerate(STAGES):
        tiles.append(f'<div class="glass tile"><img src="{icon(name)}">'
                     f'<div class="t">{title}</div><div class="r">{role}</div></div>')
        if i < len(STAGES) - 1:
            gate = name in CHECK_AFTER
            tiles.append(f'<div class="link{" gate" if gate else ""}">'
                         f'{"<span>check</span>" if gate else ""}</div>')
    body = f"""
<div class="row"><div class="glass pill">SECOM or an uploaded CSV</div></div>
<div class="down"></div>
<div class="flow"><div class="label">CrewAI Flow · about 2.5 minutes</div>
  <div class="tiles">{''.join(tiles)}</div></div>
<div class="down"></div>
<div class="row"><div class="glass pill">Run files · PDF reports · chat index (embeddings)</div>
  <div class="arrow"></div><div class="glass pill">Streamlit app · Ask Foresight</div></div>"""
    extra = f""".row {{ display: flex; justify-content: center; align-items: center; }}
.pill {{ padding: 10px 18px; font-weight: 600; font-size: 14px; color: #E2E8F0;
  border-radius: 999px; }}
.down {{ width: 2px; height: 18px; margin: 0 auto; background: rgba(148,163,184,.4); }}
.arrow {{ width: 28px; height: 2px; background: rgba(148,163,184,.4); margin: 0 8px; }}
.flow {{ border: 1px solid rgba(34,211,238,.35); border-radius: 18px; padding: 14px 14px 16px;
  background: rgba(34,211,238,.04); }}
.flow .label {{ text-align: center; margin-bottom: 12px; }}
.tiles {{ display: flex; align-items: stretch; }}
.tile {{ flex: 1 1 0; min-width: 0; padding: 12px 10px 12px; text-align: center;
  border-color: rgba(34,211,238,.45);
  background: linear-gradient(135deg, rgba(34,211,238,.13), rgba(255,255,255,.02)); }}
.tile img {{ width: 100%; height: 40px; margin-bottom: 8px; }}
.t {{ font-family: 'Space Grotesk', sans-serif; font-weight: 600; font-size: 12.8px;
  color: #F1F5F9; white-space: nowrap; }}
.r {{ font-size: 12px; color: #94A3B8; margin-top: 3px; white-space: nowrap; }}
.link {{ flex: 0 0 34px; align-self: center; height: 2px; background: rgba(148,163,184,.3);
  position: relative; }}
.gate {{ background: {GREEN}; }}
.gate::after {{ content: ""; position: absolute; left: 50%; top: 50%; width: 8px; height: 8px;
  border-radius: 2px; transform: translate(-50%, -50%) rotate(45deg); background: {GREEN}; }}
.gate span {{ position: absolute; left: 50%; bottom: 8px; transform: translateX(-50%);
  font-size: 10px; color: {GREEN}; font-weight: 600; }}"""
    return body, extra, "20px 22px 22px"


def block(name: str, detail: str, color: str = CYAN) -> str:
    return (f'<div class="glass blk" style="--c:{color}"><div class="n">{name}</div>'
            f'<div class="d">{detail}</div></div>')


DEPLOY_CSS = """.grid { display: grid; grid-template-columns: 1fr 110px 1fr 110px 1fr;
  align-items: center; }
.blk { padding: 14px 16px; text-align: center;
  border-color: color-mix(in srgb, var(--c) 55%, transparent);
  background: linear-gradient(135deg, color-mix(in srgb, var(--c) 16%, transparent),
  rgba(255,255,255,.02)); }
.n { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 17px;
  color: #F1F5F9; }
.d { font-size: 12.5px; color: #94A3B8; margin-top: 3px; white-space: nowrap; }
.edge { height: 2px; background: rgba(148,163,184,.4); position: relative; margin: 0 6px; }
.edge::after { content: ""; position: absolute; right: -1px; top: -4px;
  border: 5px solid transparent;
  border-left: 7px solid rgba(148,163,184,.6); border-right: 0; }
.edge span, .vert span { position: absolute; left: 50%; bottom: 7px; transform: translateX(-50%);
  font-size: 11px; color: #CBD5E1; white-space: nowrap; }
.vert { width: 2px; height: 46px; background: rgba(148,163,184,.4); justify-self: center;
  position: relative; }
.vert::after { content: ""; position: absolute; left: -4px; bottom: -1px;
  border: 5px solid transparent;
  border-top: 7px solid rgba(148,163,184,.6); border-bottom: 0; }
.vert span { left: 12px; bottom: 50%; transform: translateY(50%); }"""


def deployment() -> tuple[str, str, str]:
    body = f"""
<div class="grid">
  {block("GitHub", "feature → dev → main", VIOLET)}
  <div class="edge"><span>CI + E2E</span></div>
  {block("Railway", "dev and main apps")}
  <div class="edge"><span>crews + chat</span></div>
  {block("OpenAI", "gpt-4o-mini", AMBER)}
  <div class="vert"><span>after each deploy</span></div><div></div>
  <div class="vert"><span>runs, accounts, chat</span></div><div></div><div></div>
  {block("Deployed tests", "smoke + E2E on the live apps", VIOLET)}<div></div>
  {block("Supabase", "Postgres + pgvector · Storage", GREEN)}<div></div><div></div>
</div>"""
    return body, DEPLOY_CSS, "22px 24px"


TILES = [("Failing runs caught", "5 of 24", "with 40 alarms", CYAN),
         ("Alarm precision", "12.5%", "2× the fail rate", CYAN),
         ("Report checks", "26 of 26", "passed", GREEN),
         ("A full analysis", "2.5 min", "under 1 US cent", VIOLET)]


def results() -> tuple[str, str, str]:
    tiles = "".join(f'<div class="glass kpi"><div class="label">{label}</div>'
                    f'<div class="v">{value}</div><div class="s" style="--c:{color}">{sub}</div>'
                    f"</div>" for label, value, sub, color in TILES)
    extra = """.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.kpi { padding: 12px 14px 13px; }
.kpi .label { color: #94A3B8; font-size: 10.5px; }
.v { font-family: 'Space Grotesk', sans-serif; font-weight: 600; font-size: 30px; color: #F1F5F9;
  margin: 4px 0 6px; }
.s { display: inline-block; font-size: 12px; padding: 1px 8px; border-radius: 6px;
  color: var(--c); background: color-mix(in srgb, var(--c) 14%, transparent); }"""
    return f'<div class="kpis">{tiles}</div>', extra, "16px"


def rag() -> tuple[str, str, str]:
    def row(blocks, color):
        cells = []
        for i, (name, detail) in enumerate(blocks):
            cells.append(block(name, detail, color))
            if i < len(blocks) - 1:
                cells.append('<div class="edge"></div>')
        return f'<div class="row4">{"".join(cells)}</div>'
    index = row([("Reports + run data", "documents and tables as text"),
                 ("Chunks", "by section, 800 characters"),
                 ("Embeddings", "all-MiniLM-L6-v2 · 384-d"),
                 ("Index", "per analysis · pgvector for all")], CYAN)
    ask = row([("Question", "this analysis or all of them"),
               ("Hybrid retrieval", "cosine + section-title bonus"),
               ("gpt-4o-mini", "answers only from excerpts"),
               ("Guards", "sources, numbers, no leaks")], VIOLET)
    inside = (block("Similar past runs", "each run's sensor profile, the 5 nearest past runs",
                    AMBER)
              + block("Background knowledge", "12 documents, cited by the AI investigator",
                      AMBER))
    body = f"""
<div class="label">At the end of each analysis: its chat index</div>{index}
<div class="label">Ask Foresight: each question</div>{ask}
<div class="label">Retrieval inside the analysis</div><div class="row2">{inside}</div>"""
    extra = """.label { margin: 4px 0 8px 2px; } .label ~ .label { margin-top: 16px; }
.row4 { display: grid; grid-template-columns: 1fr 30px 1fr 30px 1fr 30px 1fr;
  align-items: stretch; }
.row4 .edge { align-self: center; margin: 0 4px; }
.row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }
.blk { padding: 11px 10px; }
.n { font-size: 15px; } .d { white-space: normal; font-size: 12px; line-height: 1.35; }"""
    return body, DEPLOY_CSS + extra, "18px 20px 20px"


ART = {"banner": banner, "pipeline": pipeline, "deployment": deployment, "rag": rag,
       "results": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "images")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    css = app_css()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": 400}, device_scale_factor=2)
        for name, make in ART.items():
            body, extra, pad = make()
            page.set_content(PAGE.format(fonts=FONTS, app_css=css, width=WIDTH, pad=pad,
                                         extra=extra, body=body), wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(500)
            png = page.locator(".frame").screenshot(omit_background=True,
                                                    animations="disabled")
            Image.open(BytesIO(png)).save(args.out / f"{name}.webp", "WEBP", quality=92,
                                          method=6)
            print("saved", name)
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
