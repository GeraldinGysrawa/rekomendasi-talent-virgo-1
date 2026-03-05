"""
Modul CBF — Content-Based Filtering + Knowledge Graph (Increment 2)
====================================================================
Implementasi Tversky Similarity berbasis ontologi skill.

Formula Rodriguez & Egenhofer (2003) — adaptasi Tversky (1977) untuk ontologi:

    sim(a, b) = |F(a) ∩ F(b)| / (|F(a) ∩ F(b)| + α|F(a) \ F(b)| + (1-α)|F(b) \ F(a)|)

Dimana:
    F(x) = himpunan semua ancestor dari skill x via relasi IS_A dalam Knowledge Graph
    a    = skill yang dimiliki talent
    b    = skill yang dibutuhkan klien (dari NER)
    α    = parameter asimetri (dikalibrasi via konsultasi stakeholder)

Dua implementasi repository:
    1. Neo4jKnowledgeGraph   → production, query ancestor via Cypher traversal
    2. InMemoryKnowledgeGraph → development, menggunakan ontologi Python dict
"""

import os
import sys
from typing import Protocol, runtime_checkable

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))


# ─── Knowledge Graph Interface ────────────────────────────────────────────────

@runtime_checkable
class KnowledgeGraphRepository(Protocol):
    """
    Interface untuk Knowledge Graph.
    Bisa diimplementasikan dengan Neo4j (production) atau in-memory (development).
    """

    def get_ancestors(self, skill_name: str) -> set[str]:
        """
        Kembalikan himpunan semua ancestor dari skill dalam hierarki IS_A.
        Termasuk skill itu sendiri.

        Contoh (dari Neo4j):
            MATCH (s:Skill {name: 'React.js'})-[:IS_A*]->(ancestor)
            RETURN collect(ancestor.name)
            → {'JSFrameworkFrontend', 'FrontendSkill', 'SoftwareSkill', 'TechnicalSkill'}

        Plus skill itu sendiri:
            → {'React.js', 'JSFrameworkFrontend', 'FrontendSkill', 'SoftwareSkill', 'TechnicalSkill'}
        """
        ...

    def skill_exists(self, skill_name: str) -> bool:
        """Cek apakah skill ada dalam Knowledge Graph."""
        ...


# ─── In-Memory Knowledge Graph ───────────────────────────────────────────────

# Ontologi hierarkis: skill/class → [parent classes]
# Mencerminkan struktur IS_A di Neo4j
_ONTOLOGY: dict[str, list[str]] = {
    # Root
    "TechnicalSkill":       [],
    # Level 1
    "SoftwareSkill":        ["TechnicalSkill"],
    "DatabaseSkill":        ["TechnicalSkill"],
    "DevOpsSkill":          ["TechnicalSkill"],
    "MobileSkill":          ["TechnicalSkill"],
    # Level 2
    "FrontendSkill":        ["SoftwareSkill"],
    "BackendSkill":         ["SoftwareSkill"],
    "FullstackSkill":       ["SoftwareSkill"],
    # Level 3
    "JSFrameworkFrontend":  ["FrontendSkill"],
    "CSSFramework":         ["FrontendSkill"],
    "MarkupLanguage":       ["FrontendSkill"],
    "JSFrameworkBackend":   ["BackendSkill"],
    "PHPFramework":         ["BackendSkill"],
    "PythonFramework":      ["BackendSkill"],
    "JavaFramework":        ["BackendSkill"],
    "DotNetFramework":      ["BackendSkill"],
    "CrossPlatformMobile":  ["MobileSkill"],
    "NativeMobile":         ["MobileSkill"],
    # Leaf skills (konkret)
    "React.js":         ["JSFrameworkFrontend"],
    "Next.js":          ["JSFrameworkFrontend"],
    "Vue.js":           ["JSFrameworkFrontend"],
    "Angular":          ["JSFrameworkFrontend"],
    "Svelte":           ["JSFrameworkFrontend"],
    "Redux":            ["JSFrameworkFrontend"],
    "RxJS":             ["JSFrameworkFrontend"],
    "Tailwind CSS":     ["CSSFramework"],
    "Bootstrap":        ["CSSFramework"],
    "HTML":             ["MarkupLanguage"],
    "CSS":              ["MarkupLanguage"],
    "JavaScript":       ["FrontendSkill", "BackendSkill"],   # multi-parent
    "TypeScript":       ["FrontendSkill", "BackendSkill"],   # multi-parent
    "Node.js":          ["JSFrameworkBackend"],
    "Express.js":       ["JSFrameworkBackend"],
    "PHP":              ["BackendSkill"],
    "Laravel":          ["PHPFramework"],
    "CodeIgniter":      ["PHPFramework"],
    "Python":           ["BackendSkill"],
    "Django":           ["PythonFramework"],
    "Flask":            ["PythonFramework"],
    "FastAPI":          ["PythonFramework"],
    "Java":             ["BackendSkill"],
    "Spring Boot":      ["JavaFramework"],
    ".NET":             ["DotNetFramework"],
    "C#":               ["DotNetFramework"],
    "MySQL":            ["DatabaseSkill"],
    "PostgreSQL":       ["DatabaseSkill"],
    "SQL Server":       ["DatabaseSkill"],
    "MongoDB":          ["DatabaseSkill"],
    "Redis":            ["DatabaseSkill"],
    "Firebase":         ["DatabaseSkill"],
    "Flutter":          ["CrossPlatformMobile"],
    "Dart":             ["CrossPlatformMobile"],
    "React Native":     ["CrossPlatformMobile"],
    "Docker":           ["DevOpsSkill"],
    "Kubernetes":       ["DevOpsSkill"],
    "Kafka":            ["DevOpsSkill"],
    "REST API":         ["BackendSkill"],
    "Microservices":    ["BackendSkill"],
}


