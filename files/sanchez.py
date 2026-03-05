"""
Modul CBF — Sánchez et al. (2011/2012) Intrinsic IC + Semantic Similarity
==========================================================================

Formula IC Intrinsik (Sánchez, Batet & Isern, 2011):
------------------------------------------------------
  IC(c) = -log( (|leaves(c)| / |ancestors(c)|) + 1 / (|max_leaves| + 1) )

  Di mana:
    leaves(c)    = semua leaf node (skill konkret) yang merupakan descendant c,
                   termasuk c sendiri jika c adalah leaf
    ancestors(c) = semua ancestor c via IS_A, termasuk c sendiri
    max_leaves   = total leaf node di seluruh ontologi

  Intuisi:
    - Skill spesifik (sedikit leaves)  → IC tinggi   (informatif)
    - Skill abstrak  (banyak leaves)   → IC rendah   (general)

Formula Similarity (Lin, 1998 dengan IC model Sánchez):
--------------------------------------------------------
  sim(a, b) = 2 × IC(LCS(a,b)) / (IC(a) + IC(b))

  Di mana LCS (Least Common Subsumer) = ancestor bersama dengan IC tertinggi
  (paling spesifik di antara semua common ancestor)

  Rentang hasil: [0.0, 1.0]
    1.0 = identik
    0.0 = tidak ada common ancestor (selain root)

Dua implementasi KnowledgeGraphRepository:
  - InMemoryKnowledgeGraph  : development, tanpa Neo4j
  - Neo4jKnowledgeGraph     : production, query Cypher langsung ke Neo4j

Referensi:
  Sánchez, D., Batet, M., & Isern, D. (2011). Ontology-based information
    content computation. Knowledge-Based Systems, 24(2), 297–303.
  Sánchez, D., & Batet, M. (2012). A new model to compute the information
    content of concepts from taxonomic knowledge. IJSWIS, 8(2), 34–50.
  Lin, D. (1998). An information-theoretic definition of similarity. ICML.
"""

import math
import os, sys
from typing import Optional
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))


# ─── Ontologi In-Memory ────────────────────────────────────────────────────────
# Struktur: { node_name: [parent, ...] }
# Harus sinkron dengan data/cypher/ontology_setup.cypher

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
    # Leaf: skill konkret
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
    "JavaScript":       ["FrontendSkill", "BackendSkill"],
    "TypeScript":       ["FrontendSkill", "BackendSkill"],
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


# ─── Interface Protocol ────────────────────────────────────────────────────────

class KnowledgeGraphRepository:
    """Interface untuk KG — diimplementasi InMemory atau Neo4j."""

    def get_ancestors(self, node: str) -> set[str]:
        """Semua ancestor node via IS_A (inklusif diri sendiri)."""
        raise NotImplementedError

    def get_leaves(self, node: str) -> set[str]:
        """Semua leaf node (skill konkret) yang merupakan descendant node."""
        raise NotImplementedError

    def get_all_leaves(self) -> set[str]:
        """Semua leaf node di seluruh ontologi."""
        raise NotImplementedError

    def node_exists(self, node: str) -> bool:
        raise NotImplementedError


# ─── In-Memory Knowledge Graph ────────────────────────────────────────────────

class InMemoryKnowledgeGraph(KnowledgeGraphRepository):
    """
    KG in-memory untuk development (tanpa Neo4j).
    Dibangun dari _ONTOLOGY dict saat inisialisasi.
    """

    def __init__(self, ontology: dict[str, list[str]] = None):
        self._onto = ontology or _ONTOLOGY
        # Bangun reverse map: parent → set(children)
        self._children: dict[str, set[str]] = {k: set() for k in self._onto}
        for node, parents in self._onto.items():
            for parent in parents:
                if parent in self._children:
                    self._children[parent].add(node)
        # Cache
        self._ancestor_cache: dict[str, set[str]] = {}
        self._leaf_cache: dict[str, set[str]] = {}
        self._all_leaves: Optional[set[str]] = None

    def get_ancestors(self, node: str) -> set[str]:
        if node in self._ancestor_cache:
            return self._ancestor_cache[node]
        if node not in self._onto:
            result = {node}
            self._ancestor_cache[node] = result
            return result
        visited = {node}
        queue = list(self._onto.get(node, []))
        while queue:
            cur = queue.pop(0)
            if cur not in visited:
                visited.add(cur)
                queue.extend(self._onto.get(cur, []))
        self._ancestor_cache[node] = visited
        return visited

    def get_leaves(self, node: str) -> set[str]:
        """Semua leaf descendant dari node (inklusif jika node sendiri leaf)."""
        if node in self._leaf_cache:
            return self._leaf_cache[node]
        all_leaves = self.get_all_leaves()
        # BFS ke bawah
        visited = set()
        queue = [node]
        while queue:
            cur = queue.pop(0)
            if cur not in visited:
                visited.add(cur)
                queue.extend(self._children.get(cur, []))
        result = visited & all_leaves
        self._leaf_cache[node] = result
        return result

    def get_all_leaves(self) -> set[str]:
        if self._all_leaves is not None:
            return self._all_leaves
        # Leaf = node yang tidak punya children
        self._all_leaves = {n for n in self._onto if not self._children.get(n)}
        return self._all_leaves

    def node_exists(self, node: str) -> bool:
        return node in self._onto


