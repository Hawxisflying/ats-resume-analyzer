"""
ATS Resume Extractor — Evidence-based extraction engine.

Design principles:
  - No hardcoded TECH_SKILLS list of "the" technologies to look for
  - BUT: tech *term recognition* uses a closed vocabulary check, NOT
    capitalization heuristics. JD bullets are routinely written in Title
    Case for emphasis ("Website Performance Optimization", "Lead
    Generation Strategies") — treating "any capitalized word" as a likely
    tech term causes plain English nouns (growth, engine, content, theme,
    paid, keyword, lead, media, search, console, platforms, exposure,
    google, facebook, instagram...) to leak into the skills list.
  - A term is only emitted if it matches a real, recognizable technology,
    tool, platform, protocol, or named concept — via multi-word phrase
    patterns or a single-token vocabulary regex. Nothing is inferred
    purely from "this word started with a capital letter."
  - Infer capabilities via a small, deliberate capability map.
  - Build structured evidence per section (skills / projects / experience).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Dict, Set

from app.services.parser import ParsedResume, ParsedJobDescription, _normalize_section_content


# ─────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────

@dataclass
class Project:
    title: str = ""
    description: str = ""
    technologies: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)


@dataclass
class Experience:
    title: str = ""
    company: str = ""
    duration: str = ""
    description: str = ""
    technologies: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)


@dataclass
class Education:
    degree: str = ""
    institution: str = ""
    year: str = ""


@dataclass
class Certification:
    name: str = ""
    issuer: str = ""


@dataclass
class ExtractedResume:
    skills: List[str] = field(default_factory=list)
    projects: List[Project] = field(default_factory=list)
    experience: List[Experience] = field(default_factory=list)
    education: List[Education] = field(default_factory=list)
    certifications: List[Certification] = field(default_factory=list)


@dataclass
class ExtractedJobDescription:
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    qualifications: List[str] = field(default_factory=list)
    preferred_certifications: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────
# TEXT NORMALIZATION
# ─────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _unique(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    out = []
    for x in items:
        k = _norm(x)
        if k and k not in seen:
            seen.add(k)
            out.append(x)
    return out


# ─────────────────────────────────────────────────────────
# MULTI-WORD TECH / TOOL PHRASES
# ─────────────────────────────────────────────────────────

_MULTI_WORD_PATTERNS: List[str] = [
    r"react\s*native", r"react\.?js", r"node\.?js", r"next\.?js",
    r"vue\.?js", r"express\.?js", r"angular\.?js", r"nuxt\.?js",
    r"nest\.?js", r"svelte\.?js",
    r"spring\s+boot", r"spring\s+mvc",
    r"machine\s+learning", r"deep\s+learning",
    r"natural\s+language\s+processing", r"computer\s+vision",
    r"data\s+science", r"artificial\s+intelligence",
    r"large\s+language\s+model", r"generative\s+ai",
    r"rest(?:ful)?\s*api[s]?", r"graphql\s+api", r"grpc",
    r"role.?based\s+access\s+control", r"\brbac\b", r"oauth\s*2(?:\.0)?",
    r"ci[/\-]cd", r"continuous\s+integration", r"continuous\s+deployment",
    r"github\s+actions", r"gitlab\s+ci",
    r"object.?oriented\s+(?:programming|design)", r"\boop\b",
    r"test.?driven\s+development", r"\btdd\b",
    r"micro\s*services", r"event.?driven",
    r"domain.?driven\s+design", r"\bddd\b",
    r"version\s+control", r"design\s+patterns?",
    r"software\s+development\s+life\s*cycle", r"\bsdlc\b",
    r"scikit.?learn", r"tensor\s*flow",
    r"sql\s+server", r"ms\s+sql",
    r"amazon\s+(?:rds|s3|ec2|lambda|dynamodb)",
    r"google\s+cloud", r"azure\s+(?:functions|devops|blob)",
    r"word\s*press", r"woo\s*commerce", r"wp\s+engine",
    r"shopify(?:\s+plus)?", r"magento", r"drupal", r"joomla",
    r"prestashop",
    r"elementor", r"divi\s+builder", r"gutenberg",
    r"html\s*5", r"css\s*3", r"jquery",
    r"responsive\s+web\s+design",
    r"pay\s*pal", r"stripe", r"razorpay", r"authorize\.?net",
    r"google\s+pay", r"apple\s+pay",
    r"search\s+engine\s+optimi[sz]ation", r"\bseo\b",
    r"technical\s+seo", r"on.?page\s+seo", r"off.?page\s+seo",
    r"keyword\s+research",
    r"google\s+analytics", r"google\s+search\s+console",
    r"google\s+tag\s+manager", r"google\s+ads",
    r"meta\s+ads", r"facebook\s+ads",
    r"social\s+media\s+marketing",
    r"adobe\s+photoshop", r"adobe\s+illustrator",
    r"adobe\s+xd", r"figma", r"canva", r"sketch",
    r"ssl\s+certificate[s]?", r"dns\s+management",
    r"cloud\s+hosting",
]

_MULTI_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(_MULTI_WORD_PATTERNS) + r")(?!\w)",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────
# SINGLE-TOKEN CLOSED VOCABULARY
# ─────────────────────────────────────────────────────────

_KNOWN_TECH_RE = re.compile(
    r"""(?x)
    ^(
        python|java|golang|ruby|kotlin|swift|rust|scala|perl|
        php|typescript|javascript|coffeescript|elixir|clojure|
        laravel|symfony|codeigniter|rails|django|flask|fastapi|
        sinatra|express|nestjs|nextjs|nuxtjs|sveltekit|
        react|angular|vue|svelte|jquery|bootstrap|tailwind|
        sass|less|webpack|vite|babel|
        flutter|xamarin|ionic|cordova|
        mysql|postgresql|postgres|sqlite|mongodb|redis|
        firebase|cassandra|dynamodb|elasticsearch|neo4j|
        couchdb|mariadb|oracle|mssql|
        docker|kubernetes|k8s|terraform|ansible|vagrant|
        nginx|apache|jenkins|gradle|maven|
        aws|azure|gcp|heroku|digitalocean|vercel|netlify|
        jwt|oauth|saml|ldap|rbac|cors|csrf|ssl|tls|ssh|
        pandas|numpy|scipy|matplotlib|seaborn|
        tensorflow|pytorch|keras|xgboost|
        git|github|gitlab|bitbucket|jira|confluence|slack|
        postman|swagger|figma|linux|bash|powershell|
        html|xml|yaml|json|csv|graphql|soap|rest|grpc|
        api|apis|orm|mvc|mvp|mvvm|crud|oop|tdd|bdd|seo|ajax|fbml|
        wordpress|woocommerce|shopify|magento|drupal|joomla|
        elementor|wix|squarespace|
        paypal|stripe|razorpay|
        photoshop|illustrator|canva|figma|sketch|
        mailchimp|hubspot|salesforce|
    )$
    """,
    re.IGNORECASE,
)

# Tokens matching these suffixes are almost always tech.
#
# NOTE: bare 2-3 letter endings like "js", "ts", "py", "orm" were
# REMOVED from this list. They caused severe false positives because
# they are also common English word endings:
#   "products"    ends in "ts"  -> false match
#   "scientists"  ends in "ts"  -> false match
#   "requirements"ends in "ts"  -> false match
#   "perform"/"inform"/"uniform"/"platform" end in "orm" -> false match
#   "happy"/"copy" end in "py"  -> false match
# Legitimate cases like "main.js" / "app.ts" / "script.py" are still
# correctly caught by _TECH_CHAR_RE below, since they contain a literal
# dot followed by a letter (".py"), so nothing real is lost by removing
# these from the suffix list.
_TECH_SUFFIX_RE = re.compile(
    r"(sql|css|json|xml|api|sdk|cli|css3|html5|es6|es2015)$",
    re.IGNORECASE,
)

# Common plain-English words that could otherwise slip through suffix or
# vocabulary checks (defense in depth backstop).
_FORCE_REJECT: Set[str] = {
    "clients", "client", "projects", "project", "research", "campaign",
    "campaigns", "opportunities", "opportunity", "growth", "engine",
    "engines", "content", "theme", "themes", "paid", "keyword", "keywords",
    "lead", "leads", "media", "tag", "tags", "search", "console",
    "platform", "platforms", "exposure", "facebook", "google", "instagram",
    "linkedin", "youtube", "international", "twitter",
    "aspects", "aspect", "ctc", "requirements", "requirement",
    "strategists", "strategist", "audits", "audit", "trainings", "training",
    "deliverables", "deliverable", "layout", "layouts", "reviews", "review",
    "codes", "code", "members", "member", "plan", "plans", "change", "changes",
    "suggestions", "suggestion", "discussion", "discussions", "sessions", "session",
    # Additional plain-English nouns observed leaking via the (now-fixed)
    # over-broad "ts"/"orm"/"py" suffix matches — kept here as a defensive
    # backstop in case other patterns ever re-introduce similar leaks.
    "products", "product", "scientists", "scientist", "perform", "inform",
    "uniform", "perform's", "informs", "performs", "platformed",
    "colleagues", "colleague", "perks", "perk", "rocket", "ship",
    "industry", "compensation", "impact", "culture", "environment",
}

# Tokens with these characters are almost always tech (c++, c#, .net, etc.)
_TECH_CHAR_RE = re.compile(r"[+#]|\.[a-z]|\d")

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9.+#\-]{1,}")


def _extract_terms(text: str) -> List[str]:
    text_lower = _norm(text)
    found: List[str] = []
    covered_spans: List[tuple] = []

    for m in _MULTI_RE.finditer(text_lower):
        term = re.sub(r"\s+", " ", m.group().strip())
        found.append(term)
        covered_spans.append((m.start(), m.end()))

    def _in_covered(start: int, end: int) -> bool:
        return any(s <= start and end <= e for s, e in covered_spans)

    for m in _TOKEN_RE.finditer(text):
        if _in_covered(m.start(), m.end()):
            continue

        tok_orig = m.group()
        tok = tok_orig.lower()

        if len(tok) <= 2:
            continue

        if tok in _FORCE_REJECT:
            continue

        if "₹" in tok_orig:
            continue

        if re.fullmatch(r"\d+", tok):
            continue

        if _TECH_CHAR_RE.search(tok) and not re.fullmatch(r"\d+(\.\d+)*", tok):
            found.append(tok)
            continue

        if _TECH_SUFFIX_RE.search(tok):
            found.append(tok)
            continue

        if _KNOWN_TECH_RE.match(tok):
            found.append(tok)
            continue

        if tok_orig.isupper() and 2 <= len(tok_orig) <= 5:
            found.append(tok)
            continue

    return _unique(found)


# ─────────────────────────────────────────────────────────
# CAPABILITY INFERENCE MAP
# ─────────────────────────────────────────────────────────

_CAPABILITY_MAP: Dict[str, str] = {
    "react": "frontend", "react native": "frontend", "react.js": "frontend",
    "reactjs": "frontend", "angular": "frontend", "angular.js": "frontend",
    "angularjs": "frontend", "vue": "frontend", "vue.js": "frontend",
    "vuejs": "frontend", "svelte": "frontend", "next.js": "frontend",
    "nextjs": "frontend", "nuxt.js": "frontend", "nuxtjs": "frontend",
    "html": "frontend", "html5": "frontend", "css": "frontend",
    "css3": "frontend", "javascript": "frontend", "typescript": "frontend",
    "bootstrap": "frontend", "tailwind": "frontend", "sass": "frontend",
    "jquery": "frontend", "flutter": "frontend", "ionic": "frontend",
    "laravel": "backend", "django": "backend", "flask": "backend",
    "fastapi": "backend", "node": "backend", "node.js": "backend",
    "nodejs": "backend", "express": "backend", "express.js": "backend",
    "expressjs": "backend", "spring": "backend", "spring boot": "backend",
    "php": "backend", "ruby": "backend", "rails": "backend",
    "golang": "backend", "kotlin": "backend", "nestjs": "backend",
    "symfony": "backend", "codeigniter": "backend", "sinatra": "backend",
    "python": "backend", "java": "backend",
    "mysql": "database", "postgresql": "database", "postgres": "database",
    "sqlite": "database", "mongodb": "database", "redis": "database",
    "firebase": "database", "oracle": "database", "cassandra": "database",
    "sql": "database", "mssql": "database", "mariadb": "database",
    "dynamodb": "database", "elasticsearch": "database",
    "jwt": "authentication", "oauth": "authentication",
    "oauth2": "authentication", "saml": "authentication",
    "ldap": "authentication", "rbac": "authentication",
    "role based access control": "authentication", "authentication": "authentication",
    "authorization": "authentication",
    "machine learning": "ml", "deep learning": "ml",
    "scikit-learn": "ml", "scikit learn": "ml", "tensorflow": "ml",
    "pytorch": "ml", "keras": "ml", "xgboost": "ml",
    "pandas": "data", "numpy": "data", "scipy": "data",
    "matplotlib": "data", "data science": "ml",
    "artificial intelligence": "ml",
    "natural language processing": "ml", "computer vision": "ml",
    "docker": "devops", "kubernetes": "devops", "k8s": "devops",
    "terraform": "devops", "ci/cd": "devops", "continuous integration": "devops",
    "continuous deployment": "devops", "jenkins": "devops",
    "github actions": "devops", "ansible": "devops",
    "aws": "cloud", "azure": "cloud", "gcp": "cloud",
    "heroku": "cloud", "digitalocean": "cloud", "vercel": "cloud",
    "cloud hosting": "cloud",
    "rest api": "api", "rest apis": "api", "restful api": "api",
    "restful apis": "api", "graphql": "api", "grpc": "api",
    "soap": "api", "api": "api", "apis": "api",
    "wordpress": "cms", "woocommerce": "cms", "shopify": "cms",
    "magento": "cms", "drupal": "cms", "joomla": "cms",
    "elementor": "cms",
    "seo": "marketing", "search engine optimization": "marketing",
    "technical seo": "marketing", "on-page seo": "marketing",
    "keyword research": "marketing", "google analytics": "marketing",
    "google search console": "marketing", "google tag manager": "marketing",
    "google ads": "marketing", "social media marketing": "marketing",
    "paypal": "payments", "stripe": "payments", "razorpay": "payments",
    "authorize.net": "payments",
    "photoshop": "design", "illustrator": "design", "figma": "design",
    "canva": "design", "sketch": "design",
}


def _infer_capabilities(terms: List[str]) -> Set[str]:
    caps: Set[str] = set()
    for t in terms:
        cap = _CAPABILITY_MAP.get(_norm(t))
        if cap:
            caps.add(cap)
    return caps


def _is_full_stack(caps: Set[str]) -> bool:
    return {"frontend", "backend", "database"}.issubset(caps)


# ─────────────────────────────────────────────────────────
# RESUME EXTRACTION — per section
# ─────────────────────────────────────────────────────────

def _extract_skills(parsed: ParsedResume) -> List[str]:
    raw = _normalize_section_content(parsed.sections.get("skills", ""))
    all_items: List[str] = []
    for s in raw:
        s = s.strip()
        if not s:
            continue
        all_items.append(s)
        for t in _extract_terms(s):
            all_items.append(t)
    return _unique(all_items)


def _split_into_blocks(text: str) -> List[str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return []
    blocks: List[str] = []
    current: List[str] = []
    for line in lines:
        is_title = (
            len(line) < 60
            and not line.startswith(("-", "•", "●", "*", "–"))
            and not re.match(r"^\d+[\.\)]", line)
        )
        if is_title and current:
            blocks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _extract_projects(parsed: ParsedResume) -> List[Project]:
    section = parsed.sections.get("projects", "").strip()
    if not section:
        return []
    projects: List[Project] = []
    blocks = [b.strip() for b in re.split(r"\n{2,}", section) if b.strip()]
    if len(blocks) == 1:
        blocks = _split_into_blocks(section)
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        title = lines[0]
        description = " ".join(lines[1:])
        full_text = f"{title} {description}"
        terms = _extract_terms(full_text)
        caps = list(_infer_capabilities(terms))
        if _is_full_stack(set(caps)):
            caps.append("full stack")
            caps.append("full stack development")
        projects.append(Project(title=title, description=description, technologies=terms, concepts=caps))
    return projects


def _extract_experience(parsed: ParsedResume) -> List[Experience]:
    section = parsed.sections.get("experience", "").strip()
    if not section:
        return []
    experiences: List[Experience] = []
    blocks = [b.strip() for b in re.split(r"\n{2,}", section) if b.strip()]
    if len(blocks) == 1:
        blocks = _split_into_blocks(section)
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        title = lines[0]
        description = " ".join(lines[1:])
        full_text = f"{title} {description}"
        terms = _extract_terms(full_text)
        caps = list(_infer_capabilities(terms))
        if _is_full_stack(set(caps)):
            caps.append("full stack")
            caps.append("full stack development")
        experiences.append(Experience(title=title, description=description, technologies=terms, concepts=caps))
    return experiences


def _extract_education(parsed: ParsedResume) -> List[Education]:
    section = parsed.sections.get("education", "").strip()
    if not section:
        return []
    education: List[Education] = []
    blocks = [b.strip() for b in re.split(r"\n{2,}", section) if b.strip()]
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        education.append(Education(degree=lines[0], institution=lines[1] if len(lines) >= 2 else ""))
    return education


def _extract_certifications(parsed: ParsedResume) -> List[Certification]:
    section = parsed.sections.get("certifications", "").strip()
    if not section:
        return []
    certs: List[Certification] = []
    for line in _normalize_section_content(section):
        if line.strip():
            certs.append(Certification(name=line.strip()))
    return certs


def extract_resume(parsed: ParsedResume) -> ExtractedResume:
    return ExtractedResume(
        skills=_extract_skills(parsed),
        projects=_extract_projects(parsed),
        experience=_extract_experience(parsed),
        education=_extract_education(parsed),
        certifications=_extract_certifications(parsed),
    )


# ─────────────────────────────────────────────────────────
# JD EXTRACTION
# ─────────────────────────────────────────────────────────

_JD_NOISE_PATTERNS = [
    "salary", "pay", "₹", "per month", "location", "work location",
    "job type", "full-time", "permanent", "benefits", "perks",
    "growth opportunities", "hands-on learning", "english", "preferred",
    "in person", "remote", "hybrid", "flexible schedule", "paid sick time",
    "incentives", "compensation", "career growth",
]


def extract_job_description(parsed: ParsedJobDescription) -> ExtractedJobDescription:

    def extract(section: str):
        terms = []
        for line in _normalize_section_content(section):
            line_lower = line.lower()
            if any(x in line_lower for x in _JD_NOISE_PATTERNS):
                continue
            terms.extend(_extract_terms(line))
        return _unique(terms)

    # The JD "Projects" section (e.g. "Candidates should have experience
    # with: Authentication, RBAC, CRUD applications...") describes expected
    # project-level capabilities, not generic responsibilities — but the
    # ParsedJobDescription model has no dedicated projects field, and this
    # content was previously parsed correctly into sections["projects"]
    # and then never read by anything, silently dropping it. Folding it
    # into responsibilities ensures it still contributes to matching
    # (responsibilities terms are used by both project and experience
    # scoring) instead of being discarded after parsing.
    responsibilities_terms = extract(parsed.sections.get("responsibilities", ""))
    responsibilities_terms += extract(parsed.sections.get("projects", ""))
    responsibilities_terms = _unique(responsibilities_terms)

    return ExtractedJobDescription(
        required_skills=extract(parsed.sections.get("required_skills", "")),
        preferred_skills=extract(parsed.sections.get("preferred_skills", "")),
        responsibilities=responsibilities_terms,
        qualifications=extract(parsed.sections.get("qualifications", "")),
        preferred_certifications=_normalize_section_content(
            parsed.sections.get("preferred_certifications", "")
        ),
    )


# ─────────────────────────────────────────────────────────
# RESUME EVIDENCE BUILDER
# ─────────────────────────────────────────────────────────

@dataclass
class ResumeEvidence:
    skill_terms: Set[str] = field(default_factory=set)
    project_terms: Set[str] = field(default_factory=set)
    project_caps: Set[str] = field(default_factory=set)
    experience_terms: Set[str] = field(default_factory=set)
    experience_caps: Set[str] = field(default_factory=set)
    all_terms: Set[str] = field(default_factory=set)
    education_levels: Set[str] = field(default_factory=set)
    cert_text: str = ""
    is_full_stack: bool = False


def build_resume_evidence(resume: ExtractedResume) -> ResumeEvidence:
    ev = ResumeEvidence()

    for s in resume.skills:
        n = _norm(s)
        ev.skill_terms.add(n)
        ev.all_terms.add(n)
        for t in _extract_terms(s):
            tn = _norm(t)
            ev.skill_terms.add(tn)
            ev.all_terms.add(tn)

    all_project_caps: Set[str] = set()
    for project in resume.projects:
        terms = project.technologies or _extract_terms(f"{project.title} {project.description}")
        for t in terms:
            tn = _norm(t)
            ev.project_terms.add(tn)
            ev.all_terms.add(tn)
        for c in project.concepts:
            cn = _norm(c)
            ev.project_caps.add(cn)
            all_project_caps.add(cn)

    all_exp_caps: Set[str] = set()
    for exp in resume.experience:
        terms = exp.technologies or _extract_terms(f"{exp.title} {exp.description}")
        for t in terms:
            tn = _norm(t)
            ev.experience_terms.add(tn)
            ev.all_terms.add(tn)
        for c in exp.concepts:
            cn = _norm(c)
            ev.experience_caps.add(cn)
            all_exp_caps.add(cn)

    all_caps = all_project_caps | all_exp_caps | _infer_capabilities(list(ev.all_terms))

    if _is_full_stack(all_caps):
        ev.is_full_stack = True
        for t in ("full stack", "full stack development", "full stack applications",
                  "full-stack", "full-stack development"):
            ev.all_terms.add(t)
            ev.project_caps.add(t)
            ev.experience_caps.add(t)

    _auth_triggers = {"jwt", "oauth", "oauth2", "saml", "rbac", "role based access control", "login", "token", "session"}
    if ev.all_terms & _auth_triggers:
        ev.all_terms.update({"authentication", "authorization", "auth"})
        ev.project_caps.update({"authentication", "authorization"})
        ev.experience_caps.update({"authentication", "authorization"})

    _api_triggers = {"rest api", "rest apis", "restful api", "restful apis", "api", "apis"}
    if ev.all_terms & _api_triggers:
        ev.all_terms.update({"rest api", "rest apis", "restful api", "restful apis", "api integration", "api development", "api"})

    _ml_triggers = {"machine learning", "deep learning", "scikit learn", "scikit-learn", "tensorflow", "pytorch", "keras", "ml"}
    if ev.all_terms & _ml_triggers:
        ev.all_terms.update({"machine learning", "ml", "ai", "artificial intelligence"})

    for edu in resume.education:
        d = _norm(edu.degree)
        if any(x in d for x in ["bca", "bsc", "b.sc", "be", "b.e", "btech", "b.tech", "bachelor", "b.s.", "bs", "undergraduate"]):
            ev.education_levels.add("bachelor")
        if any(x in d for x in ["mca", "msc", "m.sc", "mtech", "m.tech", "me", "master", "m.s.", "ms", "postgraduate"]):
            ev.education_levels.add("master")
        if any(x in d for x in ["phd", "ph.d", "doctor", "doctorate"]):
            ev.education_levels.add("doctorate")

    ev.cert_text = " ".join(_norm(c.name) for c in resume.certifications)

    return ev


# ─────────────────────────────────────────────────────────
# BACKWARDS COMPAT EXPORTS
# ─────────────────────────────────────────────────────────

def enrich_resume(resume: ExtractedResume) -> ExtractedResume:
    return resume


def enrich_job_description(jd: ExtractedJobDescription) -> ExtractedJobDescription:
    return jd


@dataclass
class ResumeConcepts:
    concepts: Set[str] = field(default_factory=set)
    evidence: dict = field(default_factory=dict)


def infer_resume_concepts(resume: ExtractedResume) -> ResumeConcepts:
    return ResumeConcepts()


def infer_full_stack(concepts: ResumeConcepts) -> ResumeConcepts:
    return concepts


def extract_project_terms(project: Project) -> List[str]:
    return _extract_terms(f"{project.title} {project.description}")


def extract_experience_terms(exp: Experience) -> List[str]:
    return _extract_terms(f"{exp.title} {exp.description}")