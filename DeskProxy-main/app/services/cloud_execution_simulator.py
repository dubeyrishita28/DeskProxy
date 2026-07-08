"""
Cloud execution simulator.

Simulates a remote cloud workload so that cache-miss responses look and
feel like a real backend call, complete with realistic variable latency.

The response text is deterministically generated from the query so tests
can assert on content without nondeterminism.
"""

from __future__ import annotations

import hashlib
import random
import time

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Pre-built result templates keyed by semantic domain
_DOMAIN_TEMPLATES: dict[str, str] = {
    "revenue": (
        "Revenue analysis complete. Total revenue for the period: $4.2M. "
        "Month-over-month growth: +8.3%. Top contributing segment: Enterprise (+12.1%). "
        "Recommendation: focus retention efforts on SMB tier to improve blended growth rate."
    ),
    "employee": (
        "HR workforce summary generated. Total headcount: 847 FTE. "
        "Active open requisitions: 23. Average tenure: 3.2 years. "
        "Q3 attrition rate: 4.1% (below industry benchmark of 5.8%)."
    ),
    "dashboard": (
        "Dashboard data refreshed. Displaying 14 KPI tiles across 4 departments. "
        "3 metrics require attention: CSAT (-2.1 pts), CAC (+7%), Ticket SLA compliance (-4.5%). "
        "Full drill-down available via /reports/executive-summary."
    ),
    "performance": (
        "Performance report compiled. System throughput: 98.7% of SLO target. "
        "P95 latency: 142 ms. Error rate: 0.03%. "
        "Capacity headroom at current growth: ~6 months."
    ),
    "budget": (
        "Budget vs actuals computed. YTD spend: $2.1M vs $2.3M budget (91% utilisation). "
        "Operating under budget by $210K. Largest variance: Cloud infrastructure (-$45K). "
        "Forecast: on track to close within 2% of annual target."
    ),
    "analytics": (
        "Analytics pipeline executed. Processed 1.2M events across 7 data sources. "
        "Anomalies detected: 2 (low severity). "
        "Report exported to data lake partition analytics/2025/Q3/."
    ),
}


def _detect_domain(query: str) -> str:
    """Map query text to a domain key for template selection."""
    lower = query.lower()
    if any(w in lower for w in ("revenue", "sales", "income", "arr", "mrr", "roi")):
        return "revenue"
    if any(w in lower for w in ("employee", "headcount", "hr", "workforce", "attrition", "hire")):
        return "employee"
    if any(w in lower for w in ("dashboard", "kpi", "tile", "metric", "scorecard")):
        return "dashboard"
    if any(w in lower for w in ("performance", "latency", "throughput", "uptime", "slo", "sla")):
        return "performance"
    if any(w in lower for w in ("budget", "spend", "cost", "expense", "capex", "opex")):
        return "budget"
    return "analytics"


def execute_cloud_query(query: str) -> tuple[str, float]:
    """
    Simulate a cloud workload execution.

    Returns (result_text, elapsed_ms).
    """
    # Simulate network + compute latency
    delay_ms = random.uniform(
        settings.cloud_min_latency_ms,
        settings.cloud_max_latency_ms,
    )
    time.sleep(delay_ms / 1000.0)

    domain = _detect_domain(query)
    template = _DOMAIN_TEMPLATES.get(domain, _DOMAIN_TEMPLATES["analytics"])

    # Append a query fingerprint so callers can verify round-trip
    fingerprint = hashlib.sha1(query.encode()).hexdigest()[:8]
    result = f"{template} [query_ref={fingerprint}]"

    logger.debug(
        "Cloud execution complete (domain=%s, simulated_latency=%.1f ms)",
        domain,
        delay_ms,
    )
    return result, delay_ms
