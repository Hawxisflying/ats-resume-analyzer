from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict
import re

@dataclass
class ResumeSection:
    name: str
    content: str


@dataclass
class ParsedResume:
    skills: List[str] = field(default_factory=list)
    projects: List[str] = field(default_factory=list)
    experience: List[str] = field(default_factory=list)
    education: List[str] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    sections: Dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedJobDescription:
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    qualifications: List[str] = field(default_factory=list)
    preferred_certifications: List[str] = field(default_factory=list)
    sections: Dict[str, str] = field(default_factory=dict)

# -----------------------------
# Section Heading Patterns
# -----------------------------

SECTION_PATTERNS = {
    "skills": [
        r"technical\s+skills?",
        r"skills?",
        r"core\s+skills?",
        r"technical\s+expertise",
        r"competencies",
    ],

    "projects": [
        r"projects?",
        r"academic\s+projects?",
        r"professional\s+projects?",
        r"personal\s+projects?",
    ],

    "experience": [
        r"experience",
        r"work\s+experience",
        r"professional\s+experience",
        r"employment\s+history",
        r"work\s+history",
        r"internships?",
    ],

    "education": [
        r"education",
        r"academic\s+background",
        r"academic\s+qualification",
        r"qualifications?",
    ],

    "certifications": [
        r"certifications?",
        r"licenses?",
        r"training",
        r"professional\s+certifications?",
    ]
}


JD_SECTION_PATTERNS = {
    "required_skills": [
        r"required\s+skills?",
        r"skills?\s+required",
        r"must\s+have",
        r"requirements?",
        r"required",
        r"required\s+qualifications?",
        r"technical\s+requirements?",
        r"technical\s+skills?",
        r"core\s+skills?",
        r"key\s+skills?",
        r"web\s+technologies",
        # A bare "Skills" heading is extremely common in real JDs
        r"skills?",
        # NEW (round 2): "Core Technologies" / "Tech Stack" / bare
        # "Technologies" are extremely common headings used for the
        # primary required tech list in real-world JDs. Previously
        # unmatched, this silently dropped the entire core skills
        # section into an unclassified bucket that was never read by
        # the analyzer — e.g. a JD listing HTML5, CSS3, JavaScript,
        # TypeScript, React, Node.js, Express.js, MySQL, Git, REST APIs
        # under "Core Technologies" had ALL of those terms discarded.
        r"core\s+technologies",
        r"technology\s+stack",
        r"tech\s+stack",
        r"technologies",
        r"tools?\s+(?:and|&)\s+technologies",
    ],

    "preferred_skills": [
        r"preferred\s+skills?",
        r"good\s+to\s+have",
        r"nice\s+to\s+have",
        r"desired\s+skills?",
        r"preferred",
        r"preferred\s+qualifications?",
        r"additional\s+(?:technologies|skills|requirements)?",
        r"bonus\s+(?:skills|points)?",
        r"good\s+to\s+know",
        # NEW (round 2): "Preferred Technologies" heading — same bug
        # class as "Core Technologies" above, for the secondary/bonus
        # tech list.
        r"preferred\s+technologies",
        r"optional\s+technologies",
    ],

    "responsibilities": [
        r"responsibilities",
        r"roles?\s+and\s+responsibilities",
        r"what\s+you.?ll\s+do",
        r"job\s+description",
        r"key\s+responsibilities",
        r"duties",
        r"day.?to.?day",
    ],

    "qualifications": [
        r"qualifications?",
        r"education",
        r"eligibility",
        r"who\s+you\s+are",
        r"minimum\s+qualifications?",
        r"basic\s+qualifications?",
    ],

    "preferred_certifications": [
        r"preferred\s+certifications?",
        r"certifications?",
        r"professional\s+certifications?",
    ],

    "projects": [
        r"projects?",
        r"project\s+experience",
    ]
}

