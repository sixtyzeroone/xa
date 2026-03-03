#!/usr/bin/env bash
# =============================================================================
# LeakOS Linux Installer - FIXED & FULL VERSION (Terminal Step-by-Step)
# =============================================================================
# Versi dengan tampilan lebih rapi menggunakan echo -e + warna ANSI
# Deteksi support warna otomatis
# FIXED: Unbound variable ROOT_UUID di line 658

set -euo pipefail

# =============================================================================
# DETEKSI WARNA (agar aman di terminal yang tidak support)
# =============================================================================
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' CYAN='' BOLD='' NC=''
fi

clear

echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                  L E A K O S   L I N U X                   ║${NC}"
echo -e "${CYAN}║                                                            ║${NC}"
echo -e "${CYAN}║     Unleashed Freedom • Privacy First • Indonesian Root    ║${NC}"
echo -e "${CYAN}║       Custom LFS-based Distro • Pentest & Developer Ready  ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo -e ""
echo -e "           Installer Terminal - Versi Aman & User-Friendly"
echo -e "                    (Tekan Ctrl+C kapan saja untuk batal)"
echo -e ""
echo -e "${YELLOW}Tekan Enter untuk memulai instalasi...${NC}"
read -r dummy

# =============================================================================
# ROOT CHECK
# =============================================================================
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}${BOLD}ERROR: Harus dijalankan sebagai root.${NC}"
    exit 1
fi

# =============================================================================
# DEPENDENCY CHECK
# =============================================================================
echo -e "${BLUE}Memeriksa dependensi...${NC}"
for cmd in lsblk cfdisk mkfs.ext4 rsync grub-install grub-mkconfig blkid git partprobe; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}ERROR: Tidak ditemukan perintah: $cmd${NC}"
        echo -e "Pastikan paket yang dibutuhkan sudah terinstall di live environment."
        exit 1
    fi
done
echo -e "${GREEN}Semua dependensi OK.${NC}"
echo -e ""

# =============================================================================
# PERINGATAN AWAL
# =============================================================================
echo -e "${RED}${BOLD}┌────────────────────────────────────────────────────────────┐${NC}"
echo -e "${RED}│  ${BOLD}SEMUA DATA DI DISK TARGET AKAN DIHAPUS SELAMANYA!${NC}         ${RED}│${NC}"
echo -e "${RED}│                                                            │${NC}"
echo -e "${RED}│  • Hanya gunakan pada mesin kosong atau VM testing         │${NC}"
echo -e "${RED}│  • Tidak ada backup otomatis                               │${NC}"
echo -e "${RED}│  • Tidak ada UNDO setelah konfirmasi                       │${NC}"
echo -e "${RED}└────────────────────────────────────────────────────────────┘${NC}"
echo -e ""
echo -en "${YELLOW}Lanjut instalasi? (ketik 'yes' lalu Enter) : ${NC}"
read -r confirm
if [[ "${confirm,,}" != "yes" ]]; then
    echo -e "${GREEN}Instalasi dibatalkan oleh pengguna.${NC}"
    exit 0
fi

# =============================================================================
# DISK SELECTION
# =============================================================================
echo -e ""
echo -e "${BLUE}Disk yang terdeteksi (hanya hard disk fisik):${NC}"
echo "------------------------------------------------------------"
disk_list=()
i=1
while IFS= read -r line; do
    name=$(echo "$line" | awk '{print $1}')
    size=$(echo "$line" | awk '{print $2}')
    model=$(echo "$line" | awk '{$1=$2=""; print substr($0,3)}' | xargs || echo "Unknown")
    printf " %2d) /dev/%-6s (%6s) - %s\n" "$i" "$name" "$size" "$model"
    disk_list+=("/dev/$name")
    ((i++))
done < <(lsblk -dno NAME,SIZE,MODEL | awk '$1~/^[a-z]+$/ && $1!="loop" && $1!="sr" && $1!="zram"')

