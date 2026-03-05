"""
Tests — Modul CBF Tversky Similarity (Increment 2)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
import pytest
from src.cbf.tversky import InMemoryKnowledgeGraph, tversky_similarity, compute_skill_score

@pytest.fixture
def graph():
    return InMemoryKnowledgeGraph()

class TestAncestors:
    def test_react_ancestors(self, graph):
        ancestors = graph.get_ancestors("React.js")
        assert "React.js" in ancestors
        assert "JSFrameworkFrontend" in ancestors
        assert "FrontendSkill" in ancestors
        assert "SoftwareSkill" in ancestors
        assert "TechnicalSkill" in ancestors

    def test_unknown_skill(self, graph):
        ancestors = graph.get_ancestors("UnknownSkill")
        assert ancestors == {"UnknownSkill"}

    def test_skill_exists(self, graph):
        assert graph.skill_exists("React.js") is True
        assert graph.skill_exists("NonExistent") is False

class TestTverskySimilarity:
    def test_identical(self, graph):
        assert tversky_similarity("React.js", "React.js", graph) == 1.0

    def test_same_framework_family(self, graph):
        score = tversky_similarity("React.js", "Vue.js", graph)
        assert score > 0.5, f"React.js vs Vue.js expected > 0.5, got {score}"

    def test_parent_child(self, graph):
        score = tversky_similarity("Laravel", "PHP", graph)
        assert score > 0.4, f"Laravel vs PHP expected > 0.4, got {score}"

    def test_different_domain(self, graph):
        score = tversky_similarity("React.js", "Docker", graph)
        assert score < 0.4, f"React.js vs Docker expected < 0.4, got {score}"

    def test_score_range(self, graph):
        for a, b in [("React.js","Vue.js"),("PHP","Laravel"),("Python","Django")]:
            score = tversky_similarity(a, b, graph)
            assert 0.0 <= score <= 1.0

    def test_related_higher_than_unrelated(self, graph):
        related = tversky_similarity("React.js", "Vue.js", graph)
        unrelated = tversky_similarity("React.js", "Docker", graph)
        assert related > unrelated

class TestComputeSkillScore:
    def test_exact_match(self, graph):
        r = compute_skill_score(["React.js"], ["React.js"], graph)
        assert r["score"] == 1.0

    def test_related_skill(self, graph):
        r = compute_skill_score(["React.js"], ["Vue.js"], graph)
        assert r["score"] > 0.0

    def test_empty_required_no_constraint(self, graph):
        r = compute_skill_score(["React.js"], [], graph)
        assert r["score"] == 1.0  # tidak ada constraint = semua lolos

    def test_detail_structure(self, graph):
        r = compute_skill_score(["React.js","PHP"], ["Vue.js","Laravel"], graph)
        assert "score" in r
        assert "detail" in r
        assert "matched" in r
        assert "coverage" in r
        assert len(r["detail"]) == 2

    def test_coverage_calculation(self, graph):
        r = compute_skill_score(["React.js"], ["React.js","Laravel"], graph)
        # React.js matched, Laravel tidak → coverage = 0.5
        assert 0.0 <= r["coverage"] <= 1.0
