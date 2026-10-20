# Builds the Workato-branded post-training survey PDF from a Qualtrics CSV.
# Used by api/survey-report.py; kept here (an underscore folder, so not a
# route) so it can be run and tested locally without the HTTP layer.
#
# Mirrors the pull-training-survey-report Claude skill: same grouping, scoring,
# section layout and brand styling. Body contract lives with the endpoint:
#   { ett_key, csv, summaries?: [{ curriculum, session_date, summary }],
#     flags?: [str], timezone?: str }
#
# Personal data: only an allow-list of columns is ever read (ratings,
# categoricals, topics, free text, grouping fields). Emails, names, IPs and
# locations are never touched, so they can't leak into the PDF.

import csv
import io
import os
import re
import statistics
from datetime import datetime, timezone as dt_timezone
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    Flowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - zoneinfo ships with Python 3.9+
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception


ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_LINE = os.path.join(ASSETS, "workato-logo.png")  # skill: workato-logo_line_blk.png
LOGO_ICON = os.path.join(ASSETS, "workato-icon.png")  # skill: workato-logo_icon_blk.png

# ---- Brand (white-background variant, per the skill) ------------------------
WHITE = HexColor("#FFFFFF")
INK = HexColor("#111010")
MUTED = HexColor("#686868")
TEAL = HexColor("#67EADD")        # header fills, accent rules
TEAL_DARK = HexColor("#3EA2A8")   # group labels / pre-headers (teal text on white)
TEAL_CARD = HexColor("#22DBC8")   # metric card left border
ROW_ALT = HexColor("#F8FFFE")
GRID = HexColor("#DADADA")

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

PAGE_W, PAGE_H = letter
MARGIN = 0.6 * inch
FRAME_PAD = 6  # SimpleDocTemplate's frame padding on each side
CONTENT_W = PAGE_W - 2 * MARGIN - 2 * FRAME_PAD
CELL_PAD = 3

# ---- Survey column map (from the skill) -------------------------------------
RATING_CODES = ["Q4", "Q5", "Q21", "Q22", "Q27", "Q28", "Q3"]
CATEGORICAL_CODES = ["Q7", "Q6"]
TOPIC_PREFIX = "Q29_"
FREE_TEXT_CODES = ["Q30", "Q8", "Q9", "Q10", "Q11", "Q12"]

# Short labels for the overview table headers and the notes line. Q3 is
# CSAT-style and Q5 the closest to NPS, but it's a 5-point agree scale, so
# neither is ever labelled NPS.
SHORT = {
    "Q4": "Apply", "Q5": "Recommend", "Q21": "Depth", "Q22": "Labs",
    "Q27": "Lab guide", "Q28": "Unblocked", "Q3": "Satisfied",
    "Q7": "future training interest", "Q6": "how challenging",
    "Q29": "topics for deeper coverage", "Q30": "next automation idea",
    "Q8": "more time on", "Q9": "less time on", "Q10": "how to improve",
    "Q11": "other feedback", "Q12": "quote",
}

SCALE = [
    (5, "Strongly Agree"), (4, "Agree"), (3, "Neither Agree Nor Disagree"),
    (2, "Disagree"), (1, "Strongly Disagree"),
]
SCALE_LOOKUP = {label.lower(): score for score, label in SCALE}

# The built-in Helvetica only has WinAnsi (cp1252) glyphs; anything else
# (Hebrew, CJK, emoji) can't be drawn and is called out in the Notes line.
def helvetica_can_draw(text):
    try:
        text.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


class ReportInputError(ValueError):
    """Bad request body or unusable CSV; the endpoint maps this to a 400."""


# ============================================================================
# Public entry point
# ============================================================================

