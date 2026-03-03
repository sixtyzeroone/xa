#!/usr/bin/env bash
# =============================================================================
# LeakOS Linux Installer (TERMINAL VERSION - STEP-BY-STEP + CATEGORIZED PENTEST TOOLS)
# =============================================================================
# FIXED: Disk selection now accepts both number AND /dev/sda format
# =============================================================================

set -euo pipefail

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  L E A K O S   L I N U X                  ║"
echo "║     Unleashed Freedom • Privacy First • Indonesian Root   ║"
echo "║          Custom LFS Distro - Pentest / Developer Ready    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "LeakOS Installer - Terminal mode with step-by-step confirmation"
echo "Press Enter to start, or Ctrl+C to cancel."
read -r dummy

# =============================================================================
# ROOT CHECK
# =============================================================================
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This installer must be run as root."
    exit 1
fi

# =============================================================================
# DEPENDENCY CHECK
# =============================================================================
echo "Checking dependencies..."
for cmd in lsblk cfdisk mkfs.ext4 rsync grub-install grub-mkconfig blkid git; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: Missing dependency: $cmd"
        echo "Make sure all required packages (including git) are installed in the live environment."
        exit 1
    fi
done
echo "All dependencies OK."
echo ""

# =============================================================================
# INITIAL WARNING
# =============================================================================
echo "⚠️  IMPORTANT WARNING:"
echo "• ALL DATA ON THE TARGET DISK WILL BE PERMANENTLY DELETED"
echo "• Use only on empty machine or test VM"
echo "• There is NO UNDO after confirmation"
echo ""
echo "Proceed with installation? (type 'yes' and press Enter)"
read -r confirm
if [[ "$confirm" != "yes" ]]; then
    echo "Installation cancelled by user."
    exit 0
fi

# =============================================================================
# DISK SELECT - FIXED VERSION
# =============================================================================
echo "Detected disks:"
lsblk -dno NAME,SIZE,TYPE,MODEL | awk '$3=="disk"{print NR ".) /dev/"$1 " ("$2") - " $4}'
echo ""
echo "Enter the target disk (you can enter number OR /dev/sdX):"
read -r disk_input

# Function to get disk from number
get_disk_from_number() {
    local num=$1
    lsblk -dno NAME,TYPE | awk '$2=="disk"{print "/dev/"$1}' | sed -n "${num}p"
}

# Check if input is a number
if [[ "$disk_input" =~ ^[0-9]+$ ]]; then
    # Input is a number
    TARGET_DISK=$(get_disk_from_number "$disk_input")
elif [[ "$disk_input" =~ ^/dev/[a-z]+[0-9]*$ ]]; then
    # Input is a device path
    if [ -b "$disk_input" ]; then
        # Check if it's a whole disk (not a partition)
        if [[ "$disk_input" =~ ^/dev/[a-z]+$ ]]; then
            TARGET_DISK="$disk_input"
        else
            # Remove partition number to get whole disk
            TARGET_DISK=$(echo "$disk_input" | sed 's/[0-9]*$//')
            echo "Note: Using whole disk $TARGET_DISK instead of partition $disk_input"
        fi
    else
        echo "ERROR: $disk_input is not a valid block device."
        exit 1
    fi
else
    echo "ERROR: Invalid input format. Please enter a number (like 1) or device path (like /dev/sda)."
    exit 1
fi

if [ -z "$TARGET_DISK" ] || [ ! -b "$TARGET_DISK" ]; then
    echo "ERROR: Invalid disk selection. '$TARGET_DISK' is not a valid block device."
    exit 1
fi

echo ""
echo "Selected disk: $TARGET_DISK"
echo "ALL DATA ON THIS DISK WILL BE ERASED."
echo "Are you sure? (type 'yes')"
read -r confirm_disk
if [[ "$confirm_disk" != "yes" ]]; then
    echo "Cancelled."
    exit 0
fi

# =============================================================================
# PARTITIONING
# =============================================================================
echo ""
echo "Step 1: Partition the disk"
echo "Now opening cfdisk for $TARGET_DISK"
echo "Recommended: 'dos' table (MBR/BIOS), create at least 1 Linux ext4 partition"
echo ""
echo "Ready to open cfdisk? (type 'yes')"
read -r confirm_cfdisk
if [[ "$confirm_cfdisk" != "yes" ]]; then
    echo "Cancelled before partitioning."
    exit 0
