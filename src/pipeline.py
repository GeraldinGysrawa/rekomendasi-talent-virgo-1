"""
Recommendation Pipeline
========================
Menghubungkan semua modul: NLP → CBF → SAW

Alur:
  1. [NLP]  extract_entities(query)
            → NERResult(skills, pengalaman_min, lokasi, project_type, start_date)

  2. [CBF]  Untuk setiap talent di DB:
            compute_skill_score(talent.skills, ner.skills, graph)
            → skill_score [0,1]

  3. [SAW]  calculate_saw(all_talents_with_scores, ner_constraints)
            → list[SAWResult] terurut
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../"))

from src.nlp.ner_extractor import extract_entities, NERResult
from src.cbf.tversky import InMemoryKnowledgeGraph, compute_skill_score
from src.saw.saw_calculator import TalentSAWInput, SAWResult, calculate_saw
from src.repository.talent_repository import TalentRepository
from config.settings import get_settings

# Singleton instances
_graph = InMemoryKnowledgeGraph()


def recommend(
    query: str,
    top_k: int = 5,
) -> dict:
    """
    Pipeline rekomendasi end-to-end.

    Args:
        query  : kalimat natural dari user
        top_k  : jumlah rekomendasi yang dikembalikan

    Returns:
        dict berisi hasil NER, bobot yang digunakan, dan rekomendasi terranking
    """
    settings = get_settings()

    # ── Step 1: NLP — Content Analyzer ───────────────────────────────────────
    ner: NERResult = extract_entities(query)

    # ── Step 2: CBF — Filtering Component ────────────────────────────────────
    repo = TalentRepository(mode=settings.app_mode)
    talents = repo.get_all()

    saw_inputs: list[TalentSAWInput] = []
    skill_details: dict[str, dict] = {}

    for talent in talents:
        skill_result = compute_skill_score(
            talent_skills=talent.skills,
            required_skills=ner.skills,
            graph=_graph,
            alpha=settings.tversky_alpha,
        )

        skill_details[talent.kode_talent] = skill_result

        saw_inputs.append(TalentSAWInput(
            talent_id=talent.id,
            kode_talent=talent.kode_talent,
            nama=talent.nama,
            skill_score=skill_result["score"],
            pengalaman_tahun=talent.pengalaman_tahun,
            lokasi=talent.lokasi,
            preferensi_proyek=talent.preferensi_proyek,
            availability_status=talent.availability.status if talent.availability else "available",
            next_available_date=talent.availability.next_available_date if talent.availability else None,
        ))

    # ── Step 3: SAW — Ranking ─────────────────────────────────────────────────
    ranked: list[SAWResult] = calculate_saw(
        talents=saw_inputs,
        required_pengalaman=ner.pengalaman_min,
        required_lokasi=ner.lokasi,
        required_project_type=ner.project_type,
        required_start_date=ner.start_date,
    )

    # ── Format Response ───────────────────────────────────────────────────────
    return {
        "query": query,
        "extracted": {
            "skills":          ner.skills,
            "pengalaman_min":  ner.pengalaman_min,
            "level":           ner.level,
            "lokasi":          ner.lokasi,
            "project_type":    ner.project_type,
            "start_date":      ner.start_date.isoformat() if ner.start_date else None,
        },
        "weights": ranked[0].weights if ranked else {},
        "tversky_alpha": settings.tversky_alpha,
        "total_candidates": len(ranked),
        "recommendations": [
            {
                "rank":              r.rank,
                "talent_id":         r.talent_id,
                "kode_talent":       r.kode_talent,
                "nama":              r.nama,
                "final_score":       r.final_score,
                "normalized_scores": r.normalized_scores,
                "weighted_scores":   r.weighted_scores,
                "skill_detail":      skill_details.get(r.kode_talent, {}).get("detail", []),
                "skill_coverage":    skill_details.get(r.kode_talent, {}).get("coverage", 0),
                "explanation":       r.explanation,
            }
            for r in ranked[:top_k]
        ]
    }


if __name__ == "__main__":
    import json

    query = (
        "saya butuh front end, dengan kemampuan react dengan pengalaman diatas 2 tahun, "
        "pengerjaan di Bandung dan mengerjakan proyek BANK, "
        "proyek akan di kerjakan pada 20 Maret 2026 hingga 20 Desember 2026"
    )

    result = recommend(query, top_k=5)

    print(f"Query: {query}\n")
    print("=== NER Extracted ===")
    for k, v in result["extracted"].items():
        print(f"  {k:17s}: {v}")

    print("\n=== ROC Weights ===")
    for c, w in result["weights"].items():
        print(f"  {c:20s}: {w:.6f}")

    print(f"\n=== Top {len(result['recommendations'])} Recommendations ===")
    for r in result["recommendations"]:
        print(f"\n  #{r['rank']} {r['nama']} (Score: {r['final_score']:.6f})")
        print(f"     Skill coverage: {r['skill_coverage']:.0%}")
        print(f"     {r['explanation']}")
