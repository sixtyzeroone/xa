-- ============================================
-- DATABASE HOSPITAL MANAGEMENT SYSTEM (LENGKAP)
-- ============================================

CREATE DATABASE IF NOT EXISTS rumahsakit;
USE rumahsakit;

-- ============================================
-- 1. TABEL ADMINISTRATOR (untuk login)
-- ============================================
CREATE TABLE IF NOT EXISTS administrator (
    id_admin VARCHAR(20) PRIMARY KEY,
    password VARCHAR(50) NOT NULL
);

INSERT INTO administrator (id_admin, password) VALUES 
('admin', 'admin123');

-- ============================================
-- 2. TABEL PASIEN
-- ============================================
CREATE TABLE IF NOT EXISTS pasien (
    no_ruangan VARCHAR(10) PRIMARY KEY,
    nama VARCHAR(100) NOT NULL,
    alamat TEXT NOT NULL,
    no_ktp VARCHAR(20) NOT NULL UNIQUE,
    jk ENUM('L', 'P') NOT NULL,
    no_telp VARCHAR(15)
);

INSERT INTO pasien (no_ruangan, nama, alamat, no_ktp, jk, no_telp) VALUES
('R001', 'Budi Santoso', 'Jl. Merdeka No. 10, Jakarta', '3171010101010001', 'L', '081234567890'),
('R002', 'Siti Aminah', 'Jl. Sudirman No. 25, Bandung', '3273010101010002', 'P', '082345678901'),
('R003', 'Ahmad Wijaya', 'Jl. Diponegoro No. 5, Surabaya', '3578010101010003', 'L', '083456789012');

-- ============================================
-- 3. TABEL DOKTER
-- ============================================
CREATE TABLE IF NOT EXISTS dokter (
    kd_dokter VARCHAR(10) PRIMARY KEY,
    nama VARCHAR(100) NOT NULL,
    spesialis VARCHAR(50) NOT NULL,
    jk ENUM('L', 'P') NOT NULL,
    alamat TEXT,
    no_telp VARCHAR(15),
    jadwal VARCHAR(100)
);

INSERT INTO dokter (kd_dokter, nama, spesialis, jk, alamat, no_telp, jadwal) VALUES
('DR001', 'dr. Andi Wijaya', 'Umum', 'L', 'Jl. Kesehatan No. 5, Jakarta', '081234567890', 'Senin-Kamis 08:00-12:00'),
('DR002', 'dr. Siti Nurhaliza', 'Anak', 'P', 'Jl. Melati No. 10, Bandung', '082345678901', 'Selasa-Jumat 09:00-13:00'),
('DR003', 'dr. Budi Santoso', 'Jantung', 'L', 'Jl. Anggrek No. 8, Surabaya', '083456789012', 'Rabu-Sabtu 10:00-14:00');

-- ============================================
-- 4. TABEL PERAWAT
-- ============================================
CREATE TABLE IF NOT EXISTS perawat (
    kd_perawat VARCHAR(10) PRIMARY KEY,
    nama VARCHAR(100) NOT NULL,
    spesialis VARCHAR(50) NOT NULL,
    jk ENUM('L', 'P') NOT NULL,
    no_telp VARCHAR(15),
    alamat TEXT
);

INSERT INTO perawat (kd_perawat, nama, spesialis, jk, no_telp, alamat) VALUES
('PW001', 'Ns. Dewi Anggraini', 'ICU', 'P', '081234567001', 'Jl. Flamboyan No. 1, Jakarta'),
('PW002', 'Ns. Rizki Firmansyah', 'IGD', 'L', '081234567002', 'Jl. Kenanga No. 2, Bandung'),
('PW003', 'Ns. Maya Sari', 'Anak', 'P', '081234567003', 'Jl. Melati No. 3, Surabaya');

-- ============================================
-- 5. TABEL RUANGAN
-- ============================================
CREATE TABLE IF NOT EXISTS ruangan (
    kd_ruangan VARCHAR(10) PRIMARY KEY,
    nama_ruangan VARCHAR(50) NOT NULL,
    kelas VARCHAR(20) NOT NULL,
    kapasitas INT DEFAULT 1,
    harga DECIMAL(12,2) NOT NULL,
    status ENUM('Tersedia', 'Terisi', 'Perawatan') DEFAULT 'Tersedia'
);

INSERT INTO ruangan (kd_ruangan, nama_ruangan, kelas, kapasitas, harga, status) VALUES
('RG001', 'Melati', 'Kelas 1', 2, 500000, 'Tersedia'),
('RG002', 'Anggrek', 'Kelas 2', 4, 350000, 'Tersedia'),
('RG003', 'Mawar', 'VIP', 1, 1000000, 'Tersedia'),
('RG004', 'Flamboyan', 'Kelas 3', 6, 200000, 'Tersedia');

