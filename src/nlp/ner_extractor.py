"""
Modul NLP — Named Entity Recognition (Increment 1)
====================================================
Mengekstrak 5 entitas dari query natural pengguna:

  1. SKILL           → skill teknis yang dibutuhkan klien
  2. EXPERIENCE      → minimum pengalaman kerja (dalam tahun)
  3. LOCATION        → lokasi penempatan yang dibutuhkan
  4. PROJECT_TYPE    → tipe proyek yang dibutuhkan klien
  5. START_DATE      → tanggal mulai proyek yang direncanakan

Catatan arsitektur CBF (Lops et al., 2011):
  - Query user merupakan "user model" (kebutuhan klien)
  - Profil talent di DB merupakan "item model"
  - Kelima entitas ini adalah representasi user model
    yang akan dicocokkan dengan item model di tahap filtering

Pendekatan: Hybrid rule-based + statistical (Bharathi et al., 2023)
  - EntityRuler (gazetteer) untuk SKILL & PROJECT_TYPE
    yang memiliki pola leksikal konsisten
  - Regex untuk EXPERIENCE (numerik + kata kunci)
  - Regex + dateutil untuk START_DATE
  - EntityRuler (gazetteer) + regex untuk LOCATION
"""

import re
import sys
import os
from datetime import date, datetime
from typing import Optional
from dataclasses import dataclass, field
from dateutil import parser as dateutil_parser

try:
    import spacy
    from spacy.language import Language
    _SPACY_AVAILABLE = True
except ImportError:
    _SPACY_AVAILABLE = False

# Tambahkan root ke path agar bisa import config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))


# ─── Hasil Ekstraksi NER ─────────────────────────────────────────────────────

@dataclass
class NERResult:
    """
    Hasil ekstraksi NER dari satu query pengguna.
    Merepresentasikan "user model" dalam arsitektur CBF.

    Atribut:
        skills          : daftar skill teknis yang dibutuhkan
        pengalaman_min  : minimum pengalaman kerja dalam tahun (None = tidak disebutkan)
        level           : level seniority jika disebutkan ('junior'/'mid'/'senior')
        lokasi          : kota/mode lokasi penempatan (None = tidak disebutkan)
        project_type    : tipe proyek yang dibutuhkan (None = tidak disebutkan)
        start_date      : tanggal mulai proyek (None = tidak disebutkan)
        raw_query       : query asli sebelum diproses
    """
    skills: list[str] = field(default_factory=list)
    pengalaman_min: Optional[float] = None
    level: Optional[str] = None
    lokasi: Optional[str] = None
    project_type: Optional[str] = None
    start_date: Optional[date] = None
    raw_query: str = ""


# ─── Gazetteer: SKILL ─────────────────────────────────────────────────────────
# Daftar skill yang dikenali sistem — harus sinkron dengan node di Neo4j

SKILL_GAZETTEER: dict[str, str] = {
    # alias (lowercase) -> nama kanonik (sesuai Neo4j)
    "react.js": "React.js", "react":         "React.js",
    "next.js":  "Next.js",  "next":          "Next.js",
    "vue.js":   "Vue.js",   "vue":           "Vue.js",   "vuejs": "Vue.js",
    "angular":  "Angular",
    "svelte":   "Svelte",
    "redux":    "Redux",
    "rxjs":     "RxJS",
    "tailwind css": "Tailwind CSS", "tailwind": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "html":     "HTML",
    "css":      "CSS",
    "javascript": "JavaScript", "js": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript",
    "node.js":  "Node.js",   "node":         "Node.js",
    "express.js":"Express.js","express":     "Express.js",
    "php":      "PHP",
    "laravel":  "Laravel",
    "codeigniter": "CodeIgniter", "ci": "CodeIgniter",
    "python":   "Python",
    "django":   "Django",
    "flask":    "Flask",
    "fastapi":  "FastAPI",
    "java":     "Java",
    "spring boot": "Spring Boot", "spring": "Spring Boot",
    ".net":     ".NET",      "dotnet": ".NET",
    "c#":       "C#",        "csharp": "C#",
    "mysql":    "MySQL",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "sql server": "SQL Server",
    "mongodb":  "MongoDB",   "mongo": "MongoDB",
    "redis":    "Redis",
    "firebase": "Firebase",
    "flutter":  "Flutter",
    "dart":     "Dart",
    "react native": "React Native",
    "docker":   "Docker",
    "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "kafka":    "Kafka",
    "rest api": "REST API",  "restful": "REST API", "rest": "REST API",
    "microservices": "Microservices",
    "geraldin" : "Gerald",
}

