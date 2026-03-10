from whatsapp_api_client_python import API
from flask import Flask, request, jsonify
import re
from urllib.parse import urlparse
import threading
import time
from datetime import datetime

app = Flask(__name__)

# ================== KONFIGURASI GREEN-API ==================
ID_INSTANCE = "1101XXXXXXX"          # GANTI dengan idInstance kamu
API_TOKEN = "d75b3a66374942c5b3c019c698abc2067e151558acbd412345"  # GANTI dengan apiTokenInstance

greenAPI = API.GreenAPI(ID_INSTANCE, API_TOKEN)

# ================== DETEKSI PHISHING (super canggih seperti sebelumnya) ==================
WHITELIST_DOMAINS = [
    "bca.co.id", "klikbca.com", "bankmandiri.co.id", "mandiri.co.id", "livin.mandiri.co.id",
    "bri.co.id", "bni.co.id", "bsi.co.id", "dana.id", "ovo.id", "gopay.co.id",
    "shopee.co.id", "tokopedia.com", "lazada.co.id", "blibli.com"
]

BLACKLIST_PATTERNS = [
    r"bca-?login", r"bca-?verif", r"mandiri-?verif", r"dana-?verifikasi",
    r"ovo-?verif", r"gopay-?verifikasi", r"shopee-?claim", r"bit\.ly", r"tinyurl\.com",
    r"verif-?akun", r"hadiah-?gratis", r"free-?(diamond|uc)"
]

SUSPICIOUS_TLDS = [".top", ".xyz", ".club", ".online", ".site", ".shop", ".live"]
URGENT_KEYWORDS = ["segera", "sekarang", "akun diblokir", "verifikasi sekarang", "klaim hadiah"]

checked_urls = set()

def calculate_phishing_score(url, text=""):
    score = 0
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")
    path_query = parsed.path.lower() + "?" + parsed.query.lower()

    if any(w in domain for w in WHITELIST_DOMAINS):
        return 0

    for pat in BLACKLIST_PATTERNS:
        if re.search(pat, domain) or re.search(pat, path_query):
            score += 45

    if any(tld in domain for tld in SUSPICIOUS_TLDS):
        score += 30

    if len(domain) > 40 or domain.count('-') >= 5:
        score += 25

    if any(kw in text.lower() for kw in URGENT_KEYWORDS):
        score += 20

    return min(score, 100)

def extract_urls(text):
    return re.findall(r'(?:https?://|www\.)[^\s<>"\']+', text)

def send_warning(chat_id, message_text):
    warning = (
        f"⚠️ *PERINGATAN KEAMANAN TINGGI!*\n\n"
        f"Link mencurigakan terdeteksi di chat ini!\n"
        f"{message_text[:100]}...\n\n"
        f"JANGAN KLIK link tersebut!\n"
        f"Bot VortexStore Security"
    )
    greenAPI.sending.sendMessage(chatId=chat_id, message=warning)

# ================== WEBHOOK ENDPOINT (terima pesan masuk) ==================
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        data = request.json
        print("Webhook diterima:", data)

        # Cek tipe webhook incoming message
        if data.get('typeWebhook') == 'incomingMessageReceived':
            message_data = data.get('messageData', {})
            text = message_data.get('textMessageData', {}).get('textMessage', '')
            chat_id = data.get('senderData', {}).get('chatId', '')

            if text:
                urls = extract_urls(text)
                for url in urls:
                    if url in checked_urls:
                        continue
                    checked_urls.add(url)

                    score = calculate_phishing_score(url, text)
                    print(f"URL: {url} | Score: {score}")

                    if score >= 65:
                        send_warning(chat_id, text)

        return jsonify({"status": "ok"}), 200

    return "Method not allowed", 405

# ================== JALANKAN SERVER ==================
if __name__ == '__main__':
    print("Bot Phishing GREEN-API mulai...")
    print("Pastikan webhook sudah di-set di dashboard GREEN-API ke: http://localhost:5000/webhook")
    print("Gunakan ngrok untuk expose lokal: ngrok http 5000")
    
    # Jalankan Flask di thread terpisah kalau mau
    threading.Thread(target=app.run, kwargs={'host':'0.0.0.0', 'port':5000, 'debug':False}).start()
    
    # Keep alive
    while True:
        time.sleep(60)
