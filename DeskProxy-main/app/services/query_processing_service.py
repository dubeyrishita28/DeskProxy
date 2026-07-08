"""
Query pre-processing pipeline for semantic normalisation.

Transforms raw user input into a canonical form that maximises the
likelihood of a cosine-similarity match against stored embeddings,
regardless of:
  - capitalisation
  - punctuation variation
  - common abbreviations (HR, KPI, ROI, etc.)
  - British / American spelling variants
  - common misspellings
  - plural/singular forms
  - filler words ("please", "could you", "I need")
  - corporate / finance / analytics terminology synonyms
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Abbreviation expansion map
# ---------------------------------------------------------------------------

_ABBREVIATIONS: dict[str, str] = {
    # Analytics / BI
    "kpi": "key performance indicator",
    "kpis": "key performance indicators",
    "bi": "business intelligence",
    "roi": "return on investment",
    "p&l": "profit and loss",
    "pnl": "profit and loss",
    "ytd": "year to date",
    "mtd": "month to date",
    "qtd": "quarter to date",
    "yoy": "year over year",
    "qoq": "quarter over quarter",
    "mom": "month over month",
    "cagr": "compound annual growth rate",
    "cac": "customer acquisition cost",
    "ltv": "lifetime value",
    "clv": "customer lifetime value",
    "arr": "annual recurring revenue",
    "mrr": "monthly recurring revenue",
    "arpu": "average revenue per user",
    "churn": "customer churn",
    "nps": "net promoter score",
    "csat": "customer satisfaction score",
    "dau": "daily active users",
    "mau": "monthly active users",
    # HR
    "hr": "human resources",
    "hris": "human resources information system",
    "fte": "full time equivalent",
    "hc": "headcount",
    "pto": "paid time off",
    "ooo": "out of office",
    "eap": "employee assistance program",
    "l&d": "learning and development",
    # Finance
    "ebitda": "earnings before interest taxes depreciation amortization",
    "eps": "earnings per share",
    "pe": "price to earnings",
    "roe": "return on equity",
    "roa": "return on assets",
    "wacc": "weighted average cost of capital",
    "npv": "net present value",
    "irr": "internal rate of return",
    "capex": "capital expenditure",
    "opex": "operating expenditure",
    "cogs": "cost of goods sold",
    "gm": "gross margin",
    "gp": "gross profit",
    # Tech / SaaS
    "api": "application programming interface",
    "sla": "service level agreement",
    "slo": "service level objective",
    "sli": "service level indicator",
    "ci/cd": "continuous integration continuous deployment",
    "cicd": "continuous integration continuous deployment",
    "saas": "software as a service",
    "paas": "platform as a service",
    "iaas": "infrastructure as a service",
    # Dashboard / reporting
    "dash": "dashboard",
    "rpt": "report",
    "exec": "executive",
    "mgmt": "management",
    "dept": "department",
    "q1": "first quarter",
    "q2": "second quarter",
    "q3": "third quarter",
    "q4": "fourth quarter",
}

# Spelling / synonym corrections
_CORRECTIONS: dict[str, str] = {
    "analyse": "analyze",
    "analysed": "analyzed",
    "analyses": "analyzes",
    "organisation": "organization",
    "organisations": "organizations",
    "organisational": "organizational",
    "behaviour": "behavior",
    "behaviours": "behaviors",
    "colour": "color",
    "colours": "colors",
    "centre": "center",
    "centres": "centers",
    "licence": "license",
    "programme": "program",
    "programmes": "programs",
    "recognise": "recognize",
    "optimise": "optimize",
    "utilise": "utilize",
    "customise": "customize",
    # common misspellings
    "dashbord": "dashboard",
    "dashborad": "dashboard",
    "analytcs": "analytics",
    "analystics": "analytics",
    "sumary": "summary",
    "performnce": "performance",
    "reveue": "revenue",
    "reveneu": "revenue",
    "employe": "employee",
    "employes": "employees",
}

# Filler / stop phrase patterns (removed before embedding)
_FILLER_PATTERNS = re.compile(
    r"\b(please|could you|can you|i need|i want|i would like|"
    r"give me|show me|tell me|provide me|help me|let me know|"
    r"what is|what are|how do i|how can i|how to)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public normalisation function
# ---------------------------------------------------------------------------

@lru_cache(maxsize=4096)
def normalize_query(raw_query: str) -> str:
    """
    Return a normalised representation of *raw_query*.

    Cached so repeated identical queries incur zero processing cost.
    """
    text = raw_query.strip()

    # 1. Unicode normalisation (NFKC handles ligatures, fullwidth chars, etc.)
    text = unicodedata.normalize("NFKC", text)

    # 2. Lower-case
    text = text.lower()

    # 3. Remove possessives  ("company's" → "company")
    text = re.sub(r"'s\b", "", text)

    # 4. Normalise punctuation / special chars (keep alphanumeric and spaces)
    text = re.sub(r"[^\w\s&/]", " ", text)
    text = re.sub(r"[_]", " ", text)

    # 5. Expand abbreviations (whole-word match)
    tokens = text.split()
    expanded: list[str] = []
    for token in tokens:
        # Try with slash variants (e.g. "ci/cd")
        expanded.append(_ABBREVIATIONS.get(token, token))
    text = " ".join(expanded)

    # 6. Apply spelling / synonym corrections
    tokens = text.split()
    text = " ".join(_CORRECTIONS.get(t, t) for t in tokens)

    # 7. Strip filler phrases
    text = _FILLER_PATTERNS.sub(" ", text)

    # 8. Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        # Fall back to lowercased original so we always return something usable
        text = raw_query.lower().strip()

    return text


def get_cache_stats() -> dict:
    """Expose lru_cache statistics for monitoring."""
    info = normalize_query.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": info.maxsize,
        "currsize": info.currsize,
    }