class InMemoryKnowledgeGraph:
    """
    Knowledge Graph in-memory untuk development (tanpa Neo4j).
    Mengimplementasikan KnowledgeGraphRepository protocol.
    """

    def get_ancestors(self, skill_name: str) -> set[str]:
        """
        Hitung semua ancestor secara rekursif melalui hierarki IS_A.
        Setara dengan query Cypher:
            MATCH (s)-[:IS_A*]->(ancestor) RETURN collect(ancestor.name)
        """
        if skill_name not in _ONTOLOGY:
            # Unknown skill: hanya memiliki dirinya sendiri
            return {skill_name}

        visited: set[str] = {skill_name}
        queue: list[str] = [skill_name]

        while queue:
            current = queue.pop(0)
            parents = _ONTOLOGY.get(current, [])
            for parent in parents:
                if parent not in visited:
                    visited.add(parent)
                    queue.append(parent)

        return visited

    def skill_exists(self, skill_name: str) -> bool:
        return skill_name in _ONTOLOGY


class Neo4jKnowledgeGraph:
    """
    Knowledge Graph menggunakan Neo4j — untuk production.
    Memerlukan neo4j driver dan koneksi aktif.

    Query Cypher yang digunakan:
        MATCH (s {name: $skill_name})-[:IS_A*0..]->(ancestor)
        RETURN collect(DISTINCT ancestor.name) AS ancestors
    """

    def __init__(self, driver):
        """
        Args:
            driver: neo4j.GraphDatabase.driver instance
        """
        self._driver = driver

    def get_ancestors(self, skill_name: str) -> set[str]:
        query = """
        MATCH (s)-[:IS_A*0..]->(ancestor)
        WHERE (s:Skill OR s:SkillClass) AND s.name = $skill_name
        RETURN collect(DISTINCT ancestor.name) AS ancestors
        """
        with self._driver.session() as session:
            result = session.run(query, skill_name=skill_name)
            record = result.single()
            if record and record["ancestors"]:
                ancestors = set(record["ancestors"])
                ancestors.add(skill_name)  # tambahkan diri sendiri
                return ancestors
            return {skill_name}

    def skill_exists(self, skill_name: str) -> bool:
        query = """
        MATCH (s) WHERE (s:Skill OR s:SkillClass) AND s.name = $skill_name
        RETURN count(s) > 0 AS exists
        """
        with self._driver.session() as session:
            result = session.run(query, skill_name=skill_name)
            record = result.single()
            return record["exists"] if record else False


# ─── Tversky Similarity ───────────────────────────────────────────────────────

def tversky_similarity(
    skill_talent: str,
    skill_required: str,
    graph: KnowledgeGraphRepository,
    alpha: float = 0.5,
) -> float:
    """
    Hitung Tversky Similarity antara dua skill dalam Knowledge Graph.

    Implementasi formula Rodriguez & Egenhofer (2003):
        sim(a, b) = |F(a) ∩ F(b)| / (|F(a) ∩ F(b)| + α|F(a)\F(b)| + (1-α)|F(b)\F(a)|)

    Args:
        skill_talent   : skill yang dimiliki talent (entitas a)
        skill_required : skill yang dibutuhkan klien dari NER (entitas b)
        graph          : Knowledge Graph repository (Neo4j atau in-memory)
        alpha          : parameter asimetri [0, 1]
                         Dalam konteks ini:
                         - α < 0.5 → penalti lebih besar jika talent tidak punya skill klien
                         - α = 0.5 → simetris (ekuivalen Dice Coefficient)
                         - α > 0.5 → penalti lebih besar jika talent punya skill berlebih
                         Default: 0.5 (akan dikalibrasi dari konsultasi stakeholder)

    Returns:
        float: skor kemiripan semantik ∈ [0.0, 1.0]
               1.0 = identik, 0.0 = tidak ada kesamaan ancestor sama sekali
    """
    F_a = graph.get_ancestors(skill_talent)    # ancestor skill talent
    F_b = graph.get_ancestors(skill_required)  # ancestor skill yang dibutuhkan

    intersection = len(F_a & F_b)             # |F(a) ∩ F(b)|
    only_a = len(F_a - F_b)                   # |F(a) \ F(b)|
    only_b = len(F_b - F_a)                   # |F(b) \ F(a)|

    denominator = intersection + alpha * only_a + (1 - alpha) * only_b

    if denominator == 0:
        return 0.0

    return round(intersection / denominator, 6)


