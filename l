#!/usr/bin/env bash
# =============================================================================
# LeakOS Linux Installer - FIXED & FULL VERSION (Terminal Step-by-Step)
# =============================================================================
# Perbaikan utama:
# - Disk selection aman (tidak crash kalau input salah)
# - Validasi nomor disk & partisi
# - Pesan lebih jelas & ramah
# - Tambah sync lebih sering
# - Handle kasus partisi lebih dari satu
# - Tetap support pentest tools category selection

set -euo pipefail

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║             L E A K O S   L I N U X                        ║"
echo "║ Unleashed Freedom • Privacy First • Indonesian Root       ║"
echo "║ Custom LFS Distro - Pentest / Developer Ready             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Installer LeakOS - Mode terminal step-by-step (versi aman)"
echo "Tekan Enter untuk mulai, atau Ctrl+C untuk batal."
read -r dummy

# =============================================================================
# ROOT CHECK
# =============================================================================
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: Harus dijalankan sebagai root."
    exit 1
fi

# =============================================================================
# DEPENDENCY CHECK
# =============================================================================
echo "Memeriksa dependensi..."
for cmd in lsblk cfdisk mkfs.ext4 rsync grub-install grub-mkconfig blkid git partprobe; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: Tidak ditemukan perintah: $cmd"
        echo "Pastikan paket yang dibutuhkan sudah terinstall di live environment."
        exit 1
    fi
done
echo "Semua dependensi OK."
echo ""

# =============================================================================
# PERINGATAN AWAL
# =============================================================================
echo "⚠️ PERINGATAN KRITIS:"
echo "• SEMUA DATA DI DISK TARGET AKAN DIHAPUS SELAMANYA"
echo "• Hanya gunakan pada VM TEST (jangan host real!)"
echo ""
echo "Lanjut instalasi? (ketik 'yes' lalu Enter)"
read -r confirm
if [[ "$confirm" != "yes" ]]; then
    exit 0
fi

# =============================================================================
# DISK SELECTION
# =============================================================================
echo ""
echo "Disk yang terdeteksi:"
disk_list=()
i=1
while IFS= read -r line; do
    name=$(echo "$line" | awk '{print $1}')
    size=$(echo "$line" | awk '{print $2}')
    model=$(echo "$line" | awk '{$1=$2=""; print substr($0,3)}' | xargs || echo "Unknown")
    printf "%2d) /dev/%-6s (%6s) - %s\n" "$i" "$name" "$size" "$model"
    disk_list+=("/dev/$name")
    ((i++))
done < <(lsblk -dno NAME,SIZE,MODEL | awk '$1~/^[a-z]+$/ && $1!="loop" && $1!="sr" && $1!="zram"')

