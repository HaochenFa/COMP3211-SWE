"""Build the group presentation deck, docs/05-presentation/presentation-slides.pptx.

Presentation tooling only, not part of the PIM implementation: it needs the
third-party package python-pptx (`pip install python-pptx`). Run it from the
repository root:

    python3 docs/05-presentation/build_deck.py

The deck has 11 slides in four speaker sections (A–D) of about 70 seconds each,
with a timed script in the speaker notes of every slide. Speaker A is the
first member in docs/group.yaml, B the second, and so on. The
top-right corner of every slide is left empty for the presenter's webcam.

The two clips in docs/_media/ were cut, without sound, from the system video
(dist/demo.mp4, made by docs/_video/render.py):

    ffmpeg -ss 16.56 -to 30.40 -i dist/demo.mp4 -an \\
        -vf "setpts=PTS/1.3,scale=1280:-2,fps=30" -c:v libx264 -crf 22 \\
        -pix_fmt yuv420p -movflags +faststart docs/_media/clip-create-task.mp4
    ffmpeg -ss 104.80 -to 117.90 -i dist/demo.mp4 -an \\
        -vf "scale=1280:-2,fps=30" -c:v libx264 -crf 22 \\
        -pix_fmt yuv420p -movflags +faststart docs/_media/clip-combined-search.mp4
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MEDIA = ROOT / "docs" / "_media"
OUT = HERE / "presentation-slides.pptx"
GROUP_FILE = ROOT / "docs" / "group.yaml"

# ---------------------------------------------------------------- design tokens
NAVY = RGBColor(0x1F, 0x3A, 0x5F)
BLUE = RGBColor(0x2F, 0x5E, 0x8E)
INK = RGBColor(0x1B, 0x23, 0x2C)
MUTED = RGBColor(0x5A, 0x65, 0x73)
LINE = RGBColor(0xC7, 0xCF, 0xD9)
TINT = RGBColor(0xEE, 0xF2, 0xF7)
TINT2 = RGBColor(0xF7, 0xF9, 0xFB)
AMBER = RGBColor(0xC8, 0x7A, 0x1E)
AMBER_TINT = RGBColor(0xFB, 0xF1, 0xE3)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

BODY = "Calibri"
CODE = "Consolas"

SLIDE_W, SLIDE_H = 13.333, 7.5
MX = 0.6                 # left and right margin
TITLE_W = 9.2            # titles stop before the webcam corner (x > 10.1, y < 2.1)
TOTAL_SLIDES = 11


# ---------------------------------------------------------------- group details
def read_group(path: Path) -> dict:
    """Read the small YAML file of title-page details without a YAML library."""
    data: dict = {"members": []}
    member: dict | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip() if not raw.lstrip().startswith('"') else raw
        if not line.strip():
            continue
        match = re.match(r'^(\s*)(-\s+)?([\w-]+):\s*"?(.*?)"?\s*$', line)
        if not match:
            continue
        indent, dash, key, value = match.groups()
        if key == "members" and not value:
            continue
        if dash:
            member = {}
            data["members"].append(member)
        if indent and member is not None:
            member[key] = value
        else:
            data[key] = value
    return data


GROUP = read_group(GROUP_FILE)
MEMBERS = GROUP["members"] + [{"name": "[Member name]", "id": "[Student ID]"}] * 4
SPEAKERS = {letter: MEMBERS[i]["name"] for i, letter in enumerate("ABCD")}


# ---------------------------------------------------------------- low-level helpers
def _strip_style(shape) -> None:
    """Drop the theme style reference so a shape has no theme shadow or outline."""
    style = shape._element.find(qn("p:style"))
    if style is not None:
        shape._element.remove(style)


def _runs(paragraph, text: str, *, size: float, color: RGBColor, bold: bool,
          italic: bool, font: str) -> None:
    """Add runs to a paragraph; `code` spans use the code font, **bold** spans are bold."""
    for part in re.split(r"(`[^`]+`|\*\*[^*]+\*\*)", text):
        if not part:
            continue
        run = paragraph.add_run()
        run_font, run_bold, run_color = font, bold, color
        if part.startswith("`"):
            part, run_font, run_color = part[1:-1], CODE, NAVY if color != WHITE else WHITE
        elif part.startswith("**"):
            part, run_bold = part[2:-2], True
        run.text = part
        f = run.font
        f.name, f.size, f.bold, f.italic = run_font, Pt(size), run_bold, italic
        f.color.rgb = run_color


def _fill_frame(frame, paras, *, size=16, color=INK, bold=False, italic=False,
                font=BODY, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
                space_after=0.0, line_spacing=None, margins=(0, 0, 0, 0)) -> None:
    frame.word_wrap = True
    frame.margin_left, frame.margin_top, frame.margin_right, frame.margin_bottom = (
        Inches(m) for m in margins
    )
    frame.vertical_anchor = anchor
    if isinstance(paras, str):
        paras = [paras]
    for i, para in enumerate(paras):
        p = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        p.alignment = align
        if space_after:
            p.space_after = Pt(space_after)
        if line_spacing:
            p.line_spacing = line_spacing
        opts = {}
        if isinstance(para, tuple):
            para, opts = para
        _runs(p, para, size=opts.get("size", size), color=opts.get("color", color),
              bold=opts.get("bold", bold), italic=opts.get("italic", italic),
              font=opts.get("font", font))


def text(slide, x, y, w, h, paras, name=None, **style):
    """A text box with no internal padding, so it lines up with shapes at the same x."""
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        box.name = name
    _fill_frame(box.text_frame, paras, **style)
    return box


def shape(slide, x, y, w, h, *, fill=TINT, line=None, kind=MSO_SHAPE.ROUNDED_RECTANGLE,
          radius=0.10, paras=None, name=None, line_width=1.0, dash=None, **style):
    """A filled shape (rounded rectangle by default), optionally with centred text."""
    shp = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    _strip_style(shp)
    if name:
        shp.name = name
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(line_width)
        if dash:
            shp.line.dash_style = dash
    if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        shp.adjustments[0] = min(0.5, radius / min(w, h))
    if paras is not None:
        style.setdefault("align", PP_ALIGN.CENTER)
        style.setdefault("anchor", MSO_ANCHOR.MIDDLE)
        style.setdefault("margins", (0.08, 0.04, 0.08, 0.04))
        _fill_frame(shp.text_frame, paras, **style)
    return shp


def arrow(slide, x1, y1, x2, y2, *, color=MUTED, width=1.5, head="triangle", tail=None):
    """A straight connector from (x1, y1) to (x2, y2); `head` decorates the end point."""
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1),
                                      Inches(x2), Inches(y2))
    _strip_style(conn)
    conn.line.color.rgb = color
    conn.line.width = Pt(width)
    ln = conn.line._get_or_add_ln()
    if tail:
        etree.SubElement(ln, qn("a:headEnd"), type=tail, w="med", len="med")
    if head:
        etree.SubElement(ln, qn("a:tailEnd"), type=head, w="med", len="med")
    return conn


def chip(slide, x, y, label, *, w=0.9, h=0.36, fill=NAVY, color=WHITE, size=12):
    """A small rounded label, used for requirement ids and step names."""
    return shape(slide, x, y, w, h, fill=fill, radius=0.08, paras=label,
                 size=size, bold=True, color=color, margins=(0.02, 0, 0.02, 0))


def badge(slide, x, y, label, *, d=0.5, fill=NAVY, color=WHITE, size=16):
    """A filled circle with a short label: the deck's recurring marker."""
    return shape(slide, x, y, d, d, kind=MSO_SHAPE.OVAL, fill=fill, paras=label,
                 size=size, bold=True, color=color, margins=(0, 0, 0, 0))


