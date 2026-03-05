"""
Database Connectors
====================
Singleton pool/driver untuk PostgreSQL (asyncpg) dan Neo4j.

Penggunaan:
    from src.db.connectors import get_pg_pool, get_neo4j_driver

Mode:
    APP_MODE=inmemory → koneksi tidak dibuat, repository pakai dummy data
    APP_MODE=real     → koneksi sungguhan ke PostgreSQL & Neo4j
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

_pg_pool = None

async def get_pg_pool():
    """Kembalikan asyncpg connection pool (singleton)."""
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    try:
        import asyncpg
    except ImportError:
        raise ImportError("Jalankan: pip install asyncpg")
    from config.settings import get_settings
    s = get_settings()
    _pg_pool = await asyncpg.create_pool(
        host=s.postgres_host, port=s.postgres_port,
        database=s.postgres_db, user=s.postgres_user,
        password=s.postgres_password,
        min_size=2, max_size=10, command_timeout=30,
    )
    return _pg_pool

async def close_pg_pool():
    global _pg_pool
    if _pg_pool:
        await _pg_pool.close()
        _pg_pool = None

_neo4j_driver = None

def get_neo4j_driver():
    """Kembalikan Neo4j driver (singleton)."""
    global _neo4j_driver
    if _neo4j_driver is not None:
        return _neo4j_driver
    try:
        from neo4j import GraphDatabase
    except ImportError:
        raise ImportError("Jalankan: pip install neo4j")
    from config.settings import get_settings
    s = get_settings()
    _neo4j_driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    _neo4j_driver.verify_connectivity()
    return _neo4j_driver

def close_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver:
        _neo4j_driver.close()
        _neo4j_driver = None

async def close_all():
    """Tutup semua koneksi — dipanggil saat FastAPI shutdown."""
    await close_pg_pool()
    close_neo4j_driver()