if [ ${#disk_list[@]} -eq 0 ]; then
    echo -e "${RED}ERROR: Tidak ada disk fisik yang terdeteksi.${NC}"
    exit 1
fi

if [ ${#disk_list[@]} -eq 1 ]; then
    echo -e "${GREEN}(Hanya 1 disk terdeteksi → otomatis terpilih)${NC}"
    TARGET_DISK="${disk_list[0]}"
else
    echo -e ""
    echo -en "${YELLOW}Pilih nomor disk target (1-${#disk_list[@]}) : ${NC}"
    read -r disk_num
    if ! [[ "$disk_num" =~ ^[0-9]+$ ]] || [ "$disk_num" -lt 1 ] || [ "$disk_num" -gt "${#disk_list[@]}" ]; then
        echo -e "${RED}ERROR: Nomor tidak valid.${NC}"
        exit 1
    fi
    TARGET_DISK="${disk_list[$((disk_num-1))]}"
fi

echo -e ""
echo -e "Disk terpilih : ${CYAN}${TARGET_DISK}${NC}"
echo -e "${RED}SEMUA DATA AKAN HILANG!${NC}"
echo -en "${YELLOW}Yakin ingin lanjut? (ketik 'yes') : ${NC}"
read -r confirm_disk
if [[ "${confirm_disk,,}" != "yes" ]]; then
    echo -e "${GREEN}Dibatalkan.${NC}"
    exit 0
fi

# =============================================================================
# PARTITIONING
# =============================================================================
echo -e ""
echo -e "${BLUE}Langkah 1: Partisi disk${NC}"
echo "Membuka cfdisk untuk $TARGET_DISK"
echo "Rekomendasi: tabel 'dos' (MBR), buat minimal 1 partisi"
echo -e ""
echo -en "${YELLOW}Siap membuka cfdisk? (ketik 'yes') : ${NC}"
read -r confirm_cfdisk
if [[ "${confirm_cfdisk,,}" != "yes" ]]; then
    echo -e "${GREEN}Dibatalkan sebelum partisi.${NC}"
    exit 0
fi

cfdisk "$TARGET_DISK"

echo -e "Partisi selesai. Memperbarui tabel partisi..."
partprobe "$TARGET_DISK" || true
sync
sleep 3

# =============================================================================
# DETECT & FORMAT PARTISI OTOMATIS
# =============================================================================
echo -e ""
echo -e "${BLUE}Mendeteksi partisi di $TARGET_DISK...${NC}"
echo "Partisi yang ditemukan:"
lsblk -f "$TARGET_DISK" | grep -v "loop\|sr" || true

mapfile -t all_partitions < <(lsblk -ln -o NAME,TYPE "$TARGET_DISK" | awk '$2=="part" {print "/dev/"$1}')

if [ ${#all_partitions[@]} -eq 0 ]; then
    echo -e "${RED}ERROR: Tidak ada partisi ditemukan di $TARGET_DISK${NC}"
    exit 1
fi

mapfile -t ext4_parts < <(lsblk -ln -o NAME,FSTYPE "$TARGET_DISK" | awk '$2=="ext4" {print "/dev/"$1}')

if [ ${#ext4_parts[@]} -eq 0 ]; then
    echo -e ""
    echo -e "${YELLOW}⚠️ TIDAK ADA PARTISI EXT4 YANG DITEMUKAN!${NC}"
    echo "Pilih tindakan:"
    echo " 1) Format partisi pertama sebagai ext4 (otomatis)"
    echo " 2) Pilih partisi manual untuk diformat"
    echo " 3) Batalkan instalasi"
    echo -en "Pilihan (1/2/3): "
    read -r format_choice

    case $format_choice in
        1)
            PART_TO_FORMAT="${all_partitions[0]}"
            echo -e "Memformat ${CYAN}$PART_TO_FORMAT${NC} sebagai ext4..."
            mkfs.ext4 -F "$PART_TO_FORMAT"
            ROOT_PART="$PART_TO_FORMAT"
            ;;
        2)
            echo ""
            echo "Partisi tersedia:"
            for idx in "${!all_partitions[@]}"; do
                size=$(lsblk -dno SIZE "${all_partitions[idx]}" 2>/dev/null || echo "?")
                echo " $((idx+1))) ${all_partitions[idx]} ($size)"
            done
            echo -en "Pilih nomor partisi untuk root (1-${#all_partitions[@]}) : "
            read -r part_num
            if ! [[ "$part_num" =~ ^[0-9]+$ ]] || [ "$part_num" -lt 1 ] || [ "$part_num" -gt "${#all_partitions[@]}" ]; then
                echo -e "${RED}ERROR: Pilihan tidak valid.${NC}"
                exit 1
            fi
            PART_TO_FORMAT="${all_partitions[$((part_num-1))]}"
            echo -e "Memformat ${CYAN}$PART_TO_FORMAT${NC} sebagai ext4..."
            mkfs.ext4 -F "$PART_TO_FORMAT"
            ROOT_PART="$PART_TO_FORMAT"
            ;;
        3)
            echo -e "${GREEN}Instalasi dibatalkan.${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Pilihan tidak valid. Membatalkan instalasi.${NC}"
            exit 1
            ;;
    esac
else
    if [ ${#ext4_parts[@]} -eq 1 ]; then
        echo ""
        echo "Ditemukan 1 partisi ext4: ${CYAN}${ext4_parts[0]}${NC}"
        echo -en "Gunakan partisi ini? (yes) atau format ulang? (ketik 'format') : "
        read -r use_existing

        if [[ "${use_existing,,}" == "format" ]]; then
            echo -e "Memformat ${CYAN}${ext4_parts[0]}${NC}..."
            mkfs.ext4 -F "${ext4_parts[0]}"
            ROOT_PART="${ext4_parts[0]}"
        else
            ROOT_PART="${ext4_parts[0]}"
            echo -e "Menggunakan partisi existing: ${CYAN}$ROOT_PART${NC}"
        fi
    else
        echo ""
        echo "Ditemukan beberapa partisi ext4:"
        for idx in "${!ext4_parts[@]}"; do
            size=$(lsblk -dno SIZE "${ext4_parts[idx]}" 2>/dev/null || echo "?")
            echo " $((idx+1))) ${ext4_parts[idx]} ($size)"
        done
        echo ""
        echo "Pilih opsi:"
        echo " a) Pilih partisi existing"
        echo " b) Format ulang partisi tertentu"
        echo -en "Pilihan (a/b) atau nomor partisi: "
        read -r part_option

        if [[ "${part_option,,}" == "a" ]]; then
            echo -en "Pilih nomor partisi (1-${#ext4_parts[@]}) : "
            read -r part_num
            if ! [[ "$part_num" =~ ^[0-9]+$ ]] || [ "$part_num" -lt 1 ] || [ "$part_num" -gt "${#ext4_parts[@]}" ]; then
                echo -e "${RED}ERROR: Pilihan tidak valid.${NC}"
                exit 1
            fi
            ROOT_PART="${ext4_parts[$((part_num-1))]}"
            echo -e "Menggunakan partisi: ${CYAN}$ROOT_PART${NC}"
        elif [[ "${part_option,,}" == "b" ]]; then
            echo -en "Pilih nomor partisi yang akan diformat (1-${#ext4_parts[@]}) : "
            read -r part_num
            if ! [[ "$part_num" =~ ^[0-9]+$ ]] || [ "$part_num" -lt 1 ] || [ "$part_num" -gt "${#ext4_parts[@]}" ]; then
                echo -e "${RED}ERROR: Pilihan tidak valid.${NC}"
                exit 1
            fi
            PART_TO_FORMAT="${ext4_parts[$((part_num-1))]}"
            echo -e "Memformat ${CYAN}$PART_TO_FORMAT${NC}..."
            mkfs.ext4 -F "$PART_TO_FORMAT"
            ROOT_PART="$PART_TO_FORMAT"
        elif [[ "$part_option" =~ ^[0-9]+$ ]] && [ "$part_option" -ge 1 ] && [ "$part_option" -le "${#ext4_parts[@]}" ]; then
            ROOT_PART="${ext4_parts[$((part_option-1))]}"
            echo -e "Menggunakan partisi: ${CYAN}$ROOT_PART${NC}"
        else
            echo -e "${RED}ERROR: Pilihan tidak valid.${NC}"
            exit 1
        fi
    fi
fi

echo -e ""
echo -e "Partisi root: ${CYAN}$ROOT_PART${NC}"
echo -e ""

# =============================================================================
# INPUT USER & KONFIGURASI DASAR
# =============================================================================
echo -e "${BLUE}Konfigurasi dasar sistem${NC}"
echo ""
echo -n "Username (default: leakos): "
read -r USERNAME
USERNAME=${USERNAME:-leakos}

echo -n "Hostname (default: leakos): "
read -r HOSTNAME
HOSTNAME=${HOSTNAME:-leakos}

echo -n "Password untuk user $USERNAME: "
read -s PASSWORD
echo ""
echo -n "Konfirmasi password: "
read -s PASSWORD2
echo ""
if [ "$PASSWORD" != "$PASSWORD2" ] || [ -z "$PASSWORD" ]; then
    echo -e "${RED}ERROR: Password tidak cocok atau kosong.${NC}"
    exit 1
fi

# =============================================================================
# TIMEZONE SELECTION - VERSI PINTAR
# =============================================================================
get_timezone() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                    SETTING ZONA WAKTU                      ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Deteksi otomatis berdasarkan IP/lokasi (jika ada internet)
    if ping -c 1 google.com >/dev/null 2>&1; then
        echo -e "${CYAN}Mendeteksi zona waktu otomatis...${NC}"
        AUTO_TZ=$(curl -s http://ip-api.com/line?fields=timezone 2>/dev/null || echo "")
        
        if [ -n "$AUTO_TZ" ] && [ -f "/usr/share/zoneinfo/$AUTO_TZ" ]; then
            echo -e "${GREEN}✅ Terdeteksi: $AUTO_TZ${NC}"
            echo -n "Gunakan zona ini? (Y/n): "
            read -r use_auto
            if [[ "$use_auto" == "y" ]] || [[ "$use_auto" == "Y" ]] || [[ -z "$use_auto" ]]; then
                TIMEZONE="$AUTO_TZ"
                echo -e "${GREEN}✅ Timezone: $TIMEZONE${NC}"
                return
            fi
        fi
    fi

    # Pilihan manual
    echo ""
    echo "Pilih berdasarkan region:"
    echo " 1) Asia (Indonesia, Singapore, Jepang, dll)"
    echo " 2) Australia & Pasifik"
    echo " 3) Eropa"
    echo " 4) Amerika"
    echo " 5) Afrika"
    echo " 6) UTC / GMT"
    echo " 7) Manual input"
    echo ""

    read -r region

    case $region in
        1) 
            echo ""
            echo "Pilih kota di Asia:"
            echo " 1) Jakarta      (WIB)"
            echo " 2) Makassar     (WITA)"
            echo " 3) Jayapura     (WIT)"
            echo " 4) Singapore"
            echo " 5) Kuala Lumpur"
            echo " 6) Bangkok"
            echo " 7) Tokyo"
            echo " 8) Seoul"
            echo " 9) Shanghai"
            echo "10) Manila"
            echo "11) Taipei"
            echo "12) Hong Kong"
            echo -n "Pilih: "
            read -r city
            case $city in
                1) TIMEZONE="Asia/Jakarta" ;;
                2) TIMEZONE="Asia/Makassar" ;;
                3) TIMEZONE="Asia/Jayapura" ;;
                4) TIMEZONE="Asia/Singapore" ;;
                5) TIMEZONE="Asia/Kuala_Lumpur" ;;
                6) TIMEZONE="Asia/Bangkok" ;;
                7) TIMEZONE="Asia/Tokyo" ;;
                8) TIMEZONE="Asia/Seoul" ;;
                9) TIMEZONE="Asia/Shanghai" ;;
                10) TIMEZONE="Asia/Manila" ;;
                11) TIMEZONE="Asia/Taipei" ;;
                12) TIMEZONE="Asia/Hong_Kong" ;;
                *) TIMEZONE="Asia/Jakarta" ;;
            esac
            ;;
        2)
            echo ""
            echo "Pilih kota di Australia/Pasifik:"
            echo " 1) Perth"
            echo " 2) Darwin"
            echo " 3) Brisbane"
            echo " 4) Sydney"
            echo " 5) Melbourne"
            echo " 6) Guam"
            echo -n "Pilih: "
            read -r city
            case $city in
                1) TIMEZONE="Australia/Perth" ;;
                2) TIMEZONE="Australia/Darwin" ;;
                3) TIMEZONE="Australia/Brisbane" ;;
                4) TIMEZONE="Australia/Sydney" ;;
                5) TIMEZONE="Australia/Melbourne" ;;
                6) TIMEZONE="Pacific/Guam" ;;
                *) TIMEZONE="Australia/Sydney" ;;
            esac
            ;;
        3)
            echo ""
            echo "Pilih kota di Eropa:"
            echo " 1) London"
            echo " 2) Paris"
            echo " 3) Berlin"
            echo " 4) Amsterdam"
            echo " 5) Rome"
            echo " 6) Madrid"
            echo -n "Pilih: "
            read -r city
            case $city in
                1) TIMEZONE="Europe/London" ;;
                2) TIMEZONE="Europe/Paris" ;;
                3) TIMEZONE="Europe/Berlin" ;;
                4) TIMEZONE="Europe/Amsterdam" ;;
                5) TIMEZONE="Europe/Rome" ;;
                6) TIMEZONE="Europe/Madrid" ;;
                *) TIMEZONE="Europe/London" ;;
            esac
            ;;
        4)
            echo ""
            echo "Pilih zona di Amerika:"
            echo " 1) New York (Eastern)"
            echo " 2) Chicago (Central)"
            echo " 3) Denver (Mountain)"
            echo " 4) Los Angeles (Pacific)"
            echo " 5) Anchorage"
            echo " 6) Honolulu"
            echo -n "Pilih: "
            read -r city
            case $city in
                1) TIMEZONE="America/New_York" ;;
                2) TIMEZONE="America/Chicago" ;;
                3) TIMEZONE="America/Denver" ;;
                4) TIMEZONE="America/Los_Angeles" ;;
                5) TIMEZONE="America/Anchorage" ;;
                6) TIMEZONE="Pacific/Honolulu" ;;
                *) TIMEZONE="America/New_York" ;;
            esac
            ;;
        5)
            echo ""
            echo "Pilih kota di Afrika:"
            echo " 1) Cairo"
            echo " 2) Johannesburg"
            echo " 3) Lagos"
            echo " 4) Nairobi"
            echo -n "Pilih: "
            read -r city
            case $city in
                1) TIMEZONE="Africa/Cairo" ;;
                2) TIMEZONE="Africa/Johannesburg" ;;
                3) TIMEZONE="Africa/Lagos" ;;
                4) TIMEZONE="Africa/Nairobi" ;;
                *) TIMEZONE="Africa/Johannesburg" ;;
            esac
            ;;
        6)
            TIMEZONE="UTC"
            ;;
        7)
            echo -n "Masukkan zona waktu (Contoh: Asia/Jakarta): "
            read -r TIMEZONE
            ;;
        *)
            TIMEZONE="Asia/Jakarta"
            ;;
    esac

    # Validasi
    if [ ! -f "/usr/share/zoneinfo/$TIMEZONE" ]; then
        echo -e "${YELLOW}⚠️  Zona '$TIMEZONE' tidak valid, menggunakan Asia/Jakarta${NC}"
        TIMEZONE="Asia/Jakarta"
    fi

    echo -e "${GREEN}✅ Timezone: $TIMEZONE${NC}"
    echo ""
}

