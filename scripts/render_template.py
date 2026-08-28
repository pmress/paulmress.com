#!/usr/bin/env python3
"""
paulmress.com template renderer (CMS-replacement recommendation #4).

Why a hand-rolled renderer instead of the real Swig template engine: this
sandbox's npm registry access is blocked (403 on any package, confirmed
Aug 2026), so `swig-templates` can't be installed here. This script speaks
a small subset of Swig's own syntax on purpose — {{ var }}, {% include %},
{% if %} — so if a future session ever does have npm access, the template
files themselves need little or no change to move to the real engine.
Until then, this is a dependency-free stand-in.

This does NOT change how the site deploys. It's a local authoring aid:
render a page from a template + a JSON data file, review the output,
then push it through the normal GitHub web-upload flow like any other
page. No build step runs automatically and nothing is wired into CI.

Template syntax:
  {{ dotted.path }}        — variable substitution, looked up in the data
                              dict. A missing path renders as empty string
                              and prints a warning to stderr (catches typos
                              in data files before they ship).
  {% include "rel/path" %} — splices in another template file, resolved
                              relative to the templates/ directory.
                              Included files see the same data dict.
  {% if dotted.path %}...{% endif %}
                            — keeps the enclosed text only if the path
                              resolves to a truthy value (non-empty
                              string, non-empty list/dict, not false/None).
                              Not nestable — each if/endif pair must be
                              self-contained.

List-shaped content (pill rows, step flows, plain-list items) is NOT a
template for-loop — Swig has one, but the separator problem (an arrow
between pills, none after the last) is fiddlier to get right in a tiny
regex engine than it's worth. Instead, this script precomputes a few
known list-shaped fields into ready HTML strings before rendering, so
template files just reference e.g. {{ workflow_traditional_html }} and
data files stay plain lists — the same shape Drive content briefs
already use. See COMPUTE_FIELDS below for the exact mapping.

Usage:
  python3 scripts/render_template.py <template.html> <data.json> [out.html]

If out.html is omitted, the rendered page prints to stdout.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "templates"

INCLUDE_RE = re.compile(r'\{%\s*include\s+"([^"]+)"\s*%\}')
IF_RE = re.compile(r'\{%\s*if\s+([\w.]+)\s*%\}(.*?)\{%\s*endif\s*%\}', re.S)
VAR_RE = re.compile(r'\{\{\s*([\w.]+)\s*\}\}')


def get(data: dict, path: str):
    node = data
    for part in path.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def expand_includes(text: str) -> str:
    def repl(m):
        included_path = TEMPLATES_DIR / m.group(1)
        included_text = included_path.read_text(encoding="utf-8")
        return expand_includes(included_text)  # allow nested includes
    return INCLUDE_RE.sub(repl, text)


def apply_ifs(text: str, data: dict) -> str:
    def repl(m):
        path, body = m.group(1), m.group(2)
        return body if get(data, path) else ""
    return IF_RE.sub(repl, text)


def apply_vars(text: str, data: dict) -> str:
    def repl(m):
        path = m.group(1)
        val = get(data, path)
        if val is None:
            print(f"WARNING: unresolved template variable {{{{ {path} }}}}", file=sys.stderr)
            return ""
        return str(val)
    return VAR_RE.sub(repl, text)


# --- computed list-shaped fields -------------------------------------------

def pill_row(items: list[str]) -> str:
    """A row of .pill spans joined by .pipeline-arrow, no trailing arrow."""
    parts = []
    for i, item in enumerate(items):
        parts.append(f'<span class="pill">{item}</span>')
        if i < len(items) - 1:
            parts.append('<span class="pipeline-arrow" aria-hidden="true">&rarr;</span>')
    return "".join(parts)


def plain_list_items(items: list[str]) -> str:
    return "".join(f"<li>{item}</li>" for item in items)


FLOW_STEP_TMPL = """<div class="flow-step{current_class}">
          <span class="step-icon" aria-hidden="true">
            {icon}
          </span>
          <h3>{title}</h3>
          <p>{body}</p>
        </div>"""


def flow_steps(steps: list[dict]) -> str:
    parts = []
    for i, step in enumerate(steps):
        current_class = " card--current" if step.get("current") else ""
        parts.append(FLOW_STEP_TMPL.format(
            current_class=current_class,
            icon=step.get("icon", ""),
            title=step.get("title", ""),
            body=step.get("body", ""),
        ))
        if i < len(steps) - 1:
            parts.append('\n        <span class="flow-arrow" aria-hidden="true">&rarr;</span>\n        ')
    return "".join(parts)


COMPUTE_FIELDS = {
    "workflow_traditional_html": ("workflow_traditional", pill_row),
    "workflow_experiment_html": ("workflow_experiment", pill_row),
    "tech_tools_html": ("tech_tools", pill_row),
    "ai_handled_html": ("ai_handled", plain_list_items),
    "human_handled_html": ("human_handled", plain_list_items),
    "flow_steps_html": ("flow_steps", flow_steps),
}


def add_computed_fields(data: dict) -> dict:
    data = dict(data)
    for out_key, (in_key, fn) in COMPUTE_FIELDS.items():
        if in_key in data:
            data[out_key] = fn(data[in_key])
    return data


# --- main --------------------------------------------------------------

def render(template_path: Path, data: dict) -> str:
    data = add_computed_fields(data)
    text = template_path.read_text(encoding="utf-8")
    text = expand_includes(text)
    text = apply_ifs(text, data)
    text = apply_vars(text, data)
    return text


def main():
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        sys.exit(2)

    template_path = Path(sys.argv[1])
    data_path = Path(sys.argv[2])
    out_path = Path(sys.argv[3]) if len(sys.argv) == 4 else None

    data = json.loads(data_path.read_text(encoding="utf-8"))
    output = render(template_path, data)

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Rendered {template_path} + {data_path} -> {out_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
