"""
FastAPI Application — Virgo Talent Recommender
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
from src.pipeline import recommend
from config.settings import get_settings

app = FastAPI(
    title="Virgo Talent Recommender API",
    description="""
Sistem rekomendasi Talent PT Padepokan Tujuh Sembilan.

**Pipeline (3 Increment):**
- **NLP (Inc.1)**: NER — ekstrak 5 entitas: skill, pengalaman, lokasi, tipe proyek, tanggal mulai
- **CBF (Inc.2)**: Tversky Similarity via Knowledge Graph (Rodriguez-Egenhofer 2003)
- **SAW (Inc.3)**: Ranking multi-kriteria SAW + ROC weights (Barron & Barrett 1996)

**Storage:**
- PostgreSQL → profil talent (skill, pengalaman, lokasi, preferensi, ketersediaan)
- Neo4j → Knowledge Graph ontologi skill IT
""",
    version="1.0.0",
)


class RecommendRequest(BaseModel):
    query: str = Field(
        ...,
        description="Kalimat natural kebutuhan talent dari pengguna",
        examples=[
            "saya butuh frontend React.js, pengalaman diatas 2 tahun, "
            "Bandung, proyek BANK, mulai 20 Maret 2026"
        ]
    )
    top_k: int = Field(default=5, ge=1, le=20)


@app.get("/", tags=["Health"])
async def root():
    settings = get_settings()
    return {
        "service": "Virgo Talent Recommender",
        "version": "1.0.0",
        "mode": settings.app_mode,
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


@app.post("/recommend", tags=["Recommendation"])
async def get_recommendations(request: RecommendRequest):
    """
    **Endpoint utama** — Query natural → ranked talent list.

    Input query natural seperti:
    - *"saya butuh frontend React.js, 2 tahun, Bandung, proyek BANK, mulai 20 Maret 2026"*
    - *"butuh senior Java Spring Boot, minimal 4 tahun, Jakarta, enterprise"*

    Response berisi:
    - Hasil ekstraksi NER (5 entitas)
    - Bobot ROC yang digunakan
    - Daftar talent terranking dengan skor dan penjelasan per kriteria
    """
    try:
        result = recommend(query=request.query, top_k=request.top_k)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract", tags=["NLP — Increment 1"])
async def extract_only(query: str = Query(..., description="Query natural untuk diekstrak")):
    """
    **Debug** — Jalankan hanya modul NLP (Increment 1).
    Berguna untuk validasi hasil NER sebelum integrasi CBF & SAW.
    """
    from src.nlp.ner_extractor import extract_entities
    result = extract_entities(query)
    return {
        "skills":         result.skills,
        "pengalaman_min": result.pengalaman_min,
        "level":          result.level,
        "lokasi":         result.lokasi,
        "project_type":   result.project_type,
        "start_date":     result.start_date.isoformat() if result.start_date else None,
        "raw_query":      result.raw_query,
    }


@app.get("/graph/skill/{skill_name}", tags=["CBF — Increment 2"])
async def get_skill_ancestors(skill_name: str):
    """
    **Debug** — Tampilkan ancestor hierarki ontologi suatu skill.
    Berguna untuk memahami mengapa dua skill punya similarity score tertentu.
    """
    from src.cbf.tversky import InMemoryKnowledgeGraph, tversky_similarity
    graph = InMemoryKnowledgeGraph()
    ancestors = graph.get_ancestors(skill_name)
    return {
        "skill":    skill_name,
        "exists":   graph.skill_exists(skill_name),
        "ancestors": sorted(list(ancestors)),
        "ancestor_count": len(ancestors),
    }


@app.get("/graph/similarity", tags=["CBF — Increment 2"])
async def get_similarity(
    skill_a: str = Query(..., description="Skill talent"),
    skill_b: str = Query(..., description="Skill yang dibutuhkan"),
):
    """
    **Debug** — Hitung Tversky Similarity antara dua skill.
    """
    from src.cbf.tversky import InMemoryKnowledgeGraph, tversky_similarity
    settings = get_settings()
    graph = InMemoryKnowledgeGraph()
    score = tversky_similarity(skill_a, skill_b, graph, alpha=settings.tversky_alpha)
    return {
        "skill_a":    skill_a,
        "skill_b":    skill_b,
        "alpha":      settings.tversky_alpha,
        "similarity": score,
        "ancestors_a": sorted(list(graph.get_ancestors(skill_a))),
        "ancestors_b": sorted(list(graph.get_ancestors(skill_b))),
    }


@app.get("/saw/weights", tags=["SAW — Increment 3"])
async def get_weights():
    """
    **Info** — Tampilkan bobot ROC yang sedang aktif.
    Bobot dapat diubah melalui .env tanpa mengubah kode.
    """
    from src.saw.saw_calculator import compute_roc_weights
    settings = get_settings()
    rank_order = settings.criteria_rank_order
    weights = compute_roc_weights(rank_order)
    return {
        "method":            "Rank Order Centroid (Barron & Barrett, 1996)",
        "formula":           "w_i = (1/n) * Σ_{j=i}^{n} (1/j)",
        "n_criteria":        len(rank_order),
        "priority_order":    rank_order,
        "weights":           weights,
        "total":             round(sum(weights.values()), 6),
        "note":              "Urutan prioritas dikonfigurasi via .env — CRITERIA_RANK_*"
    }
