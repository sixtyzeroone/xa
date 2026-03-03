#!/usr/bin/env bash
# =============================================================================
# LeakOS Linux Installer - FIXED & FULL VERSION (Terminal Step-by-Step)
# =============================================================================
# Versi dengan tampilan lebih rapi menggunakan echo -e + warna ANSI
# Deteksi support warna otomatis

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

echo ""
echo -n "Timezone (contoh: Asia/Jakarta) - Enter untuk default: "
read -r TIMEZONE
TIMEZONE=${TIMEZONE:-Asia/Jakarta}
if [ ! -f "/usr/share/zoneinfo/$TIMEZONE" ]; then
    echo -e "${YELLOW}Timezone tidak ditemukan, pakai default Asia/Jakarta${NC}"
    TIMEZONE="Asia/Jakarta"
fi

# =============================================================================
# KEYBOARD LAYOUT - Versi lebih rapi & terstruktur
# =============================================================================
echo -e ""
echo -e "${BLUE}Pilih layout keyboard:${NC}"
echo -e "──────────────────────────────────────────────────────────────"

# Grup 1: Umum & Indonesia
echo -e "  ${CYAN}1${NC}) us      ${CYAN}2${NC}) id      ${CYAN}3${NC}) gb      ${CYAN}4${NC}) fr"
echo -e "  ${CYAN}5${NC}) de      ${CYAN}6${NC}) es      ${CYAN}7${NC}) it      ${CYAN}8${NC}) pt"

# Grup 2: Eropa Utara & Timur
echo -e "  ${CYAN}9${NC}) se     ${CYAN}10${NC}) no     ${CYAN}11${NC}) dk     ${CYAN}12${NC}) fi"
echo -e " ${CYAN}13${NC}) pl     ${CYAN}14${NC}) ru     ${CYAN}15${NC}) ua     ${CYAN}16${NC}) cz"

# Grup 3: Asia & lainnya
echo -e " ${CYAN}17${NC}) tr     ${CYAN}18${NC}) cn     ${CYAN}19${NC}) jp     ${CYAN}20${NC}) kr"
echo -e " ${CYAN}21${NC}) vn     ${CYAN}22${NC}) br     ${CYAN}23${NC}) ph     ${CYAN}24${NC}) sg"

# Opsi manual
echo -e " ${CYAN}25${NC}) lain-lain (masukkan kode keymap secara manual)"
echo -e "──────────────────────────────────────────────────────────────"

echo -en "${YELLOW}Pilihan Anda (default: 1 = us) : ${NC}"
read -r kb_choice
kb_choice=${kb_choice:-1}

case $kb_choice in
    1)  KEYBOARD_LAYOUT="us"     ;;
    2)  KEYBOARD_LAYOUT="id"     ;;
    3)  KEYBOARD_LAYOUT="gb"     ;;
    4)  KEYBOARD_LAYOUT="fr"     ;;
    5)  KEYBOARD_LAYOUT="de"     ;;
    6)  KEYBOARD_LAYOUT="es"     ;;
    7)  KEYBOARD_LAYOUT="it"     ;;
    8)  KEYBOARD_LAYOUT="pt"     ;;
    9)  KEYBOARD_LAYOUT="se"     ;;
   10)  KEYBOARD_LAYOUT="no"     ;;
   11)  KEYBOARD_LAYOUT="dk"     ;;
   12)  KEYBOARD_LAYOUT="fi"     ;;
   13)  KEYBOARD_LAYOUT="pl"     ;;
   14)  KEYBOARD_LAYOUT="ru"     ;;
   15)  KEYBOARD_LAYOUT="ua"     ;;
   16)  KEYBOARD_LAYOUT="cz"     ;;
   17)  KEYBOARD_LAYOUT="tr"     ;;
   18)  KEYBOARD_LAYOUT="cn"     ;;
   19)  KEYBOARD_LAYOUT="jp"     ;;
   20)  KEYBOARD_LAYOUT="kr"     ;;
   21)  KEYBOARD_LAYOUT="vn"     ;;
   22)  KEYBOARD_LAYOUT="br"     ;;
   23)  KEYBOARD_LAYOUT="ph"     ;;
   24)  KEYBOARD_LAYOUT="sg"     ;;
   25)
       echo -en "${YELLOW}Masukkan kode keymap (contoh: us-intl, thai, arabic): ${NC}"
       read -r KEYBOARD_LAYOUT
       if [ -z "$KEYBOARD_LAYOUT" ]; then
           echo -e "${YELLOW}Kosong → menggunakan default 'us'${NC}"
           KEYBOARD_LAYOUT="us"
       fi
       ;;
    *)
       echo -e "${YELLOW}Pilihan tidak dikenali → menggunakan default 'us'${NC}"
       KEYBOARD_LAYOUT="us"
       ;;
