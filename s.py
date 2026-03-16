# phishing_detector_complete_fixed.py
import re
import requests
import json
import time
import socket
import ssl
from urllib.parse import urlparse, parse_qs
import threading
from datetime import datetime

# === KONFIGURASI ===
ID_INSTANCE = "7107549990"
API_TOKEN = "2f7a295177544c34a4f8f86b74d3c3358c797bef7a154c1ebf"
API_BASE = f"https://api.green-api.com/waInstance{ID_INSTANCE}/"

# ISI DENGAN API KEY GOOGLE SAFE BROWSING ANDA!
GOOGLE_SAFE_BROWSING_API_KEY = "AlzaSyCPhDtXXwKy-PPNrg5BYksPDqCmipg6mCO"  # GANTI!

BOT_PHONE = "6288223749303@c.us"
ADMIN_PHONE = "6288223749303@c.us"

LOG_FILE = "phishing_log.txt"

# Daftar TLD mencurigakan
SUSPICIOUS_TLD = [
    ".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".club", 
    ".site", ".online", ".link", ".buzz", ".live", ".digital", 
    ".shop", ".men", ".cyou", ".cfd", ".bid", ".trade", ".review",
    ".stream", ".download", ".gp", ".date", ".win"
]

# Keyword phishing (diperluas)
PHISHING_KEYWORDS = [
    # Login/Akun
    "login", "signin", "sign-in", "logIn", "account", "akun", 
    "verify", "verifikasi", "confirm", "konfirmasi", "validation",
    
    # Keamanan
    "secure", "security", "safe", "protection", "secure", 
    "password", "passwd", "pwd", "credentials", "kredensial",
    "otp", "kode", "token", "pin", "2fa", "mfa",
    
    # Bank/Finance
    "bank", "banking", "bca", "mandiri", "bni", "bri", "cimb", "danamon",
    "paypal", "visa", "mastercard", "credit", "card", "kartu",
    
    # E-commerce
    "tokopedia", "shopee", "bukalapak", "lazada", "blibli", "jdid",
    "payment", "pembayaran", "checkout", "cart", "keranjang",
    
    # Penipuan umum
    "hadiah", "gratis", "free", "prize", "menang", "winner",
    "promo", "discount", "diskon", "cashback", "bonus",
    "klaim", "claim", "redeem", "tukar",
    
    # Ancaman
    "suspended", "blokir", "blocked", "limited", "terbatas",
    "urgent", "important", "warning", "alert", "notice",
    "update", "upgrade", "reactivate", "aktivasi",
    
    # File/Extension
    "download", "file", "doc", "pdf", "exe", "apk", "zip", "rar"
]

# Brand yang sering ditiru
BRANDS = ["bca", "mandiri", "bni", "bri", "tokopedia", "shopee", "paypal", "dana", "ovo", "gopay"]

# EXTENSION FILE YANG MENcurigakan
SUSPICIOUS_EXTENSIONS = [
    # Executable
    ".exe", ".msi", ".bat", ".cmd", ".sh", ".bin", ".run",
    # Android
    ".apk", ".xapk",
    # Compressed
    ".zip", ".rar", ".7z", ".tar", ".gz",
    # Documents (bisa macro)
    ".docm", ".xlsm", ".pptm", ".macro",
    # Script
    ".js", ".vbs", ".ps1", ".php", ".asp", ".jsp",
    # Others
    ".jar", ".dmg", ".pkg", ".deb", ".rpm"
]

# EXTENSION YANG SERING DIPAKAI PHISHING
PHISHING_EXTENSIONS = [
    ".html", ".htm", ".php", ".asp", ".jsp",  # Web pages
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",  # Documents
]

# Path mencurigakan (sering dipakai phishing)
SUSPICIOUS_PATHS = [
    "/login", "/signin", "/verify", "/account", "/secure",
    "/banking", "/payment", "/checkout", "/cart",
    "/otp", "/token", "/pin", "/password",
    "/update", "/confirm", "/validate",
    "/suspended", "/blocked", "/limited",
    "/claim", "/redeem", "/gift", "/prize",
    "/download", "/file", "/doc", "/pdf"
]

