"""
Repository Layer — PostgreSQL
==============================
Data access layer untuk mengambil profil talent dari PostgreSQL.
Memisahkan logika data dari logika bisnis (separation of concerns).

Dalam mode 'inmemory': menggunakan data dummy in-memory.
Dalam mode 'real': menggunakan asyncpg connection ke PostgreSQL.
"""

import json
import os
import sys
from datetime import date
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))


# ─── Domain Model ─────────────────────────────────────────────────────────────

@dataclass
class TalentAvailability:
    status: str                              # 'available', 'on_project', 'unavailable'
    next_available_date: Optional[date]      # None jika sudah available sekarang


@dataclass
class TalentProfile:
    """
    Merepresentasikan "item model" dalam arsitektur CBF (Lops et al., 2011).
    Berisi semua atribut yang digunakan oleh 5 kriteria SAW.
    """
    id: int
    kode_talent: str
    nama: str
    pengalaman_tahun: float                  # Kriteria 2: Pengalaman
    lokasi: str                              # Kriteria 3: Lokasi
    skills: list[str] = field(default_factory=list)          # Kriteria 1: Skill
    preferensi_proyek: list[str] = field(default_factory=list) # Kriteria 4: Preferensi
    availability: Optional[TalentAvailability] = None        # Kriteria 5: Ketersediaan


# ─── Dummy Data (in-memory) ───────────────────────────────────────────────────

_DUMMY_TALENTS: list[TalentProfile] = [
    TalentProfile(
        id=1, kode_talent="T001", nama="Andi Firmansyah",
        pengalaman_tahun=3.0, lokasi="Bandung",
        skills=["React.js", "JavaScript", "TypeScript", "HTML", "CSS"],
        preferensi_proyek=["web", "banking"],
        availability=TalentAvailability(status="available", next_available_date=None)
    ),
    TalentProfile(
        id=2, kode_talent="T002", nama="Budi Santoso",
        pengalaman_tahun=2.0, lokasi="Jakarta",
        skills=["Vue.js", "JavaScript", "Node.js", "Express.js"],
        preferensi_proyek=["web", "retail"],
        availability=TalentAvailability(status="available", next_available_date=None)
    ),
    TalentProfile(
        id=3, kode_talent="T003", nama="Citra Dewi",
        pengalaman_tahun=4.0, lokasi="Bandung",
        skills=["Angular", "TypeScript", "RxJS", "HTML", "CSS"],
        preferensi_proyek=["web", "banking", "enterprise"],
        availability=TalentAvailability(
            status="on_project",
            next_available_date=date(2026, 5, 1)
        )
    ),
    TalentProfile(
        id=4, kode_talent="T004", nama="Dimas Pratama",
        pengalaman_tahun=2.0, lokasi="Bandung",
        skills=["PHP", "Laravel", "MySQL", "REST API"],
        preferensi_proyek=["web", "retail"],
        availability=TalentAvailability(status="available", next_available_date=None)
    ),
    TalentProfile(
        id=5, kode_talent="T005", nama="Eka Rahayu",
        pengalaman_tahun=5.0, lokasi="Jakarta",
        skills=[".NET", "C#", "SQL Server", "REST API"],
        preferensi_proyek=["banking", "enterprise", "erp"],
        availability=TalentAvailability(status="available", next_available_date=None)
    ),
    TalentProfile(
        id=6, kode_talent="T006", nama="Fajar Nugroho",
        pengalaman_tahun=3.0, lokasi="Bandung",
        skills=["Python", "Django", "PostgreSQL", "Docker"],
        preferensi_proyek=["web", "data"],
        availability=TalentAvailability(
            status="on_project",
            next_available_date=date(2026, 3, 16)
        )
    ),
    TalentProfile(
        id=7, kode_talent="T007", nama="Gina Permata",
        pengalaman_tahun=1.0, lokasi="Surabaya",
        skills=["React.js", "Next.js", "TypeScript", "Tailwind CSS"],
        preferensi_proyek=["web", "startup"],
        availability=TalentAvailability(status="available", next_available_date=None)
    ),
    TalentProfile(
        id=8, kode_talent="T008", nama="Hendra Wijaya",
        pengalaman_tahun=6.0, lokasi="Jakarta",
        skills=["Java", "Spring Boot", "Microservices", "Kafka", "Docker"],
        preferensi_proyek=["banking", "enterprise", "microservices"],
        availability=TalentAvailability(
            status="on_project",
            next_available_date=date(2026, 7, 1)
        )
    ),
    TalentProfile(
        id=9, kode_talent="T009", nama="Indira Sari",
        pengalaman_tahun=2.0, lokasi="Bandung",
        skills=["Flutter", "Dart", "Firebase", "REST API"],
        preferensi_proyek=["mobile", "startup"],
        availability=TalentAvailability(status="available", next_available_date=None)
    ),
    TalentProfile(
        id=10, kode_talent="T010", nama="Joko Susilo",
        pengalaman_tahun=3.0, lokasi="Jakarta",
        skills=["React Native", "JavaScript", "Firebase", "Redux"],
        preferensi_proyek=["mobile", "web"],
        availability=TalentAvailability(
            status="on_project",
            next_available_date=date(2026, 3, 1)
        )
    ),
]


# ─── Repository Interface ─────────────────────────────────────────────────────

class TalentRepository:
    """
    Repository untuk mengakses data talent.
    Mode ditentukan dari settings (inmemory / real).
    """

    def __init__(self, mode: str = "inmemory"):
        self.mode = mode

    def get_all(self) -> list[TalentProfile]:
        """Ambil semua talent dengan profil lengkap (skill, preferensi, ketersediaan)."""
        if self.mode == "inmemory":
            return _DUMMY_TALENTS
        else:
            raise NotImplementedError(
                "Mode 'real' membutuhkan koneksi PostgreSQL. "
                "Implementasikan dengan asyncpg setelah DB siap."
            )

    def get_by_id(self, talent_id: int) -> Optional[TalentProfile]:
        if self.mode == "inmemory":
            return next((t for t in _DUMMY_TALENTS if t.id == talent_id), None)
        raise NotImplementedError

    def get_by_kode(self, kode: str) -> Optional[TalentProfile]:
        if self.mode == "inmemory":
            return next((t for t in _DUMMY_TALENTS if t.kode_talent == kode), None)
        raise NotImplementedError