def notes(slide, script: str) -> None:
    slide.notes_slide.notes_text_frame.text = script.strip()


# ---------------------------------------------------------------- slide frame
def new_slide(prs, *, kicker: str | None, title: str | None, speaker: str | None, number: int):
    """A white slide with the kicker, title, and footer in their fixed positions."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = WHITE
    if kicker:
        text(slide, MX, 0.48, TITLE_W, 0.3, kicker.upper(), name="Kicker",
             size=12, bold=True, color=BLUE)
    if title:
        text(slide, MX, 0.8, TITLE_W, 0.9, title, name="Title", size=32, bold=True,
             color=NAVY, anchor=MSO_ANCHOR.TOP)
    if speaker:
        footer_left = f"COMP3211 Software Engineering  ·  {GROUP.get('group', '')}  ·  PIM System"
        text(slide, MX, 7.0, 7.0, 0.3, footer_left, name="Footer", size=10, color=MUTED)
        footer_right = f"Speaker {speaker}  ·  {SPEAKERS[speaker]}     {number} / {TOTAL_SLIDES}"
        text(slide, 6.9, 7.0, SLIDE_W - MX - 6.9, 0.3, footer_right, name="Footer right",
             size=10, color=MUTED, align=PP_ALIGN.RIGHT)
    return slide


def requirement_rows(slide, x, y, w, rows, *, row_h=0.88, size=16, chip_w=0.9):
    """Requirement statements, each with its SRS id in a navy chip on the left."""
    for i, (rid, statement) in enumerate(rows):
        top = y + i * row_h
        chip(slide, x, top + 0.02, rid, w=chip_w)
        text(slide, x + chip_w + 0.25, top, w - chip_w - 0.25, row_h - 0.05, statement,
             size=size, color=INK, line_spacing=1.05)


def clip(slide, x, y, w, movie: str, poster: str, caption: str):
    """An embedded silent clip with its poster frame, a hairline frame, and a caption."""
    h = w * 9 / 16
    slide.shapes.add_movie(str(MEDIA / movie), Inches(x), Inches(y), Inches(w), Inches(h),
                           poster_frame_image=str(MEDIA / poster), mime_type="video/mp4")
    shape(slide, x, y, w, h, fill=None, line=LINE, kind=MSO_SHAPE.RECTANGLE, line_width=0.75)
    text(slide, x, y + h + 0.12, w, 0.6, caption, size=12, color=MUTED, line_spacing=1.05)


# ---------------------------------------------------------------- slides
def slide_title(prs):
    s = new_slide(prs, kicker=None, title=None, speaker=None, number=1)
    text(s, MX, 0.48, 7.0, 0.3, f"{GROUP.get('course', '')}  ·  {GROUP.get('term', '')}".upper(),
         size=12, bold=True, color=BLUE)
    text(s, MX, 1.75, 6.5, 2.0, "A Command-Line Personal Information Manager",
         size=40, bold=True, color=NAVY, line_spacing=0.95)
    text(s, MX, 3.75, 6.4, 0.5, "Three requirements, the design, and one lesson learned",
         size=18, color=MUTED)
    text(s, MX, 4.75, 6.4, 0.4, GROUP.get("group", ""), size=16, bold=True, color=NAVY)
    for i, member in enumerate(MEMBERS[:4]):
        col, row = divmod(i, 2)
        text(s, MX + col * 3.2, 5.25 + row * 0.62, 3.0, 0.6,
             [(f"{'ABCD'[i]}  {member['name']}", {"bold": True}),
              (member["id"], {"color": MUTED, "size": 12})], size=14, color=INK)
    pic_x, pic_w = 7.0, SLIDE_W - MX - 7.0
    s.shapes.add_picture(str(MEDIA / "screen-overview.png"), Inches(pic_x), Inches(2.45),
                         Inches(pic_w))
    pic_h = pic_w * 760 / 1440
    shape(s, pic_x, 2.45, pic_w, pic_h, fill=None, line=LINE, kind=MSO_SHAPE.RECTANGLE,
          line_width=0.75)
    text(s, pic_x, 2.45 + pic_h + 0.12, pic_w, 0.5,
         "The full-screen interface: alarm band, Current Result, and details.",
         size=12, color=MUTED)
    notes(s, f"""