# Parameter query mencurigakan
SUSPICIOUS_QUERY = [
    "redirect", "url", "link", "goto", "return", "next",
    "source", "ref", "referrer", "campaign",
    "token", "auth", "session", "id",
    "file", "download", "doc"
]

# Shortener services
SHORTENERS = ["bit.ly", "tinyurl.com", "goo.gl", "ow.ly", "tiny.cc", "is.gd", "rb.gy", "short.link"]

# Domain yang DIKECUALIKAN dari deteksi (domain aman/terkenal)
WHITELIST_DOMAINS = [
    "google.com", "youtube.com", "facebook.com", "instagram.com",
    "twitter.com", "whatsapp.com", "github.com", "stackoverflow.com",
    "wikipedia.org", "amazon.com", "netflix.com", "spotify.com",
    "telegram.org", "discord.com", "reddit.com", "linkedin.com",
    "tokopedia.com", "shopee.co.id", "bukalapak.com", "lazada.co.id",
    "blibli.com", "traveloka.com", "gojek.com", "grab.com",
    "office.com", "microsoft.com", "windows.com",
    "apple.com", "icloud.com", "zoom.us"
]

# ----------------- FUNGSI CEK EXTENSION DI URL -----------------
def extract_extension(path):
    """
    Ekstrak extension dari path URL
    Contoh: /file/document.pdf -> .pdf
            /image.jpg?size=large -> .jpg
    """
    if not path or path == '/':
        return None
    
    # Ambil bagian terakhir dari path
    last_part = path.split('/')[-1]
    
    # Cek apakah ada titik di nama file
    if '.' in last_part:
        # Ambil extension (termasuk titik)
        ext = '.' + last_part.split('.')[-1].lower()
        # Bersihkan dari query parameters
        if '?' in ext:
            ext = ext.split('?')[0]
        return ext
    return None

def analyze_extension(extension):
    """
    Analisis extension file untuk indikasi bahaya
    """
    if not extension:
        return [], 0
    
    results = []
    score = 0
    
    # Cek extension executable (sangat berbahaya)
    if extension in SUSPICIOUS_EXTENSIONS:
        if extension in ['.exe', '.msi', '.apk']:
            results.append(f"❌ EXTENSION EKSEKUTABEL {extension}")
            score += 5
        else:
            results.append(f"❌ Extension berbahaya {extension}")
            score += 4
    
    # Cek extension yang sering dipakai phishing
    elif extension in PHISHING_EXTENSIONS:
        if extension in ['.php', '.asp', '.html']:
            results.append(f"⚠️ Extension script {extension}")
            score += 2
        else:
            results.append(f"⚠️ Extension {extension}")
            score += 1
    
    # Cek extension dokumen (bisa macro)
    elif extension in ['.docm', '.xlsm']:
        results.append(f"⚠️ Extension macro {extension}")
        score += 3
    
    return results, score

def is_downloadable_extension(extension):
    """Cek apakah extension menandakan file download"""
    download_extensions = ['.exe', '.msi', '.apk', '.zip', '.rar', '.pdf', '.doc', '.xls']
    return extension in download_extensions

# ----------------- FUNGSI CEK APAKAH DOMAIN DI WHITELIST -----------------
def is_whitelisted(domain):
    """Cek apakah domain masuk whitelist (aman)"""
    domain = domain.lower()
    for whitelisted in WHITELIST_DOMAINS:
        if domain == whitelisted or domain.endswith('.' + whitelisted):
            return True
    return False

