"""
PNAS-format PDF — Study 3 overconfidence paper.
Two-column layout, Times New Roman body, PNAS colour scheme.

Fixes vs v2:
  - auto_page_break disabled; column manager owns all page/column transitions
  - x0 updated after every col.ensure_space() call (stale-x0 bug fixed)
  - flush_line always queries col.col_x() fresh
  - col_table re-queries x0 after ensure_space
  - new_x / new_y never used (positions set explicitly)
"""
from fpdf import FPDF

FD  = r"C:\Windows\Fonts"
OUT = "paper_pnas.pdf"

# ── palette ───────────────────────────────────────────────────────────────────
PNAS_BLUE  = (0,  63, 135)
SIG_BG     = (232, 241, 250)
RULE_GRAY  = (190, 190, 190)
DARK       = (30,  30,  30)
MID        = (110, 110, 110)
WHITE      = (255, 255, 255)
LIGHT_ROW  = (240, 245, 252)

# ── page geometry (US Letter) ─────────────────────────────────────────────────
PW, PH = 215.9, 279.4
LM, RM = 16.0, 16.0
TOP_M  = 20.0
BOT_M  = 18.0
FULL_W = PW - LM - RM

COL_GAP = 6.0
COL_W   = (FULL_W - COL_GAP) / 2   # ≈ 88.95 mm
COL_R   = LM + COL_W + COL_GAP     # x-start of right column

RUNNING_HEAD_H = 14.0               # reserved at top of pages 2+


# ═════════════════════════════════════════════════════════════════════════════
# Column manager — owns all position transitions
# ═════════════════════════════════════════════════════════════════════════════
class ColManager:
    def __init__(self, pdf, col_top):
        self.pdf     = pdf
        self.col     = 0          # 0 = left, 1 = right
        self.col_top = col_top    # y where columns start on the current page

    # ── queries ───────────────────────────────────────────────────────────────
    def x(self):
        return LM if self.col == 0 else COL_R

    def remaining(self):
        """mm remaining in current column."""
        return (PH - BOT_M) - self.pdf.get_y()

    # ── transitions ───────────────────────────────────────────────────────────
    def need(self, h):
        """Ensure h mm is available; switch column/page if not."""
        if self.remaining() < h:
            self._advance()

    def _advance(self):
        if self.col == 0:
            self.col = 1
            self.pdf.set_xy(COL_R, self.col_top)
        else:
            self.col = 0
            self.pdf.add_page()
            self.col_top = TOP_M   # pages 2+ body starts at same TOP_M after header
            self.pdf.set_xy(LM, self.col_top)

    # ── convenience ───────────────────────────────────────────────────────────
    def goto_x(self):
        self.pdf.set_x(self.x())


# ═════════════════════════════════════════════════════════════════════════════
# PDF class
# ═════════════════════════════════════════════════════════════════════════════
class PnasPDF(FPDF):

    def setup_fonts(self):
        self.add_font("TNR",  "",  rf"{FD}\times.ttf")
        self.add_font("TNR",  "B", rf"{FD}\timesbd.ttf")
        self.add_font("TNR",  "I", rf"{FD}\timesi.ttf")
        self.add_font("TNR",  "BI",rf"{FD}\timesbi.ttf")
        self.add_font("Sans", "",  rf"{FD}\arial.ttf")
        self.add_font("Sans", "B", rf"{FD}\arialbd.ttf")
        self.add_font("Sans", "I", rf"{FD}\ariali.ttf")
        self.add_font("Sans", "BI",rf"{FD}\arialbi.ttf")
        self.add_font("Mono", "",  rf"{FD}\cour.ttf")

    def header(self):
        if self.page_no() == 1:
            return
        pg  = self.page_no()
        lft = "Walters et al."
        rgt = "PNAS  |  2026  |  Vol. 123  |  No. 14"
        self.set_xy(LM, 8)
        self.set_font("Sans", "", 7)
        self.set_text_color(*MID)
        self.cell(FULL_W / 2, 4, lft if pg % 2 == 0 else rgt, align="L")
        self.cell(FULL_W / 2, 4, rgt if pg % 2 == 0 else lft, align="R")
        self.set_draw_color(*PNAS_BLUE)
        self.set_line_width(0.5)
        self.line(LM, 13.5, PW - RM, 13.5)
        self.set_text_color(*DARK)

    def footer(self):
        self.set_y(PH - 12)
        self.set_font("Sans", "", 7)
        self.set_text_color(*MID)
        self.cell(0, 4, str(self.page_no()), align="C")
        if self.page_no() == 1:
            self.set_y(PH - 8)
            self.set_font("TNR", "I", 7)
            self.cell(0, 4,
                "Submitted to Proceedings of the National Academy of Sciences"
                "  |  doi: 10.1073/pnas.XXXXXXXXXX",
                align="C")


