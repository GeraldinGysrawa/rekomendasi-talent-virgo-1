"""
Modul SAW — Simple Additive Weighting + Rank Order Centroid (Increment 3)
=========================================================================
Implementasi MCDM untuk meranking talent berdasarkan 5 kriteria.

ROC Weights (Barron & Barrett, 1996):
    w_i = (1/n) * Σ_{j=i}^{n} (1/j)
    Urutan kriteria dikonfigurasi via .env (hasil konsultasi stakeholder).

SAW (Taherdoost, 2023):
    Step 1: Buat decision matrix (nilai mentah per kriteria)
    Step 2: Normalisasi — semua kriteria BENEFIT: r_ij = x_ij / max(x_j)
    Step 3: Skor akhir: S_i = Σ_j (w_j * r_ij)
    Step 4: Ranking berdasarkan S_i descending

5 Kriteria (semua BENEFIT — semakin tinggi semakin baik):
    1. skill           : skor Sánchez dari CBF [0,1]
    2. pengalaman      : kesesuaian pengalaman dengan kebutuhan [0,1]
    3. lokasi          : kesesuaian lokasi [0,1]
    4. preferensi_proyek : kesesuaian tipe proyek [0,1]
    5. ketersediaan    : skor ketersediaan berbasis tanggal [0,1]
"""

import os
import sys
from datetime import date
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))
from config.settings import get_settings


# ─── ROC Weight Calculator ────────────────────────────────────────────────────

def compute_roc_weights(criteria_rank_order: list[str]) -> dict[str, float]:
    """
    Hitung bobot ROC dari urutan prioritas kriteria.

    Formula (Barron & Barrett, 1996):
        w_i = (1/n) * Σ_{j=i}^{n} (1/j)

    Args:
        criteria_rank_order: list kriteria diurutkan dari prioritas tertinggi ke terendah
                             (dari settings.criteria_rank_order)

    Returns:
        dict: {nama_kriteria: bobot}

    Contoh untuk n=5, urutan default:
        skill=0.4567, pengalaman=0.2567, lokasi=0.1567,
        preferensi_proyek=0.0900, ketersediaan=0.0400
    """
    n = len(criteria_rank_order)
    raw_weights = []

    for i in range(1, n + 1):
        w = (1 / n) * sum(1 / j for j in range(i, n + 1))
        raw_weights.append(w)

    # Normalisasi agar total = 1.0 persis
    total = sum(raw_weights)
    normalized = [w / total for w in raw_weights]

    return {
        criterion: round(weight, 6)
        for criterion, weight in zip(criteria_rank_order, normalized)
    }


# ─── Raw Score Calculators ────────────────────────────────────────────────────

def score_pengalaman(
    talent_tahun: float,
    required_min: Optional[float]
) -> float:
    """
    Normalisasi skor pengalaman (kriteria BENEFIT).

    Jika ada requirement minimum:
        - talent_tahun >= required_min → skor proporsional (max 1.0)
        - talent_tahun < required_min  → skor proporsional (< 1.0, bukan 0)
          karena talent mungkin masih layak dipertimbangkan

    Jika tidak ada requirement:
        - Normalisasi berdasarkan pengalaman relatif antar talent
          (diselesaikan saat normalisasi SAW dengan max)
        - Di sini: kembalikan nilai raw (tahun)
    """
    if required_min is None or required_min == 0:
        # Kembalikan nilai raw, SAW akan normalisasi terhadap max
        return float(talent_tahun)

    # Rasio terhadap requirement, capped di 1.0
    return min(talent_tahun / required_min, 1.0)


def score_lokasi(
    talent_lokasi: str,
    required_lokasi: Optional[str]
) -> float:
    """
    Normalisasi skor lokasi (kriteria BENEFIT).

    Skala:
        1.0 → lokasi persis cocok
        0.8 → remote / wfh (fleksibel)
        0.2 → tidak cocok (masih bisa dipertimbangkan)
        1.0 → tidak ada constraint (semua sama)
    """
    if required_lokasi is None:
        return 1.0

    req_lower = required_lokasi.lower()

    if req_lower in ("remote", "wfh", "work from home"):
        return 0.8  # semua talent bisa remote, tidak sempurna karena ada cost

    if talent_lokasi.lower() == req_lower:
        return 1.0

    return 0.2


def score_preferensi_proyek(
    talent_preferensi: list[str],
    required_project_type: Optional[str]
) -> float:
    """
    Normalisasi skor preferensi proyek (kriteria BENEFIT).

    Skala:
        1.0 → tipe proyek ada dalam preferensi talent
        0.3 → tidak ada preferensi yang cocok
        1.0 → tidak ada constraint tipe proyek dari query
    """
    if required_project_type is None:
        return 1.0

    req_lower = required_project_type.lower()
    if any(req_lower == p.lower() for p in talent_preferensi):
        return 1.0

    return 0.3


