#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle

DEFAULT_FILES = [
    "app.py",
    "static/style.css",
    "templates/admin_assign.html",
    "templates/admin_delete_student_confirm.html",
    ".env.example",
]


def detect_kind(path: Path) -> str:
    if path.name == ".env.example":
        return "env"
    s = path.suffix.lower()
    if s == ".py":
        return "python"
    if s in {".html", ".htm"}:
        return "html"
    if s == ".css":
        return "css"
    return "text"


def explain_env(s: str) -> str:
    if not s:
        return "Blank line used to separate groups of environment variables."
    if s.startswith("#"):
        return "Comment describing the environment variables below."
    if "=" not in s:
        return "Raw config text. Most lines in this file are expected as KEY=VALUE."
    key, val = s.split("=", 1)
    val_text = "empty value" if val == "" else f"example value `{val}`"
    hints = {
        "SECRET_KEY": "Flask secret key used for signing session cookies",
        "DB_HOST": "database host name",
        "DB_USER": "database username",
        "DB_PASSWORD": "database password",
        "DB_NAME": "database/schema name",
        "DB_PORT": "database TCP port",
        "SEED_ADMIN_NAME": "default name for seeded admin account",
        "SEED_ADMIN_EMAIL": "default email for seeded admin account",
        "SEED_ADMIN_PASSWORD": "default password for seeded admin account",
    }
    return f"Sets `{key}` ({hints.get(key, 'application setting')}) with {val_text}."


def explain_python(s: str) -> str:
    if not s:
        return "Blank line used to separate logical blocks of Python code."
    if s.startswith("#"):
        return "Comment line used to document intent or create section dividers."
    if s.startswith("@app.route"):
        return "Flask route decorator: binds the next function to a URL endpoint."
    if s.startswith("@"):
        return "Decorator that changes behavior of the next function/class."
    if s.startswith(("from ", "import ")):
        return "Import statement: loads modules or symbols needed in this file."
    m = re.match(r"class\s+([A-Za-z_]\w*)", s)
    if m:
        return f"Class declaration for `{m.group(1)}`."
    m = re.match(r"def\s+([A-Za-z_]\w*)\s*\((.*)\)\s*:", s)
    if m:
        params = m.group(2).strip() or "no parameters"
        return f"Function definition `{m.group(1)}` with {params}."
    if s.startswith("if ") and s.endswith(":"):
        return "Starts an `if` block that runs only when its condition is true."
    if s.startswith("elif ") and s.endswith(":"):
        return "Starts an `elif` branch checked when previous conditions are false."
    if s == "else:":
        return "Fallback `else` branch for the current conditional."
    if s.startswith("for ") and s.endswith(":"):
        return "Starts a `for` loop over an iterable sequence."
    if s.startswith("while ") and s.endswith(":"):
        return "Starts a `while` loop that repeats while condition is true."
    if s.startswith("try:"):
        return "Starts a `try` block for exception-safe execution."
    if s.startswith("except"):
        return "Exception handler for errors raised in the matching `try` block."
    if s == "finally:":
        return "`finally` block: cleanup code that runs whether or not errors occur."
    if s.startswith("with ") and s.endswith(":"):
        return "Context manager block that handles resource setup and cleanup."
    if s.startswith("return"):
        return "Returns a value (or nothing) from the current function."
    if ".execute(" in s:
        return "Executes a SQL query/command using the active database cursor."
    if any(x in s for x in (".fetchone()", ".fetchall()")):
        return "Reads query results from the cursor."
    if ".commit()" in s:
        return "Commits the active database transaction."
    if ".close()" in s:
        return "Closes a resource such as a cursor, connection, or file."
    if re.match(r"[A-Za-z_][\w\.\[\]'\"]*\s*=\s*.+", s):
        return "Assignment statement: stores the expression result in a variable/field."
    if re.match(r"[A-Za-z_]\w*\(.*\)\s*$", s):
        return "Function/method call that performs an action at runtime."
    return "General Python statement that participates in program control flow."


