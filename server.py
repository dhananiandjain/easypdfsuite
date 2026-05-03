from flask import Flask, request, jsonify
from flask import render_template_string
from flask import make_response
import sqlite3
import datetime
import hashlib
import random, string
import hmac, hashlib, json
import os

import smtplib
from email.mime.text import MIMEText

def send_email(to_email, key):
    sender = "easypdftool.ai@gmail.com"

    password = os.environ.get("EMAIL_PASS")   # 🔥 ADD THIS

    if not password:
        print("Email password not set")
        return

    subject = "Your EASY PDF TOOL License Key"
    html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; background:#f4f6f8; padding:20px;">

<div style="max-width:600px; margin:auto; background:white; border-radius:10px; overflow:hidden; box-shadow:0 2px 10px rgba(0,0,0,0.1);">

    <div style="background:#1f6aa5; color:white; padding:20px; text-align:center;">
        <h2 style="margin:0;">EASY PDF TOOL</h2>
        <p style="margin:0;">License Activation</p>
    </div>

    <div style="padding:20px; color:#333;">
        <h3>🎉 Thank you for your purchase!</h3>

        <p>Your license key is ready:</p>

        <div style="background:#f1f5f9; padding:15px; text-align:center; font-size:18px; font-weight:bold; border-radius:8px;">
            {key}
        </div>

        <p style="margin-top:15px;">
            ✔ Valid for 1 Year<br>
            ✔ One device activation
        </p>

        <h4>How to activate:</h4>
        <ol>
            <li>Open EASY PDF TOOL</li>
            <li>Click <b>Activate License</b></li>
            <li>Paste your key</li>
        </ol>

        <p>If you face any issue, contact support:</p>

        <div style="text-align:center; margin-top:10px;">
            <a href="https://wa.me/919687167883"
               style="
               background:#25D366;
               color:white;
               padding:12px 20px;
               text-decoration:none;
               border-radius:6px;
               font-weight:bold;
               display:inline-block;">
               💬 Contact Support on WhatsApp
           </a>
       </div>

        <p style="margin-top:20px;">Thank you,<br><b>EASY PDF TOOL Team</b></p>
    </div>

</div>

</body>
</html>
"""

    msg = MIMEText(html_body, "html")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print("Email error:", e)



SIGN_SECRET = b"SUPER_SECRET_SERVER_KEY_2026"

def check_api():
    key = request.headers.get("X-API-KEY")
    if key != SECRET_API_KEY:
        return False
    return True

app = Flask(__name__)
SECRET_API_KEY = "X9kL_78@pdfSecureKey_2026"	
DB = "/data/licenses.db"

# Ensure folder exists
os.makedirs("/data", exist_ok=True)

print("Database path:", DB)
print("Files in /data:", os.listdir("/data") if os.path.exists("/data") else "No /data")

# -------- CREATE DATABASE --------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS licenses (
        key TEXT PRIMARY KEY,
        expiry TEXT,
        device TEXT,
        reset_count INTEGER DEFAULT 0
    )
""")

# ✅ ADD THIS BELOW (DO NOT REMOVE ABOVE)
    c.execute("""
    CREATE TABLE IF NOT EXISTS trials (
    device TEXT PRIMARY KEY,
    start_date TEXT,
    ip TEXT
)
""")

    conn.commit()
    conn.close()

init_db()

def sign_data(data_dict):
    data_str = json.dumps(data_dict, sort_keys=True)
    signature = hmac.new(SIGN_SECRET, data_str.encode(), hashlib.sha256).hexdigest()
    return signature


def signed_response(data):
    data["signature"] = sign_data(data.copy())
    return jsonify(data)

# -------- VERIFY LICENSE --------
@app.route("/verify", methods=["POST"])
def verify():
    if not check_api():
        response = {"valid": False}
        response["signature"] = sign_data(response)
        return jsonify(response)

    data = request.json
    key = data.get("key")
    device = data.get("device")
    ip = request.remote_addr

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT expiry, device, reset_count FROM licenses WHERE key=?", (key,))
    row = c.fetchone()

    if not row:
        return signed_response({"valid": False, "msg": "Invalid key"})

    expiry, saved_device, reset_count = row

    # ✅ Expiry check
    if expiry != "lifetime":
        if datetime.date.today() > datetime.datetime.strptime(expiry, "%Y-%m-%d").date():
            return signed_response({"valid": False, "msg": "Expired"})

    # ✅ Device check
    if saved_device and saved_device != device:
        return signed_response({"valid": False, "msg": "Used on another device"})

    # ✅ First time bind device
    if not saved_device:
        today = str(datetime.date.today())
        c.execute(
            "UPDATE licenses SET device=? WHERE key=?",
            (device, key)
    )
    conn.commit()

    # 🔥 NEW: REMOVE FROM TRIAL TABLE
    c.execute("DELETE FROM trials WHERE device=?", (device,))
    conn.commit()

    conn.close()

    # 🔐 SECURE RESPONSE HERE
    return signed_response({
        "valid": True,
        "expiry": expiry,
        "device": device
    })
    
