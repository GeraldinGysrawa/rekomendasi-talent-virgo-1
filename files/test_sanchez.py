"""
Tests — Modul CBF Sánchez Similarity (Increment 2)
Menggantikan test_tversky.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
import pytest
from src.cbf.sanchez import (
    InMemoryKnowledgeGraph, compute_ic, sanchez_similarity,
    find_lcs, compute_skill_score
)

@pytest.fixture
def g():
    return InMemoryKnowledgeGraph()

class TestIC:
    def test_root_ic_zero(self, g):
        ic = compute_ic("TechnicalSkill", g)
        assert ic <= 0.001, f"Root IC harus ≈ 0, got {ic}"

    def test_leaf_ic_higher_than_abstract(self, g):
        assert compute_ic("React.js", g) > compute_ic("FrontendSkill", g)
        assert compute_ic("FrontendSkill", g) > compute_ic("SoftwareSkill", g)

    def test_same_depth_same_ic(self, g):
        # React.js dan Vue.js struktur sama → IC sama
        assert abs(compute_ic("React.js", g) - compute_ic("Vue.js", g)) < 0.001

    def test_ic_positive_for_non_root(self, g):
        for n in ["React.js", "FrontendSkill", "JSFrameworkFrontend"]:
            assert compute_ic(n, g) > 0

class TestLCS:
    def test_lcs_identical(self, g):
        assert find_lcs("React.js", "React.js", g) == "React.js"

    def test_lcs_same_family(self, g):
        lcs = find_lcs("React.js", "Vue.js", g)
        assert lcs == "JSFrameworkFrontend"

    def test_lcs_cross_domain(self, g):
        # React.js (frontend) vs Docker (devops) → TechnicalSkill
        lcs = find_lcs("React.js", "Docker", g)
        assert lcs == "TechnicalSkill"

    def test_lcs_python_frameworks(self, g):
        lcs = find_lcs("Django", "Flask", g)
        assert lcs == "PythonFramework"

class TestSanchezSimilarity:
    def test_identical(self, g):
        assert sanchez_similarity("React.js", "React.js", g) == 1.0

    def test_same_framework_family_high(self, g):
        s = sanchez_similarity("React.js", "Vue.js", g)
        assert s > 0.6, f"React.js vs Vue.js harus > 0.6, got {s}"

    def test_different_domain_low(self, g):
        s = sanchez_similarity("React.js", "Docker", g)
        assert s < 0.1, f"React.js vs Docker harus < 0.1, got {s}"

    def test_parent_child(self, g):
        s = sanchez_similarity("Laravel", "PHP", g)
        assert 0.3 < s < 0.9

    def test_related_higher_than_unrelated(self, g):
        related   = sanchez_similarity("React.js", "Vue.js", g)
        unrelated = sanchez_similarity("React.js", "Docker", g)
        assert related > unrelated

    def test_symmetry(self, g):
        # sim(a,b) harus == sim(b,a)
        assert sanchez_similarity("React.js","Vue.js",g) == sanchez_similarity("Vue.js","React.js",g)

    def test_range_0_to_1(self, g):
        for a,b in [("React.js","Vue.js"),("PHP","Laravel"),("Python","Docker")]:
            s = sanchez_similarity(a, b, g)
            assert 0.0 <= s <= 1.0, f"sim({a},{b})={s} harus dalam [0,1]"

class TestSkillScore:
    def test_exact_match(self, g):
        r = compute_skill_score(["React.js"], ["React.js"], g)
        assert r["score"] == 1.0

    def test_no_constraint(self, g):
        r = compute_skill_score(["React.js"], [], g)
        assert r["score"] == 1.0

    def test_unrelated_low(self, g):
        r = compute_skill_score(["React.js"], ["Docker"], g)
        assert r["score"] < 0.2

    def test_detail_keys(self, g):
        r = compute_skill_score(["React.js"], ["Vue.js"], g)
        assert all(k in r for k in ["score","detail","matched","coverage"])

    def test_coverage(self, g):
        r = compute_skill_score(["React.js"], ["React.js","Docker"], g)
        # React.js matched, Docker tidak → coverage = 0.5
        assert 0.0 <= r["coverage"] <= 1.0