def _normalize_heading(text: str) -> str:
    """
    Normalize a heading before matching.

    Handles plain headings AND markdown-formatted headings, e.g.:
        "Skills:"                       -> "skills"
        "## Key Responsibilities"       -> "key responsibilities"
        "### Additional Technologies (Preferred)" -> "additional technologies"
        "**Required Skills**"           -> "required skills"
    """
    text = text.strip()

    # Strip leading markdown heading hashes (#, ##, ###, ...)
    text = re.sub(r"^#{1,6}\s*", "", text)

    # Strip markdown bold / italic markers (**text**, *text*, __text__, _text_)
    text = re.sub(r"\*{1,3}", "", text)
    text = re.sub(r"_{1,3}", "", text)

    text = text.lower().strip()

    # Strip trailing punctuation/separator noise, repeatedly, to handle
    # any combination of colon/dash/whitespace at the end — JDs use
    # inconsistent styles like "Skills:", "Skills: -", "Skills -", "Skills --",
    # "Skills :", etc. A single anchored pass only catches adjacent runs
    # of ":"/"-" with no whitespace between them, so loop until nothing
    # changes to also catch "colon, space, dash" and similar combos.
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"[:\-–—]+\s*$", "", text).strip()

    # Strip trailing parenthetical qualifiers, e.g. "(Preferred)"
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text)

    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _match_resume_heading(line: str):
    """
    Returns:
        skills
        projects
        experience
        education
        certifications
        None
    """

    heading = _normalize_heading(line)

    for section, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            if re.fullmatch(pattern, heading):
                return section

    return None

def _match_jd_heading(line: str):
    """
    Returns JD section name if matched.
    """

    heading = _normalize_heading(line)

    if not heading:
        return None

    for section, patterns in JD_SECTION_PATTERNS.items():
        for pattern in patterns:
            if re.fullmatch(pattern, heading):
                return section

    return None

# -----------------------------
# Heading Line Detection
# -----------------------------

def _looks_like_heading_line(line: str) -> bool:
    """
    A heading-shaped line is short, has no sentence-ending punctuation,
    and is often markdown-formatted (#, ##, **bold**) or title-cased.
    This lets us recognize headings even before they're matched against
    known patterns, which matters for short markdown sub-headings like
    "### WordPress" that don't correspond to a known JD section but
    should still not be merged into the preceding bullet content as if
    it were a sentence.
    """
    stripped = line.strip()
    if not stripped:
        return False
    if len(stripped) > 60:
        return False
    if stripped.endswith((".", ",", ";")):
        return False
    if re.match(r"^#{1,6}\s", stripped):
        return True
    if re.match(r"^\*{1,3}.+\*{1,3}$", stripped):
        return True
    return False

def _append_section(sections: Dict[str, str], name: str, buffer: List[str]) -> None:
    """
    Append buffered lines to a section instead of overwriting it.

    A JD frequently has the same logical section appear more than once
    under different headings (e.g. "### Additional Technologies (Preferred)"
    and a later "## Preferred Skills" both map to "preferred_skills").
    Overwriting would silently drop the earlier block's content; appending
    preserves all evidence collected under that section name.
    """
    block = "\n".join(buffer).strip()
    if not block:
        return
    existing = sections.get(name, "").strip()
    sections[name] = (existing + "\n" + block).strip() if existing else block


# -----------------------------
# Generic Section Builder
# -----------------------------

def _build_sections(text: str, is_job_description: bool = False) -> Dict[str, str]:
    """
    Splits a resume or job description into logical sections.

    Returns:
    {
        "skills": "...",
        "projects": "...",
        ...
    }

    Markdown sub-headings that don't match a known section pattern
    (e.g. "### WordPress" under "## Technical Requirements") are
    dropped as heading noise rather than being merged into bullet
    content, so they don't pollute extracted terms.
    """

    text = _clean_text(text)

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]      

    sections: Dict[str, str] = {}
    current_section = "general"
    buffer = []

    for line in lines:

        if is_job_description:
            detected = _match_jd_heading(line)
        else:
            detected = _match_resume_heading(line)

        if detected:

            if buffer:
                _append_section(sections, current_section, buffer)

            current_section = detected
            buffer = []

        elif _looks_like_heading_line(line):
            # Unrecognized markdown sub-heading (e.g. "### WordPress").
            # Skip it as noise instead of treating it as bullet content
            # under the current section.
            continue

        else:
            buffer.append(line)

    if buffer:
        _append_section(sections, current_section, buffer)

    return sections