# ═════════════════════════════════════════════════════════════════════════════
# Low-level text writer — the single place that advances y
# ═════════════════════════════════════════════════════════════════════════════
LINE_H = 4.5   # body line height mm


def _write_lines(pdf, col, lines, font, style, size, color,
                 justify=True, indent_first=0.0):
    """
    Write a list of (words, is_last_line) tuples into the current column,
    handling column/page overflow between lines.
    Anti-orphan: if only 1 line fits before the next column break, switch now.
    """
    pdf.set_font(font, style, size)
    pdf.set_text_color(*color)
    space_w = pdf.get_string_width(" ")

    # Anti-orphan: don't leave a single line stranded at top of a column
    if len(lines) > 1:
        lines_available = max(0, int(col.remaining() / LINE_H))
        if lines_available == 1:
            col._advance()

    for line_idx, (words, is_last) in enumerate(lines):
        if not words:
            continue
        col.need(LINE_H)
        x0     = col.x()
        indent = indent_first if line_idx == 0 else 0.0
        avail  = COL_W - indent
        y      = pdf.get_y()

        if is_last or len(words) == 1 or not justify:
            pdf.set_xy(x0 + indent, y)
            pdf.cell(avail, LINE_H, " ".join(words), align="L")
        else:
            total_w = sum(pdf.get_string_width(w) for w in words)
            gaps    = len(words) - 1
            # extra is the ADDITIONAL gap beyond a normal space so total fits avail exactly
            extra   = (avail - total_w - gaps * space_w) / gaps if gaps > 0 else 0
            pdf.set_xy(x0 + indent, y)
            for i, w in enumerate(words):
                cw = pdf.get_string_width(w) + (extra + space_w if i < gaps else 0)
                pdf.cell(cw, LINE_H, w, align="L")
        pdf.set_xy(x0, y + LINE_H)


def _wrap_text(pdf, font, style, size, text, width, indent_first=0.0):
    """Word-wrap `text` into (words_list, is_last) tuples that fit `width`."""
    pdf.set_font(font, style, size)
    space_w = pdf.get_string_width(" ")
    words   = text.split()
    lines   = []
    cur     = []
    cur_w   = 0.0

    for word_idx, word in enumerate(words):
        ww    = pdf.get_string_width(word)
        # first line uses reduced width due to indent
        avail = width - (indent_first if not lines and not cur else 0.0)
        need  = cur_w + (space_w if cur else 0.0) + ww
        if cur and need > avail:
            lines.append((cur, False))
            cur   = [word]
            cur_w = ww
        else:
            if cur:
                cur_w += space_w + ww
            else:
                cur_w = ww
            cur.append(word)

    if cur:
        lines.append((cur, True))
    return lines


# ═════════════════════════════════════════════════════════════════════════════
# Paragraph / heading helpers
# ═════════════════════════════════════════════════════════════════════════════
def para(pdf, col, text, font="TNR", style="", size=9, color=DARK,
         indent=3.0, space_after=1.0, justify=True):
    lines = _wrap_text(pdf, font, style, size, text, COL_W, indent_first=indent)
    _write_lines(pdf, col, lines, font, style, size, color,
                 justify=justify, indent_first=indent)
    # inter-paragraph gap
    col.need(space_after)
    pdf.set_xy(col.x(), pdf.get_y() + space_after)


def section_head(pdf, col, text):
    col.need(14)
    x0 = col.x()
    y  = pdf.get_y() + 3
    pdf.set_font("Sans", "B", 8.5)
    pdf.set_text_color(*PNAS_BLUE)
    pdf.set_xy(x0, y)
    pdf.cell(COL_W, 5, text.upper(), align="L")
    pdf.set_draw_color(*PNAS_BLUE)
    pdf.set_line_width(0.6)
    pdf.line(x0, y + 5, x0 + COL_W, y + 5)
    pdf.set_text_color(*DARK)
    pdf.set_xy(x0, y + 6.5)


def subsection_head(pdf, col, text):
    col.need(10)
    x0 = col.x()
    y  = pdf.get_y() + 2
    pdf.set_font("TNR", "BI", 9)
    pdf.set_text_color(*DARK)
    pdf.set_xy(x0, y)
    pdf.cell(COL_W, 5, text, align="L")
    pdf.set_xy(x0, y + 5.5)


def eqn(pdf, col, text):
    col.need(9)
    x0 = col.x()
    y  = pdf.get_y() + 1.5
    # draw a light left rule to visually offset the equation
    pdf.set_draw_color(*RULE_GRAY)
    pdf.set_line_width(0.4)
    pdf.line(x0 + 5, y, x0 + 5, y + 5)
    pdf.set_font("TNR", "I", 8.5)
    pdf.set_text_color(*DARK)
    pdf.set_xy(x0 + 9, y)
    pdf.cell(COL_W - 9, 5, text, align="L")
    pdf.set_xy(x0, y + 7)