-- ============================================
-- 6. TABEL OBAT
-- ============================================
CREATE TABLE IF NOT EXISTS obat (
    id_obat VARCHAR(20) PRIMARY KEY,
    nama_obat VARCHAR(100) NOT NULL,
    harga DOUBLE NOT NULL
);

INSERT INTO obat (id_obat, nama_obat, harga) VALUES
('OB001', 'Paracetamol', 5000),
('OB002', 'Amoxicillin', 15000),
('OB003', 'Vitamin C', 3000),
('OB004', 'Antasida', 8000),
('OB005', 'Ibuprofen', 12000);

-- ============================================
-- 7. TABEL DAFTAR BEROBAT (Pendaftaran)
-- ============================================
CREATE TABLE IF NOT EXISTS daftar_berobat (
    id_daftar VARCHAR(20) PRIMARY KEY,
    no_ruangan VARCHAR(10),
    nama_pasien VARCHAR(100),
    kd_dokter VARCHAR(10),
    tgl_daftar DATE,
    status VARCHAR(20) DEFAULT 'Menunggu'
);

INSERT INTO daftar_berobat (id_daftar, no_ruangan, nama_pasien, kd_dokter, tgl_daftar, status) VALUES
('DF001', 'R001', 'Budi Santoso', 'DR001', CURDATE(), 'Menunggu'),
('DF002', 'R002', 'Siti Aminah', 'DR002', CURDATE(), 'Selesai'),
('DF003', 'R003', 'Ahmad Wijaya', 'DR003', CURDATE(), 'Menunggu');

-- ============================================
-- 8. TABEL PERIKSA (Pemeriksaan)
-- ============================================
CREATE TABLE IF NOT EXISTS periksa (
    id_periksa VARCHAR(20) PRIMARY KEY,
    id_daftar VARCHAR(20),
    diagnosa TEXT,
    tgl_periksa DATE,
    biaya DECIMAL(12,2) DEFAULT 0,
    FOREIGN KEY (id_daftar) REFERENCES daftar_berobat(id_daftar) ON DELETE CASCADE
);

INSERT INTO periksa (id_periksa, id_daftar, diagnosa, tgl_periksa, biaya) VALUES
('PR001', 'DF002', 'Demam dan batuk', CURDATE(), 50000);

-- ============================================
-- 9. TABEL RESEP (dengan ON DELETE CASCADE)
-- ============================================
CREATE TABLE IF NOT EXISTS resep (
    id_resep VARCHAR(20) PRIMARY KEY,
    id_periksa VARCHAR(20),
    id_obat VARCHAR(20),
    jumlah INT,
    subtotal DECIMAL(12,2) DEFAULT 0,
    FOREIGN KEY (id_periksa) REFERENCES periksa(id_periksa) ON DELETE CASCADE,
    FOREIGN KEY (id_obat) REFERENCES obat(id_obat) ON DELETE CASCADE
);

INSERT INTO resep (id_resep, id_periksa, id_obat, jumlah, subtotal) VALUES
('RP001', 'PR001', 'OB001', 3, 15000),
('RP002', 'PR001', 'OB003', 2, 6000);

-- ============================================
-- 10. TABEL PEMBAYARAN (dengan ON DELETE CASCADE)
-- ============================================
CREATE TABLE IF NOT EXISTS pembayaran (
    id_pembayaran VARCHAR(20) PRIMARY KEY,
    id_resep VARCHAR(20),
    total_bayar DECIMAL(12,2),
    tgl_bayar DATE,
    metode VARCHAR(20) DEFAULT 'Tunai',
    FOREIGN KEY (id_resep) REFERENCES resep(id_resep) ON DELETE CASCADE
);

-- ============================================
-- 11. VIEW untuk laporan
-- ============================================

-- View pendaftaran lengkap
CREATE OR REPLACE VIEW v_pendaftaran AS
SELECT 
    d.id_daftar,
    d.nama_pasien,
    d.no_ruangan,
    dk.nama AS nama_dokter,
    d.tgl_daftar,
    d.status
FROM daftar_berobat d
LEFT JOIN dokter dk ON d.kd_dokter = dk.kd_dokter;

-- View pemeriksaan lengkap
CREATE OR REPLACE VIEW v_pemeriksaan AS
SELECT 
    p.id_periksa,
    p.id_daftar,
    d.nama_pasien,
    dk.nama AS nama_dokter,
    p.diagnosa,
    p.tgl_periksa,
    p.biaya
FROM periksa p
JOIN daftar_berobat d ON p.id_daftar = d.id_daftar
LEFT JOIN dokter dk ON d.kd_dokter = dk.kd_dokter;

-- View total pembayaran per pasien
CREATE OR REPLACE VIEW v_pembayaran AS
SELECT 
    pb.id_pembayaran,
    r.id_periksa,
    d.nama_pasien,
    pb.total_bayar,
    pb.tgl_bayar,
    pb.metode