def build_report(payload, now=None):
    """Validate the request body and return (filename, pdf_bytes)."""
    if not isinstance(payload, dict):
        raise ReportInputError("Body must be a JSON object.")

    ett_key = normalize_ett_key(payload.get("ett_key"))
    csv_text = payload.get("csv")
    if not isinstance(csv_text, str) or not csv_text.strip():
        raise ReportInputError("csv is required (the full Qualtrics CSV text).")

    summaries = payload.get("summaries") or []
    if not isinstance(summaries, list):
        raise ReportInputError("summaries must be a list.")
    flags = payload.get("flags") or []
    if not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
        raise ReportInputError("flags must be a list of strings.")
    tz_name = payload.get("timezone") or "UTC"
    if not isinstance(tz_name, str):
        raise ReportInputError("timezone must be a string such as America/Los_Angeles.")

    survey = parse_survey(csv_text)
    groups = group_rows(survey, summaries)
    generated = format_generated(tz_name, now)

    pdf = render_pdf(ett_key, survey, groups, [f.strip() for f in flags if f.strip()], generated)
    return "%s Survey Report.pdf" % ett_key, pdf


def normalize_ett_key(value):
    """'ett-684', 'ETT-684' and '684' all become 'ETT-684'."""
    s = str(value).strip() if isinstance(value, (str, int)) else ""
    m = re.fullmatch(r"(?i)(?:ett-?)?(\d{1,7})", s)
    if not m:
        raise ReportInputError("ett_key is required, e.g. ETT-684.")
    return "ETT-%s" % m.group(1)


# ============================================================================
# Parsing
# ============================================================================

def parse_survey(csv_text):
    """Row 1 codes, row 2 question text, row 3 import metadata, data from row 4.

    Rows whose column count differs from the header are skipped and counted
    (the upstream recipe currently splits multi-line answers into broken rows).
    """
    text = csv_text.lstrip("﻿")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if len(rows) < 3:
        raise ReportInputError("CSV needs the 3 Qualtrics header rows plus data.")

    codes = [c.strip() for c in rows[0]]
    texts = rows[1] + [""] * (len(codes) - len(rows[1]))
    col = {c: i for i, c in enumerate(codes) if c}
    for required in ("session_name", "session_date", "training_name"):
        if required not in col:
            raise ReportInputError("CSV is missing the %s column." % required)

    malformed = 0
    data = []
    for r in rows[3:]:
        if not any(cell.strip() for cell in r):
            continue  # blank line, not a response
        if len(r) != len(codes):
            malformed += 1
            continue
        data.append(r)
    if not data:
        raise ReportInputError("CSV has no usable response rows.")

    def qtext(code):
        t = texts[col[code]].strip()
        return t or code

    rating = [(c, qtext(c)) for c in RATING_CODES if c in col]
    categorical = [(c, qtext(c)) for c in CATEGORICAL_CODES if c in col]
    free_text = [(c, qtext(c)) for c in FREE_TEXT_CODES if c in col]
    topics = []
    topic_stem = ""
    for c in sorted((c for c in col if c.startswith(TOPIC_PREFIX)),
                    key=lambda c: int(c[len(TOPIC_PREFIX):]) if c[len(TOPIC_PREFIX):].isdigit() else 999):
        full = texts[col[c]].strip()
        stem, sep, label = full.rpartition(" - ")
        topics.append((c, label.strip() if sep else (full or c)))
        if sep and not topic_stem:
            topic_stem = stem.strip()

    # Keep only allow-listed fields per response.
    wanted = [c for c, _ in rating + categorical + free_text + topics]
    responses = []
    for r in data:
        resp = {c: r[col[c]] for c in wanted}
        resp["_session_name"] = r[col["session_name"]].strip()
        resp["_training_name"] = r[col["training_name"]].strip()
        resp["_session_date"] = r[col["session_date"]].strip()
        responses.append(resp)

    return {
        "responses": responses,
        "malformed": malformed,
        "rating": rating,
        "categorical": categorical,
        "free_text": free_text,
        "topics": topics,
        "topic_stem": topic_stem or "Topics for deeper coverage",
    }


# ============================================================================
# Grouping (contract: endpoint and Genie must agree)
# ============================================================================

def split_curriculum(session_name, training_name):
    """Return (curriculum, session_label).

    curriculum = session_name, unless session_name contains " | ": then the row
    predates the 19 Oct 2026 swap and the two fields are swapped.
    """
    if " | " in session_name:
        return training_name, session_name
    return session_name, training_name


