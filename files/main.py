"""
FastAPI Application — Virgo Talent Recommender
Mendukung APP_MODE=inmemory (dev) dan APP_MODE=real (PostgreSQL + Neo4j).
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from config.settings import get_settings
from src.pipeline import recommend, recommend_async, set_neo4j_graph

# ─── State aplikasi ────────────────────────────────────────────────────────────
_pg_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Buka koneksi DB saat startup, tutup saat shutdown."""
    global _pg_pool
    settings = get_settings()

    if settings.app_mode == "real":
        from src.db.connectors import get_pg_pool, get_neo4j_driver, close_all
        _pg_pool = await get_pg_pool()
        driver = get_neo4j_driver()
        set_neo4j_graph(driver)
        print(f"[startup] PostgreSQL pool OK | Neo4j OK | mode=real")
    else:
        print(f"[startup] mode=inmemory — dummy data, tanpa koneksi DB")

    yield  # ← aplikasi berjalan

    if settings.app_mode == "real":
        from src.db.connectors import close_all
        await close_all()
        print("[shutdown] Koneksi DB ditutup.")


# ─── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Virgo Talent Recommender API",
    description="""
**Pipeline:** NLP (NER) → CBF (Sánchez IC Similarity) → SAW (ROC Weights)

**Storage:**
- PostgreSQL → profil talent (5 tabel, 5 kriteria SAW)
- Neo4j → Knowledge Graph ontologi skill IT (IS_A hierarchy)

**Similarity:** Sánchez et al. (2011) Intrinsic IC + Lin (1998)
""",
    version="2.0.0",
    lifespan=lifespan,
)


# ─── Models ────────────────────────────────────────────────────────────────────
class RecommendRequest(BaseModel):
    query: str = Field(..., examples=[
        "saya butuh frontend React.js, pengalaman diatas 2 tahun, Bandung, proyek BANK, mulai 20 Maret 2026"
    ])
    top_k: int = Field(default=5, ge=1, le=20)


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
async def root():
    settings = get_settings()
    return {
        "service": "Virgo Talent Recommender",
        "version": "2.0.0",
        "mode": settings.app_mode,
        "similarity": "Sánchez et al. (2011) + Lin (1998)",
        "docs": "/docs",
    }


@app.get("/health", tags=["Info"])
async def health():
    settings = get_settings()
    status = {"status": "ok", "mode": settings.app_mode}
    if settings.app_mode == "real":
        status["pg_pool"] = "connected" if _pg_pool else "not connected"
    return status


@app.post("/recommend", tags=["Rekomendasi"])
async def get_recommendations(request: RecommendRequest):
    """
    **Endpoint utama** — query natural → ranked talent list.

    Proses:
    1. NER ekstrak 5 entitas (skill, exp, lokasi, proyek, tanggal)
    2. Sánchez IC Similarity per talent dari Knowledge Graph Neo4j
    3. SAW ranking dengan ROC weights (dikonfigurasi dari .env)
    """
    try:
        settings = get_settings()
        if settings.app_mode == "real":
            result = await recommend_async(request.query, request.top_k, pg_pool=_pg_pool)
        else:
            result = recommend(request.query, request.top_k)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract", tags=["Debug — NLP Inc.1"])
async def extract_only(query: str = Query(...)):
    """Debug NER — tampilkan 5 entitas yang diekstrak dari query."""
    from src.nlp.ner_extractor import extract_entities
    r = extract_entities(query)
    return {
        "skills": r.skills, "pengalaman_min": r.pengalaman_min,
        "level": r.level, "lokasi": r.lokasi,
        "project_type": r.project_type,
        "start_date": r.start_date.isoformat() if r.start_date else None,
    }


@app.get("/graph/skill/{skill_name}", tags=["Debug — CBF Inc.2"])
async def skill_info(skill_name: str):
    """Debug — IC value + ancestors + leaves suatu skill dari Knowledge Graph."""
    from src.cbf.sanchez import compute_ic, find_lcs
    from src.pipeline import get_graph
    g = get_graph()
    ic = compute_ic(skill_name, g)
    ancestors = sorted(g.get_ancestors(skill_name))
    leaves = sorted(g.get_leaves(skill_name))
    return {
        "skill": skill_name,
        "exists": g.node_exists(skill_name),
        "ic": round(ic, 6),
        "ancestors": ancestors,
        "ancestor_count": len(ancestors),
        "leaves": leaves,
        "leaf_count": len(leaves),
    }


@app.get("/graph/similarity", tags=["Debug — CBF Inc.2"])
async def skill_similarity(
    skill_a: str = Query(...),
    skill_b: str = Query(...),
):
    """Debug — hitung Sánchez similarity dua skill + tampilkan LCS dan IC masing-masing."""
    from src.cbf.sanchez import sanchez_similarity, compute_ic, find_lcs
    from src.pipeline import get_graph
    g = get_graph()
    sim  = sanchez_similarity(skill_a, skill_b, g)
    lcs  = find_lcs(skill_a, skill_b, g)
    return {
        "skill_a":  skill_a, "ic_a": round(compute_ic(skill_a, g), 6),
        "skill_b":  skill_b, "ic_b": round(compute_ic(skill_b, g), 6),
        "lcs":      lcs,     "ic_lcs": round(compute_ic(lcs, g), 6),
        "similarity": sim,
        "formula": "sim(a,b) = 2×IC(LCS) / (IC(a)+IC(b))  — Lin 1998 + Sánchez 2011 IC",
    }


@app.get("/saw/weights", tags=["Debug — SAW Inc.3"])
async def saw_weights():
    """Info — bobot ROC yang sedang aktif (dikonfigurasi dari .env)."""
    from src.saw.saw_calculator import compute_roc_weights
    settings = get_settings()
    rank_order = settings.criteria_rank_order
    weights = compute_roc_weights(rank_order)
    return {
        "method": "Rank Order Centroid — Barron & Barrett (1996)",
        "formula": "w_i = (1/n) × Σ_{j=i}^{n} (1/j)",
        "priority_order": rank_order,
        "weights": weights,
        "total": round(sum(weights.values()), 6),
        "note": "Ubah ranking via CRITERIA_RANK_* di .env tanpa ganti kode",
    }