# -------- GENERATE LICENSE --------
@app.route("/generate", methods=["POST"])
def generate():
    # 🔐 Admin login check
    if request.cookies.get("auth") != "1":
        return jsonify({"error": "Unauthorized"}), 401

    # 🔐 API key check (VERY IMPORTANT)
    if request.headers.get("X-API-KEY") != SECRET_API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

    days = 365

    if days == 0:
        expiry = "lifetime"
    else:
        expiry = str(datetime.date.today() + datetime.timedelta(days=days))

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        "INSERT INTO licenses (key, expiry, device) VALUES (?, ?, ?)",
        (key, expiry, "")
    )

    conn.commit()
    conn.close()

    return jsonify({"key": key, "expiry": expiry})


# ✅ -------- NEW TRIAL SYSTEM (ADD THIS) --------
@app.route("/check-trial", methods=["POST"])
def check_trial():
    # 🔐 STEP 3.2: API SECURITY
    key = request.headers.get("X-API-KEY")
    if key != SECRET_API_KEY:
        return jsonify({"trial": False, "days_left": 0})

    data = request.json
    device = data.get("device")
    ip = request.remote_addr

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # ✅ Check device
    c.execute("SELECT start_date FROM trials WHERE device=?", (device,))
    row = c.fetchone()

    today = datetime.date.today()

    # 🚫 STEP 2: Block multiple trials from same IP
    c.execute("SELECT * FROM trials WHERE ip=?", (ip,))
    ip_exists = c.fetchone()

    if not row and ip_exists:
        conn.close()
        return jsonify({"trial": False, "days_left": 0})

    # 🥇 First time → create trial
    if not row:
        c.execute("INSERT INTO trials VALUES (?, ?, ?)", (device, str(today), ip))
        conn.commit()
        conn.close()
        return jsonify({"trial": True, "days_left": 30})

    # 🥈 Existing user
    start_date = datetime.datetime.strptime(row[0], "%Y-%m-%d").date()
    days_used = (today - start_date).days
    days_left = max(0, 30 - days_used)

    conn.close()

    return jsonify({
        "trial": days_left > 0,
        "days_left": days_left
    })

# -------- RESET DEVICE --------
@app.route("/reset", methods=["POST"])
def reset_device():
    if not check_api():
        return jsonify({"status": "unauthorized"})

    data = request.json
    key = data.get("key")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT reset_count FROM licenses WHERE key=?", (key,))
    row = c.fetchone()

    if not row:
        return jsonify({"status": "invalid key"})

    reset_count = row[0]

    if reset_count >= 2:
        return jsonify({"status": "limit reached"})

    # reset device
    c.execute("UPDATE licenses SET device='', reset_count=? WHERE key=?", (reset_count+1, key))
    conn.commit()
    conn.close()

    return jsonify({"status": "reset successful"})

ADMIN_USER = "admin"
ADMIN_PASS = "Raku@21521$"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("user")
        pwd = request.form.get("pass")

        if user == ADMIN_USER and pwd == ADMIN_PASS:
            resp = make_response("<script>window.location='/admin'</script>")
            resp.set_cookie("auth", "1")
            return resp
        else:
            return "❌ Invalid Login"

    return """
    <h2>🔐 Admin Login</h2>
    <form method="POST">
        Username: <input name="user"><br><br>
        Password: <input name="pass" type="password"><br><br>
        <button type="submit">Login</button>
    </form>
    """

# 🔐 LOGOUT ROUTE (ADD HERE 👇)
@app.route("/logout")
def logout():
    resp = make_response("<script>window.location='/login'</script>")
    resp.set_cookie("auth", "", expires=0)
    return resp