# Panggil fungsi
get_timezone

# =============================================================================
# KEYBOARD LAYOUT SELECTION - VERSI SEDERHANA
# =============================================================================
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                   PILIH LAYOUT KEYBOARD                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Tampilan grid 4 kolom dengan border sederhana
echo "┌──────┬────────────┬──────┬────────────┬──────┬────────────┬──────┬────────────┐"
echo "│ No   │ Layout     │ No   │ Layout     │ No   │ Layout     │ No   │ Layout     │"
echo "├──────┼────────────┼──────┼────────────┼──────┼────────────┼──────┼────────────┤"
echo "│ 1    │ us         │ 2    │ id         │ 3    │ fr         │ 4    │ de         │"
echo "│ 5    │ es         │ 6    │ it         │ 7    │ pt         │ 8    │ gb         │"
echo "│ 9    │ se         │ 10   │ no         │ 11   │ dk         │ 12   │ fi         │"
echo "│ 13   │ pl         │ 14   │ ru         │ 15   │ ua         │ 16   │ cz         │"
echo "│ 17   │ tr         │ 18   │ cn         │ 19   │ jp         │ 20   │ kr         │"
echo "│ 21   │ vn         │ 22   │ br         │ 23   │ ph         │ 24   │ sg         │"
echo "├──────┼────────────┼──────┼────────────┼──────┼────────────┼──────┼────────────┤"
echo "│ 25   │ manual     │      │            │      │            │      │            │"
echo "└──────┴────────────┴──────┴────────────┴──────┴────────────┴──────┴────────────┘"
echo ""

