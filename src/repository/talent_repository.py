"""
Repository Layer — Talent Data Access
=======================================
Switch otomatis antara PostgreSQL (real) dan in-memory (development).

Mode dikontrol dari APP_MODE di .env:
  inmemory → pakai _DUMMY_TALENTS, tanpa koneksi DB
  real     → query PostgreSQL via asyncpg pool
"""

import os, sys
from datetime import date
from dataclasses import dataclass, field
from typing import Optional
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))


# ─── Domain Model ──────────────────────────────────────────────────────────────

@dataclass
class TalentAvailability:
    status: str                          # 'available', 'on_project', 'unavailable'
    next_available_date: Optional[date]  # None = sudah available sekarang


@dataclass
class TalentProfile:
    """
    'Item model' dalam arsitektur CBF — berisi semua atribut 5 kriteria SAW.
    """
    id: int
    kode_talent: str
    nama: str
    pengalaman_tahun: float              # Kriteria 2
    lokasi: str                          # Kriteria 3
    skills: list[str] = field(default_factory=list)           # Kriteria 1
    preferensi_proyek: list[str] = field(default_factory=list) # Kriteria 4
    availability: Optional[TalentAvailability] = None         # Kriteria 5


# ─── Dummy Data (inmemory) ─────────────────────────────────────────────────────

# _DUMMY_TALENTS: list[TalentProfile] = [
#     TalentProfile(1,"T001","Andi Firmansyah", 3.0,"Bandung",
#         ["React.js","JavaScript","TypeScript","HTML","CSS"],
#         ["web","banking"], TalentAvailability("available",None)),
#     TalentProfile(2,"T002","Budi Santoso",    2.0,"Jakarta",
#         ["Vue.js","JavaScript","Node.js","Express.js"],
#         ["web","retail"], TalentAvailability("available",None)),
#     TalentProfile(3,"T003","Citra Dewi",      4.0,"Bandung",
#         ["Angular","TypeScript","RxJS","HTML","CSS"],
#         ["web","banking","enterprise"], TalentAvailability("on_project",date(2026,5,1))),
#     TalentProfile(4,"T004","Dimas Pratama",   2.0,"Bandung",
#         ["PHP","Laravel","MySQL","REST API"],
#         ["web","retail"], TalentAvailability("available",None)),
#     TalentProfile(5,"T005","Eka Rahayu",      5.0,"Jakarta",
#         [".NET","C#","SQL Server","REST API"],
#         ["banking","enterprise","erp"], TalentAvailability("available",None)),
#     TalentProfile(6,"T006","Fajar Nugroho",   3.0,"Bandung",
#         ["Python","Django","PostgreSQL","Docker"],
#         ["web","data"], TalentAvailability("on_project",date(2026,3,16))),
#     TalentProfile(7,"T007","Gina Permata",    1.0,"Surabaya",
#         ["React.js","Next.js","TypeScript","Tailwind CSS"],
#         ["web","startup"], TalentAvailability("available",None)),
#     TalentProfile(8,"T008","Hendra Wijaya",   6.0,"Jakarta",
#         ["Java","Spring Boot","Microservices","Kafka","Docker"],
#         ["banking","enterprise"], TalentAvailability("on_project",date(2026,7,1))),
#     TalentProfile(9,"T009","Indira Sari",     2.0,"Bandung",
#         ["Flutter","Dart","Firebase","REST API"],
#         ["mobile","startup"], TalentAvailability("available",None)),
#     TalentProfile(10,"T010","Joko Susilo",    3.0,"Jakarta",
#         ["React Native","JavaScript","Firebase","Redux"],
#         ["mobile","web"], TalentAvailability("on_project",date(2026,3,1))),
#     TalentProfile(11,"T011","Geraldin",       12.0,"Bandung",
#         ["React.js","JavaScript","TypeScript","Node.js","HTML","CSS"],
#         ["web","startup"], TalentAvailability("available",None)),
# ]


# ─── Repository ────────────────────────────────────────────────────────────────

class TalentRepository:

    def __init__(self, mode: str = "inmemory", pg_pool=None):
        self.mode = mode
        self._pool = pg_pool  # asyncpg pool, diset dari luar saat APP_MODE=real

    # ── Sync API (inmemory) ───────────────────────────────────────────────────

    def get_all(self) -> list[TalentProfile]:
        if self.mode == "inmemory":
            return list(_DUMMY_TALENTS)
        raise RuntimeError("Gunakan get_all_async() untuk mode 'real'")

    def get_by_kode(self, kode: str) -> Optional[TalentProfile]:
        if self.mode == "inmemory":
            return next((t for t in _DUMMY_TALENTS if t.kode_talent == kode), None)
        raise RuntimeError("Gunakan get_by_kode_async() untuk mode 'real'")

    # ── Async API (PostgreSQL) ────────────────────────────────────────────────

    async def get_all_async(self) -> list[TalentProfile]:
        """
        Query PostgreSQL — JOIN 4 tabel sekaligus untuk profil lengkap talent.

        Query terpisah untuk skills dan preferensi karena relasi 1-to-many:
        menggabungkan lewat GROUP BY + array_agg.
        """
        if self.mode == "inmemory":
            return self.get_all()

        pool = self._pool
        if pool is None:
            raise RuntimeError("pg_pool belum diset. Pastikan APP_MODE=real dan pool sudah diinisialisasi.")

        # Query utama: profil + availability
        rows = await pool.fetch("""
            SELECT
                t.id, t.kode_talent, t.nama,
                t.pengalaman_tahun, t.lokasi,
                ta.status,
                ta.next_available_date
            FROM talents t
            LEFT JOIN talent_availability ta ON ta.talent_id = t.id
            ORDER BY t.id
        """)

        if not rows:
            return []

        talent_ids = [r["id"] for r in rows]

        # Query skills (1-to-many)
        skill_rows = await pool.fetch("""
            SELECT talent_id, skill_name FROM talent_skills
            WHERE talent_id = ANY($1::int[])
        """, talent_ids)

        # Query preferensi (1-to-many)
        pref_rows = await pool.fetch("""
            SELECT talent_id, project_type FROM talent_project_preferences
            WHERE talent_id = ANY($1::int[])
        """, talent_ids)

        # Group by talent_id
        skills_map: dict[int, list[str]] = {}
        for sr in skill_rows:
            skills_map.setdefault(sr["talent_id"], []).append(sr["skill_name"])

        prefs_map: dict[int, list[str]] = {}
        for pr in pref_rows:
            prefs_map.setdefault(pr["talent_id"], []).append(pr["project_type"])

        # Assemble TalentProfile
        result = []
        for r in rows:
            tid = r["id"]
            avail = TalentAvailability(
                status=r["status"] or "available",
                next_available_date=r["next_available_date"],
            )
            result.append(TalentProfile(
                id=tid,
                kode_talent=r["kode_talent"],
                nama=r["nama"],
                pengalaman_tahun=float(r["pengalaman_tahun"]),
                lokasi=r["lokasi"],
                skills=skills_map.get(tid, []),
                preferensi_proyek=prefs_map.get(tid, []),
                availability=avail,
            ))
        return result

    async def get_by_kode_async(self, kode: str) -> Optional[TalentProfile]:
        if self.mode == "inmemory":
            return self.get_by_kode(kode)
        all_talents = await self.get_all_async()
        return next((t for t in all_talents if t.kode_talent == kode), None)