fi

cfdisk "$TARGET_DISK"

echo ""
echo "Partitioning done. Refreshing partition table..."
partprobe "$TARGET_DISK" || true
sleep 3

# =============================================================================
# DETECT ROOT PARTITION - IMPROVED
# =============================================================================
echo "Scanning for ext4 partitions on $TARGET_DISK..."
ROOT_PART=$(lsblk -ln -o NAME,FSTYPE "$TARGET_DISK" | awk '$2=="ext4" {print "/dev/"$1; exit}')

if [ ! -b "$ROOT_PART" ]; then
    echo "No ext4 partition found automatically."
    echo "Available partitions on $TARGET_DISK:"
    lsblk "$TARGET_DISK"
    echo ""
    echo "Enter the partition to use as root (e.g., ${TARGET_DISK}1):"
    read -r manual_part
    
    if [ -b "$manual_part" ]; then
        ROOT_PART="$manual_part"
        echo "Using $ROOT_PART as root partition."
    else
        echo "ERROR: $manual_part is not a valid block device."
        exit 1
    fi
fi

echo "Root partition detected: $ROOT_PART"
echo "Proceed to format this partition? (type 'yes' - this will ERASE data!)"
read -r confirm_format
if [[ "$confirm_format" != "yes" ]]; then
    echo "Cancelled before formatting."
    exit 0
fi

# =============================================================================
# USER INPUT
# =============================================================================
echo ""
echo "Enter username (default: leakos):"
read -r USERNAME
USERNAME=${USERNAME:-leakos}

echo "Enter hostname (default: leakos):"
read -r HOSTNAME
HOSTNAME=${HOSTNAME:-leakos}

echo "Enter password for user $USERNAME:"
read -s PASSWORD
echo "Confirm password:"
read -s PASSWORD2

if [ "$PASSWORD" != "$PASSWORD2" ] || [ -z "$PASSWORD" ]; then
    echo "ERROR: Passwords do not match or empty."
    exit 1
fi

# =============================================================================
# TIMEZONE & KEYBOARD
# =============================================================================
echo ""
echo "Timezone (e.g. Asia/Jakarta) - press Enter for default:"
read -r TIMEZONE
TIMEZONE=${TIMEZONE:-Asia/Jakarta}
if [ ! -f "/usr/share/zoneinfo/$TIMEZONE" ]; then
    echo "Timezone not found, using Asia/Jakarta"
    TIMEZONE="Asia/Jakarta"
fi

echo ""
echo "Select keyboard layout:"
echo " 1) us     United States"
echo " 2) id     Indonesia"
echo " 3) fr     France"
echo " 4) de     Germany"
echo " 5) es     Spain"
echo " 6) it     Italy"
echo " 7) pt     Portugal"
echo " 8) gb     United Kingdom"
echo " 9) se     Sweden"
echo "10) no     Norway"
echo "11) dk     Denmark"
echo "12) fi     Finland"
echo "13) pl     Poland"
echo "14) ru     Russia"
echo "15) ua     Ukraine"
echo "16) cz     Czech Republic"
echo "17) tr     Turkey"
echo "18) cn     China"
echo "19) jp     Japan"
echo "20) kr     South Korea"
echo "21) vn     Vietnam"
echo "22) br     Brazil"
echo "23) ph     Philippines"
echo "24) sg     Singapore"
echo "25) other  (enter manually)"
echo ""
echo "Enter number (default: 1):"
read -r kb_choice
kb_choice=${kb_choice:-1}