# ─── Gazetteer: PROJECT_TYPE ──────────────────────────────────────────────────
# Kata kunci tipe proyek → nama kanonik
# Diisi dari domain bisnis PT Padepokan Tujuh Sembilan
# (akan diperbarui setelah konsultasi stakeholder)

PROJECT_TYPE_GAZETTEER: dict[str, str] = {
    # Banking & Finance
    "bank":         "banking", "banking":      "banking",
    "perbankan":    "banking", "fintech":       "banking",
    "keuangan":     "banking", "finance":       "banking",
    # Enterprise
    "enterprise":   "enterprise", "perusahaan": "enterprise",
    "erp":          "erp",         "sap":        "erp",
    # E-commerce & Retail
    "ecommerce":    "retail",  "e-commerce":    "retail",
    "retail":       "retail",  "marketplace":   "retail",
    "toko":         "retail",  "belanja":        "retail",
    # Web
    "web":          "web",     "website":       "web",
    "portal":       "web",
    # Mobile
    "mobile":       "mobile",  "android":       "mobile",
    "ios":          "mobile",  "aplikasi":      "mobile",
    # Data & AI
    "data":         "data",    "ai":            "data",
    "machine learning": "data", "ml":           "data",
    "analitik":     "data",    "analytics":     "data",
    # Startup
    "startup":      "startup",
}

# ─── Kota yang Dikenali ───────────────────────────────────────────────────────

LOCATION_GAZETTEER: dict[str, str] = {
    "bandung":   "Bandung",   "jakarta":    "Jakarta",
    "surabaya":  "Surabaya",  "yogyakarta": "Yogyakarta",
    "jogja":     "Yogyakarta","semarang":   "Semarang",
    "medan":     "Medan",     "bali":       "Bali",
    "denpasar":  "Bali",      "makassar":   "Makassar",
    "remote":    "remote",    "wfh":        "remote",
    "work from home": "remote",
    "on-site":   "on-site",   "onsite":     "on-site",
}

# ─── Level Keywords ───────────────────────────────────────────────────────────

LEVEL_KEYWORDS: dict[str, list[str]] = {
    "junior": ["junior", "fresh", "fresher", "entry", "pemula", "baru"],
    "mid":    ["mid", "middle", "menengah", "intermediate"],
    "senior": ["senior", "sr.", "sr ", "expert", "ahli", "berpengalaman"],
}


# ─── spaCy Pipeline ───────────────────────────────────────────────────────────

def _build_spacy_pipeline():
    """
    Bangun pipeline spaCy dengan EntityRuler untuk SKILL, PROJECT_TYPE, LOCATION.
    Menggunakan blank pipeline karena domain sangat teknis dan spesifik —
    model pretrained Indonesia umum tidak mengenal istilah seperti 'React.js'.
    """
    if not _SPACY_AVAILABLE:
        return None

    try:
        nlp = spacy.load("id_core_news_sm")
    except OSError:
        nlp = spacy.blank("id")

    ruler = nlp.add_pipe(
        "entity_ruler",
        before="ner" if "ner" in nlp.pipe_names else None,
        config={"overwrite_ents": True}
    )

    patterns = []

    # ── SKILL patterns ────────────────────────────────────────────────────────
    for alias, canonical in SKILL_GAZETTEER.items():
        # Pattern token-level untuk menangani multi-word
        tokens = alias.split()
        if len(tokens) == 1:
            patterns.append({
                "label": "SKILL",
                "pattern": [{"LOWER": alias}],
                "id": canonical
            })
        else:
            patterns.append({
                "label": "SKILL",
                "pattern": [{"LOWER": t} for t in tokens],
                "id": canonical
            })

    # ── PROJECT_TYPE patterns ─────────────────────────────────────────────────
    for keyword, canonical in PROJECT_TYPE_GAZETTEER.items():
        tokens = keyword.split()
        patterns.append({
            "label": "PROJECT_TYPE",
            "pattern": [{"LOWER": t} for t in tokens],
            "id": canonical
        })

    # ── LOCATION patterns ─────────────────────────────────────────────────────
    for keyword, canonical in LOCATION_GAZETTEER.items():
        tokens = keyword.split()
        patterns.append({
            "label": "LOCATION",
            "pattern": [{"LOWER": t} for t in tokens],
            "id": canonical
        })

    ruler.add_patterns(patterns)
    return nlp


