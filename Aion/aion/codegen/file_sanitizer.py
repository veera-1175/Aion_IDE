"""Clean and validate LLM-generated file contents before writing to disk."""

from __future__ import annotations

import re
from pathlib import Path

# Wrong LLM filenames -> actual files on disk
WEB_ASSET_ALIASES: dict[str, str] = {
    "style.css": "styles.css",
    "calendar_js.js": "script.js",
}

VALID_PATH = re.compile(r"^[\w][\w./-]*\.[a-zA-Z0-9]+$")


def is_valid_path(path: str) -> bool:
    p = path.replace("\\", "/").strip()
    if not p or "\n" in p or "<" in p:
        return False
    return bool(VALID_PATH.match(p)) or p in ("README.md", "LICENSE")


def sanitize_content(path: str, content: str) -> str:
    """Remove JSON artifacts and extract real source from malformed LLM output."""
    if not content:
        return content

    text = content.strip()

    # Strip accidental JSON object wrapper around file body
    if text.startswith('{"') and (path.endswith(".html") or path.endswith(".css") or path.endswith(".js")):
        text = text[2:]
    if text.endswith('"}') or text.endswith('"}"'):
        text = re.sub(r'"\}?\s*$', "", text)
    if text.startswith('"') and text.endswith('"') and len(text) > 2:
        text = text[1:-1]

    if path.endswith(".html"):
        m = re.search(r"(<!DOCTYPE[\s\S]*?</html>)", text, re.IGNORECASE)
        if m:
            text = m.group(1)
        elif "<html" in text.lower():
            m = re.search(r"(<html[\s\S]*?</html>)", text, re.IGNORECASE)
            if m:
                text = m.group(1)

    if path.endswith(".css"):
        # Extract CSS from JSON garbage like {"body { ... }}"}
        m = re.search(r"(\{[\s\S]*\})", text)
        if m and ("{" in text[:5] or '"' in text[:3]):
            text = m.group(1)
        text = text.replace("m\nths", "months").replace("m ths", "months")

    if path.endswith(".js"):
        m = re.search(r"(<script[\s\S]*?</script>)", text, re.IGNORECASE)
        if m and text.strip().startswith("{"):
            text = m.group(1)
        elif text.startswith('{"') or text.startswith("<script"):
            text = re.sub(r"^\{[\"']?", "", text)
            text = re.sub(r"[\"']?\}$", "", text)

    return text.replace("\\n", "\n").replace("\\t", "\t")


def normalize_files(files: dict[str, str]) -> dict[str, str]:
    """
    Fix LLM mistakes: content placed in JSON keys, wrong paths, broken wrappers.
    """
    out: dict[str, str] = {}

    for key, value in files.items():
        k = str(key).replace("\\", "/").strip()
        v = sanitize_content(k, str(value) if value is not None else "")

        if is_valid_path(k):
            out[k] = sanitize_content(k, v if v else k)
            continue

        # Key is file content, not a path (Groq bug)
        if re.search(r"<!DOCTYPE|<html", k, re.I):
            out["index.html"] = sanitize_content("index.html", k)
            if v and len(v) > 30 and not v.startswith("{"):
                if "{" in v and ":" in v:
                    out["styles.css"] = sanitize_content("styles.css", v)
        elif k.strip().startswith("<script") or "function " in k:
            out["script.js"] = sanitize_content("script.js", k)
        elif re.search(r"\{[\s\S]*\}", k) and ("body" in k or "#" in k or "." in k):
            out["styles.css"] = sanitize_content("styles.css", k)
        elif v and is_valid_path(k):
            out[k] = v

    # Rename common mismatches
    if "style.css" in out and "styles.css" not in out:
        out["styles.css"] = out.pop("style.css")
    if "calendar_js.js" in out and "script.js" not in out:
        out["script.js"] = out.pop("calendar_js.js")

    if "index.html" in out:
        out["index.html"] = repair_html_asset_links(out["index.html"], out)

    return out


def repair_html_asset_links(html: str, files: dict[str, str] | None = None, project_dir: Path | None = None) -> str:
    """Fix LLM typos: href=style.css when styles.css exists, wrong script names, etc."""
    names = set((files or {}).keys())
    if project_dir and project_dir.is_dir():
        names |= {p.name for p in project_dir.iterdir() if p.is_file()}

    text = html
    if "styles.css" in names and "style.css" not in names:
        text = re.sub(r"""href\s*=\s*["']style\.css["']""", 'href="styles.css"', text, flags=re.I)
    if "style.css" in names and "styles.css" not in names:
        text = re.sub(r"""href\s*=\s*["']styles\.css["']""", 'href="style.css"', text, flags=re.I)
    if "script.js" in names:
        text = re.sub(
            r"""src\s*=\s*["']calendar_js\.js["']""", 'src="script.js"', text, flags=re.I
        )
    return text


def resolve_web_asset(project_dir: Path, rel: str) -> Path | None:
    """Return path to an existing asset, following WEB_ASSET_ALIASES when needed."""
    project_dir = project_dir.resolve()
    rel = rel.replace("\\", "/").lstrip("/")
    target = (project_dir / rel).resolve()
    if str(target).startswith(str(project_dir)) and target.is_file():
        return target
    alt_name = WEB_ASSET_ALIASES.get(rel)
    if alt_name:
        alt = (project_dir / alt_name).resolve()
        if str(alt).startswith(str(project_dir)) and alt.is_file():
            return alt
    return None