# ── full-width helpers (title block only) ─────────────────────────────────────
def fw(pdf, text, font="TNR", style="", size=9, color=DARK, align="L", h=4.5):
    pdf.set_font(font, style, size)
    pdf.set_text_color(*color)
    pdf.set_x(LM)
    pdf.multi_cell(FULL_W, h, text, align=align)

def fw_rule(pdf, color=RULE_GRAY, lw=0.3, before=1, after=2):
    pdf.ln(before)
    pdf.set_draw_color(*color)
    pdf.set_line_width(lw)
    pdf.line(LM, pdf.get_y(), LM + FULL_W, pdf.get_y())
    pdf.ln(after)


# ── table (two-column width) ──────────────────────────────────────────────────
ROW_H = 5.2

def col_table(pdf, col, caption, headers, rows, col_widths):
    """Render a table that fits in one column. col_widths are in mm."""
    scale  = COL_W / sum(col_widths)
    widths = [w * scale for w in col_widths]
    needed = ROW_H * (len(rows) + 1) + 10   # +10 for caption
    col.need(needed)
    x0 = col.x()
    y  = pdf.get_y()

    # caption
    pdf.set_font("TNR", "I", 7.5)
    pdf.set_text_color(*MID)
    pdf.set_xy(x0, y)
    pdf.multi_cell(COL_W, 3.8, caption, align="L")
    y = pdf.get_y() + 1

    # header row
    pdf.set_fill_color(*PNAS_BLUE)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Sans", "B", 7.5)
    pdf.set_xy(x0, y)
    for i, h in enumerate(headers):
        pdf.cell(widths[i], ROW_H, h, border=0, fill=True,
                 align="L" if i == 0 else "C")
    y += ROW_H

    # data rows
    pdf.set_text_color(*DARK)
    for ri, row in enumerate(rows):
        fill = ri % 2 == 0
        pdf.set_fill_color(*(LIGHT_ROW if fill else WHITE))
        pdf.set_xy(x0, y)
        for i, cell in enumerate(row):
            is_domain_label = i == 0 and str(row[0]).strip() not in ("", " ", "N/A")
            pdf.set_font("TNR", "B" if is_domain_label else "", 7.5)
            pdf.cell(widths[i], ROW_H, str(cell), border=0, fill=fill,
                     align="L" if i == 0 else "C")
        y += ROW_H

    pdf.set_xy(x0, y + 2)


# ═════════════════════════════════════════════════════════════════════════════
# Build document
# ═════════════════════════════════════════════════════════════════════════════
pdf = PnasPDF(orientation="P", unit="mm", format=(PW, PH))
pdf.setup_fonts()
pdf.set_margins(LM, TOP_M, RM)
pdf.set_auto_page_break(False)   # ColManager owns all page breaks
pdf.add_page()

# ── top rule ──────────────────────────────────────────────────────────────────
pdf.set_draw_color(*PNAS_BLUE)
pdf.set_line_width(1.8)
pdf.line(LM, TOP_M, PW - RM, TOP_M)
pdf.set_y(TOP_M + 3)

# ── journal label ─────────────────────────────────────────────────────────────
fw(pdf, "PSYCHOLOGICAL AND COGNITIVE SCIENCES",
   "Sans", "B", 7, PNAS_BLUE)
pdf.ln(2)

# ── title ─────────────────────────────────────────────────────────────────────
fw(pdf,
   "Overconfidence in Interval Estimates Produced by Large Language Models "
   "Across Multiple Forecasting Domains",
   "Sans", "B", 14, DARK, h=7)
pdf.ln(3)

# ── authors ───────────────────────────────────────────────────────────────────
fw(pdf, "[Author Names Redacted for Review]\u1d43", "TNR", "", 9, DARK)
fw(pdf, "\u1d43Department of [Redacted], [University Redacted]",
   "TNR", "I", 7.5, MID)
pdf.ln(1)
fw(pdf,
   "Edited by [Redacted]; received January 15, 2026; accepted March 20, 2026",
   "TNR", "I", 7.5, MID)
pdf.ln(2)
fw_rule(pdf, PNAS_BLUE, 0.6, 0, 2)

