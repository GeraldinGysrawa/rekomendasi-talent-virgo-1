// ============================================================================
// Neo4j Knowledge Graph: Skill Ontology
// Virgo Talent Recommender — PT Padepokan Tujuh Sembilan
// ============================================================================
// Struktur mengikuti Noy & McGuinness (2001):
//   - Node (:SkillClass)  → konsep / kategori (abstract)
//   - Node (:Skill)       → skill konkret yang dimiliki talent
//   - Edge [:IS_A]        → hubungan subclass / inheritance
//   - Edge [:RELATED_TO]  → hubungan lateral antar skill
//
// F(skill) = semua ancestor via IS_A → digunakan dalam Tversky Similarity
// ============================================================================
// ─── Constraint & Index ───────────────────────────────────────────────────────
CREATE CONSTRAINT skill_name_unique IF NOT EXISTS
FOR (s:Skill)
REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT skillclass_name_unique IF NOT EXISTS
FOR (c:SkillClass)
REQUIRE c.name IS UNIQUE;

// ─── Root ─────────────────────────────────────────────────────────────────────
MERGE (:SkillClass {name: 'TechnicalSkill', level: 0});

// ─── Level 1: Domain Utama ────────────────────────────────────────────────────
MERGE (:SkillClass {name: 'SoftwareSkill', level: 1});
MERGE (:SkillClass {name: 'DatabaseSkill', level: 1});
MERGE (:SkillClass {name: 'DevOpsSkill', level: 1});
MERGE (:SkillClass {name: 'MobileSkill', level: 1});

