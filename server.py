from flask import Flask, request, jsonify
from flask import render_template_string
from flask import make_response
import sqlite3
import datetime
import hashlib
import random, string

app = Flask(__name__)
SECRET_API_KEY = "X9kL_78@pdfSecureKey_2026"
DB = "licenses.db"

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

# -------- VERIFY LICENSE --------
@app.route("/verify", methods=["POST"])
def verify():
    data = request.json
    key = data.get("key")
    device = data.get("device")
    ip = request.remote_addr

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT expiry, device, reset_count FROM licenses WHERE key=?", (key,))
    row = c.fetchone()

    if not row:
        return jsonify({"valid": False, "msg": "Invalid key"})

    expiry, saved_device, reset_count = row

    # ✅ Expiry check
    if expiry != "lifetime":
        if datetime.date.today() > datetime.datetime.strptime(expiry, "%Y-%m-%d").date():
            return jsonify({"valid": False, "msg": "Expired"})

    # ✅ Device check
    if saved_device and saved_device != device:
        return jsonify({"valid": False, "msg": "Used on another device"})

    # ✅ First time bind device
    if not saved_device:
        today = str(datetime.date.today())
        c.execute(
            "UPDATE licenses SET device=?, activated_on=? WHERE key=?",
            (device, today, key)
    )
    conn.commit()

    # 🔥 NEW: REMOVE FROM TRIAL TABLE
    c.execute("DELETE FROM trials WHERE device=?", (device,))
    conn.commit()

    conn.close()
    return jsonify({"valid": True})


# -------- GENERATE LICENSE --------
@app.route("/generate", methods=["GET"])
def generate():
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

    # 🔹 CHANGE PLAN HERE
    days = 30   # 30 = monthly

    if days == 0:
        expiry = "lifetime"
    else:
        expiry = str(datetime.date.today() + datetime.timedelta(days=days))

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("INSERT INTO licenses (key, expiry, device) VALUES (?, ?, ?)", (key, expiry, ""))
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
ADMIN_PASS = "1234"

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

    </body>c.execute("SELECT key, expiry, device, activated_on FROM licenses")
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

# -------- RUN SERVER --------
if __name__ == "__main__":
    app.run(port=5000)
