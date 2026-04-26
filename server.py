from flask import Flask, request, jsonify
import sqlite3
import datetime
import hashlib
import random, string

app = Flask(__name__)
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
        start_date TEXT
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
        c.execute("UPDATE licenses SET device=? WHERE key=?", (device, key))
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
    data = request.json
    device = data.get("device")

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT start_date FROM trials WHERE device=?", (device,))
    row = c.fetchone()

    today = datetime.date.today()

    # 🥇 First time → create trial
    if not row:
        c.execute("INSERT INTO trials VALUES (?, ?)", (device, str(today)))
        conn.commit()
        conn.close()
        return jsonify({"trial": True, "days_left": 30})

    # 🥈 Existing user
    start_date = datetime.datetime.strptime(row[0], "%Y-%m-%d").date()
    days_used = (today - start_date).days
    days_left = 30 - days_used

    conn.close()

    if days_left > 0:
        return jsonify({"trial": True, "days_left": days_left})
    else:
        return jsonify({"trial": False, "msg": "Trial expired"})


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


# -------- RUN SERVER --------
if __name__ == "__main__":
    app.run(port=5000)