def parse_date(raw):
    for fmt in ("%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            pass
    return None


def date_key(raw):
    d = parse_date(raw or "")
    return d.strftime("%m-%d-%Y") if d else (raw or "").strip()


def long_date(d):
    return "%s %d, %d" % (d.strftime("%B"), d.day, d.year)


def group_rows(survey, summaries):
    summary_by_key = {}
    for s in summaries:
        if not isinstance(s, dict):
            raise ReportInputError("Each summaries item must be an object.")
        text = s.get("summary")
        if isinstance(text, str) and text.strip():
            key = (str(s.get("curriculum") or "").strip().lower(),
                   date_key(str(s.get("session_date") or "")))
            summary_by_key[key] = text.strip()

    groups = {}
    for resp in survey["responses"]:
        curriculum, label = split_curriculum(resp["_session_name"], resp["_training_name"])
        key = (curriculum.strip().lower(), date_key(resp["_session_date"]))
        g = groups.get(key)
        if g is None:
            d = parse_date(resp["_session_date"])
            g = groups[key] = {
                "key": key,
                "curriculum": curriculum.strip(),
                "date": d,
                "date_label": long_date(d) if d else (resp["_session_date"] or "No date"),
                "session_labels": [],
                "rows": [],
            }
        if label and label not in g["session_labels"]:
            g["session_labels"].append(label)
        g["rows"].append(resp)

    out = sorted(groups.values(),
                 key=lambda g: (g["date"] is None, g["date"] or datetime.min.date(), g["key"][0]))
    for g in out:
        code = g["curriculum"].upper() or "NO CURRICULUM"
        g["label"] = "%s · %s" % (code, g["date_label"])
        g["summary"] = summary_by_key.get(g["key"], "")

    total = sum(len(g["rows"]) for g in out)
    if total != len(survey["responses"]):  # Rule: group counts sum to the total.
        raise RuntimeError("Group counts do not add up to the total response count.")
    return out


# ============================================================================
# Scoring
# ============================================================================

def score(value):
    v = (value or "").strip().lower()
    if v in SCALE_LOOKUP:
        return SCALE_LOOKUP[v]
    if v in ("1", "2", "3", "4", "5"):  # numeric exports
        return int(v)
    return None


def scores_for(rows, code):
    return [s for s in (score(r.get(code)) for r in rows) if s is not None]


def modes(values):
    if not values:
        return []
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    top = max(counts.values())
    tied = [v for v, n in counts.items() if n == top]
    try:
        return sorted(tied, reverse=True)
    except TypeError:
        return tied


def fmt_num(x):
    if x is None:
        return "–"
    if float(x).is_integer():
        return "%d" % x
    return "%.2f" % x


def mean_or_none(values):
    return statistics.mean(values) if values else None


def overall_mean(rows, codes):
    """Average of the per-question means (questions with data only)."""
    means = [m for m in (mean_or_none(scores_for(rows, c)) for c in codes) if m is not None]
    return statistics.mean(means) if means else None


def answered(rows, code):
    return [r[code] for r in rows if (r.get(code) or "").strip()]


def format_generated(tz_name, now=None):
    tz = dt_timezone.utc
    if ZoneInfo is not None and tz_name.upper() != "UTC":
        try:
            tz = ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, ValueError, KeyError, OSError):
            tz = dt_timezone.utc  # unknown zone or no tzdata on the host
    t = (now or datetime.now(dt_timezone.utc)).astimezone(tz)
    clock = t.strftime("%I:%M %p").lstrip("0")
    return "%s, %s %s" % (long_date(t), clock, t.tzname() or "UTC")


# ============================================================================
# Rendering helpers
# ============================================================================

def P(text, style):
    return Paragraph(text, style)


def esc(text):
    """Escape for reportlab Paragraph markup; wording itself is unchanged."""
    return escape(text).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")