# ─── Neo4j Knowledge Graph ────────────────────────────────────────────────────

class Neo4jKnowledgeGraph(KnowledgeGraphRepository):
    """
    KG menggunakan Neo4j — untuk production.
    Query Cypher langsung ke database.

    Query ancestors:
        MATCH (s)-[:IS_A*0..]->(a) WHERE s.name=$name
        RETURN collect(DISTINCT a.name)

    Query leaves of node:
        MATCH (root)-[:IS_A*0..]->(desc)
        WHERE root.name=$name AND NOT (desc)<-[:IS_A]-()
        RETURN collect(DISTINCT desc.name)
    """

    def __init__(self, driver):
        self._driver = driver
        self._total_leaves: Optional[int] = None

    def get_ancestors(self, node: str) -> set[str]:
        query = """
        MATCH (s)-[:IS_A*0..]->(a)
        WHERE (s:Skill OR s:SkillClass) AND s.name = $name
        RETURN collect(DISTINCT a.name) AS ancestors
        """
        with self._driver.session() as session:
            rec = session.run(query, name=node).single()
            result = set(rec["ancestors"]) if rec and rec["ancestors"] else {node}
            result.add(node)
            return result

    def get_leaves(self, node: str) -> set[str]:
        query = """
        MATCH (root)-[:IS_A*0..]->(desc)
        WHERE (root:Skill OR root:SkillClass) AND root.name = $name
          AND NOT (desc)<-[:IS_A]-(:Skill)
          AND NOT (desc)<-[:IS_A]-(:SkillClass)
        RETURN collect(DISTINCT desc.name) AS leaves
        """
        with self._driver.session() as session:
            rec = session.run(query, name=node).single()
            leaves = set(rec["leaves"]) if rec and rec["leaves"] else set()
            # Jika node sendiri tidak punya anak, dia adalah leaf
            if not leaves:
                leaves = {node}
            return leaves

    def get_all_leaves(self) -> set[str]:
        query = """
        MATCH (n) WHERE (n:Skill OR n:SkillClass)
          AND NOT (n)<-[:IS_A]-(:Skill)
          AND NOT (n)<-[:IS_A]-(:SkillClass)
        RETURN collect(DISTINCT n.name) AS leaves
        """
        with self._driver.session() as session:
            rec = session.run(query).single()
            return set(rec["leaves"]) if rec and rec["leaves"] else set()

    def node_exists(self, node: str) -> bool:
        query = "MATCH (n) WHERE (n:Skill OR n:SkillClass) AND n.name=$name RETURN count(n)>0 AS ex"
        with self._driver.session() as session:
            rec = session.run(query, name=node).single()
            return rec["ex"] if rec else False


# ─── IC Calculator (Sánchez et al., 2011) ─────────────────────────────────────

def compute_ic(node: str, graph: KnowledgeGraphRepository) -> float:
    """
    Hitung Information Content intrinsik (Sánchez, Batet & Isern, 2011):

        IC(c) = -log( (|leaves(c)| / |ancestors(c)|) + 1 / (|max_leaves| + 1) )

    Properti:
        - IC(root) = 0.0  (paling tidak informatif)
        - IC(leaf konkret) → tertinggi
        - Semakin spesifik skill, semakin tinggi IC-nya

    Args:
        node  : nama skill atau SkillClass
        graph : KnowledgeGraphRepository

    Returns:
        float: IC value >= 0.0
    """
    leaves_c   = graph.get_leaves(node)
    ancestors_c = graph.get_ancestors(node)
    max_leaves = graph.get_all_leaves()

    n_leaves    = len(leaves_c)
    n_ancestors = len(ancestors_c)
    n_max       = len(max_leaves)

    if n_ancestors == 0 or n_max == 0:
        return 0.0

    # Formula Sánchez 2011: -log((leaves/ancestors + 1) / (maxLeaves + 1))
    numerator   = (n_leaves / n_ancestors) + 1
    denominator = n_max + 1
    probability = numerator / denominator

    return -math.log(probability)


# ─── LCS (Least Common Subsumer) ──────────────────────────────────────────────