# ----------------- FUNGSI ANALISIS PATH OTOMATIS (DENGAN EXTENSION) -----------------
def analyze_path_automatically(path):
    """
    Analisis path secara otomatis termasuk extension
    """
    if not path or path == '/':
        return [], 0
    
    results = []
    score = 0
    
    # Bersihkan path
    path = path.lower()
    
    # CEK EXTENSION
    extension = extract_extension(path)
    if extension:
        ext_results, ext_score = analyze_extension(extension)
        results.extend(ext_results)
        score += ext_score
    
    # 1. CEK PANJANG PATH
    path_length = len(path)
    if path_length > 100:
        results.append(f"❌ Path sangat panjang ({path_length} chars)")
        score += 3
    elif path_length > 50:
        results.append(f"⚠️ Path panjang ({path_length} chars)")
        score += 1
    
    # 2. HITUNG JUMLAH SEGMEN
    segments = [s for s in path.split('/') if s]
    depth = len(segments)
    
    if depth > 10:
        results.append(f"❌ Path terlalu dalam ({depth} level)")
        score += 3
    elif depth > 5:
        results.append(f"⚠️ Path dalam ({depth} level)")
        score += 1
    
    # 3. CEK SETIAP SEGMEN
    dangerous_segments = []
    file_indicators = []
    
    for segment in segments:
        # Cek keyword phishing
        for keyword in PHISHING_KEYWORDS:
            if keyword in segment and len(segment) > 2:
                dangerous_segments.append(segment)
                score += 2
                break
        
        # Cek indikasi file
        if '.' in segment:
            file_indicators.append(segment)
            score += 1
        
        # Cek angka random
        if re.match(r'^\d+$', segment) and len(segment) > 3:
            dangerous_segments.append(f"#{segment}")
            score += 1
    
    if dangerous_segments:
        results.append(f"❌ Segmen berbahaya: {' → '.join(dangerous_segments[:3])}")
    
    if file_indicators:
        results.append(f"⚠️ Indikasi file: {', '.join(file_indicators[:2])}")
    
    # 4. CEK BRAND DI PATH
    for brand in BRANDS:
        if brand in path:
            results.append(f"❌ Path mengandung brand {brand.upper()}")
            score += 3
    
    # 5. CEK POLA FILE DOWNLOAD
    if any(word in path for word in ['download', 'file', 'get']):
        if extension and is_downloadable_extension(extension):
            results.append(f"❌ Link download file {extension}")
            score += 4
    
    return results, score

# ----------------- FUNGSI ANALISIS DOMAIN OTOMATIS -----------------
def analyze_domain_automatically(domain):
    """Analisis domain secara otomatis"""
    results = []
    score = 0
    
    # 1. CEK TLD
    for tld in SUSPICIOUS_TLD:
        if domain.endswith(tld):
            results.append(f"❌ TLD {tld}")
            score += 3
            break
    
    # 2. CEK IP LANGSUNG
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", domain):
        results.append("❌ Menggunakan IP langsung")
        score += 4
    
    # 3. CEK KEYWORD DI DOMAIN
    domain_keywords = []
    for keyword in PHISHING_KEYWORDS:
        if keyword in domain:
            domain_keywords.append(keyword)
    
    if domain_keywords:
        results.append(f"❌ Domain mengandung keyword: {', '.join(domain_keywords[:3])}")
        score += len(domain_keywords)
    
    # 4. CEK BRAND TIRUAN
    for brand in BRANDS:
        if brand in domain and brand not in domain.split('.')[0]:
            if domain != f"{brand}.com" and domain != f"{brand}.co.id":
                results.append(f"❌ Meniru brand {brand.upper()}")
                score += 3
                break
    
    # 5. CEK PANJANG DOMAIN
    domain_length = len(domain)
    if domain_length > 40:
        results.append(f"❌ Domain terlalu panjang ({domain_length})")
        score += 2
    elif domain_length > 30:
        results.append(f"⚠️ Domain panjang ({domain_length})")
        score += 1
    
    # 6. CEK SUBDOMAIN
    subdomain_count = domain.count('.')
    if subdomain_count >= 4:
        results.append(f"❌ Terlalu banyak subdomain ({subdomain_count})")
        score += 3
    elif subdomain_count >= 3:
        results.append(f"⚠️ Banyak subdomain ({subdomain_count})")
        score += 1
    
    return results, score