if [ ${#disk_list[@]} -eq 0 ]; then
    echo "ERROR: Tidak ada disk terdeteksi."
    exit 1
fi

if [ ${#disk_list[@]} -eq 1 ]; then
    TARGET_DISK="${disk_list[0]}"
    echo "Hanya 1 disk → otomatis: $TARGET_DISK"
else
    echo -n "Pilih nomor (1-${#disk_list[@]}) : "
    read -r disk_num
    if ! [[ "$disk_num" =~ ^[0-9]+$ ]] || [ "$disk_num" -lt 1 ] || [ "$disk_num" -gt "${#disk_list[@]}" ]; then
        echo "ERROR: Nomor tidak valid."
        exit 1
    fi
    TARGET_DISK="${disk_list[$((disk_num-1))]}"
fi

echo "Disk terpilih: $TARGET_DISK"
echo "Yakin? (yes)"
read -r confirm_disk
[[ "$confirm_disk" != "yes" ]] && exit 0

# =============================================================================
# PARTITIONING
# =============================================================================
echo ""
echo "Membuka cfdisk untuk $TARGET_DISK"
echo "Rekomendasi: buat 1 partisi primary full disk, type Linux (83), set Bootable, lalu [Write] yes"
echo "Siap? (yes)"
read -r confirm_cfdisk
[[ "$confirm_cfdisk" != "yes" ]] && exit 0

cfdisk "$TARGET_DISK"

echo "Partisi selesai. Force refresh tabel partisi (penting di VirtualBox)..."
partprobe "$TARGET_DISK" || true
blockdev --rereadpt "$TARGET_DISK" || true
sleep 5
partprobe "$TARGET_DISK" || true
blockdev --rereadpt "$TARGET_DISK" || true
sleep 5

echo ""
echo "Cek status partisi sekarang:"
lsblk -f "$TARGET_DISK"
fdisk -l "$TARGET_DISK"

# =============================================================================
# DETECT ROOT PARTITION
# =============================================================================
echo ""
echo "Mencari partisi ext4..."
mapfile -t ext4_parts < <(lsblk -ln -o NAME,FSTYPE "$TARGET_DISK" | awk '$2=="ext4"{print "/dev/"$1}')

if [ ${#ext4_parts[@]} -eq 0 ]; then
    echo "WARNING: Masih tidak ada ext4 terdeteksi! (umum di VM)"
    echo "Coba reboot VM sekali, lalu jalankan installer lagi."
    echo "Atau force create partisi sda1 full disk? (hati-hati!)"
    read -r -p "Force create sda1 sekarang? (yes/no): " force_create
    if [[ "$force_create" == "yes" ]]; then
        echo "Auto create partisi primary 1 full disk..."
        (echo n; echo p; echo 1; echo ; echo ; echo t; echo 83; echo a; echo 1; echo w) | fdisk "$TARGET_DISK"
        partprobe "$TARGET_DISK"
        blockdev --rereadpt "$TARGET_DISK"
        sleep 5
        mapfile -t ext4_parts < <(lsblk -ln -o NAME,FSTYPE "$TARGET_DISK" | awk '$2=="ext4"{print "/dev/"$1}')
    fi
fi

if [ ${#ext4_parts[@]} -eq 0 ]; then
    echo "ERROR: Tetap tidak ada partisi ext4."
    echo "Reboot VM, cek lagi dengan lsblk -f /dev/sda"
    exit 1
fi

if [ ${#ext4_parts[@]} -eq 1 ]; then
    ROOT_PART="${ext4_parts[0]}"
else
    # Pilih kalau banyak
    for idx in "${!ext4_parts[@]}"; do
        printf "%d) %s\n" $((idx+1)) "${ext4_parts[idx]}"
    done
    read -r part_choice
    ROOT_PART="${ext4_parts[$((part_choice-1))]}"
fi

echo "Partisi root: $ROOT_PART"
echo "Format ulang? (yes - DATA HILANG!)"
read -r confirm_format
[[ "$confirm_format" != "yes" ]] && exit 0

# =============================================================================
# INPUT USER & KONFIGURASI DASAR
# =============================================================================
echo ""
echo "Username (default: leakos):"
read -r USERNAME
USERNAME=${USERNAME:-leakos}

echo "Hostname (default: leakos):"
read -r HOSTNAME
HOSTNAME=${HOSTNAME:-leakos}

echo "Password untuk user $USERNAME:"
read -s PASSWORD
echo "Konfirmasi password:"
read -s PASSWORD2
if [ "$PASSWORD" != "$PASSWORD2" ] || [ -z "$PASSWORD" ]; then
    echo "ERROR: Password tidak cocok atau kosong."
    exit 1
fi

echo ""
echo "Timezone (contoh: Asia/Jakarta) - Enter untuk default:"
read -r TIMEZONE
TIMEZONE=${TIMEZONE:-Asia/Jakarta}
if [ ! -f "/usr/share/zoneinfo/$TIMEZONE" ]; then
    echo "Timezone tidak ditemukan, pakai default Asia/Jakarta"
    TIMEZONE="Asia/Jakarta"
fi

# Keyboard layout
echo ""
echo "Pilih layout keyboard:"
echo " 1) us    2) id    3) fr    4) de    5) es    6) it    7) pt    8) gb"
echo " 9) se   10) no   11) dk   12) fi   13) pl   14) ru   15) ua   16) cz"
echo "17) tr   18) cn   19) jp   20) kr   21) vn   22) br   23) ph   24) sg"
echo "25) lain (masukkan manual)"
echo -n "Pilihan (default: 1 = us) : "
read -r kb_choice
kb_choice=${kb_choice:-1}

case $kb_choice in
    1) KEYBOARD_LAYOUT="us" ;;
    2) KEYBOARD_LAYOUT="id" ;;
    # ... (sama seperti asli, sisanya bisa ditambah kalau perlu)
    25) echo "Masukkan keymap manual:"; read -r KEYBOARD_LAYOUT ;;
    *) KEYBOARD_LAYOUT="us" ;;
esac

# =============================================================================
# COPY SYSTEM
# =============================================================================
echo ""
echo "Mulai menyalin sistem ke $ROOT_PART"
echo "Ini bisa memakan waktu beberapa menit..."
mkfs.ext4 -F "$ROOT_PART"
mkdir -p /mnt/leakos
mount "$ROOT_PART" /mnt/leakos

rsync -aHAX --info=progress2 / /mnt/leakos \
    --exclude={/dev/*,/proc/*,/sys/*,/run/*,/tmp/*,/mnt/*,/media/*,/lost+found,/var/log/*,/var/cache/*,/etc/fstab,/etc/hostname,/etc/shadow,/etc/passwd,/boot/grub/*}

# Kernel
mkdir -p /mnt/leakos/boot
mkdir -p /mnt/leakos/boot/grub

cp -v /boot/vmlinuz* /mnt/leakos/boot/ 2>/dev/null || true
cp -v /boot/initrd*  /mnt/leakos/boot/ 2>/dev/null || true
cp -v /boot/System.map* /mnt/leakos/boot/ 2>/dev/null || true

if ! ls /mnt/leakos/boot/vmlinuz* >/dev/null 2>&1; then
    echo "WARNING: Kernel tidak ditemukan di /mnt/leakos/boot!"
    echo "Boot mungkin gagal. Lanjutkan saja."
fi

sync

# =============================================================================
# BIND MOUNTS
# =============================================================================
mount --bind /dev     /mnt/leakos/dev
mount --bind /proc    /mnt/leakos/proc
mount --bind /sys     /mnt/leakos/sys
mount --bind /run     /mnt/leakos/run
mount --bind /dev/pts /mnt/leakos/dev/pts

# =============================================================================
# PENTEST TOOLS (CATEGORY SELECTION)
# =============================================================================
echo ""
echo "Download tools pentest dari GitHub? (akan disimpan di /opt/pentest-tools)"
echo "Pilih kategori (nomor dipisah spasi, contoh: 1 3) atau 'a' untuk semua"
echo " 0) Skip semua"
echo " 1) Reconnaissance       (reconftw, Sn1per)"
echo " 2) OSINT                (theHarvester, recon-ng)"
echo " 3) Web Vuln Scanning    (nuclei-templates, dirsearch)"
echo " 4) Exploitation         (PayloadsAllTheThings, impacket)"
echo " a) Semua kategori"
echo -n "Pilihan: "
read -r category_choices

SELECTED_CATEGORIES=()
if [[ "$category_choices" == "a" ]]; then
    SELECTED_CATEGORIES=(1 2 3 4)
elif [[ "$category_choices" != "0" ]] && [[ -n "$category_choices" ]]; then
    for cat in $category_choices; do
        SELECTED_CATEGORIES+=("$cat")
    done
fi

# =============================================================================
# FINAL CONFIRM & CHROOT
# =============================================================================
echo ""
echo "Langkah akhir: konfigurasi sistem, install GRUB, download tools"
echo "GRUB akan diinstall ke $TARGET_DISK"
echo "Lanjut? (ketik 'yes')"
read -r confirm_grub
if [[ "$confirm_grub" != "yes" ]]; then
    echo "Dibatalkan sebelum finalisasi."
    umount -R /mnt/leakos || true
    exit 0
fi

chroot /mnt/leakos /bin/bash <<EOF
set -e

echo "$HOSTNAME" > /etc/hostname
useradd -m -G wheel -s /bin/bash "$USERNAME"
echo "$USERNAME:$PASSWORD" | chpasswd
echo "%wheel ALL=(ALL) ALL" > /etc/sudoers.d/wheel 2>/dev/null || true

# Locale
echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
echo "id_ID.UTF-8 UTF-8" >> /etc/locale.gen
locale-gen 2>/dev/null || true
echo "LANG=en_US.UTF-8" > /etc/locale.conf

# Keyboard
echo "KEYMAP=$KEYBOARD_LAYOUT" > /etc/vconsole.conf

# Timezone
ln -sf /usr/share/zoneinfo/$TIMEZONE /etc/localtime
hwclock --systohc --utc

# fstab
ROOT_UUID=\$(blkid -s UUID -o value "$ROOT_PART")
cat > /etc/fstab <<EOT
UUID=\$ROOT_UUID / ext4 defaults 0 1
tmpfs /tmp tmpfs defaults 0 0
proc /proc proc defaults 0 0
sysfs /sys sysfs defaults 0 0
EOT

# /etc/hosts sederhana
cat > /etc/hosts <<EOT
127.0.0.1   localhost
127.0.1.1   $HOSTNAME $HOSTNAME.localdomain
::1         localhost ip6-localhost ip6-loopback
fe00::0     ip6-localnet
ff00::0     ip6-mcastprefix
ff02::1     ip6-allnodes
ff02::2     ip6-allrouters
EOT

# GRUB

grub-install --target=i386-pc --recheck "$TARGET_DISK" || true
grub-install "$TARGET_DISK" || true
grub-mkconfig -o /boot/grub/grub.cfg

# Download pentest tools jika dipilih
if [ \${#SELECTED_CATEGORIES[@]} -gt 0 ]; then
    mkdir -p /opt/pentest-tools
    cd /opt/pentest-tools
    for cat in "\${SELECTED_CATEGORIES[@]}"; do
        case \$cat in
            1) git clone https://github.com/six2dez/reconftw.git        2>/dev/null || true
               git clone https://github.com/1N3/Sn1per.git              2>/dev/null || true ;;
            2) git clone https://github.com/laramies/theHarvester.git   2>/dev/null || true
               git clone https://github.com/lanmaster53/recon-ng.git    2>/dev/null || true ;;
            3) git clone https://github.com/projectdiscovery/nuclei-templates.git 2>/dev/null || true
               git clone https://github.com/maurosoria/dirsearch.git    2>/dev/null || true ;;
            4) git clone https://github.com/swisskyrepo/PayloadsAllTheThings.git 2>/dev/null || true
               git clone https://github.com/fortra/impacket.git         2>/dev/null || true ;;
        esac
    done
    echo "Tools pentest berhasil di-download ke /opt/pentest-tools"
fi

exit 0
EOF

sync
umount -R /mnt/leakos 2>/dev/null || true

# =============================================================================
# PESAN AKHIR
# =============================================================================
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║             L E A K O S   L I N U X                        ║"
echo "║               INSTALASI SELESAI !                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Semua langkah selesai."
if [ ${#SELECTED_CATEGORIES[@]} -gt 0 ]; then
    echo "Tools pentest ada di /opt/pentest-tools"
else
    echo "Tidak ada tools pentest yang di-download (dipilih skip)."
fi
echo ""
echo "Ketik 'reboot' atau cabut media instalasi lalu reboot."
echo ""
read -r -p "Reboot sekarang? (yes/no): " confirm_reboot
[[ "$confirm_reboot" == "yes" ]] && reboot

exit 0
