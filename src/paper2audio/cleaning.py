"""Text-level clean-up: remove things nobody wants read aloud.

Each rule has a name so that journal profiles can disable or add rules.
Rules run in list order.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Union

Repl = Union[str, Callable[[re.Match], str]]


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern
    repl: Repl = ""

    def apply(self, text: str) -> str:
        return self.pattern.sub(self.repl, text)


def rule(name: str, pattern: str, repl: Repl = "", flags: int = 0) -> Rule:
    return Rule(name, re.compile(pattern, flags), repl)


# --------------------------------------------------------------------------- statistics

_STAT_NAME = r"(?:p|P|t|F|r|R2|R²|z|Z|U|W|H|d|g|b|B|β|η2|η²|ηp2|η²p|ω2|ω²|χ2|χ²|BF(?:01|10)?|OR|RR|HR|CI|SD|SEM|SE|M|Mdn|df|N|n|k|τ|ρ|κ|Q|T|V|X2|AIC|BIC|LL)"
_NUM_VAL = r"[-−–]?\s?(?:\d+(?:[.,]\d+)?|\.\d+)(?:\s?(?:[×x]|e)\s?10\^?[-−]?\d+|e[-−]?\d+)?\s?%?"
_STAT = (
    rf"(?<![A-Za-z]){_STAT_NAME}"
    r"(?:\s?\(\s?[\d.,\s]+\))?"  # degrees of freedom: t(23), F(1, 40)
    rf"\s?(?:[=<>≤≥≈]|&lt;|&gt;)\s?{_NUM_VAL}"
    r"(?:\s?(?:\[[^\]]{0,40}\]|\([^()]{0,40}\)))?"  # CI [0.1, 0.4]
)
_STAT_RE = re.compile(_STAT)
_CI_RE = re.compile(r"\d{2}\s?%\s?(?:CI|confidence interval)s?\s?[:=]?\s?[\[(][^\])]{0,50}[\])]", re.I)


_ASSIGNMENT = re.compile(r"(?:[=<>≤≥≈]|&lt;|&gt;)\s?[-−–]?\s?\.?\d")
_KEEP_SEGMENT = re.compile(r"^\s*[nN]\s?=\s?\d[\d,]*\s*$")  # "(n = 12; 7 female)"
_FIG_SEGMENT = re.compile(
    r"^\s*(?:see |cf\. |e\.g\.,? |compare )?(?:(?:Supplementary|Suppl\.|Extended Data|Supporting)\s)?"
    r"(?:Fig(?:ure)?s?\.?|Tables?|Movies?|Videos?|Eqs?\.?|Equations?|Box(?:es)?|Appendix)\s?[S]?\d", re.I)


def _strip_stat_parentheticals(m: re.Match) -> str:
    """Drop the statistical and figure-pointer parts of a parenthetical.

    '(mean: r = 0.01, z = 0.59; Fig. 1D)' -> ''
    '(alpha = 0.05)' -> ''          '(n = 12; 7 female)' -> unchanged
    """
    whole = m.group(0)
    opener, closer = whole[0], whole[-1]
    segments = whole[1:-1].split(";")
    kept = [seg for seg in segments
            if _KEEP_SEGMENT.match(seg)
            or not (_ASSIGNMENT.search(seg) or _CI_RE.search(seg) or _FIG_SEGMENT.match(seg))]
    if len(kept) == len(segments):
        return whole
    return f"{opener}{';'.join(kept).strip()}{closer}" if kept else ""


# Outside parentheses we only remove unambiguous statistics: p values, Bayes
# factors, and test statistics that carry degrees of freedom ("t(23) = 2.1").
# A bare "t = 0" or "n = 12" may be ordinary prose and is kept.
_INLINE_STAT = (
    r"(?<![A-Za-z])(?:"
    rf"(?:p|P|BF(?:01|10)?)\s?(?:[=<>≤≥]|&lt;|&gt;)\s?{_NUM_VAL}"
    rf"|(?:t|F|z|χ2|χ²|U|W|H|r)\s?\(\s?[\d.,\s]+\)\s?=\s?{_NUM_VAL}"
    r")"
)

# --------------------------------------------------------------------------- citations

_NAME = r"(?:(?:[Vv]an |[Vv]on |[Dd]e |[Dd]er |[Dd]en |[Ll]a |[Ll]e |[Dd]i |[Dd]a |[Dd]u |dos |[Dd]el |Mc|Mac|O['’])*[A-Z][\w'’\-]+)"
_AUTHORS = rf"{_NAME}(?:(?: et al\.?)|(?:,? (?:and|&) {_NAME})|(?:, {_NAME})*(?:,? (?:and|&) {_NAME})?)?"
_YEARS = r"(?:\d{4}[a-z]?|in press|submitted|n\.d\.)(?:\s?[,;]\s?(?:\d{4}[a-z]?|in press))*"
_CITE = rf"(?:(?:see|e\.g\.|i\.e\.|cf\.|but see|see also|reviewed in|for (?:a )?review(?:s)?,? see)[,:]?\s+)?{_AUTHORS},?\s+{_YEARS}(?:,\s?(?:p|pp)\.\s?\d+(?:[-–]\d+)?)?"
_CITE_PAREN = rf"\(\s?{_CITE}(?:\s?;\s?{_CITE})*\s?\)"
_CITE_ONLY = re.compile(rf"^\s*{_CITE}\s*$")


def _strip_citation_segments(m: re.Match) -> str:
    """'(vlPFC; Romanski and Diehl, 2011)' -> '(vlPFC)'; all-citation groups vanish."""
    segments = m.group(1).split(";")
    kept = [s.strip() for s in segments if not _CITE_ONLY.match(s)]
    if len(kept) == len(segments):
        return m.group(0)
    return f" ({'; '.join(kept)})" if kept else ""


GENERIC_RULES: list[Rule] = [
    # --- identifiers & links
    rule("doi", r"(?:https?://(?:dx\.)?doi\.org/|\bdoi:\s?|\bDOI:?\s?)?\b10\.\d{4,9}/[^\s,;)\]—]*[^\s,;)\].—]"),
    rule("url", r"(?:\bhttps?://|\bwww\.)[^\s,;)\]]*[^\s,;)\].]"),
    rule("email", r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    rule("orcid", r"\b(?:ORCID:?\s?)?\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b"),
    rule("arxiv_id", r"\barXiv:\s?\d{4}\.\d{4,5}(?:v\d+)?(?:\s?\[[\w.-]+\])?", flags=re.I),
    # --- citations
    rule("numeric_citation", r"\s?\[\s?\d+(?:\s?[-–,]\s?\d+)*\s?\]"),
    # what is left of "(for example, [12])", "(but see [94])", "(see [3] for a review)" once the numbers are gone
    rule("dangling_citation_lead", r"\s?\((?:for (?:example|instance)|e\.g\.|i\.e\.|see(?: also)?|but see|though see|cf\.|reviewed in)[,;:]?\s*\)",
         flags=re.I),
    rule("dangling_see_for", r"(?:\s?[;,]\s?|\s?\()(?:see|reviewed in)(?: also)? for (?:an? )?(?:[a-z]+ )?(?:review|overview|summary|details|discussion)s?\)",
         lambda m: ")" if not m.group(0).lstrip().startswith("(") else "", flags=re.I),
    rule("glossary_reference", r"\s?\((?:see )?Glossary\)"),
    rule("refs_parenthetical", r"\s?\((?:see |cf\. )?refs?\.\s?\d+(?:\s?(?:[-–,]|and)\s?\d+)*\)", flags=re.I),
    rule("author_year_citation", _CITE_PAREN),
    rule("mixed_citation_parenthetical", r"\s?\(([^()]{0,600})\)", _strip_citation_segments),
    rule("author_year_in_brackets", rf"\[\s?{_CITE}(?:\s?;\s?{_CITE})*\s?\]"),
    rule("narrative_citation_year", rf"(et al\.?|{_NAME})\s?\(\s?(?:\d{{4}}[a-z]?|in press)(?:\s?[,;]\s?\d{{4}}[a-z]?)*\s?\)", r"\1"),
    # --- statistics
    rule("confidence_interval", rf",?\s?{_CI_RE.pattern}", flags=re.I),
    # one level of nesting allowed: "(Kruskal-Wallis, H(2) = 11.4, ε² = 0.12)"
    rule("stat_parenthetical", r"[(\[](?:[^()\[\]]|\([^()]{0,40}\)|\[[^\[\]]{0,40}\]){0,300}[)\]]",
         _strip_stat_parentheticals),
    rule("inline_stats", rf"[,;]?\s?{_INLINE_STAT}(?:\s?[,;]\s?(?:{_STAT}))*"),
    # --- references to figures, tables, equations, supplements
    rule(
        "figure_reference",
        r"\s?\((?:see |cf\. |e\.g\.,? )?(?:(?:Supplementary|Suppl\.|Extended Data|Supporting)\s)?(?:Fig(?:ure)?s?\.?|Tables?|Movies?|Videos?|Eqs?\.?|Equations?|Box|Appendix|Note|Data|Information|Section|Sect?\.|§)\s?[S]?[\dA-Z][^()]{0,60}\)",
    ),
    rule("supplementary_reference", r"\s?\((?:see )?(?:Supplementary|Suppl\.|Supporting) (?:Information|Material|Materials|Text|Methods|Note|Notes)[^()]{0,30}\)"),
    rule("equation_number", r"\s+\(\d{1,3}[a-z]?\)\s*$"),
    # --- typographic leftovers
    rule("footnote_marks", r"(?<=\w)[*†‡§¶]+"),
    rule("empty_brackets", r"\s?[(\[]\s*[,;]?\s*[)\]]"),
]

TIDY_RULES: list[Rule] = [
    rule("space_before_punct", r"\s+([,.;:!?)])", r"\1"),
    rule("space_after_open", r"([(\[])\s+", r"\1"),
    rule("double_punct", r"([,;:])\s*([,;:.])", r"\2"),
    rule("comma_period", r",\s*\.", "."),
    rule("multi_space", r"[ \t]{2,}", " "),
]


def normalize_unicode(text: str) -> str:
    # NFKC turns ligatures (ﬁ, ﬂ) and full-width chars into plain letters
    # but would also flatten super/subscripts; that is fine for speech.
    text = unicodedata.normalize("NFKC", text)
    # control characters and private-use glyphs (symbol fonts without a Unicode mapping)
    text = "".join(c for c in text if c in "\n\t" or unicodedata.category(c) not in ("Cc", "Co"))
    text = text.replace("­", "").replace("​", "")
    return text


def apply_rules(text: str, rules: list[Rule]) -> str:
    for r in rules:
        text = r.apply(text)
    for r in TIDY_RULES:
        text = r.apply(text)
    return text.strip()
