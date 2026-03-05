"""
Tests — Modul NLP (Increment 1, Blackbox Testing)
Pengujian fungsional NER sesuai proposal.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
from datetime import date
from src.nlp.ner_extractor import extract_entities

class TestSkillExtraction:
    def test_single_skill(self):
        r = extract_entities("cari programmer React.js")
        assert "React.js" in r.skills

    def test_alias_normalization(self):
        r = extract_entities("butuh developer react")
        assert "React.js" in r.skills

    def test_multiple_skills(self):
        r = extract_entities("butuh developer React.js dan PHP Laravel")
        assert len(r.skills) >= 2

    def test_no_skill(self):
        r = extract_entities("halo ada tidak programmer tersedia")
        assert isinstance(r.skills, list)

class TestExperienceExtraction:
    def test_year_basic(self):
        assert extract_entities("pengalaman 2 tahun").pengalaman_min == 2.0

    def test_year_with_diatas(self):
        assert extract_entities("pengalaman diatas 2 tahun").pengalaman_min == 2.0

    def test_year_with_minimal(self):
        assert extract_entities("minimal 3 tahun").pengalaman_min == 3.0

    def test_month_conversion(self):
        r = extract_entities("pengalaman 18 bulan")
        assert r.pengalaman_min == 1.5

    def test_no_experience(self):
        assert extract_entities("cari React.js developer").pengalaman_min is None

    def test_level_senior(self):
        assert extract_entities("senior backend developer").level == "senior"

    def test_level_junior(self):
        assert extract_entities("fresh graduate programmer").level == "junior"

    def test_level_mid(self):
        assert extract_entities("mid level programmer").level == "mid"

class TestLocationExtraction:
    def test_bandung(self):
        r = extract_entities("developer lokasi Bandung")
        assert r.lokasi == "Bandung"

    def test_jakarta(self):
        r = extract_entities("talent Jakarta")
        assert r.lokasi == "Jakarta"

    def test_remote(self):
        r = extract_entities("posisi remote WFH")
        assert r.lokasi == "remote"

    def test_no_location(self):
        assert extract_entities("cari programmer Python").lokasi is None

class TestProjectTypeExtraction:
    def test_bank(self):
        r = extract_entities("proyek BANK fintech")
        assert r.project_type == "banking"

    def test_perbankan(self):
        r = extract_entities("mengerjakan proyek perbankan")
        assert r.project_type == "banking"

    def test_mobile(self):
        r = extract_entities("pengembangan aplikasi mobile android")
        assert r.project_type == "mobile"

    def test_no_project_type(self):
        r = extract_entities("cari programmer React.js")
        assert r.project_type is None

class TestStartDateExtraction:
    def test_indonesian_date(self):
        r = extract_entities("mulai 20 Maret 2026")
        assert r.start_date == date(2026, 3, 20)

    def test_full_query_date(self):
        r = extract_entities(
            "proyek akan dikerjakan pada 20 Maret 2026 hingga 20 Desember 2026"
        )
        # Hanya start date yang diambil (tanggal pertama)
        assert r.start_date == date(2026, 3, 20)

    def test_no_date(self):
        r = extract_entities("cari React.js developer Bandung")
        assert r.start_date is None

class TestFullQuery:
    def test_complete_query_from_discussion(self):
        """Test dengan query persis dari diskusi proposal."""
        r = extract_entities(
            "saya butuh front end, dengan kemampuan react dengan pengalaman diatas 2 tahun, "
            "pengerjaan di Bandung dan mengerjakan proyek BANK, "
            "proyek akan di kerjakan pada 20 Maret 2026 hingga 20 Desember 2026"
        )
        assert "React.js" in r.skills
        assert r.pengalaman_min == 2.0
        assert r.lokasi == "Bandung"
        assert r.project_type == "banking"
        assert r.start_date == date(2026, 3, 20)

    def test_raw_query_preserved(self):
        q = "cari senior Java developer"
        assert extract_entities(q).raw_query == q