case $kb_choice in
    1) KEYBOARD_LAYOUT="us" ;;
    2) KEYBOARD_LAYOUT="id" ;;
    3) KEYBOARD_LAYOUT="fr" ;;
    4) KEYBOARD_LAYOUT="de" ;;
    5) KEYBOARD_LAYOUT="es" ;;
    6) KEYBOARD_LAYOUT="it" ;;
    7) KEYBOARD_LAYOUT="pt" ;;
    8) KEYBOARD_LAYOUT="gb" ;;
    9) KEYBOARD_LAYOUT="se" ;;
   10) KEYBOARD_LAYOUT="no" ;;
   11) KEYBOARD_LAYOUT="dk" ;;
   12) KEYBOARD_LAYOUT="fi" ;;
   13) KEYBOARD_LAYOUT="pl" ;;
   14) KEYBOARD_LAYOUT="ru" ;;
   15) KEYBOARD_LAYOUT="ua" ;;
   16) KEYBOARD_LAYOUT="cz" ;;
   17) KEYBOARD_LAYOUT="tr" ;;
   18) KEYBOARD_LAYOUT="cn" ;;
   19) KEYBOARD_LAYOUT="jp" ;;
   20) KEYBOARD_LAYOUT="kr" ;;
   21) KEYBOARD_LAYOUT="vn" ;;
   22) KEYBOARD_LAYOUT="br" ;;
   23) KEYBOARD_LAYOUT="ph" ;;
   24) KEYBOARD_LAYOUT="sg" ;;
   25) echo "Enter keymap code manually:"; read -r KEYBOARD_LAYOUT ;;
   *)  KEYBOARD_LAYOUT="us" ;;
esac

# =============================================================================
# COPY SYSTEM
# =============================================================================
echo ""
echo "Starting system copy to $ROOT_PART"
echo "This may take several minutes..."
echo ""

mkfs.ext4 -F "$ROOT_PART"
mkdir -p /mnt/leakos
mount "$ROOT_PART" /mnt/leakos

