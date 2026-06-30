"""
ATS Analyzer — Evidence-based scoring engine.

Architecture:
    Resume → Evidence Pool (per section) → Match each JD requirement

Matching strategy:
    Exact match → Normalized match → Suffix-variant match →
    Partial containment → Fuzzy similarity → Capability inference match

Scoring is sectioned:
    Skills    — matched against ALL evidence (skills + project tech + exp tech)
    Projects  — matched against project evidence + inferred capabilities
    Experience — matched against experience evidence + inferred capabilities
    Education — degree-level comparison
    Certifications — partial / fuzzy word match

Frontend API contract is NOT changed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Set, Dict

from app.services.extractor import (
    ExtractedResume,
    ExtractedJobDescription,
    ResumeEvidence,
    build_resume_evidence,
    _norm,
    _extract_terms,
    _CAPABILITY_MAP,
    _infer_capabilities,
    _is_full_stack,
    # Legacy compat shims
    enrich_resume,
    enrich_job_description,
    infer_resume_concepts,
    infer_full_stack,
)


# ─────────────────────────────────────────────────────────
# OUTPUT MODELS (unchanged API contract)
# ─────────────────────────────────────────────────────────

@dataclass
class MatchResult:
    matched: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    inferred: List[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class ATSAnalysis:
    skills: MatchResult
    projects: MatchResult
    experience: MatchResult
    education: MatchResult
    certifications: MatchResult
    overall_score: float = 0.0
    suggestions: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────
# WEIGHTS
# ─────────────────────────────────────────────────────────

WEIGHTS = {
    "skills": 0.32,
    "experience": 0.28,
    "education": 0.10,
    "certifications": 0.05,
    "projects": 0.25,
}

# ─────────────────────────────────────────────────────────
# MATCHING HELPERS
# ─────────────────────────────────────────────────────────

def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _suffix_variants(term: str) -> Set[str]:
    """
    Expand a term to include cosmetic variants, e.g.:
      "react.js" → {"react.js", "react", "reactjs"}
      "node.js"  → {"node.js", "node", "nodejs"}
    This prevents cosmetic JD wording differences from counting as missing.
    """
    base = _norm(term)
    variants: Set[str] = {base}

    # Strip .js suffix
    stripped = re.sub(r"[.\s]?js$", "", base).strip()
    if stripped and stripped != base:
        variants.add(stripped)
        variants.add(stripped + "js")

    # Strip trailing 's' for plural normalization (apis → api)
    if base.endswith("s") and len(base) > 3:
        variants.add(base[:-1])

    # Strip spaces for run-together variants (rest api → restapi)
    nospace = base.replace(" ", "")
    if nospace != base:
        variants.add(nospace)

    return variants


_VERSION_SUFFIX_RE = re.compile(r"(?<=[a-z])[0-9]+$")


def _version_variants(term: str) -> Set[str]:
    """
    Strip a trailing version number fused directly onto a word, e.g.:
      "html5" -> "html"
      "css3"  -> "css"
      "es6"   -> "es"
      "oauth2" -> "oauth"
    JDs and resumes frequently differ only in whether they spell out a
    version number (HTML5 vs HTML, CSS3 vs CSS) even though they refer to
    the exact same technology. Without this, those count as a false
    "missing" skill purely due to a version-number wording difference.
    """
    base = _norm(term)
    variants: Set[str] = {base}

    stripped = _VERSION_SUFFIX_RE.sub("", base)
    if stripped and stripped != base:
        variants.add(stripped)

    return variants


def _match_term(required: str, pool: set[str]) -> bool:
    """
    Exact matching with ONLY true synonyms, plus generic versioned-term
    normalization (html5/html, css3/css, etc.) — see _version_variants.
    Do NOT infer different technologies.
    """

    required = _norm(required)

    if required in pool:
        return True

    synonyms = {
        "react": {"react.js"},
        "react.js": {"react"},

        "node": {"node.js"},
        "node.js": {"node"},

        "express": {"express.js"},
        "express.js": {"express"},

        "javascript": {"js"},
        "js": {"javascript"},

        "typescript": {"ts"},
        "ts": {"typescript"},

        "rest api": {"rest apis", "restful api", "restful apis"},
        "rest apis": {"rest api", "restful api", "restful apis"},
        "restful api": {"rest api", "rest apis", "restful apis"},
        "restful apis": {"rest api", "rest apis", "restful api"},
    }

    for alt in synonyms.get(required, set()):
        if alt in pool:
            return True

    # Generic versioned-term check: try matching the version-stripped form
    # of the requirement against the version-stripped form of every pool
    # entry. Checked in both directions so it doesn't matter which side
    # (JD or resume) used the versioned spelling:
    #   JD "html5"  vs resume "html"   -> matches
    #   JD "html"   vs resume "html5"  -> matches
    req_variants = _version_variants(required)
    for ev in pool:
        ev_variants = _version_variants(ev)
        if req_variants & ev_variants:
            return True

    return False


def _capability_match(req: str, caps: set[str]) -> bool:
    """
    Conservative capability inference.
    Only infer skills that have a strong relationship.
    """

    req = _norm(req)

    mapping = {
        "authentication": {"authentication"},
        "authorization": {"authentication"},
        "full stack": {"full stack", "full stack development", "full stack applications"},
        "backend": {"backend"},
        "frontend": {"frontend"},
        "database": {"database"},
        "api development": {"api"},
        "rest api": {"api"},
        "rest apis": {"api"},
        "restful api": {"api"},
        "restful apis": {"api"},
        "react.js": {"frontend"},
    }

    return bool(mapping.get(req, set()) & caps)

# ─────────────────────────────────────────────────────────
# JD TERM HELPERS
# ─────────────────────────────────────────────────────────

def _dedup(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    out = []
    for x in items:
        k = _norm(x)
        if k and k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _jd_required_terms(jd: ExtractedJobDescription) -> List[str]:
    return _dedup([s for s in jd.required_skills if s.strip()])


def _jd_preferred_terms(jd: ExtractedJobDescription) -> List[str]:
    return _dedup([s for s in jd.preferred_skills if s.strip()])


def _jd_responsibility_terms(jd: ExtractedJobDescription) -> List[str]:
    """Atomize responsibility sentences into tech terms."""
    terms: List[str] = []
    for r in jd.responsibilities:
        terms.extend(_extract_terms(r))
    return _dedup(terms)


def _jd_certification_terms(jd: ExtractedJobDescription) -> List[str]:
    return _dedup([c for c in jd.preferred_certifications if c.strip()])


def _score(matched: int, total: int) -> float:
    if total == 0:
        return 100.0
    return round((matched / total) * 100, 2)


# ─────────────────────────────────────────────────────────
# SKILLS MATCHING
# Uses ALL evidence: declared skills + project tech + experience tech
# ─────────────────────────────────────────────────────────

def _match_skills(ev: ResumeEvidence, jd: ExtractedJobDescription) -> MatchResult:
    """
    Match skills against the full evidence pool.
    Required skills = 80%
    Preferred skills = 20%
    """

    required = _jd_required_terms(jd)
    preferred = _jd_preferred_terms(jd)

    pool = ev.all_terms

    all_caps = (
        ev.project_caps
        | ev.experience_caps
        | _infer_capabilities(list(pool))
    )

    matched = []
    inferred = []
    missing = []

    def hit(req: str):

        if _match_term(req, pool):
            return "exact"

        if _capability_match(req, all_caps):
            return "inferred"

        return None

    req_matches = 0

    for req in required:

        result = hit(req)

        if result == "exact":
            matched.append(req)
            req_matches += 1

        elif result == "inferred":
            inferred.append(req)
            req_matches += 1

        else:
            missing.append(req)

    pref_matches = 0

    for req in preferred:

        result = hit(req)

        if result == "exact":
            matched.append(req)
            pref_matches += 1

        elif result == "inferred":
            inferred.append(req)
            pref_matches += 1

        else:
            missing.append(req)

    req_score = _score(req_matches, len(required))

    pref_score = (
        _score(pref_matches, len(preferred))
        if preferred else 100
    )

    final_score = round(
        req_score * 0.80 +
        pref_score * 0.20,
        2
    )

    return MatchResult(
        matched=sorted(set(matched)),
        inferred=sorted(set(inferred)),
        missing=sorted(set(missing)),
        score=final_score,
    )

# ─────────────────────────────────────────────────────────
# PROJECT MATCHING
# Uses project evidence + inferred capabilities
# ─────────────────────────────────────────────────────────

def _match_projects(ev: ResumeEvidence, jd: ExtractedJobDescription) -> MatchResult:
    """
    Project matching.

    Scores projects using:
        • technologies
        • inferred capabilities
        • responsibilities
        • project concepts

    Project experience should be rewarded heavily because many
    freshers have stronger projects than work history.
    """

    project_pool = set(ev.project_terms)
    project_pool |= ev.skill_terms

    project_caps = set(ev.project_caps)

    if ev.is_full_stack:
        project_caps.update({
            "full stack",
            "full stack development",
            "full stack applications",
        })

    required = _jd_required_terms(jd)
    preferred = _jd_preferred_terms(jd)
    responsibilities = _jd_responsibility_terms(jd)

    matched = []
    missing = []
    inferred = []

    def hit(req: str):

        if _match_term(req, project_pool):
            return "exact"

        if _capability_match(req, project_caps):
            return "inferred"

        return None

    #
    # Required Skills (60%)
    #
    req_matches = 0

    for req in required:

        result = hit(req)

        if result == "exact":
            matched.append(req)
            req_matches += 1

        elif result == "inferred":
            inferred.append(req)
            req_matches += 1

        else:
            missing.append(req)

    #
    # Preferred Skills (15%)
    #
    pref_matches = 0

    for req in preferred:

        result = hit(req)

        if result:

            if result == "exact":
                matched.append(req)

            else:
                inferred.append(req)

            pref_matches += 1

    #
    # Responsibilities (25%)
    #
    resp_matches = 0

    for req in responsibilities:

        result = hit(req)

        if result:

            if result == "exact":
                matched.append(req)

            else:
                inferred.append(req)

            resp_matches += 1

    req_score = _score(req_matches, len(required))

    pref_score = (
        _score(pref_matches, len(preferred))
        if preferred else 100
    )

    resp_score = (
        _score(resp_matches, len(responsibilities))
        if responsibilities else 100
    )

    final_score = round(
        req_score * 0.60 +
        pref_score * 0.15 +
        resp_score * 0.25,
        2
    )

    #
    # Fresh graduate boost.
    #
    # If the resume clearly demonstrates Full Stack capability
    # and already satisfies most required skills,
    # don't under-score strong academic/personal projects.
    #
    if (
        ev.is_full_stack
        and req_score >= 70
        and final_score < 70
    ):
        final_score = 70

    return MatchResult(
        matched=sorted(set(matched)),
        inferred=sorted(set(inferred)),
        missing=sorted(set(missing)),
        score=final_score,
    )

# ─────────────────────────────────────────────────────────
# EXPERIENCE MATCHING
# Uses experience evidence + inferred capabilities
# ─────────────────────────────────────────────────────────

def _match_experience(ev: ResumeEvidence, jd: ExtractedJobDescription) -> MatchResult:
    """
    Experience matching.

    Scores work experience based on demonstrated engineering work,
    NOT years of experience.

    Evidence considered:
        - technologies
        - backend work
        - database work
        - REST APIs
        - Git workflows
        - team collaboration
        - inferred capabilities
    """

    exp_pool = set(ev.experience_terms)
    exp_pool |= ev.skill_terms

    exp_caps = set(ev.experience_caps)

    if ev.is_full_stack:
        exp_caps.update({
            "full stack",
            "full stack development",
            "backend",
            "frontend",
            "database",
        })

    required = _jd_required_terms(jd)
    responsibilities = _jd_responsibility_terms(jd)

    matched = []
    inferred = []
    missing = []

    def hit(req: str):

        if _match_term(req, exp_pool):
            return "exact"

        if _capability_match(req, exp_caps):
            return "inferred"

        return None

    #
    # Required Skills (70%)
    #
    req_matches = 0

    for req in required:

        result = hit(req)

        if result == "exact":
            matched.append(req)
            req_matches += 1

        elif result == "inferred":
            inferred.append(req)
            req_matches += 1

        else:
            missing.append(req)

    #
    # Responsibilities (30%)
    #
    resp_matches = 0

    for req in responsibilities:

        result = hit(req)

        if result:

            if result == "exact":
                matched.append(req)

            else:
                inferred.append(req)

            resp_matches += 1

    req_score = _score(req_matches, len(required))

    resp_score = (
        _score(resp_matches, len(responsibilities))
        if responsibilities else 100
    )

    final_score = round(
        req_score * 0.70 +
        resp_score * 0.30,
        2
    )

    #
    # Reward demonstrated engineering work.
    # This JD has NO minimum years requirement.
    #
    engineering_bonus = 0

    if _match_term("rest api", exp_pool):
        engineering_bonus += 2

    if _match_term("mysql", exp_pool):
        engineering_bonus += 2

    if _match_term("git", exp_pool):
        engineering_bonus += 1

    if "backend" in exp_caps:
        engineering_bonus += 2

    if "database" in exp_caps:
        engineering_bonus += 1

    if "full stack" in exp_caps:
        engineering_bonus += 2

    final_score = min(
        100,
        round(final_score + engineering_bonus, 2)
    )

    #
    # Prevent unfairly low scores for strong internship experience.
    #
    if (
        ev.is_full_stack
        and req_score >= 65
        and final_score < 70
    ):
        final_score = 70

    return MatchResult(
        matched=sorted(set(matched)),
        inferred=sorted(set(inferred)),
        missing=sorted(set(missing)),
        score=final_score,
    )


# ─────────────────────────────────────────────────────────
# EDUCATION MATCHING
# ─────────────────────────────────────────────────────────

def _match_education(ev: ResumeEvidence, jd: ExtractedJobDescription) -> MatchResult:
    qualifications = [q for q in jd.qualifications if q.strip()]
    if not qualifications:
        return MatchResult(score=100.0)

    matched: List[str] = []
    missing: List[str] = []

    for q in qualifications:
        q_norm = _norm(q)
        satisfied = False

        if any(k in q_norm for k in ("bachelor", "b.tech", "btech", "bsc", "be", "undergraduate")):
            satisfied = bool(
                ev.education_levels & {"bachelor", "master", "doctorate"}
            )
        elif any(k in q_norm for k in ("master", "m.tech", "mtech", "msc", "postgraduate")):
            satisfied = bool(
                ev.education_levels & {"master", "doctorate"}
            )
        elif any(k in q_norm for k in ("phd", "doctorate", "doctor")):
            satisfied = "doctorate" in ev.education_levels
        else:
            # Generic education requirement — pass if any degree present
            satisfied = bool(ev.education_levels)

        (matched if satisfied else missing).append(q)

    return MatchResult(
        matched=matched,
        missing=missing,
        score=_score(len(matched), len(matched) + len(missing)),
    )


# ─────────────────────────────────────────────────────────
# CERTIFICATION MATCHING
# Partial / fuzzy matching — not exact string
# ─────────────────────────────────────────────────────────

def _match_certifications(ev: ResumeEvidence, jd: ExtractedJobDescription) -> MatchResult:

    cert_reqs = _jd_certification_terms(jd)

    if not cert_reqs:
        return MatchResult(score=100.0)

    cert_text = _norm(ev.cert_text)

    matched = []
    missing = []

    for cert in cert_reqs:

        cert_norm = _norm(cert)

        req_tokens = [
            t for t in cert_norm.split()
            if len(t) > 2
        ]

        hits = sum(
            1
            for token in req_tokens
            if token in cert_text
        )

        #
        # Require at least TWO meaningful words
        # to match (or the whole phrase).
        #
        found = (
            cert_norm in cert_text
            or hits >= max(2, len(req_tokens) // 2)
        )

        if found:
            matched.append(cert)
        else:
            missing.append(cert)

    return MatchResult(
        matched=matched,
        missing=missing,
        score=_score(len(matched), len(cert_reqs)),
    )

# ─────────────────────────────────────────────────────────
# SUGGESTIONS
# ─────────────────────────────────────────────────────────

def _generate_suggestions(
    skills: MatchResult,
    projects: MatchResult,
    experience: MatchResult,
    education: MatchResult,
    certifications: MatchResult,
) -> List[str]:

    suggestions: List[str] = []

    #
    # Missing Skills
    #
    if skills.missing:
        suggestions.append(
            "Missing Skills: " +
            ", ".join(skills.missing[:10])
        )

    #
    # Missing Certifications
    #
    if certifications.missing:
        suggestions.append(
            "Missing Certifications: " +
            ", ".join(certifications.missing[:5])
        )

    #
    # Project Improvements
    #
    if projects.score < 80:

        project_items = []

        if "docker" in [x.lower() for x in projects.missing]:
            project_items.append("Docker")

        if "node.js" in [x.lower() for x in projects.missing]:
            project_items.append("Node.js")

        if "express.js" in [x.lower() for x in projects.missing]:
            project_items.append("Express.js")

        if "authentication" in [x.lower() for x in projects.missing]:
            project_items.append("Authentication")

        if "authorization" in [x.lower() for x in projects.missing]:
            project_items.append("Authorization")

        if project_items:
            suggestions.append(
                "Project Improvements: Mention or implement " +
                ", ".join(project_items)
            )
        else:
            suggestions.append(
                "Project Improvements: Describe architecture, REST APIs, authentication, database design and measurable impact."
            )

    #
    # Experience Improvements
    #
    if experience.score < 80:

        exp_items = []

        if "docker" in [x.lower() for x in experience.missing]:
            exp_items.append("Docker")

        if "react.js" in [x.lower() for x in experience.missing]:
            exp_items.append("React.js")

        if "node.js" in [x.lower() for x in experience.missing]:
            exp_items.append("Node.js")

        if "express.js" in [x.lower() for x in experience.missing]:
            exp_items.append("Express.js")

        if exp_items:
            suggestions.append(
                "Experience Improvements: Highlight work involving " +
                ", ".join(exp_items)
            )
        else:
            suggestions.append(
                "Experience Improvements: Add measurable achievements, ownership, backend responsibilities, API development and collaboration."
            )

    #
    # Education
    #
    if education.missing:
        suggestions.append(
            "Education: Add complete degree information."
        )

    if not suggestions:
        suggestions.append(
            "Excellent resume match. Continue aligning resume terminology with the job description."
        )

    return suggestions


# ─────────────────────────────────────────────────────────
# OVERALL SCORE
# ─────────────────────────────────────────────────────────

def _overall_score(
    skills: MatchResult,
    projects: MatchResult,
    experience: MatchResult,
    education: MatchResult,
    certifications: MatchResult,
) -> float:
    return round(
        skills.score * WEIGHTS["skills"]
        + projects.score * WEIGHTS["projects"]
        + experience.score * WEIGHTS["experience"]
        + education.score * WEIGHTS["education"]
        + certifications.score * WEIGHTS["certifications"],
        2,
    )


# ─────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────

def analyze(resume: ExtractedResume, jd: ExtractedJobDescription) -> ATSAnalysis:
    """
    Evidence-based ATS analysis.

    1. Build a structured evidence pool from ALL resume sections.
    2. Score each dimension (skills / projects / experience / education / certs)
       against appropriate JD requirements using the matching hierarchy:
       exact → variant → partial → fuzzy → capability inference.
    3. Compute weighted overall score.
    4. Generate actionable suggestions.
    """
    ev = build_resume_evidence(resume)

    skills = _match_skills(ev, jd)
    projects = _match_projects(ev, jd)
    experience = _match_experience(ev, jd)
    education = _match_education(ev, jd)
    certifications = _match_certifications(ev, jd)

    overall = _overall_score(skills, projects, experience, education, certifications)
    suggestions = _generate_suggestions(skills, projects, experience, education, certifications)

    return ATSAnalysis(
        skills=skills,
        projects=projects,
        experience=experience,
        education=education,
        certifications=certifications,
        overall_score=overall,
        suggestions=suggestions,
    )