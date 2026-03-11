#!/bin/bash

# Script Auto Konfigurasi BIND9 Public DNS Server untuk Debian 10
# WARNING: Jalankan script ini sebagai root!
# Pastikan sudah memiliki IP Publik dan Domain yang sudah diarahkan NS record-nya

# ==============================================
# VARIABEL KONFIGURASI - UBAH SESUAI KEBUTUHAN!
# ==============================================
DOMAIN="contoh.com"           # Ganti dengan domain Anda
IP_PUBLIK="103.10.50.100"     # Ganti dengan IP publik server Anda
NS1="ns1"                      # Prefix untuk nameserver 1
NS2="ns2"                      # Prefix untuk nameserver 2
ADMIN_EMAIL="admin.contoh.com." # Email admin (ganti @ dengan titik)
SERVER_IP_PRIVATE=$(hostname -I | awk '{print $1}') # IP private server (otomatis)

# ==============================================
# FUNGSI PRINT COLOR
# ==============================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}[✓] $1${NC}"
}

print_error() {
    echo -e "${RED}[✗] $1${NC}"
}

print_info() {
    echo -e "${YELLOW}[i] $1${NC}"
}

print_line() {
    echo "================================================"
}

# ==============================================
# CEK ROOT PRIVILEGES
# ==============================================
print_line
echo "BIND9 PUBLIC DNS CONFIGURATION SCRIPT"
print_line

if [[ $EUID -ne 0 ]]; then
   print_error "Script ini harus dijalankan sebagai root!"
   exit 1
fi

print_success "Menjalankan script sebagai root"

# ==============================================
# KONFIRMASI KONFIGURASI
# ==============================================
echo ""
print_info "Konfigurasi yang akan digunakan:"
echo "Domain              : $DOMAIN"
echo "IP Publik           : $IP_PUBLIK"
echo "IP Private          : $SERVER_IP_PRIVATE"
echo "Nameserver 1        : $NS1.$DOMAIN"
echo "Nameserver 2        : $NS2.$DOMAIN"
echo "Email Admin         : $ADMIN_EMAIL"
echo ""

read -p "Apakah konfigurasi sudah benar? (y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_error "Script dibatalkan. Silakan edit variabel di awal script."
    exit 1
fi

# ==============================================
# UPDATE SYSTEM & INSTALL BIND9
# ==============================================
print_info "Mengupdate sistem dan menginstall BIND9..."
apt update && apt upgrade -y

if apt install bind9 bind9utils bind9-doc dnsutils -y; then
    print_success "BIND9 berhasil diinstall"
else
    print_error "Gagal menginstall BIND9"
    exit 1
fi

# ==============================================
# BACKUP KONFIGURASI ASLI
# ==============================================
print_info "Membackup konfigurasi asli..."
cp /etc/bind/named.conf.options /etc/bind/named.conf.options.backup 2>/dev/null
cp /etc/bind/named.conf.local /etc/bind/named.conf.local.backup 2>/dev/null
print_success "Backup selesai"

# ==============================================
# KONFIGURASI NAMED.CONF.OPTIONS
# ==============================================
print_info "Mengkonfigurasi named.conf.options..."

cat > /etc/bind/named.conf.options << 'EOF'
options {
        directory "/var/cache/bind";
        
        // Matikan recursion untuk keamanan DNS publik
        recursion no;
        
        // Izinkan semua orang melakukan query
        allow-query { any; };
        
        // Blokir transfer zona untuk keamanan
        allow-transfer { none; };
        
        // Listen pada semua interface
        listen-on port 53 { any; };
        listen-on-v6 { any; };
        
        // Forwarders (Google DNS & Cloudflare)
        forwarders {
                8.8.8.8;
                8.8.4.4;
                1.1.1.1;
                1.0.0.1;
        };
        
        // Security options
        allow-recursion { none; };
        dnssec-validation auto;
        auth-nxdomain no;    # Conform to RFC1035
        
        // Rate limiting untuk mencegah DDoS
        rate-limit {
                responses-per-second 10;
                window 5;
        };
};

// Logging untuk monitoring (opsional)
logging {
        channel default_log {
                file "/var/log/named/default.log" versions 3 size 2m;
                severity info;
                print-time yes;
                print-severity yes;
                print-category yes;
        };
        
        category default { default_log; };
        category queries { default_log; };
        category security { default_log; };
};
EOF

print_success "named.conf.options selesai"

# ==============================================
# KONFIGURASI NAMED.CONF.LOCAL
# ==============================================
print_info "Mengkonfigurasi named.conf.local..."

# Ekstrak oktet IP untuk reverse zone
IP1=$(echo $IP_PUBLIK | cut -d'.' -f1)
IP2=$(echo $IP_PUBLIK | cut -d'.' -f2)
IP3=$(echo $IP_PUBLIK | cut -d'.' -f3)
IP4=$(echo $IP_PUBLIK | cut -d'.' -f4)

