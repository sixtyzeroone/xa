# phishing_detector_cyber_rapidapi_enriched.py
import re
import requests
import json
import time
import socket
from urllib.parse import urlparse
import threading
from datetime import datetime

# === KONFIGURASI ===
ID_INSTANCE = "7107549990"  # GANTI DENGAN ID INSTANCE ANDA YANG AKTIF
API_TOKEN = "2f7a295177544c34a4f8f86b74d3c3358c797bef7a154c1ebf"  # GANTI JIKA EXPIRED

# RapidAPI Whatsapp Data (opsional enrichment profil pengirim)
RAPIDAPI_KEY = "fd698a7e40msh89e0e60bec7a0c4p1524abjsn8fbfbe0bec5b"  # ← GANTI DENGAN X-RapidAPI-Key kamu dari https://rapidapi.com/airaudoeduardo/api/whatsapp-data1
# Jika kosong → fitur ini di-skip otomatis

API_BASE = f"https://api.green-api.com/waInstance{ID_INSTANCE}/"

BOT_PHONE = "6288223749303@c.us"
ADMIN_PHONE = "6288223749303@c.us"  # Untuk test boleh sama

LOG_FILE = "phishing_log.txt"

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

# ----------------- CEK PROFIL WHATSAPP VIA RAPIDAPI (OPTIONAL) -----------------
def get_whatsapp_profile(phone_number):
    if not RAPIDAPI_KEY:
        return None, "RapidAPI key tidak diset (fitur profil di-skip)"
    
    clean_phone = phone_number.replace('@c.us', '').replace('+', '')
    url = f"https://whatsapp-data1.p.rapidapi.com/number/{clean_phone}"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "whatsapp-data1.p.rapidapi.com"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            return data, None
        else:
            return None, f"API error {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        return None, f"Request error: {str(e)}"

# ----------------- FUNGSI DETEKSI URL -----------------
def is_phishing_url(url):
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        parsed = urlparse(url)
        if not parsed.netloc:
            return True, "URL tidak valid"
        
        domain = parsed.netloc.lower().split(':')[0]
        
        for tld in SUSPICIOUS_TLD:
            if domain.endswith(tld):
                return True, f"TLD mencurigakan ({tld} sering dipakai phishing)"
        
        try:
            ip = socket.gethostbyname(domain)
        except socket.gaierror:
            return True, "Domain tidak ditemukan / server not found (mungkin suspended atau phishing lama)"
        except Exception as se:
            return True, f"Error resolve domain: {str(se)}"
        
        if len(domain) > 40:
            return True, "Domain terlalu panjang"
        
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", domain):
            return True, "Menggunakan IP langsung"
        
        text_check = (domain + parsed.path + parsed.query).lower()
        matched = [w for w in PHISHING_KEYWORDS if w in text_check]
        if len(matched) >= 2:
            return True, f"Keyword mencurigakan: {', '.join(matched[:3])}"
        
        for brand in BRANDS:
            if brand in domain and not domain.startswith(brand + "."):
                return True, f"Meniru brand {brand.upper()}"
        
        return False, "Aman"
    except Exception as e:
        return True, f"Error analisis URL: {str(e)}"

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

