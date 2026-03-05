"""
Recommendation Pipeline
========================
Orkestrasi: NLP → CBF (Sánchez) → SAW

Mendukung dua mode:
  inmemory → sinkron, data dummy, tanpa DB
  real     → asinkron, PostgreSQL + Neo4j
"""

import os, sys
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../"))

from src.nlp.ner_extractor import extract_entities, NERResult
from src.cbf.sanchez import (
    InMemoryKnowledgeGraph, Neo4jKnowledgeGraph,
    compute_skill_score, sanchez_similarity, compute_ic
)
from src.saw.saw_calculator import TalentSAWInput, SAWResult, calculate_saw
from src.repository.talent_repository import TalentRepository
from config.settings import get_settings

# Singleton KG (inmemory — untuk mode real diganti Neo4j di startup)
_graph_instance = None

def get_graph():
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = InMemoryKnowledgeGraph()
    return _graph_instance

def set_neo4j_graph(driver):
    """Dipanggil dari FastAPI startup saat APP_MODE=real."""
    global _graph_instance
    _graph_instance = Neo4jKnowledgeGraph(driver)


def _build_response(query, ner, ranked, skill_details, top_k):
    return {
        "query": query,
        "extracted": {
            "skills":         ner.skills,
            "pengalaman_min": ner.pengalaman_min,
            "level":          ner.level,
            "lokasi":         ner.lokasi,
            "project_type":   ner.project_type,
            "start_date":     ner.start_date.isoformat() if ner.start_date else None,
        },
        "weights": ranked[0].weights if ranked else {},
        "tversky_alpha": None,  # tidak relevan untuk Sánchez
        "similarity_method": "Sánchez et al. (2011) Intrinsic IC + Lin (1998)",
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


# ─── Mode inmemory (sync) ─────────────────────────────────────────────────────

def recommend(query: str, top_k: int = 5) -> dict:
    """Pipeline sinkron — untuk mode inmemory."""
    settings = get_settings()
    ner: NERResult = extract_entities(query)
    graph = get_graph()
    repo = TalentRepository(mode=settings.app_mode)
    talents = repo.get_all()

    saw_inputs, skill_details = [], {}
    for talent in talents:
        sr = compute_skill_score(talent.skills, ner.skills, graph)
        skill_details[talent.kode_talent] = sr
        saw_inputs.append(TalentSAWInput(
            talent_id=talent.id, kode_talent=talent.kode_talent, nama=talent.nama,
            skill_score=sr["score"],
            pengalaman_tahun=talent.pengalaman_tahun,
            lokasi=talent.lokasi,
            preferensi_proyek=talent.preferensi_proyek,
            availability_status=talent.availability.status if talent.availability else "available",
            next_available_date=talent.availability.next_available_date if talent.availability else None,
        ))

    ranked = calculate_saw(
        saw_inputs, ner.pengalaman_min, ner.lokasi,
        ner.project_type, ner.start_date,
    )
    return _build_response(query, ner, ranked, skill_details, top_k)


# ─── Mode real (async) ────────────────────────────────────────────────────────

async def recommend_async(query: str, top_k: int = 5, pg_pool=None) -> dict:
    """Pipeline asinkron — untuk mode real dengan PostgreSQL + Neo4j."""
    settings = get_settings()
    ner: NERResult = extract_entities(query)
    graph = get_graph()  # Neo4jKnowledgeGraph jika set_neo4j_graph sudah dipanggil
    repo = TalentRepository(mode=settings.app_mode, pg_pool=pg_pool)
    talents = await repo.get_all_async()

    saw_inputs, skill_details = [], {}
    for talent in talents:
        sr = compute_skill_score(talent.skills, ner.skills, graph)
        skill_details[talent.kode_talent] = sr
        saw_inputs.append(TalentSAWInput(
            talent_id=talent.id, kode_talent=talent.kode_talent, nama=talent.nama,
            skill_score=sr["score"],
            pengalaman_tahun=talent.pengalaman_tahun,
            lokasi=talent.lokasi,
            preferensi_proyek=talent.preferensi_proyek,
            availability_status=talent.availability.status if talent.availability else "available",
            next_available_date=talent.availability.next_available_date if talent.availability else None,
        ))

    ranked = calculate_saw(
        saw_inputs, ner.pengalaman_min, ner.lokasi,
        ner.project_type, ner.start_date,
    )
    return _build_response(query, ner, ranked, skill_details, top_k)