# ----------------- DETEKSI LOKAL OTOMATIS (DENGAN EXTENSION) -----------------
def detect_local_auto(url):
    """Deteksi phishing secara otomatis termasuk extension"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path
        
        if ':' in domain:
            domain = domain.split(':')[0]
        
        all_reasons = []
        total_score = 0
        
        # CEK WHITELIST
        if is_whitelisted(domain):
            return False, "Domain dalam whitelist"
        
        # ANALISIS DOMAIN
        domain_results, domain_score = analyze_domain_automatically(domain)
        if domain_results:
            all_reasons.extend(domain_results)
            total_score += domain_score
        
        # ANALISIS PATH (termasuk extension)
        path_results, path_score = analyze_path_automatically(path)
        if path_results:
            all_reasons.extend(path_results)
            total_score += path_score
        
        # TAMBAHKAN INFO EXTENSION
        extension = extract_extension(path)
        if extension:
            all_reasons.append(f"📎 Extension: {extension}")
        
        if total_score >= 3:
            return True, f"Local: {' | '.join(all_reasons[:3])}"
        else:
            return False, "Local: Clean"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

# ----------------- CEK GOOGLE SAFE BROWSING -----------------
def check_gsb(url):
    """Cek URL ke Google Safe Browsing API"""
    
    if not GOOGLE_SAFE_BROWSING_API_KEY or GOOGLE_SAFE_BROWSING_API_KEY == "AIzaSyC0UJjLx6k2QZzFvKjLx6k2QZzFvKjLx6k2Q":
        return False, "GSB: API Key tidak diset"
    
    endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={GOOGLE_SAFE_BROWSING_API_KEY}"
    
    payload = {
        "client": {
            "clientId": "phishing-detector-bot",
            "clientVersion": "1.0"
        },
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}]
        }
    }
    
    try:
        resp = requests.post(endpoint, json=payload, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            if "matches" in data and data["matches"]:
                return True, "GSB: Terdeteksi"
            else:
                return False, "GSB: Clean"
        else:
            return False, f"GSB: Error {resp.status_code}"
            
    except Exception as e:
        return False, f"GSB: Error"

# ----------------- CEK DNS -----------------
def check_dns(domain):
    """Cek apakah domain bisa di-resolve"""
    try:
        ip = socket.gethostbyname(domain)
        return True, ip
    except:
        return False, "❌ DOMAIN TIDAK DITEMUKAN"

# ----------------- CEK SERVER -----------------
def check_server_status(url):
    """Cek status server"""
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        response = requests.get(url, timeout=10, allow_redirects=True)
        
        if response.status_code >= 500:
            return False, f"❌ Server Error {response.status_code}"
        elif response.status_code == 404:
            return True, f"⚠️ Halaman tidak ditemukan (404)"
        else:
            return True, f"✅ HTTP {response.status_code}"
            
    except Exception as e:
        return False, f"❌ Error: {str(e)[:30]}"

# ----------------- EXPAND SHORT URL -----------------
def expand_url(url):
    """Coba expand short URL"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        is_short = any(short in domain for short in SHORTENERS)
        
        if not is_short:
            return url, False, "Bukan short URL"
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.head(url, allow_redirects=True, timeout=5, headers=headers)
        
        if resp.url != url:
            return resp.url, True, f"Redirect ke: {resp.url}"
        else:
            return url, True, "Short URL"
            
    except:
        return url, True, "Short URL (error)"

