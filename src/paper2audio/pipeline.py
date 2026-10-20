"""High level pipeline: PDF -> profile -> ordered, cleaned, speakable sections."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import layout, profiles
from .cleaning import apply_rules, normalize_unicode
from .extract import extract
from .models import Document, Kind, Paragraph, Section
from .profiles.base import JournalProfile
from .speech import to_speech
from .year import publication_year

_READABLE = {Kind.BODY}


@dataclass
class Script:
    """What will be read aloud."""

    title: str
    sections: list[Section]
    profile: str
    profile_scores: dict[str, float] = field(default_factory=dict)
    year: int | None = None
    year_source: str = ""
    skipped: list[str] = field(default_factory=list)  # titles of skipped sections

    def to_text(self) -> str:
        out = [f"# {self.title}"] if self.title else []
        for s in self.sections:
            if s.title:
                out.append(f"## {s.title}")
            out.extend(p.text for p in s.paragraphs)
        return "\n\n".join(out).strip() + "\n"


_AFFILIATION = re.compile(
    r"\b(Department|Dept\.|University|Universit[äéà]t?|Institute|Institut|School of|Faculty|College|Center|Centre|"
    r"Hospital|Laborator(y|ies)|Clinic|Research Unit|Max Planck|CNRS|INSERM)\b")


def _looks_like_affiliations(text: str) -> bool:
    hits = len(_AFFILIATION.findall(text))
    return hits >= 2 and hits * 25 >= len(text.split())


def quality_report(script: "Script", limit: int = 15) -> str:
    """Paragraphs that look cut or misplaced: a quick way to spot layout problems."""
    paras = [p.text for s in script.sections for p in s.paragraphs]
    unterminated = [t for t in paras if not re.search(r"[.!?:)\]”\"’]$", t)]
    lowercase = [t for t in paras if t[:1].islower()]
    out = [f"{len(paras)} paragraphs, {len(unterminated)} end mid-sentence, {len(lowercase)} start lowercase"]
    out += [f"  ends:   …{t[-80:]}" for t in unterminated[:limit]]
    out += [f"  starts: {t[:80]}…" for t in lowercase[:limit]]
    return "\n".join(out)


def _looks_like_keywords(text: str) -> bool:
    """'algorithm; deep neural network; eye movements; microsaccade; saccade'"""
    items = [i for i in re.split(r"\s*[;·•|]\s*", text.strip().rstrip(".")) if i]
    return len(items) >= 3 and all(len(i.split()) <= 5 for i in items) and not re.search(r"[.!?]\s", text)


def _looks_like_prose(text: str) -> bool:
    words = text.split()
    if len(words) < 40:
        return False
    capitalised = sum(1 for w in words if w[:1].isupper())
    sentences = len(re.findall(r"[a-z)\]]\.\s+[A-Z]", text))
    return capitalised / len(words) < 0.35 and sentences >= 1


def _norm_title(text: str) -> str:
    return re.sub(r"\W+", " ", text).strip().lower()


def sectionize(paras: list[Paragraph], profile: JournalProfile,
               front_matter: bool = True) -> tuple[str, list[Section], list[str]]:
    title = " ".join(p.text for p in paras if p.kind == Kind.TITLE).strip()
    readable = set(_READABLE)
    if profile.read_captions:
        readable.add(Kind.CAPTION)
    if profile.read_footnotes:
        readable.add(Kind.FOOTNOTE)
    if profile.read_tables:
        readable.add(Kind.TABLE)

    sections: list[Section] = []
    skipped: list[str] = []
    cur = Section(title="")
    sections.append(cur)
    in_front, skipping, after_refs = front_matter, False, False
    junk = profile.junk_paragraph_patterns

    for pos, p in enumerate(paras):
        if p.kind == Kind.TITLE:
            continue
        if p.kind == Kind.HEADING:
            t = p.text.strip()
            if in_front and not profile.ends_front_matter(t):
                continue  # e.g. "ARTICLE INFO", author names set in bold
            in_front = False
            # the title repeated in the last quarter: Science's end page (authors,
            # editor's summary, permissions). Earlier repeats are a title page or a
            # running title above the abstract, and reading goes on.
            if title and pos >= 0.75 * len(paras) and _norm_title(t) == _norm_title(title):
                skipped.append(t)
                break
            if profile.is_end(t):
                skipped.append(t)
                break
            if profile.is_references(t):
                after_refs = after_refs or profile.references_end_main_text
                skipping = True
                skipped.append(t)
                continue
            if after_refs and not profile.is_resume(t):
                skipping = True
                skipped.append(t)
                continue
            after_refs = after_refs and not profile.is_resume(t)
            skipping = profile.is_skipped(t)
            if skipping:
                skipped.append(t)
                continue
            if cur.title and not cur.paragraphs:
                cur.title = f"{cur.title}: {t}"  # "Methods" directly followed by "Participants"
            else:
                cur = Section(title=t)
                sections.append(cur)
            continue
        if skipping or p.kind not in readable:
            continue
        if any(j.search(p.text) for j in junk) or _looks_like_affiliations(p.text) or _looks_like_keywords(p.text):
            continue
        if in_front:
            if not _looks_like_prose(p.text):
                continue
            in_front = False
        last = cur.paragraphs[-1] if cur.paragraphs else None
        if last is not None and p.text[:1].islower() and not re.search(r"[.!?:]['\"”’)]*$", last.text):
            # a sentence interrupted by a dropped footnote or junk line
            cur.paragraphs[-1] = Paragraph(text=f"{last.text} {p.text}", kind=last.kind, page=last.page)
            continue
        cur.paragraphs.append(p)
    return title, [s for s in sections if s.paragraphs], skipped


def clean_sections(sections: list[Section], profile: JournalProfile) -> list[Section]:
    rules = profile.rules()
    out: list[Section] = []
    for s in sections:
        paras = []
        for p in s.paragraphs:
            text = to_speech(apply_rules(normalize_unicode(p.text), rules))
            if len(text.split()) >= 3:
                paras.append(Paragraph(text=text, kind=p.kind, page=p.page))
        parts = []
        for part in s.title.split(": ") if s.title else []:  # "THEORIES OF CONSCIOUSNESS: Global workspace"
            part = re.sub(r"^\s*(\d+(\.\d+)*|[IVX]+)\.?\s+", "", part)  # "II. METHODS" -> "METHODS"
            spoken = to_speech(apply_rules(normalize_unicode(part), rules))
            # "INTRODUCTION" is not an acronym; "PCA" and, in a mixed title, "Method 6: DGCCA" are
            caps = part.isupper() and (len(re.findall(r"[^\W\d_]{3,}", part)) >= 2
                                       or (s.title.isupper() and len(part.strip()) > 4))
            parts.append(spoken.capitalize() if caps else spoken)
        title = ": ".join(parts)
        # "2. Methods: 2.1 Participants" -> "Methods: Participants"
        title = re.sub(r"(^|: )\s*(\d+(\.\d+)*|[IVX]+)\.?\s+", r"\1", title)
        if paras:
            out.append(Section(title=title, paragraphs=paras))
    return out


def _resolve(doc: Document, profile, options) -> tuple[JournalProfile, dict[str, float]]:
    scores: dict[str, float] = {}
    options = dict(options)
    year = options.pop("year", None)
    if profile is None or profile == "auto":
        prof, _, scores = profiles.detect(doc)
    elif isinstance(profile, str):
        prof = profiles.get(profile)
    else:
        prof = profile
    if year is None:
        year, source = publication_year(doc)
    else:
        source = "given"
    prof.adapt(year)
    prof.year_source = source
    for k, v in options.items():  # explicit options win over era defaults
        setattr(prof, k, v)
    return prof, scores


def debug_layout(pdf_path: str, profile: str | JournalProfile | None = None, **options) -> str:
    """Line-by-line dump (page, column, kind, font size, text) in reading order."""
    doc = extract(pdf_path)
    prof, _ = _resolve(doc, profile, options)
    paras = layout.analyse(doc, prof, keep_junk=True)
    out = [f"profile: {prof.name}  year: {prof.year} ({getattr(prof, 'year_source', '')})"]
    for page in doc.pages:
        out.append(f"\n=== page {page.number + 1} ===")
        out.extend(f"c{ln.column:<2} {ln.kind.value:13s} {ln.size:4.1f} {'B' if ln.bold else ' '} "
                   f"x{ln.x0:5.0f}-{ln.x1:<5.0f} y{ln.y0:5.0f}  {ln.text}" for ln in page.lines)
    out.append("\n=== paragraphs ===")
    out.extend(f"[{p.kind.value}] {p.text[:100]}" for p in paras)
    return "\n".join(out) + "\n"


def run(pdf_path: str, profile: str | JournalProfile | None = None, **options) -> Script:
    doc: Document = extract(pdf_path)
    prof, scores = _resolve(doc, profile, options)
    paras = layout.analyse(doc, prof)
    title, sections, skipped = sectionize(paras, prof)
    if not sections:  # front-matter detection ate everything: read from the top
        title, sections, skipped = sectionize(paras, prof, front_matter=False)
    sections = prof.postprocess(clean_sections(sections, prof))
    title = to_speech(apply_rules(normalize_unicode(title), prof.rules()))
    return Script(title=title, sections=sections, profile=prof.name, profile_scores=scores, skipped=skipped,
                  year=prof.year, year_source=getattr(prof, "year_source", ""))