MATCH
  (a:SkillClass {name: 'SoftwareSkill'}),
  (b:SkillClass {name: 'TechnicalSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'DatabaseSkill'}),
  (b:SkillClass {name: 'TechnicalSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'DevOpsSkill'}), (b:SkillClass {name: 'TechnicalSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'MobileSkill'}), (b:SkillClass {name: 'TechnicalSkill'})
MERGE (a)-[:IS_A]->(b);

// ─── Level 2: Sub-domain Software ────────────────────────────────────────────
MERGE (:SkillClass {name: 'FrontendSkill', level: 2});
MERGE (:SkillClass {name: 'BackendSkill', level: 2});
MERGE (:SkillClass {name: 'FullstackSkill', level: 2});

MATCH
  (a:SkillClass {name: 'FrontendSkill'}), (b:SkillClass {name: 'SoftwareSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'BackendSkill'}), (b:SkillClass {name: 'SoftwareSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'FullstackSkill'}),
  (b:SkillClass {name: 'SoftwareSkill'})
MERGE (a)-[:IS_A]->(b);

// ─── Level 3: Framework Categories ───────────────────────────────────────────
MERGE (:SkillClass {name: 'JSFrameworkFrontend', level: 3});
MERGE (:SkillClass {name: 'CSSFramework', level: 3});
MERGE (:SkillClass {name: 'MarkupLanguage', level: 3});
MERGE (:SkillClass {name: 'JSFrameworkBackend', level: 3});
MERGE (:SkillClass {name: 'PHPFramework', level: 3});
MERGE (:SkillClass {name: 'PythonFramework', level: 3});
MERGE (:SkillClass {name: 'JavaFramework', level: 3});
MERGE (:SkillClass {name: 'DotNetFramework', level: 3});
MERGE (:SkillClass {name: 'CrossPlatformMobile', level: 3});
MERGE (:SkillClass {name: 'NativeMobile', level: 3});

MATCH
  (a:SkillClass {name: 'JSFrameworkFrontend'}),
  (b:SkillClass {name: 'FrontendSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'CSSFramework'}), (b:SkillClass {name: 'FrontendSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'MarkupLanguage'}),
  (b:SkillClass {name: 'FrontendSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'JSFrameworkBackend'}),
  (b:SkillClass {name: 'BackendSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'PHPFramework'}), (b:SkillClass {name: 'BackendSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'PythonFramework'}),
  (b:SkillClass {name: 'BackendSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'JavaFramework'}), (b:SkillClass {name: 'BackendSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'DotNetFramework'}),
  (b:SkillClass {name: 'BackendSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'CrossPlatformMobile'}),
  (b:SkillClass {name: 'MobileSkill'})
MERGE (a)-[:IS_A]->(b);
MATCH
  (a:SkillClass {name: 'NativeMobile'}), (b:SkillClass {name: 'MobileSkill'})
MERGE (a)-[:IS_A]->(b);

// ─── Leaf: Skill Konkret ──────────────────────────────────────────────────────

// Frontend JS Frameworks
MERGE (:Skill {name: 'React.js', canonical: 'React.js'});
MERGE (:Skill {name: 'Next.js', canonical: 'Next.js'});
MERGE (:Skill {name: 'Vue.js', canonical: 'Vue.js'});
MERGE (:Skill {name: 'Angular', canonical: 'Angular'});
MERGE (:Skill {name: 'Svelte', canonical: 'Svelte'});
MERGE (:Skill {name: 'Redux', canonical: 'Redux'});
MERGE (:Skill {name: 'RxJS', canonical: 'RxJS'});

MATCH (s:Skill {name: 'React.js'}), (c:SkillClass {name: 'JSFrameworkFrontend'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Next.js'}), (c:SkillClass {name: 'JSFrameworkFrontend'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Vue.js'}), (c:SkillClass {name: 'JSFrameworkFrontend'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Angular'}), (c:SkillClass {name: 'JSFrameworkFrontend'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Svelte'}), (c:SkillClass {name: 'JSFrameworkFrontend'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Redux'}), (c:SkillClass {name: 'JSFrameworkFrontend'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'RxJS'}), (c:SkillClass {name: 'JSFrameworkFrontend'})
MERGE (s)-[:IS_A]->(c);

// CSS & Markup
MERGE (:Skill {name: 'Tailwind CSS', canonical: 'Tailwind CSS'});
MERGE (:Skill {name: 'Bootstrap', canonical: 'Bootstrap'});
MERGE (:Skill {name: 'HTML', canonical: 'HTML'});
MERGE (:Skill {name: 'CSS', canonical: 'CSS'});

MATCH (s:Skill {name: 'Tailwind CSS'}), (c:SkillClass {name: 'CSSFramework'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Bootstrap'}), (c:SkillClass {name: 'CSSFramework'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'HTML'}), (c:SkillClass {name: 'MarkupLanguage'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'CSS'}), (c:SkillClass {name: 'MarkupLanguage'})
MERGE (s)-[:IS_A]->(c);

// Languages (multi-parent: frontend & backend)
MERGE (:Skill {name: 'JavaScript', canonical: 'JavaScript'});
MERGE (:Skill {name: 'TypeScript', canonical: 'TypeScript'});

MATCH (s:Skill {name: 'JavaScript'}), (f:SkillClass {name: 'FrontendSkill'})
MERGE (s)-[:IS_A]->(f);
MATCH (s:Skill {name: 'JavaScript'}), (b:SkillClass {name: 'BackendSkill'})
MERGE (s)-[:IS_A]->(b);
MATCH (s:Skill {name: 'TypeScript'}), (f:SkillClass {name: 'FrontendSkill'})
MERGE (s)-[:IS_A]->(f);
MATCH (s:Skill {name: 'TypeScript'}), (b:SkillClass {name: 'BackendSkill'})
MERGE (s)-[:IS_A]->(b);

// Backend JS
MERGE (:Skill {name: 'Node.js', canonical: 'Node.js'});
MERGE (:Skill {name: 'Express.js', canonical: 'Express.js'});

MATCH (s:Skill {name: 'Node.js'}), (c:SkillClass {name: 'JSFrameworkBackend'})
MERGE (s)-[:IS_A]->(c);
MATCH
  (s:Skill {name: 'Express.js'}), (c:SkillClass {name: 'JSFrameworkBackend'})
MERGE (s)-[:IS_A]->(c);

// PHP
MERGE (:Skill {name: 'PHP', canonical: 'PHP'});
MERGE (:Skill {name: 'Laravel', canonical: 'Laravel'});
MERGE (:Skill {name: 'CodeIgniter', canonical: 'CodeIgniter'});

MATCH (s:Skill {name: 'PHP'}), (c:SkillClass {name: 'BackendSkill'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'gerald'}), (c:SkillClass {name: 'BackendSkill'})
MERGE (s)-[:IS_A]->(c);

MATCH (s:Skill {name: 'Laravel'}), (c:SkillClass {name: 'PHPFramework'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'CodeIgniter'}), (c:SkillClass {name: 'PHPFramework'})
MERGE (s)-[:IS_A]->(c);

// Python
MERGE (:Skill {name: 'Python', canonical: 'Python'});
MERGE (:Skill {name: 'Django', canonical: 'Django'});
MERGE (:Skill {name: 'Flask', canonical: 'Flask'});
MERGE (:Skill {name: 'FastAPI', canonical: 'FastAPI'});

MATCH (s:Skill {name: 'Python'}), (c:SkillClass {name: 'BackendSkill'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Django'}), (c:SkillClass {name: 'PythonFramework'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Flask'}), (c:SkillClass {name: 'PythonFramework'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'FastAPI'}), (c:SkillClass {name: 'PythonFramework'})
MERGE (s)-[:IS_A]->(c);

// Java
MERGE (:Skill {name: 'Java', canonical: 'Java'});
MERGE (:Skill {name: 'Spring Boot', canonical: 'Spring Boot'});

MATCH (s:Skill {name: 'Java'}), (c:SkillClass {name: 'BackendSkill'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Spring Boot'}), (c:SkillClass {name: 'JavaFramework'})
MERGE (s)-[:IS_A]->(c);

// .NET
MERGE (:Skill {name: '.NET', canonical: '.NET'});
MERGE (:Skill {name: 'C#', canonical: 'C#'});

MATCH (s:Skill {name: '.NET'}), (c:SkillClass {name: 'DotNetFramework'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'C#'}), (c:SkillClass {name: 'DotNetFramework'})
MERGE (s)-[:IS_A]->(c);

// Database
MERGE (:Skill {name: 'MySQL', canonical: 'MySQL'});
MERGE (:Skill {name: 'PostgreSQL', canonical: 'PostgreSQL'});
MERGE (:Skill {name: 'SQL Server', canonical: 'SQL Server'});
MERGE (:Skill {name: 'MongoDB', canonical: 'MongoDB'});
MERGE (:Skill {name: 'Redis', canonical: 'Redis'});
MERGE (:Skill {name: 'Firebase', canonical: 'Firebase'});

MATCH (s:Skill {name: 'MySQL'}), (c:SkillClass {name: 'DatabaseSkill'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'PostgreSQL'}), (c:SkillClass {name: 'DatabaseSkill'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'SQL Server'}), (c:SkillClass {name: 'DatabaseSkill'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'MongoDB'}), (c:SkillClass {name: 'DatabaseSkill'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Redis'}), (c:SkillClass {name: 'DatabaseSkill'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Firebase'}), (c:SkillClass {name: 'DatabaseSkill'})
MERGE (s)-[:IS_A]->(c);

// Mobile
MERGE (:Skill {name: 'Flutter', canonical: 'Flutter'});
MERGE (:Skill {name: 'Dart', canonical: 'Dart'});
MERGE (:Skill {name: 'React Native', canonical: 'React Native'});

MATCH (s:Skill {name: 'Flutter'}), (c:SkillClass {name: 'CrossPlatformMobile'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Dart'}), (c:SkillClass {name: 'CrossPlatformMobile'})
MERGE (s)-[:IS_A]->(c);
MATCH
  (s:Skill {name: 'React Native'}), (c:SkillClass {name: 'CrossPlatformMobile'})
MERGE (s)-[:IS_A]->(c);

// DevOps
MERGE (:Skill {name: 'Docker', canonical: 'Docker'});
MERGE (:Skill {name: 'Kubernetes', canonical: 'Kubernetes'});
MERGE (:Skill {name: 'Kafka', canonical: 'Kafka'});

MATCH (s:Skill {name: 'Docker'}), (c:SkillClass {name: 'DevOpsSkill'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Kubernetes'}), (c:SkillClass {name: 'DevOpsSkill'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Kafka'}), (c:SkillClass {name: 'DevOpsSkill'})
MERGE (s)-[:IS_A]->(c);

// General
MERGE (:Skill {name: 'REST API', canonical: 'REST API'});
MERGE (:Skill {name: 'Microservices', canonical: 'Microservices'});

MATCH (s:Skill {name: 'REST API'}), (c:SkillClass {name: 'BackendSkill'})
MERGE (s)-[:IS_A]->(c);
MATCH (s:Skill {name: 'Microservices'}), (c:SkillClass {name: 'BackendSkill'})
MERGE (s)-[:IS_A]->(c);

// ─── Query untuk verifikasi ancestors (dipakai Tversky) ───────────────────────
// Contoh: ambil semua ancestor React.js via IS_A traversal
// MATCH (s:Skill {name: 'React.js'})-[:IS_A*]->(ancestor)
// RETURN s.name, collect(ancestor.name) AS ancestors

//MATCH (n) RETURN n LIMIT 100;