SPEAKER A ({SPEAKERS['A']}) · about 10 seconds on this slide
[Hold your student ID card next to your face for about 5 seconds.]

Hello, we are {GROUP.get('group', '')}. In the next five minutes we present our command-line Personal Information Manager: three of its requirements, its design, and one lesson we learned while building it.
""")


def slide_overview(prs):
    s = new_slide(prs, kicker="The system", title="One place for notes, tasks, events, and contacts",
                  speaker="A", number=2)
    cards = [
        ("N", "Note", ["`text` (required)", "A quick plain-text note"]),
        ("T", "Task", ["`description` (required)", "`deadline` (optional)"]),
        ("E", "Event", ["`description`, `start` (required)", "Any number of alarms, relative or absolute"]),
        ("C", "Contact", ["`name` (required)", "`address`, `mobile` (optional)"]),
    ]
    x, w, gap = MX, 2.85, 0.2
    for i, (pin, name, lines) in enumerate(cards):
        left = x + i * (w + gap)
        shape(s, left, 2.3, w, 2.55, fill=TINT, radius=0.14)
        badge(s, left + 0.25, 2.55, pin, d=0.55, size=18)
        text(s, left + 0.95, 2.6, w - 1.1, 0.5, name, size=22, bold=True, color=NAVY)
        text(s, left + 0.25, 3.35, w - 0.45, 1.4, lines, size=14, color=INK, space_after=6)
    ops = ["create", "modify", "search", "print", "delete", "save / load .pim"]
    text(s, MX, 5.2, 5.0, 0.35, "Every record can be", size=14, color=MUTED)
    left = MX
    for op in ops:
        width = 0.35 + 0.105 * len(op)
        shape(s, left, 5.6, width, 0.46, fill=WHITE, line=NAVY, radius=0.23, line_width=1.0,
              paras=op, size=14, bold=True, color=NAVY)
        left += width + 0.15
    text(s, MX, 6.3, 12.0, 0.4,
         "Each record keeps a permanent Id  ·  Python 3 standard library only  ·  runs in the macOS Terminal",
         size=14, color=MUTED)
    notes(s, """
SPEAKER A · about 15 seconds

Our PIM keeps four kinds of personal information record, or PIR: notes, tasks, events, and contacts. Users can create, modify, search, print, and delete them, and save everything in a dot-pim file. The whole system uses only the Python standard library.
""")


def slide_req_create(prs):
    s = new_slide(prs, kicker="Requirement 1 of 3", title="Creating a PIR", speaker="A", number=3)
    requirement_rows(s, MX, 2.15, 6.35, [
        ("FR-1", "`create [type]` starts a record of one of four types: Note, Task, Event, or Contact."),
        ("FR-3", "The system asks for one field at a time; pressing Enter skips an optional field."),
        ("FR-10", "A missing required field cancels the create and names the field: `description is required`."),
        ("FR-2", "The new record gets the next Id (1, 2, 3 …), and an Id is never reused."),
        ("FR-6", "An Event can carry any number of alarms, relative to its start or at a fixed time."),
    ], row_h=0.9, size=16)
    clip(s, 7.35, 2.3, 5.4, "clip-create-task.mp4", "poster-create-task.png",
         "Clip (10 s, click to play): creating a Task. The deadline is picked from a calendar in Hong Kong Time.")
    notes(s, """