# ----------------- ALERT CYBER KEREN DENGAN PROFIL ENRICHMENT -----------------
def send_cyber_alert(sender_name, chat_id, url, is_phish, reason):
    timestamp = datetime.now().strftime("%H:%M:%S")
    date = datetime.now().strftime("%d/%m/%Y")
    
    if is_phish:
        header = "▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀"
        title = "🚨 PHISHING ALERT 🚨"
        status_emoji = "🔴"
        status_text = "TERDETEKSI BERBAHAYA"
        threat_level = "KRITIS"
        action = "BLOKIR SEGERA!"
        recommendation = "JANGAN DIKLIK! HAPUS SEGERA!"
        footer = "▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄"
    else:
        header = "▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀"
        title = "✅ Result Scan ✅"
        status_emoji = "🟢"
        status_text = "Aman"
        threat_level = "RENDAH"
        action = "Aman di aksess"
        recommendation = "Aman, tetap waspada!"
        footer = "▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄"
    
    parsed = urlparse(url)
    domain = parsed.netloc or url
    
    # Enrichment profil via RapidAPI
    profile_data, profile_error = get_whatsapp_profile(chat_id)
    profile_info = ""
    if profile_data:
        profile_info = (
            f"│ ├─📛 Nama Publik : {profile_data.get('publicName', 'Tidak tersedia')}\n"
            f"│ ├─📝 Status WA   : {profile_data.get('status', 'Tidak ada')}\n"
            f"│ ├─🏢 Business     : {'Ya' if profile_data.get('isBusiness', False) else 'Tidak'}\n"
        )
        if 'profilePic' in profile_data and profile_data['profilePic']:
            profile_info += f"│ ├─🖼️ Foto Profil : {profile_data['profilePic'][:80]}...\n"
    elif profile_error:
        profile_info = f"│ ├─ℹ️ Profil WA   : {profile_error} (mungkin API maintenance)\n"
    
    alert = f"""
{header}
║ {title} ║
{header}
[ SYSTEM SCAN ]━━━━━━━━━━━━━━━━━━━
│
├─📡 TARGET INFO
│ ├─👤 Pengirim : {sender_name}
│ ├─📱 Nomor    : {chat_id.replace('@c.us', '')}
{profile_info}│ └─⏰ Waktu    : {date} {timestamp}
│
├─🔍 URL ANALYSIS
│ ├─🌐 Domain   : {domain}
│ ├─⚠️ Status   : {status_emoji} {status_text}
│ └─📝 Reason   : {reason}
│
├─⚡ THREAT METRICS
│ ├─📊 Level    : {threat_level}
│ ├─🎯 Action   : {action}
│ └─🛡️ Protocol : {parsed.scheme or 'http'}
│
└─🔐 RECOMMENDATION
   └─💬 {recommendation}
{footer}
║ CYBER PHISHING DETECTOR v1.2 (w/ WA Profile) ║
{footer}
"""
    
    url_api = f"{API_BASE}sendMessage/{API_TOKEN}"
    payload = {"chatId": ADMIN_PHONE, "message": alert, "linkPreview": False}
    
    try:
        resp = requests.post(url_api, json=payload, timeout=15)
        if resp.status_code in (200, 201):
            log_message(f"✅ Cyber alert terkirim: {domain} → {status_text}")
        else:
            log_message(f"❌ Gagal kirim alert (HTTP {resp.status_code}): {resp.text[:150]}")
    except requests.exceptions.ConnectionError as ce:
        log_message(f"❌ Connection error ke Green API: {ce}")
    except requests.exceptions.Timeout:
        log_message("❌ Timeout kirim alert → jaringan lambat")
    except Exception as e:
        log_message(f"❌ Error kirim alert: {str(e)}")

# ----------------- EKSTRAK TEKS PESAN -----------------
def extract_message_text(message_data):
    try:
        msg_type = message_data.get('typeMessage', '')
        if msg_type == 'textMessage':
            return message_data.get('textMessageData', {}).get('textMessage', '')
        elif msg_type == 'extendedTextMessage':
            return message_data.get('extendedTextMessageData', {}).get('text', '')
        return ''
    except:
        return ''