cat > /etc/bind/named.conf.local << EOF
//
// Zona Forward untuk domain $DOMAIN
//
zone "$DOMAIN" {
    type master;
    file "/etc/bind/db.$DOMAIN";
    allow-query { any; };
    allow-transfer { none; };
    notify yes;
};

//
// Zona Reverse untuk IP $IP_PUBLIK
//
zone "$IP3.$IP2.$IP1.in-addr.arpa" {
    type master;
    file "/etc/bind/db.$IP1.$IP2.$IP3";
    allow-query { any; };
    allow-transfer { none; };
};
EOF

print_success "named.conf.local selesai"

# ==============================================
# MEMBUAT FILE ZONA FORWARD
# ==============================================
print_info "Membuat file zona forward..."

# Hitung serial number (YYYYMMDD01)
SERIAL=$(date +%Y%m%d01)

cat > /etc/bind/db.$DOMAIN << EOF
; BIND data file untuk domain $DOMAIN
; File ini dikelola secara otomatis oleh script
; Jangan lupa untuk menaikkan SERIAL jika ada perubahan manual!

\$TTL    604800
@       IN      SOA     $NS1.$DOMAIN. $ADMIN_EMAIL (
                              $SERIAL         ; Serial (auto-generated)
                              604800          ; Refresh (1 minggu)
                              86400           ; Retry (1 hari)
                              2419200         ; Expire (4 minggu)
                              604800 )        ; Negative Cache TTL (1 minggu)

; Name Servers
@       IN      NS      $NS1.$DOMAIN.
@       IN      NS      $NS2.$DOMAIN.

; A Records untuk Name Server (Glue Records)
$NS1    IN      A       $IP_PUBLIK
$NS2    IN      A       $IP_PUBLIK

; A Records untuk domain utama
@       IN      A       $IP_PUBLIK
www     IN      A       $IP_PUBLIK
mail    IN      A       $IP_PUBLIK
ftp     IN      A       $IP_PUBLIK

; CNAME Records
pop     IN      CNAME   mail.$DOMAIN.
smtp    IN      CNAME   mail.$DOMAIN.

; MX Records (Mail Exchanger)
@       IN      MX 10   mail.$DOMAIN.

; TXT Records (SPF untuk email)
@       IN      TXT     "v=spf1 mx a:$DOMAIN +all"
mail    IN      TXT     "v=spf1 a -all"

; AAAA Records (IPv6) - uncomment jika punya IPv6
; @       IN      AAAA    your_ipv6_address
; www     IN      AAAA    your_ipv6_address
EOF

print_success "File zona forward selesai"

# ==============================================
# MEMBUAT FILE ZONA REVERSE
# ==============================================
print_info "Membuat file zona reverse..."

cat > /etc/bind/db.$IP1.$IP2.$IP3 << EOF
; Reverse zone untuk $IP1.$IP2.$IP3.0/24
\$TTL    604800
@       IN      SOA     $NS1.$DOMAIN. $ADMIN_EMAIL (
                              $SERIAL         ; Serial (auto-generated)
                              604800          ; Refresh
                              86400           ; Retry
                              2419200         ; Expire
                              604800 )        ; Negative Cache TTL

; Name Servers
@       IN      NS      $NS1.$DOMAIN.
@       IN      NS      $NS2.$DOMAIN.

; PTR Records
$IP4    IN      PTR     $DOMAIN.
$IP4    IN      PTR     $NS1.$DOMAIN.
$IP4    IN      PTR     $NS2.$DOMAIN.
$IP4    IN      PTR     www.$DOMAIN.
$IP4    IN      PTR     mail.$DOMAIN.
EOF

print_success "File zona reverse selesai"

# ==============================================
# SET PERMISSION
# ==============================================
print_info "Mengatur permission file..."
chown bind:bind /etc/bind/db.$DOMAIN 2>/dev/null
chown bind:bind /etc/bind/db.$IP1.$IP2.$IP3 2>/dev/null
chmod 644 /etc/bind/db.$DOMAIN 2>/dev/null
chmod 644 /etc/bind/db.$IP1.$IP2.$IP3 2>/dev/null

# Buat direktori log
mkdir -p /var/log/named
chown bind:bind /var/log/named 2>/dev/null
chmod 755 /var/log/named 2>/dev/null

print_success "Permission selesai"

# ==============================================
# VERIFIKASI KONFIGURASI
# ==============================================
print_info "Memverifikasi konfigurasi BIND9..."

# Cek named.conf.options
if named-checkconf /etc/bind/named.conf.options; then
    print_success "named.conf.options valid"
else
    print_error "named.conf.options tidak valid!"
    exit 1
fi

# Cek named.conf.local
if named-checkconf /etc/bind/named.conf.local; then
    print_success "named.conf.local valid"
else
    print_error "named.conf.local tidak valid!"
    exit 1
fi

# Cek zona forward
if named-checkzone $DOMAIN /etc/bind/db.$DOMAIN; then
    print_success "Zona forward valid"
else
    print_error "Zona forward tidak valid!"
    exit 1
fi