SPEAKER A · about 40 seconds, including the 10-second clip

Requirement one is creating a PIR. The command create, followed by a type, starts a new record, and the system asks for one field at a time, so there is no syntax to remember. Each record gets the next Id, which is never reused. If a required field is empty, nothing is created, and the message names the field.

[Click the clip.] Here we create a Task and pick its deadline from a calendar, in Hong Kong time.

[Hand over to Speaker B.]
""")


def slide_req_criterion(prs):
    s = new_slide(prs, kicker="Requirement 2 of 3", title="Defining a search criterion",
                  speaker="B", number=4)
    chip(s, MX, 2.08, "FR-16")
    text(s, MX + 1.15, 2.03, 8.2, 0.5,
         "`search <criterion>` takes one line: tests on type, text, and time, joined by logic.",
         size=17, color=INK)
    cards = [
        ("Type", ["`type = event`"], "Exactly one of the four types"),
        ("Text", ['`description contains "COMP"`', '`contains "ada"`'],
         "Case-insensitive; without a field name, any text field"),
        ("Time", ["`deadline < 2026-11-20 20:00`", "`alarm = 2026-11-13 13:45`"],
         "On `deadline`, `start`, or `alarm`, to the minute"),
    ]
    w, gap = 3.9, 0.25
    for i, (name, examples, note) in enumerate(cards):
        left = MX + i * (w + gap)
        shape(s, left, 2.85, w, 2.0, fill=TINT, radius=0.14)
        text(s, left + 0.25, 3.0, w - 0.5, 0.4, name, size=20, bold=True, color=NAVY)
        text(s, left + 0.25, 3.5, w - 0.5, 0.8, examples, size=15, color=NAVY, space_after=2)
        text(s, left + 0.25, 4.3, w - 0.5, 0.5, note, size=13, color=MUTED)
    text(s, MX, 5.15, 4.0, 0.35, "Precedence", size=14, bold=True, color=NAVY)
    steps = [("!", "not: binds first"), ("&&", "and: binds next"), ("||", "or: binds last")]
    left = MX
    for i, (op, label) in enumerate(steps):
        badge(s, left, 5.55, op, d=0.62, size=18, fill=AMBER if i == 0 else NAVY)
        text(s, left + 0.78, 5.7, 1.6, 0.4, label, size=14, color=INK)
        if i < 2:
            arrow(s, left + 2.45, 5.86, left + 2.95, 5.86, color=MUTED, width=1.25)
        left += 3.1
    text(s, MX, 6.35, 12.0, 0.4,
         'Parentheses override the order:  `type = contact || !contains "comp"`  means  '
         '`type = contact || (!contains "comp")`',
         size=14, color=MUTED)
    notes(s, f"""
SPEAKER B ({SPEAKERS['B']}) · about 35 seconds
[Hold your student ID card next to your face for about 5 seconds.]

Our second requirement defines what a search criterion is. It is a single line made of three kinds of test: the type of a record, whether a text field contains a string, and whether a time is before, after, or equal to a given instant. Tests are combined with not, and, and or. Not binds tightest, then and, then or, and parentheses can override that order.
""")


def slide_req_search(prs):
    s = new_slide(prs, kicker="Requirement 3 of 3", title="Searching for PIRs", speaker="B", number=5)
    requirement_rows(s, MX, 2.15, 6.35, [
        ("FR-18", "`contains` ignores case and matches any part of the text. It is never fuzzy."),
        ("FR-20", "Times are compared as instants, to the minute. A missing field never matches; "
                  "`alarm` matches if any one alarm does."),
        ("FR-22", "The matches replace the list in Id order, and the first one is selected: `2 match(es)`."),
        ("FR-23", "A syntax error changes nothing, and the typed line stays so it can be corrected."),
    ], row_h=1.08, size=16)
    clip(s, 7.35, 2.3, 5.4, "clip-combined-search.mp4", "poster-combined-search.png",
         'Clip (13 s, click to play): every contact, plus every record that does not mention "comp".')
    notes(s, """
SPEAKER B · about 40 seconds, including the 13-second clip

The third requirement says how searching behaves. Contains ignores case and is never fuzzy. Times are compared as instants, so the time zone of the input cannot change the answer, and a record without the field simply does not match. For alarms, one matching alarm is enough. The matches replace the list in Id order, and a syntax error leaves the list exactly as it was.

[Click the clip.] This search combines or with not: every contact, plus every record that does not mention "comp".