esac

# Konfirmasi singkat setelah memilih
echo -e "${GREEN}Layout keyboard yang dipilih: ${CYAN}${KEYBOARD_LAYOUT}${NC}${NC}"
echo -e ""


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
# FINAL CONFIRM & CHROOT
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

chroot /mnt/leakos /bin/bash <<EOF
set -e
echo "$HOSTNAME" > /etc/hostname

useradd -m -G wheel -s /bin/bash "$USERNAME" 2>/dev/null || useradd -m -s /bin/bash "$USERNAME"
echo "$USERNAME:$PASSWORD" | chpasswd
echo "%wheel ALL=(ALL) ALL" > /etc/sudoers.d/wheel 2>/dev/null || echo "$USERNAME ALL=(ALL) ALL" >> /etc/sudoers

echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
echo "id_ID.UTF-8 UTF-8" >> /etc/locale.gen
echo "LANG=en_US.UTF-8" > /etc/locale.conf

echo "KEYMAP=$KEYBOARD_LAYOUT" > /etc/vconsole.conf

ln -sf /usr/share/zoneinfo/$TIMEZONE /etc/localtime
hwclock --systohc --utc || true

ROOT_UUID=\$(blkid -s UUID -o value "$ROOT_PART")
cat > /etc/fstab <<EOT
UUID=\$ROOT_UUID / ext4 defaults 0 1
tmpfs /tmp tmpfs defaults 0 0
proc /proc proc defaults 0 0
sysfs /sys sysfs defaults 0 0
EOT

cat > /etc/hosts <<EOT
127.0.0.1 localhost
127.0.1.1 $HOSTNAME $HOSTNAME.localdomain
::1 localhost ip6-localhost ip6-loopback
fe00::0 ip6-localnet
ff00::0 ip6-mcastprefix
ff02::1 ip6-allnodes
ff02::2 ip6-allrouters
EOT

grub-install --target=i386-pc --recheck "$TARGET_DISK" || grub-install "$TARGET_DISK" || echo "WARNING: GRUB install mungkin gagal"

cat > /boot/grub/grub.cfg <<'GRUBEOF'
# LeakOS GRUB manual configuration
set default=0
set timeout=5

set menu_color_normal=cyan/blue
set menu_color_highlight=white/blue

insmod all_video
insmod gfxterm
insmod png
insmod ext2
insmod part_msdos

if background_image /boot/grub/leakos.png; then
  set color_normal=white/black
  set color_highlight=black/white
else
  set color_normal=cyan/blue
  set color_highlight=white/blue
fi

terminal_output gfxterm

menuentry "LeakOS Linux" {
    insmod ext2
    insmod part_msdos
    search --no-floppy --fs-uuid --set=root \$ROOT_UUID
    linux /boot/vmlinuz root=UUID=\$ROOT_UUID ro quiet splash loglevel=3
}

# (tambahkan menuentry lain sesuai kebutuhan)
GRUBEOF

# Download tools jika dipilih
if [ ${#SELECTED_CATEGORIES[@]} -gt 0 ]; then
    mkdir -p /opt/pentest-tools
    cd /opt/pentest-tools
    for cat in ${CATEGORIES_STRING}; do
        case \$cat in
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

rm -f /etc/machine-id
touch /etc/machine-id
exit 0
EOF

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
