"""
FastAPI Application — Virgo Talent Recommender
==============================================
Mode: real dengan PostgreSQL + Neo4j Knowledge Graph
Similarity: Sánchez et al. (2011/2012) Intrinsic IC + Lin (1998)
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
from src.pipeline import recommend, recommend_async, set_neo4j_graph
from config.settings import get_settings

app = FastAPI(
    title="Virgo Talent Recommender API",
    description="""
Sistem rekomendasi Talent PT Padepokan Tujuh Sembilan.

**Pipeline (3 Increment):**
- **NLP (Inc.1)**: NER — ekstrak 5 entitas: skill, pengalaman, lokasi, tipe proyek, tanggal mulai
- **CBF (Inc.2)**: Sánchez Semantic Similarity via Knowledge Graph (Sánchez et al. 2011/2012)
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


@app.on_event("startup")
async def startup():
    """Inisialisasi koneksi ke PostgreSQL & Neo4j saat startup."""
    settings = get_settings()
    
    if settings.app_mode == "real":
        # Setup PostgreSQL pool
        from src.db.connectors import get_pg_pool
        await get_pg_pool()
        print("✅ PostgreSQL pool initialized")
        
        # Setup Neo4j driver & KG
        from src.db.connectors import get_neo4j_driver
        driver = get_neo4j_driver()
        set_neo4j_graph(driver)
        print("✅ Neo4j driver initialized & set as KG")


@app.on_event("shutdown")
async def shutdown():
    """Tutup koneksi saat shutdown."""
    settings = get_settings()
    if settings.app_mode == "real":
        from src.db.connectors import close_all
        await close_all()
        print("✅ All connections closed")


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
    
    **Mode:**
    - `inmemory`: data dummy, sync
    - `real`: PostgreSQL + Neo4j, async
    """
    try:
        settings = get_settings()
        
        if settings.app_mode == "real":
            # Async pipeline untuk mode real
            from src.db.connectors import get_pg_pool
            pool = await get_pg_pool()
            result = await recommend_async(query=request.query, top_k=request.top_k, pg_pool=pool)
        else:
            # Sync pipeline untuk mode inmemory
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
    from src.cbf.sanchez import InMemoryKnowledgeGraph
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
    **Debug** — Hitung Sánchez Semantic Similarity antara dua skill.
    """
    from src.cbf.sanchez import InMemoryKnowledgeGraph, sanchez_similarity
    graph = InMemoryKnowledgeGraph()
    score = sanchez_similarity(skill_a, skill_b, graph)
    return {
        "skill_a":    skill_a,
        "skill_b":    skill_b,
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