[Hand over to Speaker C.]
""")


def slide_architecture(prs):
    s = new_slide(prs, kicker="Design · architecture", title="Model–View–Controller",
                  speaker="C", number=6)
    layers = [
        ("User at a terminal", None, WHITE, NAVY),
        ("view", "Terminal  ·  CursesUI  ·  widgets", TINT, NAVY),
        ("controller", "App  ·  errors", TINT, NAVY),
        ("model", "PIM  ·  PIR classes  ·  Criterion  ·  pimfile", NAVY, WHITE),
        ("PIM File (.pim, UTF-8 JSON)", None, WHITE, NAVY),
    ]
    labels = ["keys and lines", "one call per action", "model calls", "read · atomic write"]
    x, w, h, top, step = MX, 5.6, 0.72, 2.0, 1.0
    for i, (name, detail, fill, color) in enumerate(layers):
        y = top + i * step
        line = NAVY if fill == WHITE else None
        paras = [(name, {"bold": True, "size": 17})] if not detail else [
            (name, {"bold": True, "size": 17}), (detail, {"size": 13})]
        kind = MSO_SHAPE.ROUNDED_RECTANGLE
        shape(s, x, y, w, h, fill=fill, line=line, line_width=1.25, radius=0.36 if i in (0, 4) else 0.12,
              kind=kind, paras=paras, color=color)
        if i < len(layers) - 1:
            arrow(s, x + w / 2, y + h, x + w / 2, y + step, color=MUTED, width=1.5)
            text(s, x + w / 2 + 0.15, y + h + 0.02, 2.8, 0.26, labels[i], size=11, color=MUTED)
    text(s, 7.0, 2.35, 5.7, 0.4, "Why MVC", size=20, bold=True, color=NAVY)
    reasons = [
        "The brief asks for all model code in a separate `model` package.",
        "It fits the program's loop: read an action, change the data, redraw.",
        "Two front ends, full-screen and line-by-line, share one controller.",
        "The model is tested without a screen or a real clock.",
    ]
    for i, reason in enumerate(reasons):
        y = 2.95 + i * 0.95
        badge(s, 7.0, y, str(i + 1), d=0.5, size=16)
        text(s, 7.7, y + 0.02, 5.0, 0.85, reason, size=16, color=INK, line_spacing=1.05)
    notes(s, f"""
SPEAKER C ({SPEAKERS['C']}) · about 30 seconds
[Hold your student ID card next to your face for about 5 seconds.]

For the design, we chose the Model–View–Controller pattern, for four reasons. First, the brief requires all model code in a separate package called model. Second, MVC fits the program's loop: read an action, change the data, redraw the screen. Third, our two front ends, full-screen and line-by-line, share one controller. And fourth, the model can be tested without a screen or a real clock.
""")


def slide_instantiation(prs):
    s = new_slide(prs, kicker="Design · instantiation", title="How the pattern is instantiated",
                  speaker="C", number=7)
    shape(s, MX, 2.05, 5.9, 2.25, fill=TINT2, line=LINE, line_width=0.75, radius=0.12)
    code = [
        ("# pim.py, the composition root", {"color": MUTED}),
        "def main():",
        "    pim = PIM()           # model",
        "    app = App(pim)        # controller",
        "    Terminal(app).run()   # view",
    ]
    text(s, MX + 0.3, 2.3, 5.4, 1.9, code, font=CODE, size=16, color=NAVY, line_spacing=1.15)
    text(s, MX, 4.6, 5.9, 0.35, "Dependencies point one way", size=14, bold=True, color=NAVY)
    left = MX
    for i, name in enumerate(["view", "controller", "model"]):
        width = 1.35 if name != "controller" else 1.65
        shape(s, left, 5.05, width, 0.5, fill=NAVY if name == "model" else TINT, radius=0.25,
              paras=name, size=15, bold=True, color=WHITE if name == "model" else NAVY)
        if i < 2:
            arrow(s, left + width + 0.08, 5.3, left + width + 0.5, 5.3, color=MUTED, width=1.5)
        left += width + 0.58
    text(s, MX, 5.75, 5.9, 0.9,
         "`model` imports neither `view` nor `controller`, so its unit tests need no interface at all.",
         size=14, color=MUTED, line_spacing=1.05)
    packages = [
        ("M", "model/", "PIM, the PIR classes, alarms, Criterion, pimfile. Every rule and the file format."),
        ("C", "controller/", "App and errors. One completed user action becomes model calls and one status line."),
        ("V", "view/", "Terminal, CursesUI, widgets. The event loop, prompts, Alarm Alerts, and drawing."),
    ]
    for i, (pin, name, desc) in enumerate(packages):
        y = 2.3 + i * 1.45
        shape(s, 7.0, y, 5.7, 1.25, fill=TINT, radius=0.14)
        badge(s, 7.25, y + 0.35, pin, d=0.55, size=17, fill=NAVY)
        text(s, 8.05, y + 0.14, 4.5, 0.4, f"`{name}`", size=17, bold=True, color=NAVY)
        text(s, 8.05, y + 0.55, 4.45, 0.7, desc, size=13, color=INK, line_spacing=1.0)
    notes(s, """
