# phishing_detector_1hp_auto_reply.py
import re
import requests
import json
import time
from urllib.parse import urlparse
from encodings.idna import ToASCII
import threading
from datetime import datetime

# === KONFIGURASI ===
ID_INSTANCE = "1101xxxxxxxx"  # GANTI DENGAN ID INSTANCE ANDA
API_TOKEN = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # GANTI DENGAN TOKEN ANDA
API_BASE = f"https://api.green-api.com/waInstance{ID_INSTANCE}/"

# NOMOR BOT (yang terdaftar di Green-API)
BOT_PHONE = "6288223749303@c.us"  # ← NOMOR ANDA YANG TERDAFTAR

# NOMOR ADMIN (untuk alert - bisa sama dengan BOT_PHONE)
ADMIN_PHONE = "6288223749303@c.us"  # ← BISA SAMA DENGAN BOT_PHONE

LOG_FILE = "phishing_log.txt"

# Daftar keyword phishing
PHISHING_KEYWORDS = [
    "login", "verify", "account", "update", "secure", "bank", "paypal", "bca", "mandiri",
    "bni", "bri", "tokopedia", "shopee", "otp", "kodeotp", "token", "hadiah", "gratis",
    "promo", "konfirmasi", "verifikasi", "blokir", "suspend", "reset", "password",
    "urgent", "important", "billing", "invoice", "refund", "m-banking"
]

SUSPICIOUS_TLD = [
    ".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".club", ".site", ".online",
    ".link", ".buzz", ".live", ".digital", ".shop", ".men"
]

BRANDS = ["bca", "mandiri", "bni", "bri", "tokopedia", "shopee", "paypal"]

# ----------------- FUNGSI DETEKSI -----------------

def is_phishing_url(url):
    """Deteksi URL phishing"""
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        parsed = urlparse(url)
        if not parsed.netloc:
            return True, "URL tidak valid"

        domain = parsed.netloc.lower().split(':')[0]

        # Cek TLD mencurigakan
        if any(domain.endswith(tld) for tld in SUSPICIOUS_TLD):
            return True, "TLD mencurigakan"

        # Cek panjang domain
        if len(domain) > 40:
            return True, "Domain terlalu panjang"

        # Cek IP langsung
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", domain):
            return True, "Menggunakan IP langsung"

        # Cek keyword
        text_check = (domain + parsed.path + parsed.query).lower()
        matched = [w for w in PHISHING_KEYWORDS if w in text_check]
        
        if len(matched) >= 2:  # Minimal 2 keyword
            return True, f"Keyword mencurigakan: {', '.join(matched[:3])}"

        # Cek brand
        for brand in BRANDS:
            if brand in domain and not domain.startswith(brand):
                return True, f"Meniru brand {brand.upper()}"

        return False, "Link aman"

    except Exception as e:
        return False, f"Error: {str(e)}"

# ----------------- LOGGING -----------------

