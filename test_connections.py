#!/usr/bin/env python3
"""
Test Script untuk PostgreSQL & Neo4j Connection
================================================

Jalankan dengan: python test_connections.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from config.settings import get_settings

async def test_postgres():
    """Test koneksi PostgreSQL."""
    print("\n" + "="*60)
    print("🔍 Testing PostgreSQL Connection")
    print("="*60)
    
    try:
        from src.db.connectors import get_pg_pool
        settings = get_settings()
        
        print(f"Host: {settings.postgres_host}:{settings.postgres_port}")
        print(f"Database: {settings.postgres_db}")
        print(f"User: {settings.postgres_user}")
        
        pool = await get_pg_pool()
        
        # Test query
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT NOW()")
            print(f"\n✅ PostgreSQL Connected!")
            print(f"   Server Time: {result}")
            
            # Count tables
            tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            )
            print(f"   Tables Found: {len(tables)}")
            for table in tables:
                print(f"      - {table['table_name']}")
        
        return True
    
    except Exception as e:
        print(f"\n❌ PostgreSQL Connection Failed!")
        print(f"   Error: {type(e).__name__}: {e}")
        return False

def test_neo4j():
    """Test koneksi Neo4j."""
    print("\n" + "="*60)
    print("🔍 Testing Neo4j Connection")
    print("="*60)
    
    try:
        from src.db.connectors import get_neo4j_driver
        settings = get_settings()
        
        print(f"URI: {settings.neo4j_uri}")
        print(f"User: {settings.neo4j_user}")
        
        driver = get_neo4j_driver()
        
        # Test dengan simple query
        with driver.session() as session:
            result = session.run("RETURN 'Neo4j Connected!' as message").single()
            message = result['message']
            
            print(f"\n✅ Neo4j Connected!")
            print(f"   Response: {message}")
            
            # Check constraints
            constraints = session.run("SHOW CONSTRAINTS").data()
            print(f"   Constraints: {len(constraints)}")
            
            # Check indexes
            indexes = session.run("SHOW INDEXES").data()
            print(f"   Indexes: {len(indexes)}")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Neo4j Connection Failed!")
        print(f"   Error: {type(e).__name__}: {e}")
        return False

async def main():
    """Jalankan semua tests."""
    print("\n🚀 Database Connection Tests")
    print(f"   Mode: {get_settings().app_mode}")
    
    pg_ok = await test_postgres()
    neo_ok = test_neo4j()
    
    print("\n" + "="*60)
    print("📊 Summary")
    print("="*60)
    print(f"PostgreSQL: {'✅ OK' if pg_ok else '❌ FAILED'}")
    print(f"Neo4j:      {'✅ OK' if neo_ok else '❌ FAILED'}")
    
    if pg_ok and neo_ok:
        print("\n✨ All connections successful!")
        return 0
    else:
        print("\n⚠️  Some connections failed — check config & servers")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
