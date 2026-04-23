from flask import Flask, request, jsonify
import sqlite3
import datetime
import hashlib

app = Flask(__name__)
DB = "licenses.db"

# Create database
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS licenses (
        key TEXT PRIMARY KEY,
        expiry TEXT,
        device TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

# Verify license
@app.route("/verify", methods=["POST"])
def verify():
    data = request.json
    key = data.get("key")
    device = data.get("device")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT expiry, device FROM licenses WHERE key=?", (key,))
    row = c.fetchone()

    if not row:
        return jsonify({"valid": False})

    expiry, saved_device = row

    # Expiry check
    if expiry != "lifetime":
        if datetime.date.today() > datetime.datetime.strptime(expiry, "%Y-%m-%d").date():
            return jsonify({"valid": False})

    # Device check
    if saved_device and saved_device != device:
        return jsonify({"valid": False})

    # First time save device
    if not saved_device:
        c.execute("UPDATE licenses SET device=? WHERE key=?", (device, key))
        conn.commit()

    conn.close()
    return jsonify({"valid": True})

# Generate key (manual use)
@app.route("/generate", methods=["GET", "POST"])
def generate():
    key = hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest()[:12].upper()
    expiry = str(datetime.date.today() + datetime.timedelta(days=365))

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO licenses VALUES (?, ?, ?)", (key, expiry, ""))
    conn.commit()
    conn.close()

    return jsonify({"key": key})

if __name__ == "__main__":
    app.run(port=5000)