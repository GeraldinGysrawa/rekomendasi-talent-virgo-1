"""
Settings & Configuration
=========================
Semua konfigurasi sistem dibaca dari .env file atau environment variables.
ROC weights bisa dikonfigurasi tanpa ganti kode — cukup ubah ranking
di .env sesuai hasil konsultasi stakeholder.
"""

import os
from functools import lru_cache


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


class Settings:

    def __init__(self):
        # ── Mode ──────────────────────────────────────────────────────────────
        self.app_mode: str = _env("APP_MODE", "inmemory")

        # ── PostgreSQL ─────────────────────────────────────────────────────────
        self.postgres_host: str = _env("POSTGRES_HOST", "localhost")
        self.postgres_port: int = int(_env("POSTGRES_PORT", "5432"))
        self.postgres_db: str   = _env("POSTGRES_DB", "virgo_talent")
        self.postgres_user: str = _env("POSTGRES_USER", "postgres")
        self.postgres_password: str = _env("POSTGRES_PASSWORD", "password")

        # ── Neo4j ──────────────────────────────────────────────────────────────
        self.neo4j_uri: str      = _env("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user: str     = _env("NEO4J_USER", "neo4j")
        self.neo4j_password: str = _env("NEO4J_PASSWORD", "password")

        # ── Tversky ────────────────────────────────────────────────────────────
        self.tversky_alpha: float = float(_env("TVERSKY_ALPHA", "0.5"))

        # ── ROC Criteria Ranking ───────────────────────────────────────────────
        self.criteria_rank_skill:              int = int(_env("CRITERIA_RANK_SKILL", "1"))
        self.criteria_rank_pengalaman:         int = int(_env("CRITERIA_RANK_PENGALAMAN", "2"))
        self.criteria_rank_lokasi:             int = int(_env("CRITERIA_RANK_LOKASI", "3"))
        self.criteria_rank_preferensi_proyek:  int = int(_env("CRITERIA_RANK_PREFERENSI_PROYEK", "4"))
        self.criteria_rank_ketersediaan:       int = int(_env("CRITERIA_RANK_KETERSEDIAAN", "5"))

        # ── Server ─────────────────────────────────────────────────────────────
        self.host: str = _env("HOST", "0.0.0.0")
        self.port: int = int(_env("PORT", "8000"))

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def criteria_rank_order(self) -> list[str]:
        """
        Kembalikan daftar kriteria diurutkan dari prioritas tertinggi ke terendah.
        Digunakan langsung oleh ROC weight calculator.
        """
        ranks = {
            "skill":               self.criteria_rank_skill,
            "pengalaman":          self.criteria_rank_pengalaman,
            "lokasi":              self.criteria_rank_lokasi,
            "preferensi_proyek":   self.criteria_rank_preferensi_proyek,
            "ketersediaan":        self.criteria_rank_ketersediaan,
        }
        return sorted(ranks, key=lambda k: ranks[k])


@lru_cache()
def get_settings() -> Settings:
    return Settings()