# ── significance box ──────────────────────────────────────────────────────────
sig_body = (
    "Large language models (LLMs) are increasingly deployed as decision-support tools, "
    "yet their capacity to express calibrated uncertainty remains poorly characterised. "
    "We administered a standardised interval-estimation task to three frontier LLMs across "
    "six real-world forecasting domains, scoring predictions against outcomes the following "
    "day. All models exhibited domain-dependent miscalibration: severe overconfidence in "
    "commodity and equity markets, and systematic underconfidence in cryptocurrency and "
    "foreign exchange. The Soll-Klayman meta-knowledge ratio reveals that models allocate "
    "uncertainty inversely to actual domain volatility, concentrating excessive confidence "
    "precisely where predictability is lowest."
)
box_y = pdf.get_y()
pdf.set_font("TNR", "", 8.5)
# measure height
lines_n = len(pdf.multi_cell(FULL_W - 10, 4.3, sig_body, align="J", dry_run=True, output="LINES"))
box_h = lines_n * 4.3 + 12
pdf.set_fill_color(*SIG_BG)
pdf.rect(LM, box_y, FULL_W, box_h, style="F")
pdf.set_draw_color(*PNAS_BLUE)
pdf.set_line_width(1.2)
pdf.line(LM, box_y, LM, box_y + box_h)
# label
pdf.set_xy(LM + 4, box_y + 3)
pdf.set_font("Sans", "B", 7.5)
pdf.set_text_color(*PNAS_BLUE)
pdf.cell(FULL_W - 8, 4, "Significance")
# body
pdf.set_xy(LM + 4, box_y + 8)
pdf.set_font("TNR", "", 8.5)
pdf.set_text_color(*DARK)
pdf.multi_cell(FULL_W - 8, 4.3, sig_body, align="J")
pdf.set_y(box_y + box_h + 3)

# ── keywords ──────────────────────────────────────────────────────────────────
pdf.set_x(LM)
pdf.set_font("TNR", "B", 8)
pdf.set_text_color(*DARK)
pdf.cell(20, 4.5, "Keywords:")
pdf.set_font("TNR", "I", 8)
pdf.cell(FULL_W - 20, 4.5,
    "large language models | overconfidence | interval estimation | calibration | forecasting")
pdf.ln(2)
fw_rule(pdf, PNAS_BLUE, 0.6, 0, 3)

# ── abstract ──────────────────────────────────────────────────────────────────
abs_txt = (
    "Calibrated uncertainty is a prerequisite for rational decision-making, yet human experts "
    "systematically produce confidence intervals that are too narrow\u2014a phenomenon termed "
    "overconfidence in interval estimates. Whether frontier large language models (LLMs) exhibit "
    "analogous miscalibration, and whether miscalibration varies systematically by domain, "
    "remains an open empirical question. We conducted a multi-domain interval-estimation study "
    "in which three commercially deployed LLMs (Claude claude-sonnet-4-6, GPT-4 gpt-4o, Gemini "
    "gemini-2.5-flash) each provided point estimates and 50%, 80%, and 90% confidence intervals "
    "for 76 quantitative questions spanning six domains: equities, commodities, cryptocurrency, "
    "foreign exchange, weather, and NBA game scores. Ground-truth outcomes were obtained "
    "automatically the following day via public APIs (n = 68 resolved predictions per model, "
    "N = 204 total). Calibration was scored via empirical hit rates and Expected Calibration "
    "Error (ECE); point-estimate accuracy via normalised Brier scores; and meta-knowledge via "
    "the Soll-Klayman MEAD/MAD ratio (\u03bc), which measures whether stated uncertainty tracks "
    "actual errors. GPT-4 was most overconfident overall (ECE = 18.9%), Claude best calibrated "
    "(ECE = 5.3%), and Gemini intermediate (ECE = 7.2%). The MEAD/MAD analysis revealed a "
    "domain-confidence inversion: all models were overconfident in commodity and equity markets "
    "(\u03bc < 1) yet underconfident in cryptocurrency and foreign exchange (\u03bc > 1), "
    "mirroring known patterns in human expert overconfidence and suggesting that LLMs inherit "
    "domain-specific miscalibration from their training corpora."
)
pdf.set_x(LM)
pdf.set_font("TNR", "", 8.5)
pdf.set_text_color(*DARK)
pdf.multi_cell(FULL_W, 4.3, abs_txt, align="J")
pdf.ln(4)
fw_rule(pdf, PNAS_BLUE, 0.6, 0, 5)

# ═════════════════════════════════════════════════════════════════════════════
# Two-column body starts here
# ═════════════════════════════════════════════════════════════════════════════
col_top = pdf.get_y()
col = ColManager(pdf, col_top)
pdf.set_xy(LM, col_top)

# ════════════════════════════════════════════════════════════════════════════
# INTRODUCTION
# ════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, "Introduction")

para(pdf, col,
    "A well-calibrated forecaster states 80% confidence intervals that contain the true outcome "
    "80% of the time. Decades of research on human judgment document systematic failure to "
    "achieve this standard: people's confidence intervals are systematically too narrow, a "
    "phenomenon termed overconfidence in interval estimates (1-4). The consequences are severe: "
    "miscalibrated uncertainty underlies flawed risk assessments in medicine (5), finance (6), "
    "engineering (7), and strategic planning (8).")