# Mapping array asosiatif
declare -A KEYMAPS=(
    [1]="us"  [2]="id"  [3]="fr"  [4]="de"  [5]="es"
    [6]="it"  [7]="pt"  [8]="gb"  [9]="se"  [10]="no"
    [11]="dk" [12]="fi" [13]="pl" [14]="ru" [15]="ua"
    [16]="cz" [17]="tr" [18]="cn" [19]="jp" [20]="kr"
    [21]="vn" [22]="br" [23]="ph" [24]="sg"
)

while true; do
    echo -en "${YELLOW}Pilih nomor (1-25, default: 1): ${NC}"
    read -r kb_choice
    kb_choice=${kb_choice:-1}
    
    # Validasi input numerik
    if ! [[ "$kb_choice" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}❌ Harus angka!${NC}"
        continue
    fi
    
    # Validasi range
    if [ "$kb_choice" -lt 1 ] || [ "$kb_choice" -gt 25 ]; then
        echo -e "${RED}❌ Pilih antara 1-25!${NC}"
        continue
    fi
    
    # Handle pilihan
    if [ "$kb_choice" -eq 25 ]; then
        # Manual input
        echo -n "Masukkan keymap manual (contoh: de, fr, id): "
        read -r KEYBOARD_LAYOUT
        
        # Validasi tidak kosong
        if [ -z "$KEYBOARD_LAYOUT" ]; then
            echo -e "${RED}❌ Keymap tidak boleh kosong!${NC}"
            continue
        fi
        
        # Validasi format sederhana
        if [[ ! "$KEYBOARD_LAYOUT" =~ ^[a-zA-Z]{2,3}$ ]]; then
            echo -e "${YELLOW}⚠️  Format tidak biasa (biasanya 2-3 huruf). Lanjut? (y/n): ${NC}"
            read -r confirm_manual
            if [[ "$confirm_manual" != "y" ]] && [[ "$confirm_manual" != "Y" ]]; then
                continue
            fi
        fi
    else
        # Ambil dari mapping
        KEYBOARD_LAYOUT="${KEYMAPS[$kb_choice]}"
    fi
    
    # Tampilkan pilihan dan konfirmasi
    echo -e "\n${CYAN}┌─────────────────────────────────────┐${NC}"
    echo -e "${CYAN}│      KONFIRMASI LAYOUT KEYBOARD       │${NC}"
    echo -e "${CYAN}├─────────────────────────────────────┤${NC}"
    echo -e "│ Layout dipilih: ${BOLD}$KEYBOARD_LAYOUT${NC}   │"
    echo -e "${CYAN}└─────────────────────────────────────┘${NC}"
    
    echo -en "\n${YELLOW}Lanjutkan dengan layout ini? (y/n): ${NC}"
    read -r confirm_layout
    
    if [[ "$confirm_layout" == "y" ]] || [[ "$confirm_layout" == "Y" ]] || [[ -z "$confirm_layout" ]]; then
        break
    fi
    # Jika tidak, ulangi loop
done

# Konversi ke lowercase untuk konsistensi
KEYBOARD_LAYOUT=$(echo "$KEYBOARD_LAYOUT" | tr '[:upper:]' '[:lower:]')

echo -e "${GREEN}✅ Layout keyboard: $KEYBOARD_LAYOUT${NC}"
echo ""


# Tampilkan hasil akhir
echo -e "\n${GREEN}✅ Layout keyboard: ${BOLD}$KEYBOARD_LAYOUT${NC}"
echo -e "${GREEN}✅ Akan disimpan di /etc/vconsole.conf${NC}"
echo ""


# =============================================================================
# COPY SYSTEM
# =============================================================================
echo -e ""
echo -e "${BLUE}Mulai menyalin sistem ke $ROOT_PART${NC}"
echo "Ini bisa memakan waktu beberapa menit..."
echo -e ""
echo -e "${RED}PERINGATAN TERAKHIR: Semua data di $ROOT_PART akan ditimpa!${NC}"
echo -en "${YELLOW}Lanjutkan penyalinan sistem? (ketik 'yes') : ${NC}"
read -r final_confirm
if [[ "${final_confirm,,}" != "yes" ]]; then
    echo -e "${GREEN}Dibatalkan.${NC}"
    exit 0
fi

mkdir -p /mnt/leakos
mount "$ROOT_PART" /mnt/leakos

rsync -aHAX --info=progress2 / /mnt/leakos \
    --exclude={/dev/*,/proc/*,/sys/*,/run/*,/tmp/*,/mnt/*,/media/*,/lost+found,/var/log/*,/var/cache/*,/etc/fstab,/etc/hostname,/etc/shadow,/etc/passwd,/boot/grub/*}

mkdir -p /mnt/leakos/boot /mnt/leakos/boot/grub
cp -v /boot/vmlinuz* /mnt/leakos/boot/ 2>/dev/null || true
cp -v /boot/initrd* /mnt/leakos/boot/ 2>/dev/null || true
cp -v /boot/System.map* /mnt/leakos/boot/ 2>/dev/null || true

if ! ls /mnt/leakos/boot/vmlinuz* >/dev/null 2>&1; then
    echo -e "${YELLOW}WARNING: Kernel tidak ditemukan di /mnt/leakos/boot!${NC}"
fi
sync

mount --bind /dev /mnt/leakos/dev
mount --bind /proc /mnt/leakos/proc
mount --bind /sys /mnt/leakos/sys
mount --bind /run /mnt/leakos/run
mount --bind /dev/pts /mnt/leakos/dev/pts

# =============================================================================
# PENTEST TOOLS
# =============================================================================
echo -e ""
echo -e "${BLUE}Download tools pentest dari GitHub?${NC}"
echo "akan disimpan di /opt/pentest-tools"
echo "Pilih kategori (nomor dipisah spasi, contoh: 1 3) atau 'a' untuk semua"
echo " 0) Skip semua"
echo " 1) Reconnaissance (reconftw, Sn1per)"
echo " 2) OSINT (theHarvester, recon-ng)"
echo " 3) Web Vuln Scanning (nuclei-templates, dirsearch)"
echo " 4) Exploitation (PayloadsAllTheThings, impacket)"
echo " a) Semua kategori"
echo -n "Pilihan: "
read -r category_choices

SELECTED_CATEGORIES=()
if [[ "${category_choices,,}" == "a" ]]; then
    SELECTED_CATEGORIES=(1 2 3 4)
elif [[ "$category_choices" != "0" ]] && [[ -n "$category_choices" ]]; then
    for cat in $category_choices; do
        SELECTED_CATEGORIES+=("$cat")
    done
fi

# =============================================================================
# FINAL CONFIRM & CHROOT - FIXED VERSION
# =============================================================================
echo -e ""
echo -e "${BLUE}Langkah akhir: konfigurasi sistem, install GRUB, download tools${NC}"
echo "GRUB akan diinstall ke $TARGET_DISK"
echo -en "${YELLOW}Lanjut? (ketik 'yes') : ${NC}"
read -r confirm_grub
if [[ "${confirm_grub,,}" != "yes" ]]; then
    echo -e "${GREEN}Dibatalkan sebelum finalisasi.${NC}"
    umount -R /mnt/leakos || true
    exit 0
fi

CATEGORIES_STRING="${SELECTED_CATEGORIES[*]}"

# FIXED: ROOT_UUID diambil di DALAM chroot, bukan di luar
chroot /mnt/leakos /bin/bash <<'EOF_CHROOT'
set -e
# Konfigurasi dasar
echo "$HOSTNAME" > /etc/hostname

# Setup user
useradd -m -G wheel -s /bin/bash "$USERNAME" 2>/dev/null || useradd -m -s /bin/bash "$USERNAME"
echo "$USERNAME:$PASSWORD" | chpasswd
echo "%wheel ALL=(ALL) ALL" > /etc/sudoers.d/wheel 2>/dev/null || echo "$USERNAME ALL=(ALL) ALL" >> /etc/sudoers

# Locale
echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
echo "id_ID.UTF-8 UTF-8" >> /etc/locale.gen
echo "LANG=en_US.UTF-8" > /etc/locale.conf

# Keyboard
echo "KEYMAP=$KEYBOARD_LAYOUT" > /etc/vconsole.conf

# Timezone
ln -sf /usr/share/zoneinfo/$TIMEZONE /etc/localtime
hwclock --systohc --utc || true

# FIXED: Ambil UUID di DALAM chroot
ROOT_UUID=$(blkid -s UUID -o value "$ROOT_PART")

# fstab
cat > /etc/fstab <<FSTABEOF
UUID=$ROOT_UUID / ext4 defaults 0 1
tmpfs /tmp tmpfs defaults 0 0
proc /proc proc defaults 0 0
sysfs /sys sysfs defaults 0 0
FSTABEOF

# hosts
cat > /etc/hosts <<HOSTSEOF
127.0.0.1 localhost
127.0.1.1 $HOSTNAME $HOSTNAME.localdomain
::1 localhost ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
HOSTSEOF

# Install GRUB
grub-install --target=i386-pc --recheck "$TARGET_DISK" || grub-install "$TARGET_DISK" || echo "WARNING: GRUB install mungkin gagal"

# GRUB config - FIXED: Gunakan $ROOT_UUID yang sudah diambil di atas
cat > /boot/grub/grub.cfg <<GRUBEOF
# LeakOS GRUB Configuration - Shadow Edition

set default=0
set timeout=5

menuentry "LeakOS V1 (Celuluk)" {
    search --no-floppy --fs-uuid --set=root $ROOT_UUID
    linux /boot/vmlinuz root=UUID=$ROOT_UUID ro quiet splash
}

menuentry "LeakOS V1 (Celuluk) - Recovery" {
    search --no-floppy --fs-uuid --set=root $ROOT_UUID
    linux /boot/vmlinuz root=UUID=$ROOT_UUID ro single
}
GRUBEOF

# Download tools jika dipilih
if [ ${#SELECTED_CATEGORIES[@]} -gt 0 ]; then
    mkdir -p /opt/pentest-tools
    cd /opt/pentest-tools
    for cat in ${CATEGORIES_STRING}; do
        case $cat in
            1)
                git clone https://github.com/six2dez/reconftw.git 2>/dev/null || true
                git clone https://github.com/1N3/Sn1per.git 2>/dev/null || true
                ;;
            2)
                git clone https://github.com/laramies/theHarvester.git 2>/dev/null || true
                git clone https://github.com/lanmaster53/recon-ng.git 2>/dev/null || true
                ;;
            3)
                git clone https://github.com/projectdiscovery/nuclei-templates.git 2>/dev/null || true
                git clone https://github.com/maurosoria/dirsearch.git 2>/dev/null || true
                ;;
            4)
                git clone https://github.com/swisskyrepo/PayloadsAllTheThings.git 2>/dev/null || true
                git clone https://github.com/fortra/impacket.git 2>/dev/null || true
                ;;
        esac
    done
fi

# Bersih-bersih
rm -f /etc/machine-id
touch /etc/machine-id
exit 0
EOF_CHROOT

sync
umount -R /mnt/leakos 2>/dev/null || true

# =============================================================================
# PESAN AKHIR
# =============================================================================
echo -e ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           L E A K O S   BERHASIL DIINSTALL !               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo -e ""
echo -e "Username     : ${CYAN}$USERNAME${NC}"
echo -e "Hostname     : ${CYAN}$HOSTNAME${NC}"
echo -e "Root partisi : ${CYAN}$ROOT_PART${NC}"
if [ ${#SELECTED_CATEGORIES[@]} -gt 0 ]; then
    echo -e "Tools pentest: ${CYAN}/opt/pentest-tools${NC}"
else
    echo -e "Tidak download tools pentest (dipilih skip)."
fi
echo -e ""
echo -e "Ketik 'reboot' atau cabut media lalu restart."
echo -e ""

read -r -p "Reboot sekarang? (yes/no): " confirm_reboot
[[ "${confirm_reboot,,}" == "yes" ]] && reboot

exit 0