STYLES = {
    "body": ParagraphStyle("body", fontName=FONT, fontSize=9.5, leading=13, textColor=INK),
    "meta": ParagraphStyle("meta", fontName=FONT, fontSize=9.5, leading=14, textColor=INK),
    "muted": ParagraphStyle("muted", fontName=FONT, fontSize=8, leading=11, textColor=MUTED),
    "title": ParagraphStyle("title", fontName=FONT_BOLD, fontSize=22, leading=26, textColor=INK),
    "h2": ParagraphStyle("h2", fontName=FONT_BOLD, fontSize=15, leading=19, textColor=INK),
    "h3": ParagraphStyle("h3", fontName=FONT_BOLD, fontSize=10.5, leading=14, textColor=INK,
                         spaceAfter=4),
    "count": ParagraphStyle("count", fontName=FONT, fontSize=8, leading=11, textColor=MUTED,
                            spaceAfter=6),
    "question": ParagraphStyle("question", fontName=FONT_BOLD, fontSize=10, leading=13.5,
                               textColor=INK, spaceBefore=8, spaceAfter=4),
    "answer": ParagraphStyle("answer", fontName=FONT, fontSize=9.5, leading=13, textColor=INK,
                             leftIndent=12, bulletIndent=2, spaceAfter=3),
    "th": ParagraphStyle("th", fontName=FONT_BOLD, fontSize=7.5, leading=9, textColor=INK),
    "th_c": ParagraphStyle("th_c", fontName=FONT_BOLD, fontSize=7.5, leading=9, textColor=INK,
                           alignment=1),
    "td": ParagraphStyle("td", fontName=FONT, fontSize=8, leading=10, textColor=INK),
    "td_c": ParagraphStyle("td_c", fontName=FONT, fontSize=8, leading=10, textColor=INK,
                           alignment=1),
    "td_b": ParagraphStyle("td_b", fontName=FONT_BOLD, fontSize=8, leading=10, textColor=INK),
    "td_bc": ParagraphStyle("td_bc", fontName=FONT_BOLD, fontSize=8, leading=10, textColor=INK,
                            alignment=1),
    "card_label": ParagraphStyle("card_label", fontName=FONT, fontSize=7.5, leading=9.5,
                                 textColor=MUTED),
    "card_value": ParagraphStyle("card_value", fontName=FONT_BOLD, fontSize=15, leading=18,
                                 textColor=INK),
}


class Heading(Flowable):
    """Sentence-case heading in ink with a teal accent rule beneath (skill)."""

    def __init__(self, text, style, rule_w=56, rule_h=3.5, gap=5, space_before=0):
        super().__init__()
        self.para = Paragraph(esc(text), style)
        self.rule_w, self.rule_h, self.gap = rule_w, rule_h, gap
        self.spaceBefore = space_before
        self.spaceAfter = 10
        self.keepWithNext = True

    def wrap(self, aw, ah):
        _, self.ph = self.para.wrap(aw, ah)
        self.width = aw
        self.height = self.ph + self.gap + self.rule_h
        return aw, self.height

    def draw(self):
        self.para.drawOn(self.canv, 0, self.rule_h + self.gap)
        self.canv.setFillColor(TEAL)
        self.canv.rect(0, 0, self.rule_w, self.rule_h, stroke=0, fill=1)


class PreHeader(Flowable):
    """UPPERCASE, letter-spaced group label in #3EA2A8 (skill)."""

    def __init__(self, text, size=9, char_space=1.2, space_before=6, space_after=6):
        super().__init__()
        self.text = text.upper()
        self.size, self.char_space = size, char_space
        self.spaceBefore, self.spaceAfter = space_before, space_after
        self.keepWithNext = True

    def wrap(self, aw, ah):
        self.width, self.height = aw, self.size + 3
        return aw, self.height

    def draw(self):
        t = self.canv.beginText(0, 3)
        t.setFont(FONT_BOLD, self.size)
        t.setFillColor(TEAL_DARK)
        t.setCharSpace(self.char_space)
        t.textOut(self.text)
        self.canv.drawText(t)


def keep_next(flowable):
    flowable.keepWithNext = True
    return flowable


def min_col_width(strings, font, size):
    """Narrowest column that fits the longest single word (no mid-word breaks)."""
    widest = 0
    for s in strings:
        for word in re.split(r"\s+|<br/>", s):
            widest = max(widest, stringWidth(word, font, size))
    return widest + 2 * CELL_PAD + 2


def fit_widths(fixed, flex_index, total=CONTENT_W, flex_min=110):
    """fixed: list of min widths (None at flex_index). The flex column takes the rest."""
    used = sum(w for i, w in enumerate(fixed) if i != flex_index)
    out = list(fixed)
    out[flex_index] = max(flex_min, total - used)
    return out