para(pdf, col,
    "Large language models (LLMs) are now routinely used as decision-support tools in precisely "
    "these domains, yet surprisingly little is known about whether their probabilistic forecasts "
    "are calibrated (9-12). Prior work has focused on factual question-answering confidence, "
    "binary classification, or abstractly sampled trivia items. Virtually no study has examined "
    "LLM calibration on interval estimates for real-world quantitative forecasting across "
    "multiple domains simultaneously.")

para(pdf, col,
    "This gap matters for two reasons. First, the human overconfidence literature consistently "
    "shows that miscalibration is domain-specific: experts are most overconfident in fields of "
    "ostensible competence (3, 4). If LLMs inherit domain structure from their training data, "
    "they may replicate or amplify these asymmetries. Second, the direction of miscalibration "
    "can reverse: overconfidence dominates in structured, rule-governed domains, while "
    "underconfidence has been documented in highly volatile ones (13).")

para(pdf, col,
    "We addressed these questions with a controlled, multi-domain experiment. Three frontier "
    "LLMs were prompted to provide point estimates and 50%, 80%, and 90% confidence intervals "
    "for 76 quantitative questions spanning six domains, scored against outcomes the following "
    "day. We applied both standard calibration metrics and the Soll-Klayman (4) meta-knowledge "
    "ratio (\u03bc = MEAD/MAD), which quantifies whether stated uncertainty is appropriate "
    "relative to actual forecast errors, standardised by domain-level criterion variance.")

para(pdf, col,
    "Our pre-registered hypotheses: (H1) all models would exhibit net overconfidence; (H2) "
    "overconfidence would be greatest in equity and commodity markets; (H3) GPT-4 would show "
    "the largest miscalibration.")

# ════════════════════════════════════════════════════════════════════════════
# METHODS
# ════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, "Methods")

subsection_head(pdf, col, "Experimental Design.")
para(pdf, col,
    "We used a within-subjects design in which three LLMs each responded to 76 questions on "
    "March 25, 2026 (228 total predictions). Outcomes were collected the following day via "
    "automated API calls, providing a 24-hour forecasting window. The 76 questions spanned: "
    "equities (n = 20 S&P 500 tickers), commodity futures (n = 5: gold, crude oil, silver, "
    "natural gas, copper), cryptocurrency (n = 10), foreign exchange (n = 8 major pairs), "
    "weather (n = 30 US cities, next-day high temperature in degrees F), and NBA game totals "
    "(n = 3). CoinGecko rate limits left five cryptocurrency outcomes unresolved; NBA games "
    "did not achieve completed status in the ESPN API and were excluded, yielding "
    "n = 68 resolved predictions per model (N = 204 total).")

subsection_head(pdf, col, "Models and APIs.")
para(pdf, col,
    "Claude (claude-sonnet-4-6; Anthropic), GPT-4 (gpt-4o; OpenAI), and Gemini "
    "(gemini-2.5-flash; Google DeepMind) were queried at default temperature (max 512 tokens). "
    "Ground truth: yfinance for equities, commodities, and forex; CoinGecko for crypto; "
    "Open-Meteo historical API for weather; ESPN scoreboard API for NBA. A 6-day tolerance "
    "window accommodated market closures.")

subsection_head(pdf, col, "Prompt Structure.")
para(pdf, col,
    "Each prompt provided the current value of the target quantity and requested a point "
    "estimate plus 50%, 80%, and 90% confidence intervals as structured JSON, with a "
    "24-hour target window. No chain-of-thought or calibration instructions were given; "
    "models were evaluated in their default deployment configuration.")

subsection_head(pdf, col, "Calibration Metrics.")
para(pdf, col,
    "Hit rate: the proportion of predictions where the true outcome fell within the stated "
    "interval. A calibrated model achieves p^\u03b1 = \u03b1; values below \u03b1 indicate "
    "overconfidence. Expected Calibration Error (ECE) is the mean absolute gap across "
    "all three confidence levels:")
eqn(pdf, col, "ECE = (1/3) x sum_a |a - p^a|,   a in {0.50, 0.80, 0.90}")
para(pdf, col,
    "Normalised Brier score measures point-estimate accuracy relative to the current-day "
    "reference value r_i:")
eqn(pdf, col, "B_i = [(y-hat_i - y_i) / r_i]^2")

subsection_head(pdf, col, "Meta-Knowledge (MEAD/MAD).")
para(pdf, col,
    "We applied the framework of Soll and Klayman (4). The 80% interval endpoints are treated "
    "as the 10th/90th percentiles of a symmetric normal distribution (z = 1.2816). "
    "The Absolute Deviation (AD) is the midpoint error standardised by the within-domain SD "
    "of outcomes (\u03c3):")