def inject_preview_base(html: str, base_href: str = "/preview/") -> str:
    """Ensure relative CSS/JS resolve under /preview/ even without a trailing slash."""
    if re.search(r"<base\s", html, re.I):
        return html
    return re.sub(
        r"(<head[^>]*>)",
        rf'\1\n<base href="{base_href}">',
        html,
        count=1,
        flags=re.I,
    )


def repair_project_on_disk(project_dir: Path) -> list[str]:
    """Patch index.html on disk so CSS/JS links match real filenames."""
    project_dir = project_dir.resolve()
    index = project_dir / "index.html"
    if not index.is_file():
        return []
    names = {p.name for p in project_dir.iterdir() if p.is_file()}
    original = index.read_text(encoding="utf-8")
    fixed = repair_html_asset_links(original, project_dir=project_dir)
    changes: list[str] = []
    if fixed != original:
        index.write_text(fixed, encoding="utf-8")
        changes.append("index.html (fixed CSS/JS links)")
    return changes


def validate_web_project(files: dict[str, str]) -> list[str]:
    errors = []
    html = files.get("index.html", "")
    if not html:
        errors.append("missing index.html")
    elif not re.search(r"<!DOCTYPE\s+html|<html", html, re.I):
        errors.append("index.html is not valid HTML")
    elif html.strip().startswith("{") or '"<!DOCTYPE' in html[:20]:
        errors.append("index.html still contains JSON wrapper")

    css = files.get("styles.css") or files.get("style.css", "")
    if css and css.strip().startswith('{"'):
        errors.append("styles.css contains JSON wrapper")

    return errors


def ensure_calendar_html_links(files: dict[str, str]) -> dict[str, str]:
    """Fix broken LLM HTML/CSS/JS — self-contained vanilla calendar."""
    files = dict(files)
    html = files.get("index.html", "")
    script = files.get("script.js", "")
    css = files.get("styles.css", "")

    broken = (
        validate_web_project(files)
        or "FullCalendar" in script
        or "dayjs" in script
        or (css and css.strip().startswith("{"))
    )

    if broken:
        files["index.html"] = _vanilla_calendar_html()
        files["styles.css"] = _vanilla_calendar_css()
        files["script.js"] = _vanilla_calendar_js()
        return files

    for lib in ("fullcalendar", "dayjs", "moment.js"):
        if lib.lower() in html.lower():
            files["index.html"] = _vanilla_calendar_html()
            files["styles.css"] = _vanilla_calendar_css()
            files["script.js"] = _vanilla_calendar_js()
            return files

    files["index.html"] = html.replace("calendar_js.js", "script.js")
    if not css or css.strip().startswith("{"):
        files["styles.css"] = _vanilla_calendar_css()
    if not script:
        files["script.js"] = _vanilla_calendar_js()

    return files


def _vanilla_calendar_css() -> str:
    return """* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Segoe UI", system-ui, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 1rem; }
.app { background: #1e293b; border-radius: 12px; padding: 1.25rem; width: min(100%, 380px); box-shadow: 0 12px 32px rgba(0,0,0,.4); }
header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
header button { background: #38bdf8; border: none; color: #0f172a; width: 32px; height: 32px; border-radius: 6px; cursor: pointer; font-weight: bold; }
#monthLabel { font-size: 1.1rem; }
.weekdays { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; font-size: 0.7rem; color: #94a3b8; margin-bottom: 0.35rem; }
#grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.day { aspect-ratio: 1; display: flex; align-items: center; justify-content: center; border-radius: 6px; background: #334155; font-size: 0.85rem; }
.day.other { opacity: 0.35; }
.day.today { background: #f97316; color: #fff; font-weight: 700; }
"""


def _vanilla_calendar_js() -> str:
    return """const monthLabel = document.getElementById("monthLabel");
const grid = document.getElementById("grid");
let view = new Date();

function render() {
  const y = view.getFullYear();
  const m = view.getMonth();
  monthLabel.textContent = view.toLocaleString("default", { month: "long", year: "numeric" });
  grid.innerHTML = "";
  const first = new Date(y, m, 1);
  const start = first.getDay();
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const today = new Date();
  for (let i = 0; i < start; i++) {
    const c = document.createElement("div");
    c.className = "day other";
    grid.appendChild(c);
  }
  for (let d = 1; d <= daysInMonth; d++) {
    const c = document.createElement("div");
    c.className = "day";
    c.textContent = d;
    if (d === today.getDate() && m === today.getMonth() && y === today.getFullYear()) c.classList.add("today");
    grid.appendChild(c);
  }
}
document.getElementById("prev").onclick = () => { view.setMonth(view.getMonth() - 1); render(); };
document.getElementById("next").onclick = () => { view.setMonth(view.getMonth() + 1); render(); };
render();
"""


def _vanilla_calendar_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Calendar</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <div class="app">
    <header>
      <button id="prev" type="button" aria-label="Previous month">&larr;</button>
      <h1 id="monthLabel"></h1>
      <button id="next" type="button" aria-label="Next month">&rarr;</button>
    </header>
    <div class="weekdays">
      <span>Sun</span><span>Mon</span><span>Tue</span><span>Wed</span>
      <span>Thu</span><span>Fri</span><span>Sat</span>
    </div>
    <div id="grid"></div>
  </div>
  <script src="script.js"></script>
</body>
</html>
"""
