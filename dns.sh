#!/bin/bash

# ==============================================================================
# SCRIPT AUTO-KONFIGURASI BIND9 AUTHORITATIVE DNS (DEBIAN/UBUNTU)
# ==============================================================================
# Deskripsi: Mengonfigurasi DNS Publik Aman (No-Recursion)
# Target OS: Debian 10/11/12, Ubuntu 20.04/22.04+
# ==============================================================================

# --- VARIABEL KONFIGURASI (SILAKAN UBAH) ---
DOMAIN="vortexstore.com"
IP_PUBLIK="192.168.1.9"  # Ganti dengan IP Publik asli Anda
NS1="ns1"
NS2="ns2"
ADMIN_EMAIL="admin.vortexstore.com." # Ganti @ dengan titik, akhiri dengan titik
SERIAL=$(date +%Y%m%d01)

# --- WARNA OUTPUT ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() { echo -e "${GREEN}[*] $1${NC}"; }
print_error() { echo -e "${RED}[!] $1${NC}"; exit 1; }

# 1. VALIDASI ROOT
if [[ $EUID -ne 0 ]]; then
   print_error "Script ini harus dijalankan sebagai root (gunakan sudo)."
fi

clear
echo "================================================"
echo "   BIND9 AUTHORITATIVE DNS AUTO-INSTALLER"
echo "================================================"
echo "Domain      : $DOMAIN"
echo "IP Publik   : $IP_PUBLIK"
echo "NS Records  : $NS1.$DOMAIN, $NS2.$DOMAIN"
echo "================================================"
read -p "Lanjutkan instalasi? (y/n): " confirm
[[ $confirm != [yY] ]] && exit 1

# 2. UPDATE & INSTALL BIND9
print_status "Menginstall paket BIND9..."
apt update && apt install bind9 bind9utils bind9-doc dnsutils -y || print_error "Gagal install BIND9"

# 3. KONFIGURASI NAMED.CONF.OPTIONS (SECURITY HARDENING)
print_status "Konfigurasi Security & Options..."
cat > /etc/bind/named.conf.options << EOF
options {
    directory "/var/cache/bind";

    # Matikan Recursion (Mencegah DNS Amplification Attack)
    recursion no;
    allow-query { any; };
    allow-transfer { none; };

    # Interface & Port
    listen-on port 53 { any; };
    listen-on-v6 { any; };

    # DNSSEC
    dnssec-validation auto;
    auth-nxdomain no;    # Conform to RFC1035

    # Rate Limiting (Mencegah DDoS)
    rate-limit {
        responses-per-second 10;
        window 5;
    };
};

logging {
    channel default_log {
        file "/var/log/named/default.log" versions 3 size 5m;
        severity info;
        print-time yes;
        print-severity yes;
        print-category yes;
    };
    category default { default_log; };
    category queries { default_log; };
};
EOF

# 4. KONFIGURASI NAMED.CONF.LOCAL (ZONE DEFINITION)
print_status "Konfigurasi Zone Definitions..."
IP1=$(echo $IP_PUBLIK | cut -d'.' -f1)
IP2=$(echo $IP_PUBLIK | cut -d'.' -f2)
IP3=$(echo $IP_PUBLIK | cut -d'.' -f3)
IP4=$(echo $IP_PUBLIK | cut -d'.' -f4)

cat > /etc/bind/named.conf.local << EOF
zone "$DOMAIN" {
    type master;
    file "/etc/bind/db.$DOMAIN";
};

zone "$IP3.$IP2.$IP1.in-addr.arpa" {
    type master;
    file "/etc/bind/db.$IP1.$IP2.$IP3";
};
EOF

# 5. MEMBUAT DATABASE ZONA FORWARD
print_status "Membuat Forward Zone File..."
cat > /etc/bind/db.$DOMAIN << EOF
\$TTL    604800
@       IN      SOA     $NS1.$DOMAIN. $ADMIN_EMAIL (
                              $SERIAL         ; Serial
                              604800          ; Refresh
                              86400           ; Retry
                              2419200         ; Expire
                              604800 )        ; Negative Cache TTL

; Name Servers
@       IN      NS      $NS1.$DOMAIN.
@       IN      NS      $NS2.$DOMAIN.

; A Records (Glue Records)
$NS1    IN      A       $IP_PUBLIK
$NS2    IN      A       $IP_PUBLIK

; Host Records
@       IN      A       $IP_PUBLIK
www     IN      A       $IP_PUBLIK
mail    IN      A       $IP_PUBLIK

; MX & TXT (Anti-Spam)
@       IN      MX 10   mail.$DOMAIN.
@       IN      TXT     "v=spf1 a mx ip4:$IP_PUBLIK -all"
EOF

# 6. MEMBUAT DATABASE ZONA REVERSE
print_status "Membuat Reverse Zone File..."
cat > /etc/bind/db.$IP1.$IP2.$IP3 << EOF
\$TTL    604800
@       IN      SOA     $NS1.$DOMAIN. $ADMIN_EMAIL (
                              $SERIAL
                              604800
                              86400
                              2419200
                              604800 )

@       IN      NS      $NS1.$DOMAIN.
@       IN      NS      $NS2.$DOMAIN.

; PTR Records
$IP4    IN      PTR     $DOMAIN.
$IP4    IN      PTR     $NS1.$DOMAIN.
$IP4    IN      PTR     $NS2.$DOMAIN.
EOF

# 7. IZIN & LOGGING
print_status "Mengatur Permission & Firewall..."
mkdir -p /var/log/named
chown bind:bind /var/log/named /etc/bind/db.*
chmod 644 /etc/bind/db.*

# Buka Port Firewall (UFW) jika terpasang
if command -v ufw > /dev/null; then
    ufw allow 53/tcp > /dev/null
    ufw allow 53/udp > /dev/null
fi

# 8. VERIFIKASI & RESTART
print_status "Verifikasi Konfigurasi..."
named-checkconf /etc/bind/named.conf.options || print_error "Cek Options Gagal"
named-checkconf /etc/bind/named.conf.local || print_error "Cek Local Gagal"
named-checkzone $DOMAIN /etc/bind/db.$DOMAIN || print_error "Cek Zone Gagal"

systemctl restart bind9
systemctl enable bind9

echo "------------------------------------------------"
echo " KONFIGURASI SELESAI!"
echo "------------------------------------------------"
echo "Langkah Terakhir (WAJIB):"
echo "1. Login ke Registrar Domain (GoDaddy/Namecheap/dll)."
echo "2. Buat 'Glue Records' atau 'Hostname' untuk:"
echo "   $NS1.$DOMAIN -> $IP_PUBLIK"
echo "   $NS2.$DOMAIN -> $IP_PUBLIK"
echo "3. Ubah Name Server domain Anda menjadi:"
echo "   $NS1.$DOMAIN dan $NS2.$DOMAIN"
echo "------------------------------------------------"