# ----------------- DETEKSI UTAMA -----------------
def detect_phishing(url):
    """Deteksi phishing dengan semua metode"""
    
    print(f"\n{'='*60}")
    print(f"🔍 Menganalisis: {url}")
    print(f"{'='*60}")
    
    result = {
        'is_phishing': False,
        'reasons': [],
        'method': 'none',
        'domain': '',
        'ip': None,
        'extension': None
    }
    
    try:
        # Step 1: Parse URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path
        
        if ':' in domain:
            domain = domain.split(':')[0]
        
        result['domain'] = domain
        result['path'] = path
        result['extension'] = extract_extension(path)
        
        print(f"📌 Domain: {domain}")
        print(f"📌 Path: {path if path else '/'}")
        if result['extension']:
            print(f"📌 Extension: {result['extension']}")
        
        # Step 2: Cek DNS
        dns_ok, dns_info = check_dns(domain)
        if not dns_ok:
            result['is_phishing'] = True
            result['reasons'].append(dns_info)
            result['method'] = 'dns'
            return result
        
        result['ip'] = dns_info
        print(f"✅ IP: {dns_info}")
        
        # Step 3: Cek GSB
        gsb_phish, gsb_reason = check_gsb(url)
        if gsb_phish:
            result['is_phishing'] = True
            result['reasons'].append(gsb_reason)
            result['method'] = 'gsb'
            return result
        
        # Step 4: Cek server
        server_ok, server_msg = check_server_status(url)
        if not server_ok:
            result['is_phishing'] = True
            result['reasons'].append(server_msg)
            result['method'] = 'server'
            return result
        else:
            if '⚠️' in server_msg:
                result['reasons'].append(server_msg)
        
        # Step 5: Cek lokal (dengan extension)
        local_phish, local_reason = detect_local_auto(url)
        if local_phish:
            result['is_phishing'] = True
            result['reasons'].append(local_reason)
            result['method'] = 'local'
            return result
        
        # Aman
        if not result['reasons']:
            result['reasons'].append("✅ Semua clean")
        result['method'] = 'clean'
        return result
        
    except Exception as e:
        result['is_phishing'] = True
        result['reasons'].append(f"❌ Error: {str(e)}")
        return result

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

# ----------------- KIRIM ALERT -----------------
def send_alert(sender_name, chat_id, result):
    """Kirim alert ke WhatsApp"""
    
    url = result.get('original_url', 'Unknown')
    domain = result.get('domain', 'Unknown')
    path = result.get('path', '/')
    ext = result.get('extension')
    is_phish = result.get('is_phishing', False)
    reasons = result.get('reasons', ['Unknown'])
    method = result.get('method', 'unknown')
    
    if is_phish:
        header = "🚨🚨 PHISHING DETECTED! 🚨🚨"
        status = "🔴 BERBAHAYA"
        recommendation = "❌ JANGAN DIKLIK! HAPUS SEGERA!"
    else:
        header = "✅✅ LINK AMAN ✅✅"
        status = "🟢 AMAN"
        recommendation = "✅ Aman, tetap waspada"
    
    reason_text = "\n  • ".join(reasons)
    
    # Tambah info extension
    ext_info = f"\n  • Extension: {ext}" if ext else ""
    
    message = f"""
{header}

📌 *PENGIRIM*
• Nama: {sender_name}
• Nomor: {chat_id.replace('@c.us', '')}
• Waktu: {datetime.now().strftime('%H:%M:%S')}

🔗 *LINK*
• URL: {url[:100]}{'...' if len(url)>100 else ''}
• Domain: {domain}
• Path: {path}{ext_info}
• IP: {result.get('ip', 'N/A')}

🔍 *HASIL ANALISIS*
• Status: {status}
• Metode: {method.upper()}
• Deteksi:
  • {reason_text}

💡 *REKOMENDASI*
• {recommendation}

⚡ *CYBER PHISHING DETECTOR v5.0 (Extension Aware)*
"""
    
    wa_url = f"{API_BASE}sendMessage/{API_TOKEN}"
    payload = {
        "chatId": ADMIN_PHONE,
        "message": message,
        "linkPreview": False
    }
    
    try:
        resp = requests.post(wa_url, json=payload, timeout=10)
        if resp.status_code in (200, 201):
            log_message(f"✅ Alert terkirim: {domain}{path}")
            return True
    except:
        return False

# ----------------- EKSTRAK URL -----------------
def extract_urls(text):
    """Ekstrak URL dari teks"""
    pattern = r'https?://[^\s<>"\']+|www\.[^\s<>"\']+'
    urls = re.findall(pattern, text)
    return [u.rstrip('.,;:!?)>]') for u in urls]