SPEAKER C · about 20 seconds

Here is how the pattern is instantiated. The file pim.py is the composition root: it creates the PIM, passes it to the App controller, passes that to the Terminal view, and runs it. Each component is a package, and dependencies point one way only, from view to controller to model.
""")


def _class_box(s, x, y, w, h, name, sub=None, *, fill=TINT, color=NAVY, size=15):
    paras = [(name, {"bold": True, "size": size})]
    if sub:
        paras.append((sub, {"size": 11, "color": MUTED if fill != NAVY else WHITE}))
    return shape(s, x, y, w, h, fill=fill, line=NAVY, line_width=1.0, radius=0.06,
                 paras=paras, color=color)


def slide_classes(prs):
    s = new_slide(prs, kicker="Design · main code components", title="The main classes and how they relate",
                  speaker="C", number=8)
    bw, bh, row1 = 2.25, 0.8, 2.35
    xs = [MX, 3.55, 6.5, 9.45]
    names = [("CursesUI", "full-screen front end"), ("Terminal", "prompts · line interface"),
             ("App", "controller"), ("PIM", "Working Collection")]
    for x, (name, sub) in zip(xs, names):
        _class_box(s, x, row1, bw, bh, name, sub, fill=NAVY if name == "PIM" else TINT,
                   color=WHITE if name == "PIM" else NAVY)
    for a, b, label in [(0, 1, "drives"), (1, 2, "calls"), (2, 3, "calls")]:
        arrow(s, xs[a] + bw, row1 + bh / 2, xs[b], row1 + bh / 2, color=MUTED, width=1.5)
        text(s, xs[a] + bw + 0.05, row1 + bh / 2 - 0.32, 0.65, 0.25, label, size=11, color=MUTED,
             align=PP_ALIGN.CENTER)
    # Row 2: what PIM holds (PIR) and uses (pimfile, Criterion), spread across the slide.
    row2 = 3.75
    pimfile_x, pimfile_w = MX, 2.4
    pir_x, pir_w = 4.65, 2.4
    crit_x = 9.0
    crit_w = SLIDE_W - MX - crit_x
    _class_box(s, pimfile_x, row2, pimfile_w, bh, "pimfile", "JSON codec · atomic write")
    _class_box(s, pir_x, row2, pir_w, bh, "PIR", "abstract base class")
    _class_box(s, crit_x, row2, crit_w, bh, "Criterion", "Composite tree")
    pim_cx, pim_bottom = xs[3] + bw / 2, row1 + bh
    pimfile_cx, pir_cx, crit_cx = pimfile_x + pimfile_w / 2, pir_x + pir_w / 2, crit_x + crit_w / 2
    bus = pim_bottom + 0.3
    arrow(s, pim_cx, pim_bottom, pim_cx, bus, color=MUTED, width=1.25, head=None)
    arrow(s, pimfile_cx, bus, crit_cx, bus, color=MUTED, width=1.25, head=None)
    for cx in (pimfile_cx, pir_cx, crit_cx):
        arrow(s, cx, bus, cx, row2, color=MUTED, width=1.25)
    text(s, pim_cx - 1.62, pim_bottom + 0.0, 1.5, 0.25, "holds · uses", size=11, color=MUTED,
         align=PP_ALIGN.RIGHT)
    text(s, crit_x, row2 + bh + 0.1, crit_w, 0.5,
         "Leaves: TypeIs · Contains · TimeCompare\nCombinators: And · Or · Not",
         size=11, color=MUTED, align=PP_ALIGN.CENTER)
    # Row 3: the four PIR types under PIR, and the alarms each Event owns.
    row3 = 5.45
    sub_w, sub_gap = 1.2, 0.15
    subs = ["Note", "Task", "Contact", "Event"]
    sub_x0 = pir_cx - (4 * sub_w + 3 * sub_gap) / 2
    centers = []
    for i, name in enumerate(subs):
        x = sub_x0 + i * (sub_w + sub_gap)
        _class_box(s, x, row3, sub_w, 0.62, name, size=14)
        centers.append(x + sub_w / 2)
    tree = row3 - 0.38
    arrow(s, pir_cx, tree, pir_cx, row2 + bh, color=MUTED, width=1.25)
    arrow(s, centers[0], tree, centers[-1], tree, color=MUTED, width=1.25, head=None)
    for cx in centers:
        arrow(s, cx, tree, cx, row3, color=MUTED, width=1.25, head=None)
    text(s, pir_cx + 0.12, row2 + bh + 0.05, 1.2, 0.25, "inherit", size=11, color=MUTED)
    event_right = sub_x0 + 4 * sub_w + 3 * sub_gap
    alarm_x = event_right + 0.4
    _class_box(s, alarm_x, row3 - 0.05, 2.15, 0.72, "Alarms", "Relative · Absolute", size=14)
    arrow(s, alarm_x, row3 + 0.31, event_right, row3 + 0.31, color=MUTED, width=1.25, head="diamond")
    text(s, alarm_x, row3 + 0.72, 2.15, 0.25, "owned by each Event", size=11, color=MUTED,
         align=PP_ALIGN.CENTER)
    text(s, MX, 6.5, 12.1, 0.3,
         "Arrows show calls and use; the bar under PIR joins its four subclasses; the diamond marks ownership. "
         "The design document lists every field and method.",
         size=12, color=MUTED)
    notes(s, """