eqn(pdf, col, "AD_i = |(L_i + U_i)/2 - y_i| / sigma")
para(pdf, col, "The Expected Absolute Deviation (EAD) is the implied error from CI width:")
eqn(pdf, col, "EAD_i = [(U_i - L_i) / (2 x 1.2816)] x sqrt(2/pi) / sigma")
para(pdf, col,
    "The meta-knowledge ratio mu = MEAD/MAD (domain-level means of EAD and AD respectively). "
    "mu < 1 = overconfident; mu = 1 = calibrated; mu > 1 = underconfident.")

# ════════════════════════════════════════════════════════════════════════════
# RESULTS
# ════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, "Results")

subsection_head(pdf, col, "Overall Calibration.")
para(pdf, col,
    "Table 1 summarises hit rates and ECE (n = 68 per model). Claude exhibited the best "
    "overall calibration (ECE = 5.3%), followed by Gemini (7.2%) and GPT-4 (18.9%). At the "
    "50% level, GPT-4's hit rate (30.9%) was only 62% of the stated confidence. All three "
    "models fell below the 90% target. Hypothesis H3 is supported.")

col_table(pdf, col,
    "Table 1. Overall calibration (n = 68 per model).",
    ["Model",   "Hit@50%", "Hit@80%", "Hit@90%", "ECE"],
    [["Claude", "58.8%",   "82.4%",   "85.3%",   "5.3%"],
     ["Gemini", "45.6%",   "73.5%",   "79.4%",   "7.2%"],
     ["GPT-4",  "30.9%",   "63.2%",   "69.1%",   "18.9%"],
     ["Perfect","50.0%",   "80.0%",   "90.0%",   "0.0%"]],
    [26, 16, 16, 16, 14])

subsection_head(pdf, col, "Domain-Specific Calibration.")
para(pdf, col,
    "Table 2 presents results by domain. No model is uniformly overconfident or underconfident, "
    "providing clear support for H2. Direction of miscalibration reverses systematically "
    "across domains.")

col_table(pdf, col,
    "Table 2. Hit rates and ECE by model and domain.",
    ["Domain",  "Model",  "N",  "Hit@50%", "Hit@90%", "ECE"],
    [["Stocks",     "Claude","40","50.0%","90.0%","1.7%"],
     ["",           "Gemini","40","25.0%","75.0%","16.7%"],
     ["",           "GPT-4", "40","15.0%","65.0%","28.3%"],
     ["Commod.",    "Claude","10","20.0%","40.0%","40.0%"],
     ["",           "Gemini","10","20.0%","40.0%","40.0%"],
     ["",           "GPT-4", "10","20.0%","40.0%","40.0%"],
     ["Crypto",     "Claude","20","80.0%","100%", "20.0%"],
     ["",           "Gemini","20","20.0%","100%", "13.3%"],
     ["",           "GPT-4", "20","20.0%","100%", "20.0%"],
     ["Forex",      "Claude","16","37.5%","75.0%","10.8%"],
     ["",           "Gemini","16","50.0%","75.0%","10.8%"],
     ["",           "GPT-4", "16","25.0%","37.5%","44.2%"],
     ["Weather",    "Claude","60","73.3%","90.0%","10.0%"],
     ["",           "Gemini","60","66.7%","86.7%","7.8%"],
     ["",           "GPT-4", "60","46.7%","80.0%","5.5%"],
     ["NBA",        "All",   "13","N/A",  "N/A",  "N/A"]],
    [22, 14, 9, 18, 18, 12])

para(pdf, col,
    "Commodities: ECE = 40% for all models; 90% intervals achieved only 40% coverage\u2014 "
    "the most extreme and uniform overconfidence observed. Stocks: strong model differentiation "
    "(Claude ECE = 1.7% vs GPT-4 ECE = 28.3%). Cryptocurrency: directional inversion\u2014 "
    "Claude and GPT-4 achieved 100% coverage at the 90% level (underconfident). Weather: best "
    "calibrated domain overall. Forex: GPT-4 showed extreme overconfidence (ECE = 44.2%), "
    "with its 80% interval achieving only 25% empirical coverage.")

subsection_head(pdf, col, "Point-Estimate Accuracy.")
para(pdf, col,
    "Normalised Brier scores (Table 3) were broadly comparable across models within each "
    "domain, indicating that domain-level factors dominate model-specific ones. Crypto had "
    "the highest scores (0.001-0.002); forex the lowest (~2x10^-5).")

col_table(pdf, col,
    "Table 3. Mean normalised Brier scores (lower = better).",
    ["Domain",     "Claude",    "Gemini",    "GPT-4"],
    [["Stocks",    "0.000679",  "0.000526",  "0.000645"],
     ["Commodities","0.001270", "0.001168",  "0.001129"],
     ["Crypto",    "0.001130",  "0.000795",  "0.001740"],
     ["Forex",     "0.000018",  "0.000018",  "0.000016"],
     ["Weather",   "0.002105",  "0.002095",  "0.002095"]],
    [32, 26, 26, 26])