# -------- ADMIN PANEL --------
@app.route("/admin")
def admin():
    if request.cookies.get("auth") != "1":
        return "<script>window.location='/login'</script>"

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM licenses")
    total_keys = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM licenses WHERE device != ''")
    active_users = c.fetchone()[0]

    c.execute("SELECT key, expiry, device FROM licenses")
    licenses = c.fetchall()

    c.execute("SELECT COUNT(*) FROM licenses WHERE device != ''")
    paid_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM trials")
    trial_users = c.fetchone()[0]

    # ✅ ADD THIS HERE
    conversion = 0
    if (paid_users + trial_users) > 0:
        conversion = int((paid_users / (paid_users + trial_users)) * 100)

    conn.close()

    html = """
    <html>
    <head>
    <title>Admin Dashboard</title>
    <style>
        body {background:#0f172a; color:white; font-family:Arial; margin:0;}
        header {background:#020617; padding:15px; font-size:20px;}
        .container {padding:20px;}
        .cards {display:flex; gap:20px;}
        .card {
            background:#1e293b;
            padding:20px;
            border-radius:10px;
            width:200px;
            text-align:center;
        }
        table {
            width:100%;
            margin-top:20px;
            border-collapse: collapse;
        }
        th, td {
            padding:10px;
            border:1px solid #333;
        }
        th {background:#1e293b;}
        tr:hover {background:#334155;}
        input {
            padding:8px;
            width:200px;
            margin-top:10px;
        }
        .btn {
            padding:5px 10px;
            border:none;
            cursor:pointer;
            border-radius:5px;
        }
        .delete {background:#ef4444;}
        .reset {background:#f59e0b;}
        .copy {background:#22c55e;}
    </style>
    </head>

    <body>

   <header>
🚀 EASY PDF TOOL - ADMIN DASHBOARD
<button onclick="window.location='/logout'" style="float:right; padding:5px 10px;">Logout</button>
</header>

    <div class="container">

    <br><br>
    <button onclick="generateKey()" 
    style="padding:10px; background:#22c55e; border:none; border-radius:5px;">
    ➕ Generate License
    </button>

    <h3 id="newKey"></h3>

    <div class="cards">

    <br>

        <div class="card">
            <h3>Total Keys</h3>
            <h2>{{total_keys}}</h2>
        </div>

        <div class="card">
            <h3>Active Users</h3>
            <h2>{{active_users}}</h2>
        </div>

        <div class="card">
            <h3>Conversion</h3>
            <h2>{{conversion}}%</h2>
        </div>

    </div>

    <input type="text" id="search" placeholder="🔍 Search Key..." onkeyup="searchTable()">

    <table id="table">
        <tr>
            <th>Key</th>
            <th>Expiry</th>
            <th>Device</th>
            <th>Actions</th>
        </tr>

        {% for row in licenses %}
        <tr>
            <td>{{row[0]}}</td>
            <td>{{row[1]}}</td>
            <td>{{row[2]}}</td>
            <td>
                <button class="copy" onclick="copyText('{{row[0]}}')">Copy</button>
                <button class="reset" onclick="window.location='/reset-device/{{row[0]}}'">Reset</button>
                <button class="delete" onclick="del('{{row[0]}}')">Delete</button>
            </td>
        </tr>
        {% endfor %}
    </table>

    </div>

    <br>

    <button onclick="window.location='/trial-users'" 
    style="padding:10px 15px; margin:20px; background:#22c55e; border:none; border-radius:5px; cursor:pointer;">
    📊 View Trial Users
    </button>

    <script>
    function copyText(text){
        navigator.clipboard.writeText(text);
        alert("Copied: " + text);
    }

    async function generateKey() {
    const res = await fetch("/generate", {
    method: "POST",
    headers: {
        "X-API-KEY": "X9kL_78@pdfSecureKey_2026"
    }
});

    const data = await res.json();

    if (data.key) {
        document.getElementById("newKey").innerText =
            "New Key: " + data.key + " (Expiry: " + data.expiry + ")";
    } else {
        alert("Unauthorized");
    }
}

    function del(key){
        if(confirm("Delete license?")){
            window.location="/delete/"+key;
        }
    }

    function searchTable(){
        let input = document.getElementById("search").value.toLowerCase();
        let rows = document.getElementById("table").rows;

        for(let i=1;i<rows.length;i++){
            let key = rows[i].cells[0].innerText.toLowerCase();
            rows[i].style.display = key.includes(input) ? "" : "none";
        }
    }
    </script>

    </body>
    </html>
    """

    return render_template_string(
    html,
    licenses=licenses,
    total_keys=total_keys,
    active_users=active_users,
    conversion=conversion
)
# 🧩 DELETE LICENSE (PASTE HERE 👇)
@app.route("/delete/<key>")
def delete_license(key):
    if request.cookies.get("auth") != "1":
        return "Unauthorized"

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM licenses WHERE key=?", (key,))
    conn.commit()
    conn.close()

    return "<script>window.location='/admin'</script>"

