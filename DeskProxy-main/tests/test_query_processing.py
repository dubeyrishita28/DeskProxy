"""
Unit tests for QueryProcessingService (query normalisation pipeline).
"""

from __future__ import annotations

import pytest

from app.services.query_processing_service import normalize_query


class TestBasicNormalisation:
    def test_lowercases_input(self):
        assert normalize_query("SHOW ME REVENUE") == normalize_query("show me revenue")

    def test_strips_leading_trailing_whitespace(self):
        result = normalize_query("  headcount report  ")
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_collapses_internal_whitespace(self):
        result = normalize_query("show   me   the   dashboard")
        assert "  " not in result

    def test_removes_possessives(self):
        result = normalize_query("company's revenue")
        assert "'s" not in result


class TestAbbreviationExpansion:
    def test_kpi_expands(self):
        result = normalize_query("show KPI dashboard")
        assert "key performance indicator" in result

    def test_roi_expands(self):
        result = normalize_query("calculate ROI for Q3")
        assert "return on investment" in result

    def test_hr_expands(self):
        result = normalize_query("HR headcount report")
        assert "human resources" in result

    def test_ytd_expands(self):
        result = normalize_query("YTD revenue summary")
        assert "year to date" in result

    def test_ebitda_expands(self):
        result = normalize_query("EBITDA analysis")
        assert "earnings before interest" in result

    def test_arr_expands(self):
        result = normalize_query("show ARR breakdown")
        assert "annual recurring revenue" in result

    def test_mrr_expands(self):
        result = normalize_query("MRR by segment")
        assert "monthly recurring revenue" in result

    def test_q3_expands(self):
        result = normalize_query("Q3 performance report")
        assert "third quarter" in result


class TestSpellingCorrections:
    def test_british_analyse_corrected(self):
        result = normalize_query("analyse revenue trends")
        assert "analyze" in result

    def test_british_organisation_corrected(self):
        result = normalize_query("organisation chart")
        assert "organization" in result

    def test_misspelled_dashboard(self):
        result = normalize_query("dashbord metrics")
        assert "dashboard" in result

    def test_misspelled_analytics(self):
        result = normalize_query("analytcs pipeline")
        assert "analytics" in result


class TestFillerPhraseRemoval:
    def test_please_removed(self):
        result = normalize_query("please show me the revenue report")
        assert "please" not in result

    def test_could_you_removed(self):
        result = normalize_query("could you provide the dashboard data")
        assert "could you" not in result

    def test_show_me_removed(self):
        result = normalize_query("show me the KPI summary")
        assert "show me" not in result


class TestEdgeCases:
    def test_empty_string_falls_back_gracefully(self):
        # normalize_query validates at the API layer; empty normalises to ""
        result = normalize_query("   ")
        # Should not raise; result may be empty or original
        assert isinstance(result, str)

    def test_unicode_normalised(self):
        # Fullwidth letters should normalise to ASCII equivalents
        result = normalize_query("ｒｅｖｅｎｕｅ")
        assert "revenue" in result

    def test_cache_is_deterministic(self):
        r1 = normalize_query("KPI dashboard report")
        r2 = normalize_query("KPI dashboard report")
        assert r1 == r2