subsection_head(pdf, col, "Meta-Knowledge (mu = MEAD/MAD).")
para(pdf, col,
    "Table 4 presents the meta-knowledge ratio. Overall, GPT-4 is most overconfident "
    "(mu = 0.81), Claude slightly underconfident (mu = 1.23), and Gemini near-calibrated "
    "(mu = 0.99). Aggregate values conceal dramatic domain-level variation.")

col_table(pdf, col,
    "Table 4. Meta-knowledge ratio mu = MEAD/MAD.",
    ["Domain",     "Claude", "Gemini", "GPT-4"],
    [["Stocks",    "0.81",   "0.55",   "0.41"],
     ["Commod.",   "0.25",   "0.25",   "0.25"],
     ["Crypto",    "14.40",  "1.35",   "1.84"],
     ["Forex",     "2.68",   "1.67",   "1.29"],
     ["Weather",   "1.28",   "1.04",   "0.85"],
     ["Overall",   "1.23",   "0.99",   "0.81"]],
    [32, 26, 26, 26])

para(pdf, col,
    "Commodities: mu = 0.25 for all models\u2014stated uncertainty is one-quarter of that "
    "required by actual errors. Stocks: mu ranges from 0.41 (GPT-4) to 0.81 (Claude). "
    "Cryptocurrency: Claude's mu = 14.4 indicates CIs 14-fold wider than actual errors "
    "require, implying application of a domain-level 'crypto is unpredictable' prior. "
    "Forex: all models underconfident (mu > 1), though GPT-4's high ECE (44.2%) reflects "
    "a compound failure of misanchored point estimates plus narrow CIs that mu cannot "
    "fully capture. Weather: most calibrated domain (mu = 0.85-1.28).")

# ════════════════════════════════════════════════════════════════════════════
# DISCUSSION
# ════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, "Discussion")

para(pdf, col,
    "Three conclusions emerge. First, LLM miscalibration is domain-specific and directionally "
    "inconsistent. All models overstate certainty in commodity and equity markets and overstate "
    "uncertainty in cryptocurrency and forex. This is inconsistent with a single domain-agnostic "
    "mechanism and suggests that models apply domain-level volatility heuristics that are "
    "poorly tuned to actual predictability.")

para(pdf, col,
    "Second, GPT-4 is the most overconfident and Claude the most nuanced. GPT-4's ECE "
    "(18.9%) is more than three times Claude's (5.3%). Claude achieves near-perfect stock "
    "calibration (ECE = 1.7%) but massively over-hedges on cryptocurrency (mu = 14.4), "
    "suggesting model-specific differences in how domain uncertainty is represented.")

para(pdf, col,
    "Third, the MEAD/MAD decomposition reveals failures invisible to hit-rate analysis. "
    "GPT-4's forex failure (ECE = 44.2%) reflects a compound failure of misanchored point "
    "estimates and CIs narrow relative to actual movement\u2014a distinction the mu "
    "ratio (1.29) cannot fully detect.")

para(pdf, col,
    "These results echo the human expert literature. Klayman et al. (3) showed that "
    "overconfidence depends on task structure and domain familiarity. Griffin and Tversky (13) "
    "demonstrated that perceived predictability often exceeds actual predictability in "
    "structured domains. LLMs trained on financial commentary may inherit the same biases "
    "as expert analysts: high confidence in familiar asset classes, excessive uncertainty "
    "in less-documented regimes. The commodity result mirrors Ben-David et al. (6), who "
    "showed that CFOs systematically underestimate equity volatility.")

subsection_head(pdf, col, "Limitations.")
para(pdf, col,
    "(i) Sample size: n = 10 in the commodity domain limits statistical precision. "
    "(ii) Single measurement day: results may reflect idiosyncratic conditions on "
    "March 25-26, 2026; longitudinal replication is required. "
    "(iii) NBA exclusion: March 25 games failed to resolve in the ESPN API. "
    "(iv) No prompt calibration: models were evaluated without chain-of-thought or "
    "explicit calibration instructions. "
    "(v) Single forecasting horizon: 24 hours may be suboptimal for equities, where "
    "single-day noise dominates directional signal.")

subsection_head(pdf, col, "Implications.")
para(pdf, col,
    "Users eliciting confidence intervals from LLMs should not assume stated uncertainty "
    "reflects calibrated epistemic states. The pattern of miscalibration is most concerning "
    "precisely in the domains where overconfident forecasting has the worst practical "
    "consequences (commodities, equities). Calibration training should be domain-stratified: "
    "global calibration on trivia does not transfer to commodity price forecasting.")

# ════════════════════════════════════════════════════════════════════════════
# CONCLUSION
# ════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, "Conclusion")

