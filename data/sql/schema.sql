-- ============================================================================
-- Schema PostgreSQL: Virgo Talent Recommender
-- PT Padepokan Tujuh Sembilan
-- ============================================================================
-- Desain mencerminkan 5 kriteria SAW:
--   1. skill             → tabel talent_skills
--   2. pengalaman_kerja  → kolom pengalaman_tahun di talents
--   3. lokasi            → kolom lokasi di talents
--   4. preferensi_proyek → tabel talent_project_preferences
--   5. ketersediaan      → tabel talent_availability (berbasis tanggal)
-- ============================================================================

-- ─── Tabel utama talent ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS talents (
    id                  SERIAL PRIMARY KEY,
    kode_talent         VARCHAR(10) UNIQUE NOT NULL,   -- misal: T001, T002
    nama                VARCHAR(100) NOT NULL,
    pengalaman_tahun    NUMERIC(4,1) NOT NULL DEFAULT 0,
    lokasi              VARCHAR(50) NOT NULL,           -- kota domisili talent
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- ─── Skills tiap talent ───────────────────────────────────────────────────────
-- Skill disimpan sebagai string yang mereferensikan node di Neo4j Knowledge Graph
CREATE TABLE IF NOT EXISTS talent_skills (
    id          SERIAL PRIMARY KEY,
    talent_id   INTEGER NOT NULL REFERENCES talents(id) ON DELETE CASCADE,
    skill_name  VARCHAR(100) NOT NULL,    -- harus ada node di Neo4j dengan nama ini
    UNIQUE(talent_id, skill_name)
);

-- ─── Preferensi tipe proyek tiap talent ──────────────────────────────────────
-- Diisi berdasarkan histori & preferensi talent, bukan dari query user
CREATE TABLE IF NOT EXISTS talent_project_preferences (
    id              SERIAL PRIMARY KEY,
    talent_id       INTEGER NOT NULL REFERENCES talents(id) ON DELETE CASCADE,
    project_type    VARCHAR(50) NOT NULL,   -- misal: 'banking', 'web', 'mobile'
    UNIQUE(talent_id, project_type)
);

-- ─── Ketersediaan talent berbasis tanggal ────────────────────────────────────
-- Pendekatan B: menyimpan kapan talent mulai tersedia kembali
-- Jika current_project_end_date NULL → talent sudah available sekarang
-- Sistem akan menghitung gap antara requested_start_date vs available_date
CREATE TABLE IF NOT EXISTS talent_availability (
    id                          SERIAL PRIMARY KEY,
    talent_id                   INTEGER NOT NULL REFERENCES talents(id) ON DELETE CASCADE UNIQUE,
    status                      VARCHAR(20) NOT NULL DEFAULT 'available',
                                -- 'available', 'on_project', 'unavailable'
    current_project_end_date    DATE,          -- NULL jika sudah available
    next_available_date         DATE           -- tanggal talent bisa mulai proyek baru
                                               -- NULL jika sudah available sekarang
);

-- ─── Index untuk performa query ───────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_talent_skills_talent    ON talent_skills(talent_id);
CREATE INDEX IF NOT EXISTS idx_talent_skills_name      ON talent_skills(skill_name);
CREATE INDEX IF NOT EXISTS idx_availability_talent     ON talent_availability(talent_id);
CREATE INDEX IF NOT EXISTS idx_availability_status     ON talent_availability(status);
CREATE INDEX IF NOT EXISTS idx_pref_talent             ON talent_project_preferences(talent_id);
CREATE INDEX IF NOT EXISTS idx_pref_type               ON talent_project_preferences(project_type);

-- ============================================================================
-- Dummy Data (10 talent untuk development)
-- ============================================================================

INSERT INTO talents (kode_talent, nama, pengalaman_tahun, lokasi) VALUES
    ('T001', 'Andi Firmansyah',  3.0, 'Bandung'),
    ('T002', 'Budi Santoso',     2.0, 'Jakarta'),
    ('T003', 'Citra Dewi',       4.0, 'Bandung'),
    ('T004', 'Dimas Pratama',    2.0, 'Bandung'),
    ('T005', 'Eka Rahayu',       5.0, 'Jakarta'),
    ('T006', 'Fajar Nugroho',    3.0, 'Bandung'),
    ('T007', 'Gina Permata',     1.0, 'Surabaya'),
    ('T008', 'Hendra Wijaya',    6.0, 'Jakarta'),
    ('T009', 'Indira Sari',      2.0, 'Bandung'),
    ('T010', 'Joko Susilo',      3.0, 'Jakarta')
ON CONFLICT DO NOTHING;

-- Skills
INSERT INTO talent_skills (talent_id, skill_name)
SELECT t.id, s.skill FROM talents t
JOIN (VALUES
    ('T001', 'React.js'), ('T001', 'JavaScript'), ('T001', 'TypeScript'), ('T001', 'HTML'), ('T001', 'CSS'),
    ('T002', 'Vue.js'),   ('T002', 'JavaScript'), ('T002', 'Node.js'),    ('T002', 'Express.js'),
    ('T003', 'Angular'),  ('T003', 'TypeScript'), ('T003', 'RxJS'),       ('T003', 'HTML'), ('T003', 'CSS'),
    ('T004', 'PHP'),      ('T004', 'Laravel'),    ('T004', 'MySQL'),      ('T004', 'REST API'),
    ('T005', '.NET'),     ('T005', 'C#'),         ('T005', 'SQL Server'), ('T005', 'REST API'),
    ('T006', 'Python'),   ('T006', 'Django'),     ('T006', 'PostgreSQL'), ('T006', 'Docker'),
    ('T007', 'React.js'), ('T007', 'Next.js'),    ('T007', 'TypeScript'), ('T007', 'Tailwind CSS'),
    ('T008', 'Java'),     ('T008', 'Spring Boot'),('T008', 'Microservices'),('T008','Kafka'),('T008','Docker'),
    ('T009', 'Flutter'),  ('T009', 'Dart'),       ('T009', 'Firebase'),   ('T009', 'REST API'),
    ('T010', 'React Native'),('T010','JavaScript'),('T010','Firebase'),   ('T010', 'Redux')
) AS s(kode, skill) ON t.kode_talent = s.kode
ON CONFLICT DO NOTHING;

-- Preferensi proyek
INSERT INTO talent_project_preferences (talent_id, project_type)
SELECT t.id, p.ptype FROM talents t
JOIN (VALUES
    ('T001', 'web'),      ('T001', 'banking'),
    ('T002', 'web'),      ('T002', 'retail'),
    ('T003', 'web'),      ('T003', 'banking'),   ('T003', 'enterprise'),
    ('T004', 'web'),      ('T004', 'retail'),
    ('T005', 'banking'),  ('T005', 'enterprise'), ('T005', 'erp'),
    ('T006', 'web'),      ('T006', 'data'),
    ('T007', 'web'),      ('T007', 'startup'),
    ('T008', 'banking'),  ('T008', 'enterprise'), ('T008', 'microservices'),
    ('T009', 'mobile'),   ('T009', 'startup'),
    ('T010', 'mobile'),   ('T010', 'web')
) AS p(kode, ptype) ON t.kode_talent = p.kode
ON CONFLICT DO NOTHING;

-- Ketersediaan (berbasis tanggal — Pendekatan B)
-- next_available_date: kapan talent bisa mulai proyek baru
-- NULL = sudah available sekarang
INSERT INTO talent_availability (talent_id, status, current_project_end_date, next_available_date)
SELECT t.id, a.status, a.end_date::DATE, a.avail_date::DATE
FROM talents t
JOIN (VALUES
    ('T001', 'available',   NULL,         NULL),
    ('T002', 'available',   NULL,         NULL),
    ('T003', 'on_project',  '2026-04-30', '2026-05-01'),
    ('T004', 'available',   NULL,         NULL),
    ('T005', 'available',   NULL,         NULL),
    ('T006', 'on_project',  '2026-03-15', '2026-03-16'),
    ('T007', 'available',   NULL,         NULL),
    ('T008', 'on_project',  '2026-06-30', '2026-07-01'),
    ('T009', 'available',   NULL,         NULL),
    ('T010', 'on_project',  '2026-02-28', '2026-03-01')
) AS a(kode, status, end_date, avail_date) ON t.kode_talent = a.kode
ON CONFLICT DO NOTHING;