def score_ketersediaan(
    next_available_date: Optional[date],
    status: str,
    required_start_date: Optional[date]
) -> float:
    """
    Normalisasi skor ketersediaan berbasis tanggal (Pendekatan B).

    Logika:
        - Jika tidak ada start_date dari query → nilai berdasarkan status saja
        - Jika ada start_date:
            * talent already available (None) → skor 1.0
            * next_available_date <= required_start_date → skor 1.0
              (talent selesai proyek sebelum proyek baru mulai)
            * next_available_date > required_start_date → skor berdasarkan
              gap (semakin kecil gap, semakin baik)
              gap dihitung dalam hari, max penalty = 180 hari

    Args:
        next_available_date  : tanggal talent bisa mulai proyek baru (None = sudah available)
        status               : 'available', 'on_project', 'unavailable'
        required_start_date  : tanggal mulai proyek dari query user (None = tidak disebutkan)

    Returns:
        float [0.0, 1.0]
    """
    # Talent unavailable = tidak dipertimbangkan sama sekali
    if status == "unavailable":
        return 0.0

    # Tidak ada constraint tanggal → berdasarkan status saja
    if required_start_date is None:
        if status == "available":
            return 1.0
        elif status == "on_project":
            return 0.5
        return 0.0

    # Ada constraint tanggal
    if next_available_date is None:
        # Talent sudah available sekarang → perfect match
        return 1.0

    if next_available_date <= required_start_date:
        # Talent selesai proyek sebelum proyek baru mulai → bisa
        return 1.0

    # Talent belum available saat proyek dimulai → hitung gap
    gap_days = (next_available_date - required_start_date).days
    MAX_GAP_DAYS = 180  # 6 bulan = threshold maksimum yang masih masuk akal

    if gap_days >= MAX_GAP_DAYS:
        return 0.05  # sangat tidak ideal, tapi masih muncul di ranking

    # Linear decay: semakin kecil gap, semakin baik
    # gap=0 → 1.0, gap=MAX_GAP_DAYS → 0.05
    return round(1.0 - (gap_days / MAX_GAP_DAYS) * 0.95, 4)


# ─── Decision Matrix ─────────────────────────────────────────────────────────

@dataclass
class TalentSAWInput:
    """Input satu talent ke dalam SAW calculator."""
    talent_id: int
    kode_talent: str
    nama: str
    # Raw values untuk tiap kriteria
    skill_score: float                       # dari CBF Sánchez
    pengalaman_tahun: float                  # raw tahun dari DB
    lokasi: str                              # kota dari DB
    preferensi_proyek: list                  # list tipe proyek dari DB
    availability_status: str                 # status dari DB
    next_available_date: Optional[date]      # tanggal dari DB


@dataclass
class SAWResult:
    """Hasil akhir SAW untuk satu talent."""
    rank: int
    talent_id: int
    kode_talent: str
    nama: str
    final_score: float
    # Skor per kriteria (ternormalisasi, sebelum bobot)
    normalized_scores: dict[str, float]
    # Skor terbobot per kriteria
    weighted_scores: dict[str, float]
    # Bobot yang digunakan
    weights: dict[str, float]
    # Penjelasan eksplisit (explainability SAW)
    explanation: str


# ─── SAW Calculator ──────────────────────────────────────────────────────────