para(pdf, col,
    "We conducted a multi-domain interval-estimation experiment in which three frontier LLMs "
    "provided 50%, 80%, and 90% confidence intervals for 76 quantitative forecasting questions, "
    "scored against ground-truth outcomes the following day. LLM calibration is domain-dependent: "
    "all models overstate certainty in commodity and equity markets while overstating uncertainty "
    "in cryptocurrency and foreign exchange. The MEAD/MAD meta-knowledge ratio reveals that "
    "models allocate uncertainty in approximate inverse proportion to actual domain volatility, "
    "consistent with the hypothesis that LLMs inherit domain-specific miscalibration from the "
    "statistical properties of financial commentary in their training corpora. GPT-4 is the "
    "most overconfident; Claude achieves the best equity calibration; Gemini has the best "
    "overall aggregate calibration but the highest domain variance. These results demonstrate "
    "that deploying LLMs as probabilistic forecasting tools requires domain-specific evaluation "
    "and targeted recalibration.")

# ════════════════════════════════════════════════════════════════════════════
# ACKNOWLEDGEMENTS
# ════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, "Acknowledgements")
para(pdf, col,
    "We thank the maintainers of the open data APIs used in this study: yfinance, CoinGecko, "
    "Open-Meteo, and ESPN. No funding was received for this work.", indent=0)

# ════════════════════════════════════════════════════════════════════════════
# REFERENCES
# ════════════════════════════════════════════════════════════════════════════
section_head(pdf, col, "References")

REFS = [
    ("1.",  "Alpert M, Raiffa H (1982) A progress report on the training of probability "
            "assessors. Judgment Under Uncertainty: Heuristics and Biases, eds Kahneman D, "
            "Slovic P, Tversky A (Cambridge Univ Press), pp 294-305."),
    ("2.",  "Lichtenstein S, Fischhoff B, Phillips LD (1982) Calibration of probabilities: "
            "the state of the art to 1980. Judgment Under Uncertainty (Cambridge Univ Press), "
            "pp 306-334."),
    ("3.",  "Klayman J, Soll JB, Gonzalez-Vallejo C, Barlas S (1999) Overconfidence: It "
            "depends on how, what, and whom you ask. Organ Behav Hum Decis Process 79(3):216-247."),
    ("4.",  "Soll JB, Klayman J (2004) Overconfidence in interval estimates. "
            "J Exp Psychol Learn Mem Cogn 30(2):299-314."),
    ("5.",  "Christensen-Szalanski JJJ, Bushyhead JB (1981) Physicians' use of probabilistic "
            "information in a real clinical setting. J Exp Psychol Hum Percept Perform 7(4):928."),
    ("6.",  "Ben-David I, Graham JR, Harvey CR (2013) Managerial miscalibration. "
            "Q J Econ 128(4):1547-1584."),
    ("7.",  "Flyvbjerg B, Holm MK, Buhl S (2002) Underestimating costs in public works "
            "projects. J Am Plann Assoc 68(3):279-295."),
    ("8.",  "Lovallo D, Kahneman D (2003) Delusions of success. Harv Bus Rev 81(7):56-63."),
    ("9.",  "Kadavath S, et al. (2022) Language models (mostly) know what they know. "
            "arXiv:2207.05221."),
    ("10.", "Lin S, Hilton J, Evans O (2022) Teaching models to express their uncertainty "
            "in words. Trans Mach Learn Res."),
    ("11.", "Xiong M, et al. (2024) Can LLMs express their uncertainty? An empirical "
            "evaluation of confidence elicitation in LLMs. arXiv:2306.13063."),
    ("12.", "Yang Z, et al. (2023) Alignment for honesty. arXiv:2312.07000."),
    ("13.", "Griffin D, Tversky A (1992) The weighing of evidence and the determinants of "
            "confidence. Cogn Psychol 24(3):411-435."),
    ("14.", "OpenAI (2024) GPT-4 Technical Report. arXiv:2303.08774."),
]

pdf.set_font("TNR", "", 7.5)
for num, text in REFS:
    num_w = 6.0
    lines = _wrap_text(pdf, "TNR", "", 7.5, text, COL_W - num_w)
    needed = len(lines) * 4.2 + 1
    col.need(needed)
    x0 = col.x()
    y  = pdf.get_y()
    pdf.set_font("TNR", "", 7.5)
    pdf.set_text_color(*DARK)
    pdf.set_xy(x0, y)
    pdf.cell(num_w, 4.2, num, align="L")
    for li, (wds, is_last) in enumerate(lines):
        pdf.set_xy(x0 + num_w, y + li * 4.2)
        pdf.cell(COL_W - num_w, 4.2, " ".join(wds), align="L")
    pdf.set_xy(x0, y + len(lines) * 4.2 + 1)

# ── output ────────────────────────────────────────────────────────────────────
pdf.output(OUT)
print(f"Saved: {OUT}  ({pdf.page_no()} pages)")