SPEAKER C · about 25 seconds

These are the main classes. CursesUI drives the Terminal, which calls App, which calls PIM, the Working Collection. PIM holds the records: Note, Task, Contact, and Event all extend the abstract class PIR, and each Event owns its alarms. PIM searches with a Criterion tree and reads and writes files through pimfile.

[Hand over to Speaker D.]
""")


def slide_bridge(prs):
    s = new_slide(prs, kicker="Design · search criteria", title="A criterion is a tree built inside the model",
                  speaker="D", number=9)
    shape(s, MX, 2.1, 6.4, 0.62, fill=TINT2, line=LINE, line_width=0.75, radius=0.1,
          paras='search type = event && description contains "COMP"', font=CODE, size=15, color=NAVY)
    arrow(s, MX + 3.2, 2.72, MX + 3.2, 3.45, color=MUTED, width=1.5)
    text(s, MX + 3.35, 2.92, 3.2, 0.3, "`parse_criterion` in `model`", size=13, color=MUTED)
    root_w, root_x = 1.6, MX + 3.2 - 0.8
    shape(s, root_x, 3.5, root_w, 0.62, fill=NAVY, radius=0.1, paras="And", size=17, bold=True, color=WHITE)
    leaves = [(MX, 2.3, 'TypeIs("event")'), (MX + 2.55, 3.85, 'Contains("description", "comp")')]
    for x, w, label in leaves:
        shape(s, x, 4.75, w, 0.62, fill=TINT, line=NAVY, line_width=1.0, radius=0.1,
              paras=label, font=CODE, size=13, color=NAVY)
        arrow(s, MX + 3.2, 4.12, x + w / 2, 4.75, color=MUTED, width=1.25)
    text(s, MX, 5.65, 6.4, 0.9,
         "`PIM.search` asks the root `matches(pir)` for every record; `And` asks its children.",
         size=14, color=MUTED, line_spacing=1.05)
    points = [
        "**Composite pattern.** Leaves test one record; `And`, `Or`, and `Not` combine smaller criteria.",
        "**The parser lives in the model.** `parse_criterion` turns one line into the tree, "
        "with `!` before `&&` before `||`.",
        "**So all of US7 can be unit-tested**, grammar and matching, without the view.",
    ]
    for i, point in enumerate(points):
        y = 2.45 + i * 1.3
        badge(s, 7.55, y, str(i + 1), d=0.5, size=16)
        text(s, 8.25, y, 4.5, 1.2, point, size=16, color=INK, line_spacing=1.05)
    notes(s, f"""
SPEAKER D ({SPEAKERS['D']}) · about 20 seconds
[Hold your student ID card next to your face for about 5 seconds.]

One design detail turned out to matter most. A search criterion is a Composite tree: the leaves test one record, and And, Or, and Not combine smaller criteria. The parser that builds this tree, parse_criterion, lives in the model, not in the view.
""")


def slide_lesson(prs):
    s = new_slide(prs, kicker="Lesson learned · unit testing",
                  title="Put every rule where a unit test can reach it", speaker="D", number=10)
    w, gap, top, h = 2.8, 0.33, 2.35, 4.25
    steps = [
        ("Problem", TINT, NAVY, [
            "Search mixes field tests, three time operators, missing values, alarm lists, and "
            "operator precedence.",
            "Alarms also depend on the clock. Testing all that through the terminal needs scripted keys and real time.",
        ]),
        ("Decision", TINT, NAVY, [
            "We decided early to keep every rule in `model`.",
            "`parse_criterion` is a plain function, and `due_alarms(now)` takes the time as an argument.",
            "The search tests share one six-PIR fixture.",
        ]),
        ("Result", TINT, NAVY, None),
        ("Takeaway", NAVY, WHITE, [
            ("If a rule cannot be tested through the model's interface, it is in the wrong place.",
             {"size": 19, "bold": True, "color": WHITE}),
        ]),
    ]
    for i, (name, fill, color, body) in enumerate(steps):
        x = MX + i * (w + gap)
        shape(s, x, top, w, h, fill=fill, radius=0.14)
        chip(s, x + 0.25, top + 0.25, name, w=1.25, fill=AMBER if name == "Takeaway" else NAVY)
        if body and name == "Takeaway":
            text(s, x + 0.25, top + 0.85, w - 0.5, h - 1.25, body, color=color,
                 anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.05)
        elif body:
            text(s, x + 0.25, top + 0.85, w - 0.5, h - 1.0, body, size=14, color=color,
                 space_after=8, line_spacing=1.02)
        if i < 3:
            arrow(s, x + w + 0.04, top + h / 2, x + w + gap - 0.04, top + h / 2, color=MUTED, width=1.5)
    rx = MX + 2 * (w + gap)
    text(s, rx + 0.25, top + 0.85, w - 0.5, 0.9, "100 %", size=48, bold=True, color=NAVY)
    text(s, rx + 0.25, top + 1.75, w - 0.5, 0.4, "line coverage of `model`: 800 of 800 lines",
         size=13, color=MUTED)
    text(s, rx + 0.25, top + 2.45, w - 0.5, 1.7, [
        "Search is tested with plain `unittest` calls: no screen, no clock.",
        "The model rules are tested directly, without a screen or clock.",
    ], size=14, color=INK, space_after=8, line_spacing=1.02)
    notes(s, """