def table_style(n_rows, header_rows=1, extra=None):
    cmds = [
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), TEAL),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("LEFTPADDING", (0, 0), (-1, -1), CELL_PAD),
        ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PAD),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(header_rows, n_rows):
        cmds.append(("BACKGROUND", (0, i), (-1, i),
                     WHITE if (i - header_rows) % 2 == 0 else ROW_ALT))
    return TableStyle(cmds + (extra or []))


def metric_cards(items):
    """White cards, 1pt #DADADA border, 4pt #22DBC8 left border, bold value."""
    gap = 8
    n = len(items)
    card_w = (CONTENT_W - gap * (n - 1)) / n
    row, widths, cmds = [], [], []
    for i, (label, value) in enumerate(items):
        if i:
            row.append("")
            widths.append(gap)
        c = len(row)
        row.append([P(esc(label), STYLES["card_label"]), P(esc(value), STYLES["card_value"])])
        widths.append(card_w)
        cmds += [
            ("BOX", (c, 0), (c, 0), 1, GRID),
            ("LINEBEFORE", (c, 0), (c, 0), 4, TEAL_CARD),
            ("BACKGROUND", (c, 0), (c, 0), WHITE),
            ("LEFTPADDING", (c, 0), (c, 0), 9),
            ("TOPPADDING", (c, 0), (c, 0), 6),
            ("BOTTOMPADDING", (c, 0), (c, 0), 7),
        ]
    t = Table([row], colWidths=widths)
    t.setStyle(TableStyle(cmds + [("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


class FooterCanvas(rl_canvas.Canvas):
    """Defers page output so the footer can say 'Page X of Y'."""

    def __init__(self, *args, footer_text="", **kwargs):
        super().__init__(*args, **kwargs)
        self._pages = []
        self._footer_text = footer_text

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for state in self._pages:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total):
        y = 0.38 * inch
        self.saveState()
        self.setStrokeColor(GRID)
        self.setLineWidth(0.5)
        self.line(MARGIN, y + 16, PAGE_W - MARGIN, y + 16)
        icon_h = 10
        icon_w = icon_h * 272 / 163
        self.drawImage(LOGO_ICON, MARGIN, y - 1.5, width=icon_w, height=icon_h, mask="auto")
        self.setFont(FONT, 7.5)
        self.setFillColor(MUTED)
        self.drawString(MARGIN + icon_w + 6, y, self._footer_text)
        self.drawRightString(PAGE_W - MARGIN, y, "Page %d of %d" % (self._pageNumber, total))
        self.restoreState()


def white_background(canv, _doc):
    canv.saveState()
    canv.setFillColor(WHITE)
    canv.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    canv.restoreState()


# ============================================================================
# Report
# ============================================================================

def render_pdf(ett_key, survey, groups, flags, generated):
    responses = survey["responses"]
    total = len(responses)
    rating = survey["rating"]
    rating_codes = [c for c, _ in rating]
    multi = len(groups) > 1

    # Questions with zero responses anywhere are omitted (and listed in Notes).
    rating_live = [(c, t) for c, t in rating if scores_for(responses, c)]
    cat_live = [(c, t) for c, t in survey["categorical"] if answered(responses, c)]
    free_live = [(c, t) for c, t in survey["free_text"] if answered(responses, c)]
    topics_live = any(answered(responses, c) for c, _ in survey["topics"])
    omitted = [c for c in rating_codes if c not in dict(rating_live)]
    omitted += [c for c, _ in survey["categorical"] if c not in dict(cat_live)]
    if survey["topics"] and not topics_live:
        omitted.append("Q29")
    omitted += [c for c, _ in survey["free_text"] if c not in dict(free_live)]
    live_codes = [c for c, _ in rating_live]

    story = []

    # ---- Header -----------------------------------------------------------
    logo_w = 1.45 * inch
    story.append(Image(LOGO_LINE, width=logo_w, height=logo_w * 163 / 1002, hAlign="LEFT"))
    story.append(Spacer(1, 16))
    story.append(Heading("%s Survey Report" % ett_key, STYLES["title"], rule_w=72, rule_h=4))

    labels = []
    for g in groups:
        for lbl in g["session_labels"]:
            if lbl not in labels:
                labels.append(lbl)
    dates = []
    for g in groups:
        if g["date_label"] not in dates:
            dates.append(g["date_label"])
    meta = [
        ("Training name", "; ".join(labels) or "Not recorded"),
        ("Sessions", str(len(groups))),
        ("Session date%s" % ("s" if len(dates) > 1 else ""), "; ".join(dates)),
        ("Total responses", str(total)),
        ("Report generated", generated),
    ]
    for k, v in meta:
        story.append(P("<font name='%s'>%s:</font> %s" % (FONT_BOLD, esc(k), esc(v)), STYLES["meta"]))
    story.append(Spacer(1, 6))
    story.append(P("<font name='%s'>Rating scale:</font> %s. Blank answers are ignored."
                   % (FONT_BOLD, ", ".join("%s = %d" % (lbl, s) for s, lbl in SCALE)),
                   STYLES["muted"]))
    story.append(Spacer(1, 14))

    overall = overall_mean(responses, live_codes)
    cards = [("Total responses", str(total)), ("Overall average", fmt_avg(overall))]
    if "Q3" in live_codes:
        cards.append(("Satisfied (Q3, CSAT-style)", fmt_avg(mean_or_none(scores_for(responses, "Q3")))))
    if "Q5" in live_codes:
        cards.append(("Would recommend (Q5)", fmt_avg(mean_or_none(scores_for(responses, "Q5")))))
    story.append(metric_cards(cards))
    story.append(Spacer(1, 18))

    # ---- Section 1: Overview ---------------------------------------------
    story.append(Heading("Section 1: Overview", STYLES["h2"]))
    story.append(overview_table(groups, responses, rating_live, multi))
    story.append(Spacer(1, 6))
    story.append(P("Averages on the 1–5 scale. Overall = mean of the question averages. "
                   + "; ".join("<font name='%s'>%s</font> (%s): %s"
                               % (FONT_BOLD, esc(SHORT.get(c, c)), c, esc(t))
                               for c, t in rating_live),
                   STYLES["muted"]))

    summaries = [g for g in groups if g["summary"]]
    if summaries:
        story.append(Spacer(1, 12))
        story.append(keep_next(P("Summary of themes", STYLES["h3"])))
        for g in groups:
            if not g["summary"]:
                continue
            if multi:
                story.append(PreHeader(g["label"], size=8, space_before=4, space_after=3))
            story.append(P(esc(g["summary"]), STYLES["body"]))
            story.append(Spacer(1, 4))

    story.append(Spacer(1, 12))
    story.append(P(notes_line(survey, groups, omitted, flags), STYLES["muted"]))

    # ---- Section 2: Quantitative (per group) ------------------------------
    story.append(PageBreak())
    story.append(Heading("Section 2: Quantitative", STYLES["h2"]))
    for i, g in enumerate(groups):
        story += quantitative_group(g, survey, rating_live, cat_live, topics_live, first=(i == 0))

    # ---- Section 3: Qualitative (per group) -------------------------------
    story.append(PageBreak())
    story.append(Heading("Section 3: Qualitative", STYLES["h2"]))
    story.append(P("Answers appear exactly as submitted, without respondent identity.",
                   STYLES["muted"]))
    for i, g in enumerate(groups):
        story += qualitative_group(g, free_live, first=(i == 0))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=0.55 * inch, bottomMargin=0.85 * inch,
        title="%s Survey Report" % ett_key, author="Workato Academy",
        subject="Post-training survey report",
    )
    doc.build(story, onFirstPage=white_background, onLaterPages=white_background,
              canvasmaker=lambda *a, **k: FooterCanvas(
                  *a, footer_text="%s Survey Report" % ett_key, **k))
    return buf.getvalue()


def fmt_avg(x):
    return "–" if x is None else "%.2f" % x


def overview_table(groups, responses, rating_live, multi):
    codes = [c for c, _ in rating_live]
    head = ["Session", "Responses"] + [SHORT.get(c, c) for c in codes] + ["Overall", "Future training: Yes"]
    has_future = bool(answered(responses, "Q7"))
    if not has_future:
        head.pop()

    def row_for(label, rows, bold=False):
        td = STYLES["td_bc" if bold else "td_c"]
        cells = [P(label, STYLES["td_b" if bold else "td"]), P(str(len(rows)), td)]
        for c in codes:
            cells.append(P(fmt_avg(mean_or_none(scores_for(rows, c))), td))
        cells.append(P(fmt_avg(overall_mean(rows, codes)), STYLES["td_bc"]))
        if has_future:
            yes = sum(1 for r in rows if (r.get("Q7") or "").strip().lower() == "yes")
            cells.append(P("%d of %d" % (yes, len(rows)), td))
        return cells

    data = [[P(esc(h), STYLES["th" if i == 0 else "th_c"]) for i, h in enumerate(head)]]
    for g in groups:
        code = esc(g["curriculum"].upper() or "NO CURRICULUM")
        data.append(row_for("%s<br/>%s" % (code, esc(g["date_label"])), g["rows"]))
    if multi:
        data.append(row_for("Combined", responses, bold=True))

    mins = [None] + [min_col_width([h, "Responses" if i == 0 else "0.00"], FONT_BOLD, 7.5)
                     for i, h in enumerate(head[1:])]
    if has_future:
        mins[-1] = min_col_width(["training:", "00 of 00"], FONT_BOLD, 7.5)
    widths = fit_widths(mins, 0, flex_min=80)
    extra = []
    if multi:
        extra.append(("LINEABOVE", (0, len(data) - 1), (-1, len(data) - 1), 1, TEAL_DARK))
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(table_style(len(data), extra=extra))
    return t


def quantitative_group(g, survey, rating_live, cat_live, topics_live, first):
    rows = g["rows"]
    out = [PreHeader(g["label"], space_before=0 if first else 16),
           keep_next(P("%d response%s" % (len(rows), "" if len(rows) == 1 else "s"),
                       STYLES["count"]))]

    # Rating table: one row per rating question with data in this group.
    q_rows = [(c, t, scores_for(rows, c)) for c, t in rating_live]
    q_rows = [x for x in q_rows if x[2]]
    if q_rows:
        head = ["Question"] + [lbl for _, lbl in SCALE] + ["Mean", "Median", "Mode", "Min", "Max", "Count"]
        data = [[P(esc(h), STYLES["th" if i == 0 else "th_c"]) for i, h in enumerate(head)]]
        for c, text, vals in q_rows:
            n = len(vals)
            cells = [P(esc(text), STYLES["td"])]
            for s, _ in SCALE:
                k = vals.count(s)
                cells.append(P("%d<br/><font color='#686868'>%d%%</font>" % (k, round(100.0 * k / n)),
                               STYLES["td_c"]))
            cells += [
                P("%.2f" % statistics.mean(vals), STYLES["td_bc"]),
                P(fmt_num(statistics.median(vals)), STYLES["td_c"]),
                P(", ".join(str(m) for m in modes(vals)), STYLES["td_c"]),
                P(str(min(vals)), STYLES["td_c"]),
                P(str(max(vals)), STYLES["td_c"]),
                P(str(n), STYLES["td_c"]),
            ]
            data.append(cells)
        mins = [None] + [min_col_width([h, "100%", "5, 4, 3"], FONT_BOLD, 7.5) if h == "Mode"
                         else min_col_width([h, "100%"], FONT_BOLD, 7.5) for h in head[1:]]
        t = Table(data, colWidths=fit_widths(mins, 0), repeatRows=1)
        t.setStyle(table_style(len(data)))
        out += [keep_next(P("Rating questions", STYLES["h3"])), t, Spacer(1, 12)]

    # Yes/no and categorical: count, percentage, mode.
    cat_data = [[P(esc(h), STYLES["th" if i < 2 else "th_c"])
                 for i, h in enumerate(["Question", "Response", "Count", "%", "Mode"])]]
    spans = []
    for c, text in cat_live:
        vals = [v.strip() for v in answered(rows, c)]
        if not vals:
            continue
        counts = {}
        for v in vals:
            counts[v] = counts.get(v, 0) + 1
        ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        start = len(cat_data)
        mode_txt = ", ".join(esc(m) for m in modes(vals))
        for j, (v, k) in enumerate(ordered):
            cat_data.append([
                P(esc(text), STYLES["td"]) if j == 0 else "",
                P(esc(v), STYLES["td"]),
                P(str(k), STYLES["td_c"]),
                P("%d%%" % round(100.0 * k / len(vals)), STYLES["td_c"]),
                P(mode_txt, STYLES["td_c"]) if j == 0 else "",
            ])
        if len(ordered) > 1:
            end = len(cat_data) - 1
            spans += [("SPAN", (0, start), (0, end)), ("SPAN", (4, start), (4, end))]
    if len(cat_data) > 1:
        fixed = [1.6 * inch, 0.55 * inch, 0.55 * inch, 1.0 * inch]
        widths = [CONTENT_W - sum(fixed)] + fixed
        t = Table(cat_data, colWidths=widths, repeatRows=1)
        t.setStyle(table_style(len(cat_data), extra=spans))
        out += [keep_next(P("Yes/no and categorical questions", STYLES["h3"])),
                t, Spacer(1, 12)]

    # Multi-select topics: count per option.
    if topics_live:
        topic_rows = [(label, len(answered(rows, c))) for c, label in survey["topics"]]
        if any(k for _, k in topic_rows):
            data = [[P("Topic", STYLES["th"]), P("Count", STYLES["th_c"])]]
            for label, k in topic_rows:
                data.append([P(esc(label), STYLES["td"]), P(str(k), STYLES["td_c"])])
            t = Table(data, colWidths=[3.2 * inch, 0.7 * inch], repeatRows=1, hAlign="LEFT")
            t.setStyle(table_style(len(data)))
            out += [keep_next(P(esc(survey["topic_stem"]), STYLES["h3"])), t,
                    Spacer(1, 12)]
    return out


def qualitative_group(g, free_live, first):
    out = [PreHeader(g["label"], space_before=8 if first else 18)]
    any_answers = False
    for c, text in free_live:
        answers = [a for a in (r.get(c) or "" for r in g["rows"]) if a.strip()]
        if not answers:
            continue
        any_answers = True
        out.append(keep_next(P("%s <font name='%s' color='#686868'>(%d)</font>"
                               % (esc(text), FONT, len(answers)), STYLES["question"])))
        for a in answers:
            out.append(Paragraph(esc(a), STYLES["answer"], bulletText="•"))
    if not any_answers:
        out.append(P("No written answers for this session.", STYLES["muted"]))
    return out


def notes_line(survey, groups, omitted, flags):
    parts = []
    if omitted:
        parts.append("Questions omitted for no responses: " + ", ".join(
            "%s (%s)" % (c, SHORT.get(c, c)) for c in omitted) + ".")
    else:
        parts.append("No questions were omitted.")
    n = survey["malformed"]
    if n:
        parts.append("%d malformed row%s skipped: the column count did not match the header "
                     "(usually a multi-line answer split upstream), so %s answers are not "
                     "included." % (n, " was" if n == 1 else "s were", "its" if n == 1 else "their"))

    tests = [esc(f) for f in flags]
    responses = survey["responses"]
    if len(responses) > 1:
        by_curriculum = {}
        for g in groups:
            by_curriculum.setdefault(g["key"][0], []).extend(g["rows"])
        for g in groups:
            rows = by_curriculum.get(g["key"][0], [])
            if len(rows) == 1 and len(g["rows"]) == 1:
                vals = [score(rows[0].get(c)) for c, _ in survey["rating"]]
                vals = [v for v in vals if v is not None]
                if vals and all(v == 5 for v in vals):
                    tests.append("possible test response in %s (single response, all top "
                                 "scores; not excluded)" % esc(g["label"]))
    if tests:
        parts.append("Flagged: " + "; ".join(tests) + ".")
    else:
        parts.append("No test responses were detected.")

    unrenderable = 0
    for r in responses:
        for c, _ in survey["free_text"]:
            v = r.get(c) or ""
            if v.strip() and not helvetica_can_draw(v):
                unrenderable += 1
    if unrenderable:
        parts.append("%d answer%s non-Latin characters (e.g. Hebrew) that the report font "
                     "cannot display; see the source CSV for the original text."
                     % (unrenderable, " contains" if unrenderable == 1 else "s contain"))

    parts.append("Respondent emails, names, IP addresses and locations are excluded.")
    return "<font name='%s' color='#111010'>Notes:</font> %s" % (FONT_BOLD, " ".join(parts))