_nlp_instance = None

def _get_nlp():
    global _nlp_instance
    if _nlp_instance is None:
        _nlp_instance = _build_spacy_pipeline()
    return _nlp_instance


# ─── Regex Extractors ─────────────────────────────────────────────────────────

def _extract_experience(text: str) -> tuple[Optional[float], Optional[str]]:
    """
    Ekstrak pengalaman minimum dari teks.

    Pola yang ditangani:
      "pengalaman diatas 2 tahun"  → (2.0, None)
      "minimal 3 tahun"            → (3.0, None)
      "lebih dari 4 tahun"         → (4.0, None)
      "18 bulan pengalaman"        → (1.5, None)
      "senior developer"           → (None, 'senior')
      "mid 3 tahun"                → (3.0, 'mid')

    Returns:
        (pengalaman_tahun, level)
    """
    text_lower = text.lower()

    # Tahun — termasuk kata kunci "diatas", "minimal", "lebih dari"
    year_match = re.search(
        r'(?:diatas|minimal|minimum|lebih\s+dari|>)?\s*(\d+(?:[.,]\d+)?)\s*(?:tahun|thn|year|yr)',
        text_lower
    )
    tahun = None
    if year_match:
        tahun = float(year_match.group(1).replace(",", "."))

    # Bulan → konversi ke tahun
    month_match = re.search(
        r'(\d+)\s*(?:bulan|bln|month)',
        text_lower
    )
    if month_match and tahun is None:
        tahun = round(int(month_match.group(1)) / 12, 1)

    # Level
    level = None
    for lvl, keywords in LEVEL_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            level = lvl
            break

    return tahun, level


def _extract_start_date(text: str) -> Optional[date]:
    """
    Ekstrak tanggal mulai proyek dari teks.

    Pola yang ditangani (Bahasa Indonesia & Inggris):
      "20 Maret 2026"
      "20 March 2026"
      "pada tanggal 1 April 2026"
      "dimulai 15 Februari 2026"
      "mulai dari 20 Maret 2026"

    Menggunakan dateutil.parser dengan tambahan locale Indonesia.
    Hanya mengambil tanggal PERTAMA yang ditemukan (start date).

    Returns:
        date object atau None jika tidak ditemukan
    """
    # Map bulan Indonesia → Inggris untuk dateutil
    BULAN_ID_EN = {
        "januari": "january", "februari": "february", "maret": "march",
        "april": "april",     "mei": "may",            "juni": "june",
        "juli": "july",       "agustus": "august",     "september": "september",
        "oktober": "october", "november": "november",  "desember": "december",
    }

    text_normalized = text.lower()
    for id_month, en_month in BULAN_ID_EN.items():
        text_normalized = text_normalized.replace(id_month, en_month)

    # Cari pola tanggal: angka + bulan + tahun
    date_pattern = re.search(
        r'\b(\d{1,2})\s+'
        r'(january|february|march|april|may|june|july|august|september|october|november|december)'
        r'\s+(\d{4})\b',
        text_normalized
    )

    if date_pattern:
        try:
            date_str = f"{date_pattern.group(1)} {date_pattern.group(2)} {date_pattern.group(3)}"
            return dateutil_parser.parse(date_str).date()
        except (ValueError, OverflowError):
            pass

    # Fallback: cari format DD/MM/YYYY atau YYYY-MM-DD
    iso_pattern = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', text)
    if iso_pattern:
        try:
            return date(
                int(iso_pattern.group(1)),
                int(iso_pattern.group(2)),
                int(iso_pattern.group(3))
            )
        except ValueError:
            pass

    slash_pattern = re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', text)
    if slash_pattern:
        try:
            return date(
                int(slash_pattern.group(3)),
                int(slash_pattern.group(2)),
                int(slash_pattern.group(1))
            )
        except ValueError:
            pass

    return None