SPEAKER D · about 40 seconds

That leads to our lesson about unit testing. Search mixes field tests, time operators, missing values, and precedence, and alarms depend on the clock. Testing that through the terminal would mean scripted keystrokes and waiting for real time. So we keep each rule in the model, expose the parser as a plain function, and pass the current time in as an argument. That lets unit tests check search and alarms directly, without the screen or the wall clock. Our takeaway: if a rule cannot be tested through the model's interface, it is in the wrong place.
""")


def slide_summary(prs):
    s = new_slide(prs, kicker="Summary", title="What we built and what we learned", speaker="D", number=11)
    stats = [("11 / 11", "user stories implemented"), ("53 / 53", "SRS requirements implemented"),
             ("800 / 800", "countable model lines covered"), ("4", "PIR types")]
    w, gap = 2.85, 0.2
    for i, (big, small) in enumerate(stats):
        x = MX + i * (w + gap)
        shape(s, x, 2.25, w, 1.75, fill=TINT, radius=0.14)
        text(s, x + 0.25, 2.4, w - 0.5, 0.9, big, size=40, bold=True, color=NAVY)
        text(s, x + 0.25, 3.3, w - 0.5, 0.6, small, size=14, color=MUTED)
    cols = [
        ("Requirements", "Create a PIR, define a criterion, and search, each stated so it can be tested."),
        ("Design", "MVC in three packages, with the model as the test surface and criteria as a Composite tree."),
        ("Lesson", "Testability decided where code lives: every rule sits where a unit test can reach it."),
    ]
    w3 = 3.9
    for i, (head, body) in enumerate(cols):
        x = MX + i * (w3 + 0.25)
        badge(s, x, 4.45, str(i + 1), d=0.45, size=14)
        text(s, x + 0.6, 4.47, w3 - 0.6, 0.4, head, size=18, bold=True, color=NAVY)
        text(s, x + 0.6, 4.95, w3 - 0.6, 1.1, body, size=14, color=INK, line_spacing=1.05)
    text(s, MX, 6.3, 6.0, 0.5, "Thank you.", size=24, bold=True, color=NAVY)
    notes(s, """
SPEAKER D · about 10 seconds

To sum up: all eleven user stories and every requirement in our SRS are implemented, and the unit tests execute every countable model line. Thank you for watching.
""")


# ---------------------------------------------------------------- sections
SECTIONS = [
    ("A · Introduction and requirement 1", 3),
    ("B · Requirements 2 and 3", 2),
    ("C · Design", 3),
    ("D · Design detail and lesson", 3),
]


def add_sections(prs) -> None:
    """Group the slides into one PowerPoint section per speaker."""
    p14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
    pres = prs.part._element
    ids = [sld.get("id") for sld in pres.find(qn("p:sldIdLst"))]
    ext_lst = pres.find(qn("p:extLst"))
    if ext_lst is None:
        ext_lst = etree.SubElement(pres, qn("p:extLst"))
    ext = etree.SubElement(ext_lst, qn("p:ext"), uri="{521415D9-36F7-43E2-AB2F-B90AF26B5E84}")
    section_list = etree.SubElement(ext, f"{{{p14}}}sectionLst", nsmap={"p14": p14})
    index = 0
    for name, count in SECTIONS:
        section = etree.SubElement(section_list, f"{{{p14}}}section", name=name,
                                   id="{" + str(uuid.uuid5(uuid.NAMESPACE_URL, name)).upper() + "}")
        slide_ids = etree.SubElement(section, f"{{{p14}}}sldIdLst")
        for sid in ids[index:index + count]:
            etree.SubElement(slide_ids, f"{{{p14}}}sldId", id=sid)
        index += count


def main() -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(SLIDE_W), Inches(SLIDE_H)
    for build in (slide_title, slide_overview, slide_req_create, slide_req_criterion,
                  slide_req_search, slide_architecture, slide_instantiation, slide_classes,
                  slide_bridge, slide_lesson, slide_summary):
        build(prs)
    assert len(prs.slides) == TOTAL_SLIDES
    add_sections(prs)
    props = prs.core_properties
    props.title = "PIM System: group presentation"
    props.author = f"COMP3211 {GROUP.get('group', '')}"
    props.subject = "Requirements, design, and lesson learned"
    prs.save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