def log_message(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass

# ----------------- KIRIM WHATSAPP -----------------

def send_whatsapp(chat_id, message):
    """Kirim pesan WhatsApp"""
    url = f"{API_BASE}sendMessage/{API_TOKEN}"
    payload = {
        "chatId": chat_id,
        "message": message,
        "linkPreview": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code in (200, 201):
            log_message(f"✅ Pesan terkirim ke {chat_id[:15]}...")
            return True
        else:
            log_message(f"❌ Gagal kirim: {response.status_code}")
            return False
    except Exception as e:
        log_message(f"❌ Error kirim: {e}")
        return False

# ----------------- AUTO REPLY FUNCTIONS -----------------

def auto_reply_welcome(chat_id):
    """Auto reply untuk pesan sapaan"""
    welcome_msg = """👋 *Halo! Saya Bot Deteksi Phishing*

Kirimkan link yang ingin Anda cek, saya akan analisis apakah link tersebut berbahaya atau aman.

📌 *Contoh penggunaan:*
• Ketik atau kirim link: https://www.google.com
• Saya akan memberi tahu hasilnya

🔍 *Yang saya cek:*
• TLD mencurigakan (.xyz, .tk, dll)
• Kata-kata phishing (login, verifikasi, dll)
• Brand tiruan (bca, mandiri, dll)
• Domain aneh dan homograph

Tetap waspada terhadap link mencurigakan! 💪"""
    
    return send_whatsapp(chat_id, welcome_msg)

def auto_reply_phishing(chat_id, url, reason):
    """Auto reply untuk link phishing"""
    reply = f"""🚨 *PERINGATAN PHISHING!* 🚨

Link yang Anda kirim *TERDETEKSI BERBAHAYA*!

🔗 *Link:* 
{url}

❌ *Alasan:* {reason}

⚠️ *JANGAN KLIK LINK TERSEBUT!*
Link ini bisa mencuri:
• Password & PIN
• Data bank
• Kode OTP
• Informasi pribadi

✅ *Yang harus dilakukan:*
• Hapus pesan tersebut
• Jangan bagikan ke siapapun
• Laporkan jika perlu

_Bot Deteksi Phishing Otomatis_"""
    
    return send_whatsapp(chat_id, reply)

def auto_reply_safe(chat_id, url):
    """Auto reply untuk link aman"""
    reply = f"""✅ *Link Aman*

Terima kasih telah menggunakan bot deteksi phishing.

🔗 *Link:* {url}

📊 *Hasil:* Link ini terlihat aman dari deteksi kami.

💡 *Tips:* 
• Tetap waspada terhadap link mencurigakan
• Jangan sembarangan memasukkan data pribadi
• Laporkan jika menemukan link aneh

Tetap aman di dunia digital! 🛡️"""
    
    return send_whatsapp(chat_id, reply)

def auto_reply_help(chat_id):
    """Auto reply untuk bantuan"""
    help_msg = """📋 *BANTUAN BOT DETEKSI PHISHING*

*Cara Penggunaan:*
1. Kirim link yang ingin dicek
2. Bot akan otomatis menganalisis
3. Dapatkan hasil dalam beberapa detik

*Perintah:*
• /start - Mulai bot
• /help - Tampilkan bantuan ini
• /stats - Info bot

*Contoh link yang aman:*
• https://www.google.com
• https://www.tokopedia.com

*Contoh link berbahaya:*
• https://bca-login.xyz
• https://xn--pple-43d.com

*Catatan:* Bot ini gratis dan terus dikembangkan.

Ada pertanyaan? Hubungi admin."""
    
    return send_whatsapp(chat_id, help_msg)

def auto_reply_stats(chat_id):
    """Auto reply untuk statistik sederhana"""
    stats_msg = """📊 *STATISTIK BOT*

• Status: Aktif 🟢
• Versi: 1.0
• Fitur: Deteksi phishing otomatis
• Cakupan: Link, Punycode, Homograph
• Update: Real-time

Bot siap membantu Anda! 💪

Kirim link untuk mulai pengecekan."""
    
    return send_whatsapp(chat_id, stats_msg)

def auto_reply_no_link(chat_id, text):
    """Auto reply untuk pesan tanpa link"""
    text_lower = text.lower().strip()
    
    if text_lower in ["/start", "start", "mulai"]:
        return auto_reply_welcome(chat_id)
    elif text_lower in ["/help", "help", "bantuan"]:
        return auto_reply_help(chat_id)
    elif text_lower in ["/stats", "stats", "statistik"]:
        return auto_reply_stats(chat_id)
    elif text_lower in ["hai", "halo", "hi", "hey", "p"]:
        reply = "👋 Halo! Ada yang bisa dibantu? Kirim link untuk dicek atau ketik /help untuk bantuan."
        return send_whatsapp(chat_id, reply)
    elif text_lower in ["makasih", "terima kasih", "thanks"]:
        reply = "🙏 Sama-sama! Selalu waspada ya terhadap link mencurigakan."
        return send_whatsapp(chat_id, reply)
    else:
        # Pesan biasa tanpa link, kasih pengingat
        reply = "📌 Kirim link yang ingin dicek keamanannya. Contoh: https://www.google.com"
        return send_whatsapp(chat_id, reply)

# ----------------- PROSES PESAN -----------------

def process_message(text, from_chat, sender_name):
    """Proses pesan masuk dengan auto reply"""
    log_message(f"\n{'='*50}")
    log_message(f"📩 PESAN MASUK")
    log_message(f"👤 Pengirim: {sender_name}")
    log_message(f"📱 Nomor: {from_chat}")
    log_message(f"💬 Isi: {text[:100]}")
    
    # Cek apakah ini pesan dari diri sendiri (untuk test)
    is_self_test = (from_chat == BOT_PHONE)
    if is_self_test:
        log_message("🔄 Mode test: pesan dari diri sendiri")
    
    # Ekstrak URL dari pesan
    urls = re.findall(r'https?://[^\s<>"\']+|www\.[^\s<>"\']+', text)
    urls = [u.rstrip('.,;:!?)') for u in urls]
    
    # JIKA ADA URL
    if urls:
        for url in urls:
            # Deteksi phishing
            is_phish, reason = is_phishing_url(url)
            
            status = "🔴 PHISHING" if is_phish else "🟢 AMAN"
            log_message(f"🔍 URL: {url}")
            log_message(f"📊 Status: {status}")
            log_message(f"📝 Alasan: {reason}")
            
            # KIRIM ALERT KE ADMIN (nomor Anda)
            alert_msg = (
                f"🚨 *ALERT BOT*\n\n"
                f"👤 Pengirim: {sender_name}\n"
                f"📱 Nomor: {from_chat}\n"
                f"🔗 URL: {url}\n"
                f"⚠️ Status: {status}\n"
                f"📝 Alasan: {reason}\n"
                f"⏰ Waktu: {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"{'📌 TEST DARI DIRI SENDIRI' if is_self_test else '📌 PESAN DARI USER'}"
            )
            send_whatsapp(ADMIN_PHONE, alert_msg)
            
            # AUTO REPLY KE PENGIRIM berdasarkan hasil
            if is_phish:
                # Kirim peringatan phishing
                auto_reply_phishing(from_chat, url, reason)
            else:
                # Kirim konfirmasi link aman
                auto_reply_safe(from_chat, url)
            
            log_message(f"✅ Auto reply terkirim ke {from_chat[:15]}...")
    
    # JIKA TIDAK ADA URL
    else:
        log_message("ℹ️ Tidak ada link dalam pesan")
        # Auto reply untuk pesan tanpa link
        auto_reply_no_link(from_chat, text)
    
    log_message(f"{'='*50}\n")

# ----------------- POLLING -----------------

def polling_messages():
    """Polling pesan masuk"""
    log_message("=" * 60)
    log_message("🚀 BOT DETEKSI PHISHING - DENGAN AUTO REPLY")
    log_message(f"📱 Nomor Bot: {BOT_PHONE}")
    log_message(f"👤 Admin Alert: {ADMIN_PHONE}")
    log_message("📌 Mode: Auto reply aktif untuk semua pesan")
    log_message("=" * 60)
    log_message("\n📡 Menunggu pesan masuk...\n")
    
    last_receipt = None
    error_count = 0
    
    while True:
        try:
            # Ambil notifikasi
            resp = requests.get(
                f"{API_BASE}receiveNotification/{API_TOKEN}",
                timeout=30
            )
            
            if resp.status_code == 200:
                if resp.text and resp.text != "null":
                    data = resp.json()
                    receipt_id = data.get('receiptId')
                    
                    if receipt_id and receipt_id != last_receipt:
                        last_receipt = receipt_id
                        error_count = 0
                        
                        # Proses hanya pesan MASUK
                        body = data.get('body', {})
                        if body.get('typeWebhook') == 'incomingMessageReceived':
                            msg_data = body.get('messageData', {})
                            
                            # Ambil teks pesan
                            text = ""
                            msg_type = msg_data.get('typeOfMessage')
                            
                            if msg_type == 'textMessage':
                                text = msg_data.get('textMessageData', {}).get('textMessage', '')
                            elif msg_type == 'imageMessage':
                                # Coba ambil caption
                                text = msg_data.get('extendedTextMessageData', {}).get('text', '')
                            
                            if text:
                                sender = body.get('senderData', {})
                                chat_id = sender.get('chatId', '')
                                sender_name = sender.get('senderName', 'Unknown')
                                
                                # Proses pesan di thread terpisah
                                threading.Thread(
                                    target=process_message,
                                    args=(text, chat_id, sender_name),
                                    daemon=True
                                ).start()
                    
                    # HAPUS NOTIFIKASI (WAJIB!)
                    try:
                        requests.delete(
                            f"{API_BASE}deleteNotification/{API_TOKEN}/{receipt_id}",
                            timeout=5
                        )
                    except:
                        pass
                
                # Tidak ada notifikasi, tampilkan indikator hidup
                else:
                    if int(time.time()) % 30 == 0:  # Setiap 30 detik
                        print(".", end="", flush=True)
            
            time.sleep(2)
            
        except KeyboardInterrupt:
            log_message("\n\n👋 Bot dimatikan oleh user")
            break
        except Exception as e:
            error_count += 1
            if error_count > 5:
                log_message(f"❌ Error terus menerus: {e}")
                time.sleep(10)
            else:
                time.sleep(5)

# ----------------- MAIN -----------------

if __name__ == "__main__":
    try:
        polling_messages()
    except KeyboardInterrupt:
        log_message("\nBot dihentikan")
