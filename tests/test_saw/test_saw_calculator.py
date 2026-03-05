"""
Tests — Modul SAW + ROC Weights (Increment 3)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
import pytest
from datetime import date
from src.saw.saw_calculator import (
    compute_roc_weights, calculate_saw, TalentSAWInput,
    score_ketersediaan, score_lokasi, score_preferensi_proyek, score_pengalaman,
)

CRITERIA = ["skill","pengalaman","lokasi","preferensi_proyek","ketersediaan"]

class TestROCWeights:
    def test_sum_to_one(self):
        w = compute_roc_weights(CRITERIA)
        assert abs(sum(w.values()) - 1.0) < 0.001

    def test_descending_order(self):
        w = compute_roc_weights(CRITERIA)
        vals = list(w.values())
        for i in range(len(vals)-1):
            assert vals[i] >= vals[i+1]

    def test_all_criteria_present(self):
        w = compute_roc_weights(CRITERIA)
        for c in CRITERIA:
            assert c in w

    def test_configurable_order(self):
        w1 = compute_roc_weights(["skill","pengalaman","lokasi","preferensi_proyek","ketersediaan"])
        w2 = compute_roc_weights(["ketersediaan","skill","pengalaman","lokasi","preferensi_proyek"])
        # urutan berbeda → bobot berbeda
        assert w1["skill"] != w2["skill"]

class TestScoreKetersediaan:
    TARGET = date(2026, 3, 20)

    def test_available_no_date(self):
        assert score_ketersediaan(None, "available", self.TARGET) == 1.0

    def test_on_project_before_target(self):
        assert score_ketersediaan(date(2026,3,1), "on_project", self.TARGET) == 1.0

    def test_on_project_exact_target(self):
        assert score_ketersediaan(date(2026,3,20), "on_project", self.TARGET) == 1.0

    def test_on_project_after_target(self):
        score = score_ketersediaan(date(2026,4,30), "on_project", self.TARGET)
        assert 0.0 < score < 1.0

    def test_unavailable(self):
        assert score_ketersediaan(None, "unavailable", self.TARGET) == 0.0

    def test_gap_decay(self):
        score_small = score_ketersediaan(date(2026,4,1), "on_project", self.TARGET)
        score_large = score_ketersediaan(date(2026,7,1), "on_project", self.TARGET)
        assert score_small > score_large  # gap kecil lebih baik

    def test_no_date_constraint(self):
        assert score_ketersediaan(None, "available", None) == 1.0
        assert score_ketersediaan(None, "on_project", None) == 0.5

class TestScoreLokasi:
    def test_exact_match(self):
        assert score_lokasi("Bandung", "Bandung") == 1.0

    def test_no_constraint(self):
        assert score_lokasi("Bandung", None) == 1.0

    def test_remote(self):
        assert score_lokasi("Bandung", "remote") == 0.8

    def test_mismatch(self):
        assert score_lokasi("Bandung", "Jakarta") == 0.2

class TestSAWCalculator:
    def _make(self, tid, kode, nama, skill, exp, lok, pref, status, avail_date=None):
        return TalentSAWInput(
            talent_id=tid, kode_talent=kode, nama=nama,
            skill_score=skill, pengalaman_tahun=exp, lokasi=lok,
            preferensi_proyek=pref, availability_status=status,
            next_available_date=avail_date
        )

    def test_ranking_order(self):
        inputs = [
            self._make(1,"T1","A", 0.9, 5, "Bandung", ["banking"], "available"),
            self._make(2,"T2","B", 0.3, 1, "Jakarta", ["mobile"],  "on_project", date(2026,7,1)),
        ]
        results = calculate_saw(inputs, 2.0, "Bandung", "banking", date(2026,3,20))
        assert results[0].final_score >= results[1].final_score

    def test_rank_starts_at_one(self):
        inputs = [self._make(1,"T1","A", 0.7, 3, "Bandung", ["web"], "available")]
        results = calculate_saw(inputs, None, None, None, None)
        assert results[0].rank == 1

    def test_score_range(self):
        inputs = [
            self._make(1,"T1","A", 0.7, 3, "Bandung", ["web"], "available"),
            self._make(2,"T2","B", 0.5, 2, "Jakarta", ["web"], "on_project"),
        ]
        results = calculate_saw(inputs, None, None, None, None)
        for r in results:
            assert 0.0 <= r.final_score <= 1.0

    def test_empty_input(self):
        assert calculate_saw([], None, None, None, None) == []

    def test_explanation_populated(self):
        inputs = [self._make(1,"T1","A", 0.7, 3, "Bandung", ["web"], "available")]
        results = calculate_saw(inputs, None, None, None, None)
        assert results[0].explanation != ""
        assert "skill" in results[0].explanation

    def test_all_criteria_in_scores(self):
        inputs = [self._make(1,"T1","A", 0.7, 3, "Bandung", ["web"], "available")]
        results = calculate_saw(inputs, None, None, None, None)
        for c in CRITERIA:
            assert c in results[0].normalized_scores

    def test_available_beats_on_project_same_skill(self):
        inputs = [
            self._make(1,"T1","Available", 0.8, 3, "Bandung", ["banking"], "available"),
            self._make(2,"T2","OnProject",  0.8, 3, "Bandung", ["banking"], "on_project", date(2026,7,1)),
        ]
        results = calculate_saw(inputs, 2.0, "Bandung", "banking", date(2026,3,20))
        avail = next(r for r in results if r.kode_talent == "T1")
        on_proj = next(r for r in results if r.kode_talent == "T2")
        assert avail.final_score >= on_proj.final_score

    def test_start_date_affects_ranking(self):
        """Talent yang selesai proyek mendekati start_date harus unggul."""
        inputs = [
            self._make(1,"T1","SelesaiMaret", 0.8, 3, "Bandung", ["banking"], "on_project", date(2026,3,1)),
            self._make(2,"T2","SelesaiJuli",  0.8, 3, "Bandung", ["banking"], "on_project", date(2026,7,1)),
        ]
        results = calculate_saw(inputs, 2.0, "Bandung", "banking", date(2026,3,20))
        maret = next(r for r in results if r.kode_talent == "T1")
        juli  = next(r for r in results if r.kode_talent == "T2")
        assert maret.final_score > juli.final_score