# 🧩 RESET LICENSE (PASTE HERE 👇)
@app.route("/reset-device/<key>")
def reset_device_admin(key):
    if request.cookies.get("auth") != "1":
        return "Unauthorized"

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE licenses SET device='', reset_count=0 WHERE key=?", (key,))
    conn.commit()
    conn.close()

    return "<script>window.location='/admin'</script>"

@app.route("/trial-users")
def trial_users():
    if request.cookies.get("auth") != "1":
        return "<script>window.location='/login'</script>"

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT device, start_date, ip FROM trials")
    rows = c.fetchall()

    today = datetime.date.today()

    data = []
    for device, start_date, ip in rows:
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        days_used = (today - start).days
        days_left = max(0, 30 - days_used)

        data.append((device, ip, start_date, days_left))

    conn.close()

    html = """
    <html>
    <head>
    <title>Trial Users</title>
    <style>
        body {background:#0f172a; color:white; font-family:Arial;}
        table {width:100%; border-collapse: collapse; margin-top:20px;}
        th, td {padding:10px; border:1px solid #333;}
        th {background:#1e293b;}
        tr:hover {background:#334155;}
        button {padding:10px; margin:20px; background:#22c55e; border:none; border-radius:5px;}
    </style>
    </head>

    <body>

    <h2 style="padding:20px;">📊 Trial Users</h2>

    <table>
        <tr>
            <th>Device</th>
            <th>IP</th>
            <th>Start Date</th>
            <th>Days Left</th>
            <th>Action</th>
        </tr>

        {% for row in data %}
        <tr>
    <td>{{row[0]}}</td>
    <td>{{row[1]}}</td>
    <td>{{row[2]}}</td>
    <td>{{row[3]}}</td>
    <td>
        <button onclick="if(confirm('Delete user?')) window.location='/delete-trial/{{row[0]}}'" 
        style="background:#ef4444; border:none; padding:5px; border-radius:5px;">
        Delete
        </button>
    </td>
</tr>
        {% endfor %}
    </table>

    <button onclick="window.location='/admin'">⬅ Back</button>

    </body>
    </html>
    """

    return render_template_string(html, data=data)

@app.route("/delete-trial/<device>")
def delete_trial(device):
    if request.cookies.get("auth") != "1":
        return "Unauthorized"

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM trials WHERE device=?", (device,))
    conn.commit()
    conn.close()

    return "<script>window.location='/trial-users'</script>"

@app.route("/webhook", methods=["POST"])
def razorpay_webhook():
    print("🔥 Webhook triggered")
    print("Headers:", dict(request.headers))
    print("Body:", request.data)
    import hmac, hashlib

    webhook_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET")

    if not webhook_secret:
        print("Webhook secret not set")
        return "Error", 500

    body = request.data
    received_signature = request.headers.get("X-Razorpay-Signature")

    # 🔐 Verify webhook signature
    generated_signature = hmac.new(
        webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if generated_signature != received_signature:
        return "Invalid signature", 400

    data = request.json

    # ✅ Only process successful payments
    if data.get("event") == "payment.captured":
        payment = data["payload"]["payment"]["entity"]

        email = payment.get("email")
        phone = payment.get("contact")

        # 🔥 Generate license
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        expiry = str(datetime.date.today() + datetime.timedelta(days=365))

        conn = sqlite3.connect(DB)
        c = conn.cursor()

        c.execute(
            "INSERT INTO licenses (key, expiry, device) VALUES (?, ?, ?)",
            (key, expiry, "")
        )

        conn.commit()
        conn.close()

        # 🔥 SEND LICENSE (OPTION 1: print/log)
        if email:
            send_email(email, key)
        else:
            print("No email provided, license:", key)

        print(f"License sent to {email or phone}: {key}")

        # 👉 You can later send via email / WhatsApp

    return "OK", 200

# -------- RUN SERVER --------
if __name__ == "__main__":
    app.run(port=5000)