def parse_resume(text: str) -> ParsedResume:
    """
    Parse resume into structured sections.
    """

    sections = _build_sections(text)
    sections = _classify_general_section(sections)

    return ParsedResume(
        sections=sections
    )

DEGREE_KEYWORDS_RE = re.compile(
    r"\b("
    r"bachelor|master|b\.?tech|btech|b\.?e\.?|bca|bsc|b\.?sc|"
    r"m\.?tech|mtech|mca|msc|m\.?sc|phd|doctorate|diploma|"
    r"degree|graduate|undergraduate|postgraduate|"
    r"years?\s+of\s+experience|years?\s+experience|"
    r"computer\s+science|information\s+technology|"
    r"related\s+field|equivalent"
    r")\b",
    re.IGNORECASE,
)


def _split_qualifications_by_content(sections: Dict[str, str]) -> Dict[str, str]:
    """
    Some JDs use a "Qualifications" heading to list their actual technical
    requirements (PHP, MySQL, REST APIs, MVC frameworks, etc.) rather than
    degree/education eligibility criteria. Matching purely on the heading
    name causes the entire tech stack to be silently excluded from
    required_skills, which then makes the skills score meaningless (it
    falls back to a 100% "no requirements" default while real technology
    requirements go uncompared).

    Each bullet/line under "qualifications" is checked individually:
      - lines containing degree/education/experience-duration language
        stay under qualifications
      - everything else (the technology bullets) is moved into
        required_skills, since that's what it actually is
    """
    qual_text = sections.get("qualifications", "").strip()
    if not qual_text:
        return sections

    degree_lines: List[str] = []
    tech_lines: List[str] = []

    for line in qual_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if DEGREE_KEYWORDS_RE.search(line):
            degree_lines.append(line)
        else:
            tech_lines.append(line)

    # Only reclassify if there's a meaningful amount of non-degree,
    # tech-looking content — avoids false-splitting a normal short
    # "Bachelor's degree in CS" qualifications block.
    if len(tech_lines) >= 2:
        sections["qualifications"] = "\n".join(degree_lines).strip()
        existing_required = sections.get("required_skills", "").strip()
        moved = "\n".join(tech_lines).strip()
        sections["required_skills"] = (
            (existing_required + "\n" + moved).strip()
            if existing_required else moved
        )

    return sections


def parse_job_description(text: str) -> ParsedJobDescription:
    """
    Parse JD into structured sections.
    """

    sections = _build_sections(
        text,
        is_job_description=True
    )

    sections = _split_qualifications_by_content(sections)

    # Safety net: don't silently drop unclassified content.
    # If nothing else was extracted, treat leftover "general" text
    # as part of responsibilities so it still contributes evidence.
    general = sections.get("general", "").strip()
    if general:
        has_other_sections = any(
            sections.get(key, "").strip()
            for key in (
                "required_skills",
                "preferred_skills",
                "responsibilities",
                "qualifications",
                "preferred_certifications",
            )
        )
        if not has_other_sections:
            sections["responsibilities"] = (
                sections.get("responsibilities", "") + "\n" + general
            ).strip()

    return ParsedJobDescription(
        sections=sections
    )

# -----------------------------
# Text Cleaning Utilities
# -----------------------------

def _clean_text(text: str) -> str:
    """
    Normalize whitespace while preserving line structure.
    """

    if not text:
        return ""

    text = text.replace("\r", "\n")
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def _clean_line(line: str) -> str:
    """
    Clean individual lines.
    """

    line = line.strip()

    # Remove bullets (including markdown "*" and "-" bullets)
    line = re.sub(r"^[•●▪■◆►▶✓✔◦○*\-]+\s*", "", line)

    # Remove numbering
    line = re.sub(r"^\d+[\.\)]\s*", "", line)

    # Strip leftover markdown emphasis markers around inline text
    line = re.sub(r"\*{1,3}", "", line)
    line = re.sub(r"_{1,3}", "", line)

    # Remove extra spaces
    line = re.sub(r"\s+", " ", line)

    return line.strip()