# ----------------- PROSES PESAN -----------------
def process_message(notification_data):
    """Proses pesan masuk"""
    try:
        body = notification_data.get('body', {})
        
        message_data = body.get('messageData', {})
        sender_data = body.get('senderData', {})
        
        msg_type = message_data.get('typeMessage', '')
        text = ""
        
        if msg_type == 'textMessage':
            text = message_data.get('textMessageData', {}).get('textMessage', '')
        elif msg_type == 'extendedTextMessage':
            text = message_data.get('extendedTextMessageData', {}).get('text', '')
        
        if not text:
            return
        
        chat_id = sender_data.get('chatId', '')
        sender_name = sender_data.get('senderName', 'Unknown')
        
        # Skip alert dari bot sendiri
        if chat_id == BOT_PHONE:
            if any(x in text.lower() for x in ['phishing', 'alert']):
                return
        
        log_message(f"\n📨 Pesan dari {sender_name}")
        log_message(f"💬 Isi: {text[:100]}...")
        
        urls = extract_urls(text)
        
        if urls:
            for url in urls:
                log_message(f"🔗 URL: {url}")
                result = detect_phishing(url)
                result['original_url'] = url
                send_alert(sender_name, chat_id, result)
                
                status = "PHISHING" if result['is_phishing'] else "AMAN"
                log_message(f"📊 Hasil: {status}")
        else:
            log_message("ℹ️ Tidak ada URL")
            
    except Exception as e:
        log_message(f"❌ Error: {e}")

# ----------------- FUNGSI POLLING -----------------
def polling():
    """Polling pesan masuk dari Green API"""
    print("\n" + "="*70)
    print("  🤖 CYBER PHISHING DETECTOR v5.0 (Extension Aware)")
    print("="*70)
    print(f"  📱 Bot: {BOT_PHONE}")
    print(f"  🎯 Alert: {ADMIN_PHONE}")
    print(f"  🔍 GSB: {'AKTIF' if GOOGLE_SAFE_BROWSING_API_KEY and GOOGLE_SAFE_BROWSING_API_KEY != 'AlzaSyCPhDtXXwKy-PPNrg5BYksPDqCmipg6mCO' else 'TIDAK AKTIF'}")
    print("="*70 + "\n")
    
    log_message("=== BOT START ===")
    
    processed = set()
    
    while True:
        try:
            # Ambil notifikasi dari Green API
            url = f"{API_BASE}receiveNotification/{API_TOKEN}"
            resp = requests.get(url, timeout=20)
            
            if resp.status_code == 200 and resp.text and resp.text != "null":
                data = resp.json()
                receipt_id = data.get('receiptId')
                
                if receipt_id and receipt_id not in processed:
                    processed.add(receipt_id)
                    
                    # Proses di thread terpisah
                    thread = threading.Thread(target=process_message, args=(data,))
                    thread.daemon = True
                    thread.start()
                
                # Hapus notifikasi (wajib!)
                try:
                    del_url = f"{API_BASE}deleteNotification/{API_TOKEN}/{receipt_id}"
                    requests.delete(del_url, timeout=5)
                except:
                    pass
            
            # Bersihin cache
            if len(processed) > 5000:
                processed.clear()
            
            time.sleep(0.5)
            
        except KeyboardInterrupt:
            log_message("Bot dihentikan user")
            print("\n👋 Shutdown...")
            break
        except Exception as e:
            log_message(f"Polling error: {e}")
            time.sleep(3)



# ----------------- MAIN -----------------
if __name__ == "__main__":
    # Uncomment untuk test extension dulu
    # test_extensions()
    # exit()
    
    try:
        # Test koneksi Green API
        test_url = f"{API_BASE}getStateInstance/{API_TOKEN}"
        test_resp = requests.get(test_url, timeout=10)
        
        if test_resp.status_code == 200:
            state = test_resp.json().get('stateInstance', 'unknown')
            print(f"✅ Green API Connected! State: {state}")
            
            if state == 'authorized':
                polling()
            else:
                print("❌ Bot belum authorized! Scan QR di console Green API")
        else:
            print(f"❌ Gagal konek Green API: {test_resp.status_code}")
            
    except Exception as e:
        print(f"❌ Startup error: {e}")