def calculate_saw(
    talents: list[TalentSAWInput],
    required_pengalaman: Optional[float],
    required_lokasi: Optional[str],
    required_project_type: Optional[str],
    required_start_date: Optional[date],
    criteria_rank_order: Optional[list[str]] = None,
) -> list[SAWResult]:
    """
    Hitung SAW untuk semua talent dan kembalikan ranking.

    Langkah implementasi (Taherdoost, 2023):
        1. Hitung nilai mentah (raw score) setiap kriteria per talent
        2. Normalisasi: r_ij = x_ij / max(x_j)  [semua kriteria BENEFIT]
        3. Hitung skor akhir: S_i = Σ_j (w_j * r_ij)
        4. Ranking descending berdasarkan S_i

    Args:
        talents              : list input talent dari pipeline
        required_pengalaman  : minimum tahun dari NER (None = tidak disebutkan)
        required_lokasi      : kota/mode dari NER (None = tidak disebutkan)
        required_project_type: tipe proyek dari NER (None = tidak disebutkan)
        required_start_date  : tanggal mulai dari NER (None = tidak disebutkan)
        criteria_rank_order  : urutan prioritas kriteria (dari settings jika None)

    Returns:
        list[SAWResult] terurut rank 1 = terbaik
    """
    if not talents:
        return []

    settings = get_settings()
    rank_order = criteria_rank_order or settings.criteria_rank_order
    weights = compute_roc_weights(rank_order)

    # ── Step 1: Hitung raw score per kriteria ─────────────────────────────────
    raw: list[dict[str, float]] = []
    for t in talents:
        raw.append({
            "skill": t.skill_score,
            "pengalaman": score_pengalaman(t.pengalaman_tahun, required_pengalaman),
            "lokasi": score_lokasi(t.lokasi, required_lokasi),
            "preferensi_proyek": score_preferensi_proyek(t.preferensi_proyek, required_project_type),
            "ketersediaan": score_ketersediaan(
                t.next_available_date,
                t.availability_status,
                required_start_date
            ),
        })

    # ── Step 2: Normalisasi SAW (benefit: r_ij = x_ij / max_j) ──────────────
    criteria = list(weights.keys())
    max_vals = {
        c: max((r[c] for r in raw), default=1.0) or 1.0
        for c in criteria
    }

    normalized: list[dict[str, float]] = [
        {c: round(r[c] / max_vals[c], 6) for c in criteria}
        for r in raw
    ]

    # ── Step 3 & 4: Hitung S_i dan ranking ───────────────────────────────────
    results: list[SAWResult] = []
    for t, norm in zip(talents, normalized):
        weighted = {c: round(norm[c] * weights[c], 6) for c in criteria}
        final = round(sum(weighted.values()), 6)

        # Penjelasan eksplisit untuk setiap talent (explainability)
        explanation = " | ".join(
            f"{c}={norm[c]:.3f}×{weights[c]:.4f}={weighted[c]:.4f}"
            for c in criteria
        )

        results.append(SAWResult(
            rank=0,  # diisi setelah sorting
            talent_id=t.talent_id,
            kode_talent=t.kode_talent,
            nama=t.nama,
            final_score=final,
            normalized_scores=norm,
            weighted_scores=weighted,
            weights=weights,
            explanation=explanation,
        ))

    results.sort(key=lambda r: r.final_score, reverse=True)
    for idx, r in enumerate(results, start=1):
        r.rank = idx

    return results


# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from config.settings import Settings

    settings = Settings()
    rank_order = settings.criteria_rank_order
    weights = compute_roc_weights(rank_order)

    print("=== ROC Weights ===")
    for c, w in weights.items():
        print(f"  {c:20s}: {w:.6f}")
    print(f"  {'TOTAL':20s}: {sum(weights.values()):.6f}")

    print("\n=== Score Ketersediaan (Pendekatan B) ===")
    target = date(2026, 3, 20)
    test_cases = [
        (None,           "available",  "Sudah available"),
        (date(2026,3,1), "on_project", "Selesai 1 Mar, proyek 20 Mar → OK"),
        (date(2026,5,1), "on_project", "Selesai 1 Mei, gap 40 hari"),
        (date(2026,7,1), "on_project", "Selesai 1 Jul, gap 102 hari"),
        (None,           "unavailable","Tidak tersedia"),
    ]
    for avail_date, status, desc in test_cases:
        score = score_ketersediaan(avail_date, status, target)
        print(f"  {desc:45s}: {score:.4f}")

    print("\n=== SAW Ranking Test ===")
    inputs = [
        TalentSAWInput(1,"T001","Andi",  0.85, 3.0, "Bandung",  ["web","banking"],    "available",  None),
        TalentSAWInput(2,"T002","Budi",  0.60, 2.0, "Jakarta",  ["web","retail"],     "available",  None),
        TalentSAWInput(3,"T003","Citra", 0.90, 4.0, "Bandung",  ["web","banking"],    "on_project", date(2026,5,1)),
        TalentSAWInput(6,"T006","Fajar", 0.40, 3.0, "Bandung",  ["web","data"],       "on_project", date(2026,3,16)),
    ]
    results = calculate_saw(
        inputs,
        required_pengalaman=2.0,
        required_lokasi="Bandung",
        required_project_type="banking",
        required_start_date=date(2026, 3, 20),
    )
    print(f"\n{'Rank':<5} {'Nama':<10} {'Score':<10}")
    print("-" * 60)
    for r in results:
        print(f"  {r.rank:<4} {r.nama:<10} {r.final_score:<10.6f}")
        print(f"       {r.explanation}")