def _extract_bullet_items(section_text: str):
    """
    Extract bullet points from a section.
    """

    items = []

    for line in section_text.splitlines():

        line = _clean_line(line)

        if not line:
            continue

        items.append(line)

    return items

INLINE_SEPARATORS = [
    "|",
    ",",
    ";",
    "•",
    "·",
]

def _split_inline_items(text: str):
    """
    Split inline lists into separate values.
    """

    values = [text]

    for sep in INLINE_SEPARATORS:

        updated = []

        for value in values:
            updated.extend(value.split(sep))

        values = updated

    return [
        item.strip()
        for item in values
        if item.strip()
    ]

def _normalize_section_content(section_text: str):
    """
    Returns clean list of lines/items from a section.
    """

    cleaned = []

    for line in _extract_bullet_items(section_text):

        parts = _split_inline_items(line)

        cleaned.extend(parts)

    return cleaned

# -----------------------------
# Entity Recognition Patterns
# -----------------------------

DATE_PATTERN = re.compile(
    r"("
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
    r"\s+\d{4}"
    r"\s*[-–]\s*"
    r"(present|current|"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4})"
    r")",
    re.IGNORECASE
)

YEAR_PATTERN = re.compile(
    r"\b(19|20)\d{2}\b"
)

DEGREE_PATTERN = re.compile(
    r"\b("
    r"b\.?tech|btech|be|b\.?e|"
    r"bca|bsc|b\.?sc|"
    r"mca|mtech|m\.?tech|"
    r"msc|m\.?sc|"
    r"phd|doctorate|"
    r"diploma"
    r")\b",
    re.IGNORECASE
)

def _looks_like_experience(text: str) -> bool:
    """
    Detect whether a block looks like work experience.
    """

    if DATE_PATTERN.search(text):
        return True

    keywords = [
        "developer",
        "engineer",
        "intern",
        "consultant",
        "manager",
        "analyst",
        "worked",
        "developed",
        "implemented",
        "designed",
        "maintained",
    ]

    text = text.lower()

    return any(word in text for word in keywords)

def _looks_like_education(text: str) -> bool:

    if DEGREE_PATTERN.search(text):
        return True

    keywords = [
        "university",
        "college",
        "institute",
        "school",
        "cgpa",
        "gpa",
        "percentage",
    ]

    text = text.lower()

    return any(word in text for word in keywords)

def _looks_like_project(text: str) -> bool:

    keywords = [
        "project",
        "developed",
        "built",
        "implemented",
        "designed",
        "application",
        "system",
        "platform",
        "dashboard",
        "api",
        "website",
        "mobile app",
    ]

    text = text.lower()

    return any(word in text for word in keywords)

def _looks_like_certification(text: str) -> bool:

    keywords = [
        "certificate",
        "certification",
        "certified",
        "issued by",
        "credential",
        "course",
    ]
    text = text.lower()

    return any(word in text for word in keywords)

def _classify_general_section(sections: Dict[str, str]) -> Dict[str, str]:
    """
    If information exists inside the 'general' section,
    try to intelligently classify it.
    """

    if "general" not in sections:
        return sections

    general = sections["general"]

    paragraphs = [
        p.strip()
        for p in general.split("\n\n")
        if p.strip()
    ]

    remaining = []

    for block in paragraphs:

        if _looks_like_experience(block):

            sections.setdefault("experience", "")
            sections["experience"] += "\n" + block

        elif _looks_like_education(block):

            sections.setdefault("education", "")
            sections["education"] += "\n" + block

        elif _looks_like_project(block):

            sections.setdefault("projects", "")
            sections["projects"] += "\n" + block

        elif _looks_like_certification(block):

            sections.setdefault("certifications", "")
            sections["certifications"] += "\n" + block

        else:
            remaining.append(block)

    sections["general"] = "\n\n".join(remaining).strip()

    return sections