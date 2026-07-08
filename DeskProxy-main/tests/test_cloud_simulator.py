"""
Unit tests for the CloudExecutionSimulator.
"""

from __future__ import annotations

import pytest
from app.services.cloud_execution_simulator import execute_cloud_query


class TestCloudExecutionSimulator:
    def test_returns_tuple_of_str_and_float(self):
        result, latency = execute_cloud_query("revenue analysis")
        assert isinstance(result, str)
        assert isinstance(latency, float)

    def test_result_is_nonempty(self):
        result, _ = execute_cloud_query("KPI dashboard")
        assert len(result) > 10

    def test_result_contains_query_fingerprint(self):
        result, _ = execute_cloud_query("unique test query xyz")
        assert "query_ref=" in result

    def test_latency_within_configured_range(self):
        from app.config import settings
        _, latency = execute_cloud_query("budget report")
        assert settings.cloud_min_latency_ms <= latency <= settings.cloud_max_latency_ms + 20

    def test_revenue_domain_detected(self):
        result, _ = execute_cloud_query("show total revenue for Q3")
        assert "revenue" in result.lower() or "income" in result.lower() or "Revenue" in result

    def test_hr_domain_detected(self):
        result, _ = execute_cloud_query("employee headcount by department")
        assert any(w in result.lower() for w in ("hr", "headcount", "workforce", "employee", "fte"))

    def test_different_queries_may_vary(self):
        r1, _ = execute_cloud_query("show revenue dashboard")
        r2, _ = execute_cloud_query("python programming tutorial")
        # Results may differ or be the same template — just ensure no crash
        assert isinstance(r1, str)
        assert isinstance(r2, str)