def find_lcs(node_a: str, node_b: str, graph: KnowledgeGraphRepository) -> str:
    """
    Temukan Least Common Subsumer (ancestor bersama dengan IC tertinggi).

    LCS = ancestor yang paling spesifik (paling informatif) yang merupakan
    ancestor dari kedua node. Dalam kasus multiple LCS, ambil yang IC-nya
    tertinggi.

    Args:
        node_a, node_b : dua skill yang dibandingkan
        graph          : KnowledgeGraphRepository

    Returns:
        str: nama node LCS
    """
    ancestors_a = graph.get_ancestors(node_a)
    ancestors_b = graph.get_ancestors(node_b)
    common = ancestors_a & ancestors_b

    if not common:
        # Fallback ke root jika tidak ada common ancestor
        return "TechnicalSkill"

    # Pilih common ancestor dengan IC tertinggi
    best = max(common, key=lambda n: compute_ic(n, graph))
    return best


# ─── Sánchez Similarity (Lin 1998 dengan IC Sánchez 2011) ─────────────────────

def sanchez_similarity(
    skill_a: str,
    skill_b: str,
    graph: KnowledgeGraphRepository,
) -> float:
    """
    Hitung Sánchez Semantic Similarity antara dua skill.

    Formula (Lin, 1998 dengan IC intrinsik dari Sánchez et al., 2011):

        sim(a, b) = 2 × IC(LCS(a,b)) / (IC(a) + IC(b))

    Kasus khusus:
        - a == b                   → 1.0
        - IC(a) + IC(b) == 0       → 0.0 (keduanya root, tidak informatif)
        - Tidak ada common ancestor→ 0.0

    Args:
        skill_a, skill_b : dua skill yang dibandingkan
        graph            : KnowledgeGraphRepository

    Returns:
        float: skor kemiripan semantik ∈ [0.0, 1.0]
    """
    if skill_a == skill_b:
        return 1.0

    ic_a   = compute_ic(skill_a, graph)
    ic_b   = compute_ic(skill_b, graph)
    denom  = ic_a + ic_b

    if denom == 0.0:
        return 0.0

    lcs    = find_lcs(skill_a, skill_b, graph)
    ic_lcs = compute_ic(lcs, graph)

    return round((2 * ic_lcs) / denom, 6)


# ─── Skill Set Similarity ─────────────────────────────────────────────────────

def compute_skill_score(
    talent_skills: list[str],
    required_skills: list[str],
    graph: KnowledgeGraphRepository,
) -> dict:
    """
    Hitung skor skill talent terhadap daftar skill yang dibutuhkan klien.

    Strategi: untuk setiap required skill, cari best-match dari semua
    skill talent (similarity tertinggi). Agregasi = rata-rata best-match.

    Args:
        talent_skills   : skill talent dari PostgreSQL
        required_skills : skill yang dibutuhkan klien (dari NER)
        graph           : KnowledgeGraphRepository

    Returns:
        dict:
            score    : float [0,1] — skor agregat
            detail   : list breakdown per required skill
            matched  : int — jumlah required skill terpenuhi (≥ threshold)
            coverage : float — rasio required skill terpenuhi
    """
    THRESHOLD = 0.30

    if not required_skills:
        return {"score": 1.0, "detail": [], "matched": 0, "coverage": 1.0}

    details = []
    for req in required_skills:
        best_score = 0.0
        best_match = None
        for ts in talent_skills:
            s = sanchez_similarity(ts, req, graph)
            if s > best_score:
                best_score = s
                best_match = ts
        details.append({
            "required":   req,
            "best_match": best_match,
            "score":      round(best_score, 6),
            "matched":    best_score >= THRESHOLD,
        })

    matched  = sum(1 for d in details if d["matched"])
    avg      = sum(d["score"] for d in details) / len(details)
    coverage = matched / len(required_skills)

    return {
        "score":    round(avg, 6),
        "detail":   details,
        "matched":  matched,
        "coverage": round(coverage, 4),
    }


# ─── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    g = InMemoryKnowledgeGraph()

    print("=== IC Values ===")
    nodes = ["TechnicalSkill", "FrontendSkill", "JSFrameworkFrontend", "React.js", "Vue.js", "Laravel"]
    for n in nodes:
        ic = compute_ic(n, g)
        leaves = len(g.get_leaves(n))
        anc = len(g.get_ancestors(n))
        print(f"  {n:25s} IC={ic:.4f}  leaves={leaves}  ancestors={anc}")

    print("\n=== Sánchez Similarity ===")
    pairs = [
        ("React.js",   "React.js"),
        ("React.js",   "Vue.js"),
        ("React.js",   "Angular"),
        ("React.js",   "Node.js"),
        ("React.js",   "Laravel"),
        ("React.js",   "Docker"),
        ("Laravel",    "PHP"),
        ("Django",     "Flask"),
    ]
    for a, b in pairs:
        s = sanchez_similarity(a, b, g)
        lcs = find_lcs(a, b, g)
        print(f"  {a:15s} <-> {b:15s}  sim={s:.4f}  LCS={lcs}")