# Cek zona reverse
REVERSE_ZONE="$IP3.$IP2.$IP1.in-addr.arpa"
if named-checkzone $REVERSE_ZONE /etc/bind/db.$IP1.$IP2.$IP3; then
    print_success "Zona reverse valid"
else
    print_error "Zona reverse tidak valid!"
    exit 1
fi

# ==============================================
# RESTART BIND9
# ==============================================
print_info "Merestart BIND9..."
systemctl restart bind9

if systemctl is-active --quiet bind9; then
    print_success "BIND9 berhasil direstart"
else
    print_error "BIND9 gagal direstart!"
    systemctl status bind9 --no-pager
    exit 1
fi

systemctl enable bind9 > /dev/null 2>&1
print_success "BIND9 diatur untuk auto-start"

# ==============================================
# KONFIGURASI FIREWALL
# ==============================================
print_info "Mengkonfigurasi firewall..."

# Cek apakah ufw aktif
if command -v ufw > /dev/null 2>&1; then
    ufw allow 53/tcp > /dev/null 2>&1
    ufw allow 53/udp > /dev/null 2>&1
    ufw reload > /dev/null 2>&1
    print_success "Firewall UFW dikonfigurasi"
else
    # Alternatif iptables jika ufw tidak ada
    # Cek apakah iptables tersedia
    if command -v iptables > /dev/null 2>&1; then
        iptables -C INPUT -p udp --dport 53 -j ACCEPT 2>/dev/null || iptables -A INPUT -p udp --dport 53 -j ACCEPT
        iptables -C INPUT -p tcp --dport 53 -j ACCEPT 2>/dev/null || iptables -A INPUT -p tcp --dport 53 -j ACCEPT
        
        # Simpan iptables rules
        if command -v iptables-save > /dev/null 2>&1; then
            # Coba simpan dengan berbagai cara
            iptables-save > /etc/iptables/rules.v4 2>/dev/null || \
            iptables-save > /etc/iptables.up.rules 2>/dev/null || \
            echo "iptables rules tidak disimpan permanen"
        fi
        print_success "Iptables dikonfigurasi"
    else
        print_info "Iptables tidak ditemukan, lewati konfigurasi firewall"
    fi
fi

# ==============================================
# TESTING DNS
# ==============================================
print_line
echo "TESTING DNS SERVER"
print_line

# Test dari lokal
print_info "Testing dari localhost..."
if dig @localhost $DOMAIN +short | grep -q $IP_PUBLIK; then
    print_success "Query lokal berhasil: $(dig @localhost $DOMAIN +short)"
else
    print_error "Query lokal gagal!"
fi

# Test NS record
print_info "Testing NS record..."
NS_TEST=$(dig @localhost $DOMAIN NS +short | head -1)
if [[ -n "$NS_TEST" ]]; then
    print_success "NS record: $NS_TEST"
else
    print_error "NS record tidak ditemukan!"
fi

# Test reverse DNS
print_info "Testing reverse DNS..."
PTR_TEST=$(dig @localhost -x $IP_PUBLIK +short | head -1)
if [[ -n "$PTR_TEST" ]]; then
    print_success "Reverse DNS: $PTR_TEST"
else
    print_error "Reverse DNS gagal!"
fi

# ==============================================
# INFORMASI FINAL
# ==============================================
print_line
echo "KONFIGURASI BIND9 SELESAI!"
print_line
echo ""
print_success "DNS Server Anda sudah siap digunakan untuk domain $DOMAIN"
echo ""
print_info "Informasi Penting:"
echo "1. Pastikan NS record di registrar domain Anda sudah diarahkan ke:"
echo "   - $NS1.$DOMAIN -> $IP_PUBLIK"
echo "   - $NS2.$DOMAIN -> $IP_PUBLIK"
echo ""
echo "2. DNS Server sudah aktif di port 53 (TCP/UDP)"
echo ""
echo "3. Untuk testing dari internet, gunakan perintah:"
echo "   dig @$IP_PUBLIK $DOMAIN"
echo "   nslookup $DOMAIN $IP_PUBLIK"
echo ""
echo "4. Lokasi file konfigurasi:"
echo "   - Options    : /etc/bind/named.conf.options"
echo "   - Local      : /etc/bind/named.conf.local"
echo "   - Forward    : /etc/bind/db.$DOMAIN"
echo "   - Reverse    : /etc/bind/db.$IP1.$IP2.$IP3"
echo ""
echo "5. Log file: /var/log/named/default.log"
echo ""
echo "6. Cek status BIND9: systemctl status bind9"
echo ""
print_info "Jangan lupa untuk menaikkan SERIAL number di file zona"
print_info "setiap kali Anda mengubah record DNS secara manual!"
print_line

# Tampilkan informasi IP
echo ""
print_info "Ringkasan Konfigurasi:"
echo "Domain            : $DOMAIN"
echo "IP Publik         : $IP_PUBLIK"
echo "Nameserver        : $NS1.$DOMAIN, $NS2.$DOMAIN"
echo "Serial Number     : $SERIAL"
echo ""