echo "Copying system files..."
rsync -aHAX --info=progress2 / /mnt/leakos \
    --exclude={/dev/*,/proc/*,/sys/*,/run/*,/tmp/*,/mnt/*,/media/*,/lost+found,/var/log/*,/var/cache/*,/etc/fstab,/etc/hostname,/etc/shadow,/etc/passwd,/boot/grub/*}

# Kernel copy
mkdir -p /mnt/leakos/boot
cp -v /boot/vmlinuz* /mnt/leakos/boot/ 2>/dev/null || true
cp -v /boot/initrd* /mnt/leakos/boot/ 2>/dev/null || true
cp -v /boot/System.map* /mnt/leakos/boot/ 2>/dev/null || true

if ! ls /mnt/leakos/boot/vmlinuz* >/dev/null 2>&1; then
    echo "WARNING: No kernel found in /mnt/leakos/boot!"
    echo "Boot may fail. Continuing anyway."
fi

# =============================================================================
# MOUNT BINDS
# =============================================================================
mount --bind /dev /mnt/leakos/dev
mount --bind /proc /mnt/leakos/proc
mount --bind /sys /mnt/leakos/sys
mount --bind /run /mnt/leakos/run
mount --bind /dev/pts /mnt/leakos/dev/pts

# =============================================================================
# PENTEST TOOLS SELECTION
# =============================================================================
echo ""
echo "Optional: Download popular pentest tools from GitHub?"
echo "Tools will be cloned to /opt/pentest-tools after installation."
echo "Select categories to install (enter numbers separated by space, e.g. 1 3):"
echo " 0) None / Skip all downloads"
echo ""
echo "1) Reconnaissance / Information Gathering"
echo "   - reconftw     - Advanced automated recon framework"
echo "   - Sn1per       - Automated attack surface scanner"
echo ""
echo "2) OSINT"
echo "   - theHarvester - Email, subdomain, host gatherer"
echo "   - Recon-ng     - Modular web reconnaissance framework"
echo ""
echo "3) Web Application / Vulnerability Scanning"
echo "   - nuclei-templates - Fast template-based vuln scanner"
echo "   - dirsearch    - Web directory brute-forcer"
echo ""
echo "4) Exploitation / Payloads"
echo "   - PayloadsAllTheThings - Cheatsheets & bypass payloads"
echo "   - Impacket     - Windows/AD exploitation collection"
echo ""
echo "a) All categories (all tools)"
echo ""
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
echo "Final step: System configuration, GRUB, and selected pentest tools"
echo "This will install GRUB to $TARGET_DISK"
echo "Proceed? (type 'yes')"
read -r confirm_grub
if [[ "$confirm_grub" != "yes" ]]; then
    echo "Cancelled before final setup."
    umount -R /mnt/leakos || true
    exit 0
fi

# Convert array to string for chroot
CATEGORIES_STRING="${SELECTED_CATEGORIES[@]}"

chroot /mnt/leakos /bin/bash <<EOF
set -e

echo "$HOSTNAME" > /etc/hostname
useradd -m -G wheel -s /bin/bash "$USERNAME"
echo "$USERNAME:$PASSWORD" | chpasswd
echo "%wheel ALL=(ALL) ALL" > /etc/sudoers.d/wheel 2>/dev/null || true

# Locale
echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
echo "id_ID.UTF-8 UTF-8" >> /etc/locale.gen
locale-gen

echo "LANG=en_US.UTF-8" > /etc/locale.conf

# Keyboard
echo "KEYMAP=$KEYBOARD_LAYOUT" > /etc/vconsole.conf

# Timezone
ln -sf /usr/share/zoneinfo/$TIMEZONE /etc/localtime
hwclock --systohc --utc

# fstab
ROOT_UUID=\$(blkid -s UUID -o value "$ROOT_PART")
cat > /etc/fstab <<EOT
UUID=\$ROOT_UUID    /               ext4    defaults        0       1
tmpfs               /tmp            tmpfs   defaults        0       0
proc                /proc           proc    defaults        0       0
sysfs               /sys            sysfs   defaults        0       0
EOT

# /etc/hosts
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
grub-install --target=i386-pc --recheck "$TARGET_DISK"
grub-mkconfig -o /boot/grub/grub.cfg
grub-install "$TARGET_DISK"

# Download pentest tools
if [ -n "$CATEGORIES_STRING" ]; then
    echo "Downloading pentest tools from selected categories..."
    mkdir -p /opt/pentest-tools
    cd /opt/pentest-tools

    for cat in $CATEGORIES_STRING; do
        case \$cat in
            1)
                git clone https://github.com/six2dez/reconftw.git || echo "Failed to clone reconftw"
                git clone https://github.com/1N3/Sn1per.git || echo "Failed to clone Sn1per"
                ;;
            2)
                git clone https://github.com/laramies/theHarvester.git || echo "Failed to clone theHarvester"
                git clone https://github.com/lanmaster53/recon-ng.git || echo "Failed to clone recon-ng"
                ;;
            3)
                git clone https://github.com/projectdiscovery/nuclei-templates.git || echo "Failed to clone nuclei-templates"
                git clone https://github.com/maurosoria/dirsearch.git || echo "Failed to clone dirsearch"
                ;;
            4)
                git clone https://github.com/swisskyrepo/PayloadsAllTheThings.git || echo "Failed to clone PayloadsAllTheThings"
                git clone https://github.com/fortra/impacket.git || echo "Failed to clone impacket"
                ;;
        esac
    done

    # Create .desktop launcher
    mkdir -p /usr/share/applications
    cat > /usr/share/applications/leakos-pentest-tools.desktop <<EOT
[Desktop Entry]
Name=LeakOS Pentest Tools
Comment=Open terminal in Pentest Tools directory (/opt/pentest-tools)
Exec=bash
Icon=utilities-terminal
Terminal=true
Type=Application
Categories=Development;Utility;System;
Path=/opt/pentest-tools
EOT

    echo "Tools from selected categories cloned to /opt/pentest-tools"
else
    echo "No categories selected - skipping pentest tools download."
fi
EOF

sync
umount -R /mnt/leakos || true

# =============================================================================
# FINAL MESSAGE
# =============================================================================
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  L E A K O S   L I N U X                  ║"
echo "║             Installation COMPLETED                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "All steps finished."
if [ ${#SELECTED_CATEGORIES[@]} -gt 0 ]; then
    echo "Pentest tools from selected categories are in /opt/pentest-tools"
    echo "Menu entry 'LeakOS Pentest Tools' created (opens terminal there)"
else
    echo "No pentest tools were downloaded (you chose to skip)."
fi
echo ""
echo "You can now type 'reboot' or remove installation media and reboot."
echo ""
echo "Reboot now? (type 'yes' for automatic reboot)"
read -r confirm_reboot
if [[ "$confirm_reboot" == "yes" ]]; then
    reboot
fi

exit 0