# ─── Skill Set Similarity ─────────────────────────────────────────────────────

def compute_skill_score(
    talent_skills: list[str],
    required_skills: list[str],
    graph: KnowledgeGraphRepository,
    alpha: float = 0.5,
) -> dict:
    """
    Hitung skor skill keseluruhan antara skillset talent dan daftar skill yang dibutuhkan.

    Strategi:
      Untuk setiap required skill, cari best-match dari seluruh skill talent
      (similarity tertinggi). Agregasi: rata-rata best-match score semua required skill.

    Skor 0.0 jika required_skills kosong (tidak ada constraint skill dari query).
    Dalam kasus ini, SAW akan memperlakukan semua talent setara di kriteria skill.

    Args:
        talent_skills    : list skill yang dimiliki talent (dari PostgreSQL)
        required_skills  : list skill yang dibutuhkan klien (dari NER)
        graph            : Knowledge Graph repository
        alpha            : parameter Tversky

    Returns:
        dict: {
            "score"        : float [0,1] — skor agregat
            "detail"       : list per-skill breakdown
            "matched"      : int — jumlah required skill yang terpenuhi (score ≥ threshold)
            "coverage"     : float — rasio required skill yang terpenuhi
        }
    """
    MATCH_THRESHOLD = 0.30  # threshold minimum untuk dianggap "matched"

    if not required_skills:
        return {
            "score": 1.0,   # tidak ada constraint → semua talent lolos penuh
            "detail": [],
            "matched": 0,
            "coverage": 1.0,
        }

    details = []
    for req in required_skills:
        best_score = 0.0
        best_match = None

        for t_skill in talent_skills:
            score = tversky_similarity(t_skill, req, graph, alpha)
            if score > best_score:
                best_score = score
                best_match = t_skill

        details.append({
            "required":   req,
            "best_match": best_match,
            "score":      best_score,
            "matched":    best_score >= MATCH_THRESHOLD,
        })

    matched_count = sum(1 for d in details if d["matched"])
    avg_score = sum(d["score"] for d in details) / len(details)
    coverage = matched_count / len(required_skills)

    return {
        "score":    round(avg_score, 6),
        "detail":   details,
        "matched":  matched_count,
        "coverage": round(coverage, 4),
    }


# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    graph = InMemoryKnowledgeGraph()

    print("=== Ancestor Sets ===")
    for skill in ["React.js", "Vue.js", "Angular", "Laravel", "Python"]:
        ancestors = graph.get_ancestors(skill)
        print(f"  {skill:15s}: {ancestors}")

    print("\n=== Tversky Similarity (α=0.5) ===")
    pairs = [
        ("React.js", "React.js"),    # identik
        ("React.js", "Vue.js"),      # satu parent (JSFrameworkFrontend)
        ("React.js", "Angular"),     # satu parent (JSFrameworkFrontend)
        ("React.js", "Node.js"),     # JS family, beda layer
        ("React.js", "Laravel"),     # jauh
        ("Laravel",  "PHP"),         # parent-child
        ("Django",   "Flask"),       # satu parent (PythonFramework)
        ("React.js", "Docker"),      # sangat jauh
    ]
    for a, b in pairs:
        score = tversky_similarity(a, b, graph)
        print(f"  {a:15s} <-> {b:15s} : {score:.4f}")

    print("\n=== Skill Set Similarity ===")
    result = compute_skill_score(
        talent_skills=["React.js", "TypeScript", "Node.js"],
        required_skills=["Vue.js", "PHP"],
        graph=graph
    )
    print(f"  Score: {result['score']} | Coverage: {result['coverage']}")
    for d in result["detail"]:
        print(f"  {d['required']:10s} → {d['best_match']:15s} score={d['score']:.4f} matched={d['matched']}")