# ----------------- PROSES PESAN -----------------
def process_message(notification_data):
    try:
        receipt_id = notification_data.get('receiptId')
        if not receipt_id:
            return
        
        body = notification_data.get('body', {})
        message_data = body.get('messageData', {})
        sender_data = body.get('senderData', {})
        
        text = extract_message_text(message_data)
        if not text:
            return
        
        chat_id = sender_data.get('chatId', '')
        sender_name = sender_data.get('senderName', 'Unknown')
        
        # ANTI-LOOP: skip pesan alert dari bot sendiri
        if chat_id == BOT_PHONE:
            lower_text = text.lower()
            skip_keywords = ["phishing alert", "secure scan", "cyber", "🚨", "✅", "threat metrics", "profil wa"]
            if any(kw in lower_text for kw in skip_keywords):
                log_message(f"SKIP self-alert (anti-loop): {text[:60]}...")
                return
        
        # Skip pesan terlalu lama (>5 menit)
        msg_timestamp = body.get('timestamp', 0)
        if time.time() - msg_timestamp > 300:
            log_message(f"SKIP pesan lama (usia >5 menit): {text[:60]}...")
            return
        
        log_message(f"Processing receipt {receipt_id} | Pesan waktu: {datetime.fromtimestamp(msg_timestamp).strftime('%H:%M:%S')} | Isi: {text[:80]}...")
        
        urls = re.findall(r'https?://[^\s<>"\']+|www\.[^\s<>"\']+', text)
        urls = [u.rstrip('.,;:!?)') for u in urls]
        
        if urls:
            for url in urls:
                is_phish, reason = is_phishing_url(url)
                send_cyber_alert(sender_name, chat_id, url, is_phish, reason)
        
    except Exception as e:
        log_message(f"❌ Error process message: {str(e)}")

# ----------------- POLLING FAST -----------------
def polling_messages():
    print("\n" + "="*80)
    print(" 🤖 CYBER PHISHING DETECTOR v1.2 - SILENT + WA PROFILE ENRICHMENT ")
    print("="*80)
    print(f" 📡 Bot          : {BOT_PHONE}")
    print(f" 🎯 Alert ke     : {ADMIN_PHONE}")
    print(f" ⚙️ Mode         : Silent (No Reply)")
    print(f" 🔄 Polling delay: 0.3 detik")
    print(f" 🌐 WA Profile   : {'Aktif' if RAPIDAPI_KEY else 'Non-aktif (key kosong)'}")
    print("="*80 + "\n")
    
    log_message("=== BOT START - FAST POLLING + RAPIDAPI ENRICHMENT ===")
    
    processed = set()
    
    while True:
        try:
            resp = requests.get(f"{API_BASE}receiveNotification/{API_TOKEN}", timeout=10)
            
            if resp.status_code == 200 and resp.text and resp.text.strip() != "null":
                data = resp.json()
                receipt_id = data.get('receiptId')
                
                if receipt_id and receipt_id not in processed:
                    processed.add(receipt_id)
                    threading.Thread(target=process_message, args=(data,), daemon=True).start()
                
                try:
                    requests.delete(f"{API_BASE}deleteNotification/{API_TOKEN}/{receipt_id}", timeout=5)
                except:
                    pass
            
            time.sleep(0.3)
            
            if len(processed) > 5000:
                processed.clear()
                
        except KeyboardInterrupt:
            log_message("👋 Bot dihentikan")
            print("\n👋 Shutdown...")
            break
        except Exception as e:
            log_message(f"Polling error: {e}")
            time.sleep(3)

# ----------------- MAIN -----------------
if __name__ == "__main__":
    try:
        print("🔍 Testing koneksi Green API...")
        test_url = f"{API_BASE}getStateInstance/{API_TOKEN}"
        test_resp = requests.get(test_url, timeout=10)
        
        print(f"Status: {test_resp.status_code}")
        
        if test_resp.status_code == 200:
            data = test_resp.json()
            print("State:", data.get("stateInstance", "Tidak diketahui"))
            if data.get("stateInstance") == "authorized":
                print("✅ Authorized → mulai bot...")
                polling_messages()
            elif data.get("stateInstance") == "notAuthorized":
                print("❌ Not authorized → SCAN QR di https://console.green-api.com/")
            else:
                print("Response:", json.dumps(data, indent=2))
        else:
            print(f"❌ Gagal koneksi: {test_resp.status_code} - {test_resp.text}")
            
    except Exception as e:
        print(f"❌ Startup error: {e}")