def explain_html(s: str) -> str:
    if not s:
        return "Blank line used to separate template sections."
    if s.startswith("{#") and s.endswith("#}"):
        return "Jinja comment; ignored when rendering HTML."
    if s.startswith("{%") and s.endswith("%}"):
        directive = s[2:-2].strip()
        kw = directive.split(" ", 1)[0]
        hints = {
            "extends": "template inheritance: chooses parent layout",
            "block": "starts a named block",
            "endblock": "ends a named block",
            "for": "starts a template loop",
            "endfor": "ends a template loop",
            "if": "starts a conditional branch",
            "elif": "additional conditional branch",
            "else": "fallback conditional branch",
            "endif": "ends conditional block",
            "include": "inserts another template here",
            "set": "creates/updates a template variable",
        }
        return f"Jinja control statement (`{kw}`): {hints.get(kw, 'template flow control')}."
    if s.startswith("{{") and s.endswith("}}"):
        return "Jinja expression output: injects dynamic data into HTML."
    tag = re.search(r"<\s*(/)?\s*([A-Za-z0-9:_-]+)([^>]*)>", s)
    if tag:
        closing = bool(tag.group(1))
        name = tag.group(2).lower()
        attrs = tag.group(3)
        if closing:
            return f"Closing HTML tag `</{name}>`."
        bits = []
        if "class=" in attrs:
            bits.append("adds CSS classes")
        if "href=" in attrs:
            bits.append("defines a link target")
        if "method=" in attrs:
            bits.append("sets form HTTP method")
        if "name=" in attrs:
            bits.append("sets form field name")
        if "required" in attrs:
            bits.append("marks field as required")
        suffix = f" and {', '.join(bits)}" if bits else ""
        return f"Opening HTML tag `<{name}>`{suffix}."
    if "{{" in s and "}}" in s:
        return "HTML line containing embedded Jinja dynamic expression(s)."
    return "Static HTML content rendered directly to the browser."


def explain_css(s: str) -> str:
    if not s:
        return "Blank line used to group related style declarations."
    if s.startswith("/*") or s.endswith("*/") or s.startswith("*"):
        return "CSS comment used to document the stylesheet."
    if s.startswith("@import"):
        return "Imports external stylesheet content (for example web fonts)."
    if s.startswith("@media"):
        return "Starts a media query block for responsive behavior."
    if s.startswith("@keyframes"):
        return "Starts a keyframes animation definition."
    if s.endswith("{"):
        return "Opens a CSS rule block for the selector on this line."
    if s == "}":
        return "Closes the current CSS rule block."
    m = re.match(r"([-\w]+)\s*:\s*(.+?);$", s)
    if m:
        prop, val = m.group(1), m.group(2)
        if prop.startswith("--"):
            return f"Defines CSS custom property `{prop}` with value `{val}`."
        return f"Sets CSS property `{prop}` to `{val}` for the active selector."
    if re.match(r"([-\w]+)\s*:\s*(.*)$", s):
        return "Starts a multi-line CSS property value that continues on next lines."
    return "CSS selector/value syntax line used by nearby declarations."


def explain_line(line: str, kind: str) -> str:
    s = line.strip()
    if kind == "python":
        return explain_python(s)
    if kind == "html":
        return explain_html(s)
    if kind == "css":
        return explain_css(s)
    if kind == "env":
        return explain_env(s)
    return "Source line."


def build_pdf(files: list[Path], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output),
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    styles = getSampleStyleSheet()
    title = styles["Title"]
    subtitle = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=9, spaceAfter=6)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=7, leading=8.5)
    code = ParagraphStyle("Code", parent=body, fontName="Courier")

    story = [
        Paragraph("NCIT SIS - Line-by-Line Code Explanation", title),
        Paragraph("Each row explains one line of source code in plain English.", subtitle),
        Spacer(1, 3 * mm),
    ]

    for i, path in enumerate(files):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        kind = detect_kind(path)

        story.append(Paragraph(f"<b>File:</b> {path.as_posix()}  (<b>Lines:</b> {len(lines)})", styles["Heading3"]))
        rows = [[Paragraph("<b>Line</b>", body), Paragraph("<b>Code</b>", body), Paragraph("<b>Explanation</b>", body)]]

        for ln, raw in enumerate(lines, start=1):
            code_line = raw.expandtabs(4)
            if code_line == "":
                code_line = " "
            rows.append(
                [
                    Paragraph(str(ln), body),
                    Paragraph(html.escape(code_line), code),
                    Paragraph(html.escape(explain_line(raw, kind)), body),
                ]
            )

        table = LongTable(rows, colWidths=[16 * mm, 118 * mm, 145 * mm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(table)
        if i < len(files) - 1:
            story.append(PageBreak())

    doc.build(story)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate line-by-line code explanation PDF.")
    parser.add_argument("--files", nargs="+", default=DEFAULT_FILES, help="List of files to explain")
    parser.add_argument("--output", default="docs/line_by_line_code_explanation.pdf", help="Output PDF path")
    args = parser.parse_args()

    files = [Path(f) for f in args.files]
    missing = [f.as_posix() for f in files if not f.exists()]
    if missing:
        raise FileNotFoundError(f"Missing file(s): {', '.join(missing)}")

    build_pdf(files, Path(args.output))
    print(f"Created: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