def _regex_fallback_extract(text: str) -> tuple[list[str], Optional[str], Optional[str]]:
    """
    Fallback extractor tanpa spaCy — digunakan jika spaCy tidak terinstall.
    Menggunakan substring matching dari gazetteer.

    Returns:
        (skills, lokasi, project_type)
    """
    text_lower = text.lower()
    skills: list[str] = []
    lokasi: Optional[str] = None
    project_type: Optional[str] = None

    # Cari skill dari panjang terpanjang dulu (greedy matching)
    sorted_skills = sorted(SKILL_GAZETTEER.keys(), key=len, reverse=True)
    matched_spans: list[tuple[int, int]] = []

    for alias in sorted_skills:
        idx = text_lower.find(alias)
        if idx == -1:
            continue
        end = idx + len(alias)
        # Cek overlap dengan span yang sudah di-match
        overlap = any(
            not (end <= s or idx >= e)
            for s, e in matched_spans
        )
        if not overlap:
            canonical = SKILL_GAZETTEER[alias]
            if canonical not in skills:
                skills.append(canonical)
            matched_spans.append((idx, end))

    # Cari lokasi
    for keyword, canonical in LOCATION_GAZETTEER.items():
        if keyword in text_lower:
            lokasi = canonical
            break

    # Cari project type (terpanjang dulu)
    sorted_proj = sorted(PROJECT_TYPE_GAZETTEER.keys(), key=len, reverse=True)
    for keyword in sorted_proj:
        if keyword in text_lower:
            project_type = PROJECT_TYPE_GAZETTEER[keyword]
            break

    return skills, lokasi, project_type


# ─── Main Extractor ───────────────────────────────────────────────────────────

def extract_entities(query: str) -> NERResult:
    """
    Pipeline utama NER.

    Berperan sebagai "Content Analyzer" dalam arsitektur CBF (Lops et al., 2011):
    mengubah teks tidak terstruktur menjadi representasi terstruktur
    yang bisa diproses secara komputasi oleh komponen CBF & SAW.

    Args:
        query : kalimat natural dari pengguna (via chatbot Telegram / API)

    Returns:
        NERResult berisi 5 entitas yang diekstrak

    Contoh:
        Input : "saya butuh frontend React.js, pengalaman diatas 2 tahun,
                 pengerjaan di Bandung, proyek BANK,
                 mulai 20 Maret 2026 hingga 20 Desember 2026"
        Output: NERResult(
                    skills=['React.js'],
                    pengalaman_min=2.0,
                    level=None,
                    lokasi='Bandung',
                    project_type='banking',
                    start_date=date(2026, 3, 20)
                )
    """
    result = NERResult(raw_query=query)

    # ── Ekstrak experience & level (regex, selalu dipakai) ────────────────────
    result.pengalaman_min, result.level = _extract_experience(query)

    # ── Ekstrak start_date (regex + dateutil, selalu dipakai) ────────────────
    result.start_date = _extract_start_date(query)

    # ── Ekstrak skill, lokasi, project_type ───────────────────────────────────
    nlp = _get_nlp()

    if nlp is not None:
        # Gunakan spaCy EntityRuler
        doc = nlp(query)
        seen_skills: list[str] = []

        for ent in doc.ents:
            if ent.label_ == "SKILL":
                canonical = ent.ent_id_ if ent.ent_id_ else ent.text
                if canonical not in seen_skills:
                    seen_skills.append(canonical)
            elif ent.label_ == "LOCATION" and result.lokasi is None:
                result.lokasi = ent.ent_id_ if ent.ent_id_ else ent.text.title()
            elif ent.label_ == "PROJECT_TYPE" and result.project_type is None:
                result.project_type = ent.ent_id_ if ent.ent_id_ else ent.text.lower()

        result.skills = seen_skills

    else:
        # Fallback regex-based
        skills, lokasi, project_type = _regex_fallback_extract(query)
        result.skills = skills
        result.lokasi = lokasi
        result.project_type = project_type

    return result


# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_queries = [
        # Query lengkap seperti contoh di diskusi
        "saya butuh front end, dengan kemampuan react dengan pengalaman diatas 2 tahun, "
        "pengerjaan di Bandung dan mengerjakan proyek BANK, "
        "proyek akan di kerjakan pada 20 Maret 2026 hingga 20 Desember 2026",

        # Query singkat
        "cari senior backend Java Spring Boot, minimal 4 tahun, Jakarta",

        # Query dengan proyek mobile
        "butuh Flutter developer mid level untuk proyek mobile banking",

        # Query tanpa tanggal
        "programmer frontend React.js TypeScript, 2 tahun, Bandung, web",
    ]

    for q in test_queries:
        r = extract_entities(q)
        print(f"\nQuery      : {q[:80]}...")
        print(f"Skills     : {r.skills}")
        print(f"Exp Min    : {r.pengalaman_min} thn | Level: {r.level}")
        print(f"Lokasi     : {r.lokasi}")
        print(f"Proj Type  : {r.project_type}")
        print(f"Start Date : {r.start_date}")