FROM pembayaran pb
JOIN resep r ON pb.id_resep = r.id_resep
JOIN periksa pk ON r.id_periksa = pk.id_periksa
JOIN daftar_berobat d ON pk.id_daftar = d.id_daftar;

-- ============================================
-- 12. STORED PROCEDURE untuk generate ID
-- ============================================

DELIMITER $$

CREATE PROCEDURE generate_id_perawat(OUT new_id VARCHAR(10))
BEGIN
    DECLARE last_num INT;
    SELECT IFNULL(MAX(CAST(SUBSTRING(kd_perawat, 3) AS UNSIGNED)), 0) INTO last_num FROM perawat;
    SET new_id = CONCAT('PW', LPAD(last_num + 1, 3, '0'));
END$$

CREATE PROCEDURE generate_id_dokter(OUT new_id VARCHAR(10))
BEGIN
    DECLARE last_num INT;
    SELECT IFNULL(MAX(CAST(SUBSTRING(kd_dokter, 3) AS UNSIGNED)), 0) INTO last_num FROM dokter;
    SET new_id = CONCAT('DR', LPAD(last_num + 1, 3, '0'));
END$$

CREATE PROCEDURE generate_id_ruangan(OUT new_id VARCHAR(10))
BEGIN
    DECLARE last_num INT;
    SELECT IFNULL(MAX(CAST(SUBSTRING(kd_ruangan, 3) AS UNSIGNED)), 0) INTO last_num FROM ruangan;
    SET new_id = CONCAT('RG', LPAD(last_num + 1, 3, '0'));
END$$

CREATE PROCEDURE generate_id_obat(OUT new_id VARCHAR(20))
BEGIN
    DECLARE last_num INT;
    SELECT IFNULL(MAX(CAST(SUBSTRING(id_obat, 3) AS UNSIGNED)), 0) INTO last_num FROM obat;
    SET new_id = CONCAT('OB', LPAD(last_num + 1, 3, '0'));
END$$

CREATE PROCEDURE generate_id_daftar(OUT new_id VARCHAR(20))
BEGIN
    DECLARE last_num INT;
    SELECT IFNULL(MAX(CAST(SUBSTRING(id_daftar, 3) AS UNSIGNED)), 0) INTO last_num FROM daftar_berobat;
    SET new_id = CONCAT('DF', LPAD(last_num + 1, 3, '0'));
END$$

CREATE PROCEDURE generate_id_periksa(OUT new_id VARCHAR(20))
BEGIN
    DECLARE last_num INT;
    SELECT IFNULL(MAX(CAST(SUBSTRING(id_periksa, 3) AS UNSIGNED)), 0) INTO last_num FROM periksa;
    SET new_id = CONCAT('PR', LPAD(last_num + 1, 3, '0'));
END$$

CREATE PROCEDURE generate_id_resep(OUT new_id VARCHAR(20))
BEGIN
    DECLARE last_num INT;
    SELECT IFNULL(MAX(CAST(SUBSTRING(id_resep, 3) AS UNSIGNED)), 0) INTO last_num FROM resep;
    SET new_id = CONCAT('RP', LPAD(last_num + 1, 3, '0'));
END$$

CREATE PROCEDURE generate_id_pembayaran(OUT new_id VARCHAR(20))
BEGIN
    DECLARE last_num INT;
    SELECT IFNULL(MAX(CAST(SUBSTRING(id_pembayaran, 3) AS UNSIGNED)), 0) INTO last_num FROM pembayaran;
    SET new_id = CONCAT('BY', LPAD(last_num + 1, 3, '0'));
END$$

DELIMITER ;

-- ============================================
-- 13. TRIGGER untuk auto-calculate subtotal resep
-- ============================================

DELIMITER $$

DROP TRIGGER IF EXISTS trg_calc_subtotal$$

CREATE TRIGGER trg_calc_subtotal
BEFORE INSERT ON resep
FOR EACH ROW
BEGIN
    DECLARE harga_obat DOUBLE;
    SELECT harga INTO harga_obat FROM obat WHERE id_obat = NEW.id_obat;
    SET NEW.subtotal = NEW.jumlah * harga_obat;
END$$

DELIMITER ;

-- ============================================
-- 14. TRIGGER untuk update subtotal saat UPDATE jumlah
-- ============================================

DELIMITER $$

DROP TRIGGER IF EXISTS trg_update_subtotal$$

CREATE TRIGGER trg_update_subtotal
BEFORE UPDATE ON resep
FOR EACH ROW
BEGIN
    DECLARE harga_obat DOUBLE;
    SELECT harga INTO harga_obat FROM obat WHERE id_obat = NEW.id_obat;
    SET NEW.subtotal = NEW.jumlah * harga_obat;
END$$

DELIMITER ;

-- ============================================
-- SELESAI
-- ============================================
SELECT 'Database rumahsakit berhasil dibuat dengan semua tabel!' AS Status;
