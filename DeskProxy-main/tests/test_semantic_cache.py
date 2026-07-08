"""
Semantic matching tests — verify that the normalisation pipeline
produces embeddings that can retrieve semantically equivalent queries.

These tests run against the real sentence-transformers model so they
require the model to be downloaded.  They are marked 'semantic' so
they can be skipped in environments without internet access.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.semantic


@pytest.fixture(scope="module", autouse=True)
def load_model():
    from app.services.semantic_embedding_service import initialise_model
    initialise_model()


class TestEmbeddingGeneration:
    def test_embedding_is_list_of_floats(self):
        from app.services.semantic_embedding_service import get_embedding
        vec = get_embedding("show me the revenue dashboard")
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)

    def test_embedding_dimension_is_384(self):
        from app.services.semantic_embedding_service import get_embedding
        vec = get_embedding("KPI breakdown")
        assert len(vec) == 384

    def test_same_text_same_embedding(self):
        from app.services.semantic_embedding_service import get_embedding
        v1 = get_embedding("annual revenue report")
        v2 = get_embedding("annual revenue report")
        assert v1 == v2


class TestSemanticSimilarity:
    """
    Verify that semantically equivalent queries produce high cosine similarity.
    """

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        import math
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(y * y for y in b))
        return dot / (mag_a * mag_b + 1e-10)

    def _sim(self, q1: str, q2: str) -> float:
        from app.services.semantic_embedding_service import get_embedding
        from app.services.query_processing_service import normalize_query
        v1 = get_embedding(normalize_query(q1))
        v2 = get_embedding(normalize_query(q2))
        return self._cosine(v1, v2)

    def test_identical_queries_near_perfect_similarity(self):
        score = self._sim("revenue dashboard", "revenue dashboard")
        assert score > 0.99

    def test_synonym_queries_high_similarity(self):
        score = self._sim("show me revenue breakdown", "display income analysis")
        assert score > 0.60

    def test_abbreviation_vs_full_form(self):
        score = self._sim("KPI summary", "key performance indicator summary")
        assert score > 0.80

    def test_unrelated_queries_low_similarity(self):
        score = self._sim("revenue dashboard", "python programming tutorial")
        assert score < 0.70

    def test_paraphrase_high_similarity(self):
        score = self._sim(
            "what is the headcount across all departments",
            "total employee count by department",
        )
        assert score > 0.65
