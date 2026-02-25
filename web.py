from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import requests
import time
import threading
import random
import string

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

API_BASE = "https://api.altare.sh/api"
running_afk = False

# --- BÊ NGUYÊN HEADERS TỪ CODE GỐC CỦA ĐẠI CA ---
HEADERS = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    "Origin": "https://altare.sh",
    "Referer": "https://altare.sh/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0"
}

def send_log(message, type="info"):
    """Đẩy log lên Web"""
    ts = time.strftime("%H:%M:%S")
    socketio.emit('new_log', {'msg': f"[{ts}] {message}", 'type': type})

def random_name(length=6):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

def login_account(email, password):
    try:
        r = requests.post(f"{API_BASE}/auth/login",
                          json={"identifier": email, "password": password},
                          headers=HEADERS)
        if r.status_code == 200:
            return r.json()["token"]
        else:
            send_log(f"Login thất bại: {r.text}", "error")
            return None
    except Exception as e:
        send_log(f"Lỗi đăng nhập: {e}", "error")
        return None

# --- CHỨC NĂNG 1: TREO AFK ---
def afk_worker(token, email):
    global running_afk
    session = requests.Session()
    session.headers.update(HEADERS)
    session.headers.update({"Authorization": f"Bearer {token}"})
    
    try:
        r = session.get(f"{API_BASE}/tenants")
        tid = r.json()['items'][0]['id']
        session.post(f"{API_BASE}/tenants/{tid}/rewards/afk/start", json={})
        send_log(f"🚀 AFK Kích hoạt cho {email}", "success")
        
        while running_afk:
            session.post(f"{API_BASE}/tenants/{tid}/rewards/afk/heartbeat", json={})
            send_log(f"💓 Heartbeat: {email} đang online", "info")
            time.sleep(30)
    except Exception as e:
        send_log(f"❌ Lỗi AFK: {str(e)}", "error")
    
    send_log(f"🛑 Đã dừng AFK cho {email}", "warning")

# --- CHỨC NĂNG 2: COPY CHÍNH XÁC MÃ NGUỒN CỦA ĐẠI CA (mao.txt) ---
def loop_worker(token, loops, delay, to, amount, email):
    session = requests.Session()
    session.headers.update(HEADERS)
    session.headers.update({"Authorization": f"Bearer {token}"})
    
    success = 0
    fail = 0
    
    send_log(f"🔥 Bắt đầu tiến trình Loop cho {email}", "warning")

    for i in range(loops):
        send_log(f"--- VÒNG {i+1}/{loops} ---", "warning")
        try:
            name = random_name()
            send_log(f"[1] Tao tenant '{name}'...", "info")
            r = session.post(f"{API_BASE}/tenants", json={"name": name})
            send_log(f"    POST /tenants: {r.status_code}", "info")

            send_log("[2] Lay tenant ID...", "info")
            r = session.get(f"{API_BASE}/tenants")
            items = r.json().get("items", [])
            tenant = None
            for t in items:
                # Tìm tenant khác Default như code gốc
                if t["name"] != "Default":
                    tenant = t
                    break
                    
            if not tenant:
                send_log("    Khong tim thay tenant moi.", "error")
                fail += 1
                continue
                
            tid = tenant["id"]
            send_log(f"    Tenant: {tenant['name']} | ID: {tid}", "info")

            send_log("[3] Claim daily reward...", "info")
            r = session.post(f"{API_BASE}/tenants/{tid}/rewards/claim", headers={"Content-Length": "0"})
            send_log(f"    Claim: {r.status_code} {r.text}", "info")

            send_log("[4] Cau hinh wallet...", "info")
            handle = random_name(12)
            r = session.post(f"{API_BASE}/tenants/{tid}/wallet/settings", json={"paymentsEnabled": True, "handle": handle})
            send_log(f"    POST wallet/settings: {r.status_code} {r.text}", "info")
            if r.status_code == 404:
                r = session.patch(f"{API_BASE}/tenants/{tid}/wallet/settings", json={"paymentsEnabled": True, "handle": handle})
                send_log(f"    PATCH wallet/settings: {r.status_code} {r.text}", "info")

            time.sleep(1)

            send_log(f"[5] Transfer {amount} cents -> {to}...", "info")
            r = session.post(f"{API_BASE}/tenants/{tid}/wallet/transfer", json={"to": to, "amountCents": amount})
            if r.status_code == 200:
                send_log("    Transfer thanh cong!", "success")
                success += 1
            else:
                send_log(f"    Transfer that bai ({r.status_code}): {r.text}", "error")
                fail += 1

            send_log(f"[6] Xoa tenant {tid}...", "info")
            r = session.delete(f"{API_BASE}/tenants/{tid}")
            send_log(f"    DELETE: {r.status_code} {r.text}", "info")

        except Exception as e:
            send_log(f"Loi: {e}", "error")
            fail += 1

        if i < loops - 1:
            send_log(f"Cho {delay}s...", "warning")
            time.sleep(delay)

    send_log(f"KET QUA: Thanh cong: {success} | That bai: {fail}", "finish")


# --- ROUTES GIAO DIỆN ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start_afk', methods=['POST'])
def api_start_afk():
    global running_afk
    data = request.json
    token = login_account(data['email'], data['password'])
    if not token: 
        return jsonify({"status": "error", "message": "Sai tài khoản!"})
    
    running_afk = True
    t = threading.Thread(target=afk_worker, args=(token, data['email']))
    t.daemon = True
    t.start()
    return jsonify({"status": "success", "message": "Đang bật AFK..."})

@app.route('/api/stop_afk', methods=['POST'])
def api_stop_afk():
    global running_afk
    running_afk = False
    return jsonify({"status": "success", "message": "Đang dừng AFK..."})

@app.route('/api/start_loop', methods=['POST'])
def api_start_loop():
    data = request.json
    token = login_account(data['email'], data['password'])
    if not token: 
        return jsonify({"status": "error", "message": "Đăng nhập thất bại!"})
    
    t = threading.Thread(target=loop_worker, args=(
        token, 
        int(data.get('loops', 10)), 
        int(data.get('delay', 3)), 
        data.get('transfer_to', '@khanhtoan'), # Mặc định theo mã gốc của đại ca
        int(data.get('transfer_amount', 7500)), 
        data['email']
    ))
    t.daemon = True
    t.start()
    
    return jsonify({"status": "success", "message": "Đã bắt đầu Loop!"})

if __name__ == '__main__':
    print("🚀 SERVER WEB ĐÃ SẴN SÀNG CHẠY (Bản chuẩn mã mao.txt)")
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)


