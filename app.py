"""
UAP RAG DAY — One-page dynamic website (Flask)
University of Asia Pacific
--------------------------------------------------
Run with:   python app.py  (or the Run button in PyCharm)
Admin page: http://127.0.0.1:5000/admin
"""

import json
import os
import sqlite3

import requests

from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")
ADMIN_PASSWORD = "123456789"          # <-- CHANGE THIS PASSWORD!
ADMIN_USERNAME = "admin"                 # <-- CHANGE THIS USERNAME!
SHEET_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycby0GtnNSe0oLZQ10rrbka0IsKbHRZ-iSqtSwiWYO5RMpjFDTjvjgb0WZnyK9ZxBXEk/exec"
# ------------------------------------------------------------------
# Default data (created as data.json on first run — edit it anytime,
# or use the /admin page in your browser)
# ------------------------------------------------------------------
DEFAULT_DATA = {
    "event": {
        "title": "RAG DAY 2026",
        "tagline": "Rejoice • Assemble • Groove",
        "subtitle": "The biggest celebration of the year at University of Asia Pacific",
        "date_time": "2026-11-10T09:00:00",
        "date_display": "Tuesday, 10 November 2026",
        "venue": "UAP Campus, 74/B Green Road, Dhanmondi, Dhaka-1205",
        "about": "RAG Day is the biggest celebration of the year at University of Asia Pacific "
                 "— a day when classes pause, the campus turns into a festival ground, and "
                 "students from every department come together for music, games, food and "
                 "unforgettable memories.",
        "email": "info@uap.edu.bd",
        "facebook": "https://facebook.com",
        "instagram": "https://instagram.com"
    },
    "stats": [
        {"label": "Participants", "value": 2500},
        {"label": "Departments", "value": 10},
        {"label": "Events & Programs", "value": 24},
        {"label": "Food Stalls", "value": 15}
    ],
    "schedule": [
        {"start": "09:00", "end": "10:00", "title": "Opening Ceremony",
         "desc": "National anthem, flag hoisting and welcome speech by the Vice Chancellor.", "icon": "🎤"},
        {"start": "10:00", "end": "12:00", "title": "Campus Rally & Banner Parade",
         "desc": "Students march across the campus with departmental banners and colorful face paint.", "icon": "🚩"},
        {"start": "12:00", "end": "14:00", "title": "Cultural Show & Music",
         "desc": "Band performances, dance, drama and singing competitions on the main stage.", "icon": "🎵"},
        {"start": "14:00", "end": "15:00", "title": "Food Festival",
         "desc": "Departmental food stalls — biryani, fuchka, chotpoti, jhalmuri and much more.", "icon": "🍛"},
        {"start": "15:00", "end": "17:00", "title": "Games & Sports",
         "desc": "Tug of war, cricket, sack race, 3-legged race and inter-department battles.", "icon": "⚽"},
        {"start": "17:00", "end": "19:00", "title": "Grand Concert & DJ Floor",
         "desc": "Guest band performance, then the DJ floor opens for everyone.", "icon": "🎧"},
        {"start": "19:00", "end": "20:30", "title": "Prize Giving & Closing",
         "desc": "Winners announced, department group photos, and the official end of RAG Day.", "icon": "🏆"}
    ],
    "programs": [
        {"title": "Inter-Department Battle of the Bands", "desc": "Top campus bands compete for the RAG trophy on the main stage.", "icon": "🎸"},
        {"title": "Face Painting & T-Shirt Stalls", "desc": "Get your department logo painted and grab the official RAG Day tee.", "icon": "🎨"},
        {"title": "Photo Booth & Memory Wall", "desc": "Themed photo corners and a giant wall to leave messages for friends.", "icon": "📸"},
        {"title": "Gaming & E-Sports Zone", "desc": "FIFA, PUBG and chess tournaments with instant prizes.", "icon": "🎮"},
        {"title": "Cultural Dance & Drama", "desc": "Traditional and modern performances by UAP cultural clubs.", "icon": "💃"},
        {"title": "DJ Night Warm-up", "desc": "The campus lights go down and the DJ takes over till closing.", "icon": "🔊"}
    ],
    "rules": [
        "Wear your UAP student ID card at all times inside the campus.",
        "Respect every participant — no harassment of any kind will be tolerated.",
        "Keep the campus clean; use the provided dustbins.",
        "Outside guests are allowed only with a valid guest pass.",
        "Follow the instructions of volunteers and security teams.",
        "No political banners or slogans are allowed on RAG Day."
    ]
}

def load_data():
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return DEFAULT_DATA

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

app = Flask(__name__)
app.secret_key = "uap-rag-day-secret-key-change-me"   # <-- change this too

# ------------------------------------------------------------------
# Public page
# ------------------------------------------------------------------
@app.route("/")
def home():
    return render_template_string(PAGE_HTML, data=load_data())

@app.route("/api/data")
def api_data():
    return jsonify(load_data())

# ------------------------------------------------------------------
# Registration system (SQLite — one registration per email)
# ------------------------------------------------------------------
REG_DB = os.path.join(BASE_DIR, "registrations.db")

def get_db():
    conn = sqlite3.connect(REG_DB, timeout=30)   # wait up to 30s instead of crashing instantly
    conn.execute("PRAGMA journal_mode=WAL")  # safer concurrent access
    conn.row_factory = sqlite3.Row
    return conn


def init_reg_db():
    conn = get_db()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS registrations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL,
            student_id TEXT DEFAULT '',
            registered_at TEXT DEFAULT (datetime('now','localtime'))
        )""")
        conn.commit()
    finally:
        conn.close()

def participant_count():
    conn = get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
    finally:
        conn.close()

init_reg_db()   # creates the DB file on first run

@app.route("/api/participant-count")
def api_participant_count():
    return jsonify({"registered": participant_count()})

def sync_to_sheet(name, email, department, student_id):
    if not SHEET_WEBHOOK_URL.startswith("https://script.google.com"):
        print("SHEET SYNC SKIPPED — SHEET_WEBHOOK_URL is not configured!")
        return
    try:
        r = requests.post(SHEET_WEBHOOK_URL, json={
            "name": name, "email": email,
            "department": department, "student_id": student_id
        }, timeout=30)
        print("SHEET SYNC response:", r.status_code, "|", r.text[:200])
    except requests.RequestException as e:
        print("SHEET SYNC FAILED:", e)

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    department = (data.get("department") or "").strip()
    student_id = (data.get("student_id") or "").strip()

    errors = {}
    if len(name) < 3:
        errors["name"] = "Please enter your full name."
    if "@" not in email or "." not in email.split("@")[-1]:
        errors["email"] = "Please enter a valid email."
    if not department:
        errors["department"] = "Department is required."
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400


    try:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO registrations(name, email, department, student_id) VALUES(?,?,?,?)",
                (name, email, department, student_id))
            conn.commit()
        finally:
            conn.close()  # ALWAYS closes now, even if the INSERT failed
    except sqlite3.IntegrityError:
        # UNIQUE constraint on email → this person already registered
        return jsonify({"ok": False,
                        "message": "This email has already registered — one registration per person!"}), 409

    sync_to_sheet(name, email, department, student_id)

    return jsonify({"ok": True,
                    "message": "Registration successful! See you at RAG Day 🎉",
                    "count": participant_count()})

@app.route("/admin/registrations")
def admin_registrations():
    if not session.get("logged_in"):
        return redirect(url_for("admin"))
    conn = get_db()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM registrations ORDER BY id DESC").fetchall()]
    finally:
        conn.close()
    return render_template_string(REGS_HTML, rows=rows, total=len(rows))

# ------------------------------------------------------------------
# Admin page (edit ALL information here)
# ------------------------------------------------------------------
def _render_admin(error=None, success=None, logged_in=False, data_json=None):
    if data_json is None:
        data_json = json.dumps(load_data(), indent=2, ensure_ascii=False)
    return render_template_string(ADMIN_HTML, error=error, success=success,
                                 logged_in=logged_in, data_json=data_json)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "GET":
        return _render_admin(logged_in=session.get("logged_in", False))

    action = request.form.get("action", "")

    if action == "logout":
            session.clear()
            return redirect(url_for("admin"))

    if action == "login":
            if (request.form.get("username") == ADMIN_USERNAME
                    and request.form.get("password") == ADMIN_PASSWORD):
                session["logged_in"] = True
            else:
                return _render_admin(error="Wrong username or password!")
            return redirect(url_for("admin"))

    if action == "save" and session.get("logged_in"):
            raw = request.form.get("data", "{}")
            try:
                new_data = json.loads(raw)
            except json.JSONDecodeError as e:
                return _render_admin(error="Invalid JSON: " + str(e), logged_in=True, data_json=raw)
            save_data(new_data)
            return _render_admin(success="Saved successfully!", logged_in=True,
                                 data_json=json.dumps(new_data, indent=2, ensure_ascii=False))

    return redirect(url_for("admin"))

# ------------------------------------------------------------------
# HTML templates
# ------------------------------------------------------------------
PAGE_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>UAP RAG DAY</title>
<style>
  :root{
    --bg:#0b0f1a; --card:rgba(255,255,255,.06); --line:rgba(255,255,255,.12);
    --accent:#ff4d6d; --accent2:#4dd4ff; --accent3:#ffd166; --text:#eef2ff; --muted:#9aa7c7;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);
       overflow-x:hidden}
  /* animated gradient background */
  body::before{content:'';position:fixed;inset:0;z-index:-2;
    background:linear-gradient(125deg,#0b0f1a,#1a1040,#001f3f,#0b0f1a);
    background-size:400% 400%;animation:flow 18s ease infinite}
  @keyframes flow{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
  body::after{content:'';position:fixed;inset:0;z-index:-1;opacity:.35;
    background-image:radial-gradient(1px 1px at 20% 30%,#fff 50%,transparent),
      radial-gradient(1px 1px at 70% 80%,#fff 50%,transparent),
      radial-gradient(1.5px 1.5px at 40% 70%,#fff 50%,transparent),
      radial-gradient(1px 1px at 85% 20%,#fff 50%,transparent),
      radial-gradient(1px 1px at 10% 90%,#fff 50%,transparent);
    animation:twinkle 4s ease-in-out infinite alternate}
  @keyframes twinkle{from{opacity:.2}to{opacity:.5}}

nav{position:fixed;top:0;left:0;right:0;z-index:50;display:flex;align-items:center;
      justify-content:space-between;padding:14px 5%;backdrop-filter:blur(14px);
      background:rgba(11,15,26,.55);border-bottom:1px solid var(--line)}
  nav .logo{font-weight:800;letter-spacing:2px}
  nav .logo span{color:var(--accent)}
  nav ul{display:flex;gap:26px;list-style:none}
  nav a{color:var(--muted);text-decoration:none;font-size:.9rem;transition:.3s}
  nav a:hover{color:var(--accent2)}
  @media(max-width:760px){nav ul{display:none}}

header{min-height:100vh;display:flex;flex-direction:column;align-items:center;
      justify-content:center;text-align:center;padding:110px 5% 60px;position:relative}
  .glow-title{font-size:clamp(3rem,9vw,6.5rem);font-weight:900;letter-spacing:6px;
      background:linear-gradient(90deg,var(--accent),var(--accent3),var(--accent2),var(--accent));
      background-size:300% 100%;-webkit-background-clip:text;background-clip:text;
      color:transparent;animation:shine 6s linear infinite}
  @keyframes shine{to{background-position:300% 0}}
  .tagline{letter-spacing:8px;color:var(--accent2);margin:14px 0 8px;font-weight:600}
  .subtitle{color:var(--muted);max-width:640px;margin:0 auto}
  .meta{display:flex;flex-wrap:wrap;gap:16px;justify-content:center;margin:26px 0}
  .badge{background:var(--card);border:1px solid var(--line);padding:10px 20px;border-radius:30px;
      backdrop-filter:blur(8px);font-size:.92rem}
  .badge b{color:var(--accent3)}

.countdown{display:flex;gap:18px;flex-wrap:wrap;justify-content:center;margin-top:30px}
  .cd-box{min-width:110px;padding:18px 10px;border-radius:18px;background:var(--card);
      border:1px solid var(--line);backdrop-filter:blur(10px);box-shadow:0 0 30px rgba(255,77,109,.15);
      transition:transform .3s}
  .cd-box:hover{transform:translateY(-6px) scale(1.03)}
  .cd-num{font-size:2.6rem;font-weight:800;color:var(--accent2);font-variant-numeric:tabular-nums}
  .cd-lab{font-size:.75rem;letter-spacing:3px;color:var(--muted);text-transform:uppercase}
  .cd-done{font-size:1.6rem;font-weight:800;color:var(--accent);animation:pulse 1.4s infinite}
  @keyframes pulse{50%{transform:scale(1.06);text-shadow:0 0 30px var(--accent)}}

.ticker{overflow:hidden;white-space:nowrap;border-top:1px solid var(--line);
      border-bottom:1px solid var(--line);background:rgba(255,77,109,.08);padding:10px 0}
  .ticker span{display:inline-block;animation:marquee 22s linear infinite;
      color:var(--accent3);font-weight:700;letter-spacing:2px}
  @keyframes marquee{from{transform:translateX(100vw)}to{transform:translateX(-100%)}}

section{padding:80px 8%;max-width:1200px;margin:0 auto}
  .sec-title{text-align:center;font-size:2.2rem;font-weight:800;margin-bottom:8px}
  .sec-title span{color:var(--accent)}
  .sec-sub{text-align:center;color:var(--muted);margin-bottom:46px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:20px;
      backdrop-filter:blur(10px);padding:26px;transition:.35s}
  .card:hover{transform:translateY(-8px);border-color:var(--accent);box-shadow:0 12px 40px rgba(255,77,109,.25)}

.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:22px}
  .stat{text-align:center;padding:34px 20px}
  .stat b{font-size:2.8rem;color:var(--accent);display:block}
  .stat span{color:var(--muted);letter-spacing:1px}

.about-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:30px;align-items:center}
  @media(max-width:860px){.about-grid{grid-template-columns:1fr}}
  .about-text{line-height:1.9;color:#cdd6f4}
  .venue-card h3{color:var(--accent2);margin-bottom:12px}
  .venue-card p{line-height:1.8;color:var(--muted)}
  .pill{display:inline-block;background:rgba(77,212,255,.12);color:var(--accent2);
      border:1px solid rgba(77,212,255,.35);padding:6px 14px;border-radius:20px;font-size:.8rem;margin:4px 4px 0 0}

.timeline{position:relative;margin-top:10px}
  .timeline::before{content:'';position:absolute;left:31px;top:10px;bottom:10px;width:3px;
      background:linear-gradient(var(--accent),var(--accent2));border-radius:3px}
  .slot{display:flex;gap:26px;margin-bottom:26px;position:relative}
  .slot .ic{width:64px;height:64px;flex:none;border-radius:50%;display:flex;align-items:center;
      justify-content:center;font-size:1.7rem;background:var(--card);border:2px solid var(--line);
      z-index:1;transition:.3s}
  .slot .body{flex:1}
  .slot .time{font-weight:800;color:var(--accent3);letter-spacing:1px;font-size:.95rem}
  .slot h3{margin:4px 0 6px}
  .slot p{color:var(--muted);line-height:1.7}
  .slot .body-card{padding:22px 26px}
  .slot.live .ic{border-color:var(--accent);box-shadow:0 0 25px rgba(255,77,109,.6);animation:pulse2 1.5s infinite}
  @keyframes pulse2{50%{transform:scale(1.08)}}
  .live-badge{display:inline-block;background:var(--accent);color:#fff;font-size:.7rem;
      font-weight:800;letter-spacing:2px;padding:4px 12px;border-radius:20px;margin-left:10px;
      animation:pulse 1.4s infinite}
  .done{opacity:.45;filter:grayscale(.4)}

.programs{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:22px}
  .program .p-icon{font-size:2.4rem;margin-bottom:14px}
  .program h3{margin-bottom:10px}
  .program p{color:var(--muted);line-height:1.7}

.rules li{margin:0 0 12px 26px;line-height:1.8;color:#cdd6f4}
  .contact-links{display:flex;gap:14px;flex-wrap:wrap;justify-content:center;margin-top:24px}
  .contact-links a{color:var(--text);text-decoration:none;background:var(--card);
      border:1px solid var(--line);padding:12px 24px;border-radius:30px;transition:.3s}
  .contact-links a:hover{border-color:var(--accent2);color:var(--accent2)}

footer{border-top:1px solid var(--line);padding:36px 5%;text-align:center;color:var(--muted)}
  footer b{color:var(--accent)}

/* scroll reveal */
  .reveal{opacity:0;transform:translateY(40px);transition:.8s cubic-bezier(.2,.7,.3,1)}
  .reveal.show{opacity:1;transform:none}

/* registration form */
  .reg-form{display:flex;flex-direction:column;gap:14px;margin-top:16px}
  .reg-form input{width:100%;padding:13px 16px;border-radius:12px;border:1px solid var(--line);
      background:rgba(255,255,255,.05);color:var(--text);font-size:.95rem;box-sizing:border-box;
      transition:.3s}
  .reg-form input:focus{outline:none;border-color:var(--accent2);box-shadow:0 0 15px rgba(77,212,255,.25)}
  .reg-btn{padding:14px 20px;border:none;border-radius:12px;background:linear-gradient(90deg,var(--accent),#ff7a59);
      color:#fff;font-weight:800;font-size:1rem;cursor:pointer;letter-spacing:1px;transition:.3s}
  .reg-btn:hover{transform:translateY(-3px);box-shadow:0 10px 30px rgba(255,77,109,.4)}
  .reg-status{margin-top:14px;padding:12px 16px;border-radius:12px;font-size:.9rem;display:none}
  .reg-status.ok{display:block;background:rgba(77,212,255,.12);border:1px solid var(--accent2);color:var(--accent2)}
  .reg-status.err{display:block;background:rgba(255,77,109,.15);border:1px solid var(--accent);color:#ffb3c1}
</style>
</head>
<body>

<nav>
  <div class="logo">UAP <span>RAG DAY</span></div>
  <ul>
    <li><a href="#about">About</a></li>
    <li><a href="#register">Register</a></li>
    <li><a href="#schedule">Schedule</a></li>
    <li><a href="#programs">Programs</a></li>
    <li><a href="#rules">Rules</a></li>
    <li><a href="#contact">Contact</a></li>
  </ul>
</nav>

<header>
  <div class="tagline" id="tagline"></div>
  <h1 class="glow-title" id="mainTitle"></h1>
  <p class="subtitle" id="subtitle"></p>
  <div class="meta" id="metaRow"></div>
  <div class="countdown" id="countdown"></div>
</header>

<div class="ticker"><span>🎉 RAG DAY 2026 — UNIVERSITY OF ASIA PACIFIC — ONE DAY • ONE CAMPUS • ONE CELEBRATION 🎉</span></div>

<section class="reveal">
  <div class="sec-title">About the <span>Event</span></div>
  <div class="sec-sub">Everything you need to know about the biggest day of the year</div>
  <div class="about-grid">
    <div class="card about-text" id="aboutText"></div>
    <div class="card venue-card" id="venueCard"></div>
  </div>
</section>

<section class="reveal">
  <div class="sec-title">Event <span>Stats</span></div>
  <div class="sec-sub">The day in numbers</div>
  <div class="stats" id="stats"></div>
</section>

<section class="reveal" id="register">
  <div class="sec-title">Register for <span>RAG Day</span></div>
  <div class="sec-sub">One registration per person — the participant counter updates live!</div>
  <div class="card" style="max-width:540px;margin:0 auto">
    <div class="reg-status" id="regStatus"></div>
    <form class="reg-form" id="regForm">
      <input id="rName" placeholder="Full Name" required>
      <input id="rEmail" type="email" placeholder="Email (one registration per email)" required>
      <input id="rDept" placeholder="Department (e.g., CSE)" required>
      <input id="rSid" placeholder="Student ID (optional)">
      <button class="reg-btn" type="submit">🎟️ Register Now</button>
    </form>
  </div>
</section>

<section class="reveal" id="schedule">
  <div class="sec-title">Time <span>Schedule</span></div>
  <div class="sec-sub">Follow the timeline — the current slot glows red LIVE</div>
  <div class="timeline" id="timeline"></div>
</section>

<section class="reveal" id="programs">
  <div class="sec-title">Programs &amp; <span>Attractions</span></div>
  <div class="sec-sub">What's happening all around the campus</div>
  <div class="programs" id="programGrid"></div>
</section>

<section class="reveal" id="rules">
  <div class="sec-title">Rules &amp; <span>Guidelines</span></div>
  <div class="sec-sub">Keep it fun, keep it safe</div>
  <div class="card"><ul id="rulesList"></ul></div>
</section>

<section class="reveal" id="contact" style="text-align:center">
  <div class="sec-title">Get in <span>Touch</span></div>
  <div class="sec-sub">Questions? The RAG Day committee is here to help</div>
  <div class="contact-links" id="contactLinks"></div>
</section>

<footer>
  Organized by the <b>RAG Day Committee</b> — University of Asia Pacific, Dhanmondi, Dhaka<br>
  <small>Made with 🤍 by UAP students</small>
</footer>

<script>
const APP_DATA = {{ data|tojson }};
let TARGET = new Date(APP_DATA.event.date_time).getTime();

/* ---------- renderers ---------- */
function esc(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML}

function renderHero(){
  document.getElementById('tagline').textContent = APP_DATA.event.tagline;
  document.getElementById('mainTitle').textContent = APP_DATA.event.title;
  document.getElementById('subtitle').textContent = APP_DATA.event.subtitle;
  document.getElementById('metaRow').innerHTML =
    '<div class="badge">📅 <b>'+esc(APP_DATA.event.date_display)+'</b></div>'+
    '<div class="badge">📍 <b>'+esc(APP_DATA.event.venue)+'</b></div>';
}

function renderStats(){
  document.getElementById('stats').innerHTML = APP_DATA.stats.map(s=>
    '<div class="card stat"><b data-target="'+s.value+'">0</b><span>'+esc(s.label)+'</span></div>').join('');
  document.querySelectorAll('.stat b').forEach(el=>{
    const target=+el.dataset.target, dur=1400, t0=performance.now();
    (function tick(t){const p=Math.min((t-t0)/dur,1);
      el.textContent=Math.round(target*(1-Math.pow(1-p,3))).toLocaleString();
      if(p<1)requestAnimationFrame(tick)})(t0);
  });
}

function nowHM(){const d=new Date();return d.getHours()*60+d.getMinutes()}
function hm(s){const[h,m]=s.split(':').map(Number);return h*60+m}

function renderSchedule(){
  const now=nowHM();
  document.getElementById('timeline').innerHTML = APP_DATA.schedule.map(s=>{
    const live = now>=hm(s.start) && now<hm(s.end);
    const done = now>=hm(s.end);
    return '<div class="slot '+(live?'live':'')+' '+(done?'done':'')+'">'+
      '<div class="ic">'+s.icon+'</div>'+
      '<div class="body"><div class="card body-card">'+
      '<div class="time">'+esc(s.start)+' — '+esc(s.end)+
      (live?'<span class="live-badge">LIVE NOW</span>':'')+'</div>'+
      '<h3>'+esc(s.title)+'</h3><p>'+esc(s.desc)+'</p></div></div></div>';
  }).join('');
}

function renderPrograms(){
  document.getElementById('programGrid').innerHTML = APP_DATA.programs.map(p=>
    '<div class="card program"><div class="p-icon">'+p.icon+'</div>'+
    '<h3>'+esc(p.title)+'</h3><p>'+esc(p.desc)+'</p></div>').join('');
}

function renderAbout(){
  document.getElementById('aboutText').innerHTML = '<p>'+esc(APP_DATA.event.about)+'</p>';
  document.getElementById('venueCard').innerHTML =
    '<h3>📍 Venue</h3><p>'+esc(APP_DATA.event.venue)+'</p>'+
    '<h3 style="margin-top:20px">✨ Highlights</h3>'+
    '<span class="pill">Music Concert</span><span class="pill">Food Festival</span>'+
    '<span class="pill">Sports</span><span class="pill">Gaming Zone</span>'+
    '<span class="pill">Photo Booth</span><span class="pill">DJ Night</span>';
}

function renderRules(){
  document.getElementById('rulesList').innerHTML =
    APP_DATA.rules.map(r=>'<li>'+esc(r)+'</li>').join('');
}

function renderContact(){
  const e=APP_DATA.event;
  document.getElementById('contactLinks').innerHTML =
    '<a href="mailto:'+esc(e.email)+'">✉️ '+esc(e.email)+'</a>'+
    '<a href="'+esc(e.facebook)+'" target="_blank">📘 Facebook</a>'+
    '<a href="'+esc(e.instagram)+'" target="_blank">📷 Instagram</a>';
}

/* ---------- countdown ---------- */
function renderCountdown(){
  const diff=TARGET-Date.now(), el=document.getElementById('countdown');
  if(diff<=0){el.innerHTML='<div class="cd-done">🎉 IT\'S RAG DAY — LET\'S GO! 🎉</div>';return}
  const d=Math.floor(diff/864e5), h=Math.floor(diff/36e5)%24,
        m=Math.floor(diff/6e4)%60, s=Math.floor(diff/1e3)%60;
  el.innerHTML=[[d,'Days'],[h,'Hours'],[m,'Minutes'],[s,'Seconds']].map(([v,l])=>
    '<div class="cd-box"><div class="cd-num">'+String(v).padStart(2,'0')+
    '</div><div class="cd-lab">'+l+'</div></div>').join('');
}

/* ---------- live refresh (edit data in /admin → site updates itself) ---------- */
async function poll(){
  try{
    const r=await fetch('/api/data',{cache:'no-store'});
    if(!r.ok)return;
    const fresh=await r.json();
    Object.keys(fresh).forEach(k=>APP_DATA[k]=fresh[k]);
    TARGET=new Date(APP_DATA.event.date_time).getTime();
    renderHero();renderAbout();renderStats();renderSchedule();
    renderPrograms();renderRules();renderContact();
    refreshParticipants();
  }catch(e){}
}

/* ---------- scroll reveal ---------- */
const io=new IntersectionObserver(es=>es.forEach(e=>{
  if(e.isIntersecting){e.target.classList.add('show');io.unobserve(e.target)}
}),{threshold:.12});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));

/* ---------- registration ---------- */
async function refreshParticipants(){
  try{
    const r=await fetch('/api/participant-count',{cache:'no-store'});
    const j=await r.json();
    document.querySelectorAll('.stat').forEach((box,i)=>{
      if(APP_DATA.stats[i] && APP_DATA.stats[i].label==='Participants')
        box.querySelector('b').textContent=(+j.registered).toLocaleString();
    });
  }catch(e){}
}

document.getElementById('regForm').addEventListener('submit', async e=>{
  e.preventDefault();
  const status=document.getElementById('regStatus');
  status.className='reg-status'; status.style.display='none';
  try{
    const r=await fetch('/api/register',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        name:document.getElementById('rName').value,
        email:document.getElementById('rEmail').value,
        department:document.getElementById('rDept').value,
        student_id:document.getElementById('rSid').value
      })
    });
    const res=await r.json();
    if(res.ok){
      status.textContent=res.message;
      status.className='reg-status ok';
      e.target.reset();
      refreshParticipants();
    }else if(res.errors){
      status.textContent='⚠️ '+Object.values(res.errors).join(' ');
      status.className='reg-status err';
    }else{
      status.textContent='⚠️ '+res.message;
      status.className='reg-status err';
    }
  }catch(err){
    status.textContent='⚠️ Something went wrong. Try again.';
    status.className='reg-status err';
  }
});

/* ---------- boot ---------- */
renderHero();renderAbout();renderStats();renderSchedule();
renderPrograms();renderRules();renderContact();
renderCountdown();refreshParticipants();
setInterval(renderCountdown,1000);
setInterval(renderSchedule,30000);   // re-check LIVE badge
setInterval(poll,30000);             // auto-refresh info every 30 s
</script>
</body>
</html>
"""

ADMIN_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RAG Day Admin</title>
<style>
  body{font-family:'Segoe UI',sans-serif;background:#0b0f1a;color:#eef2ff;display:flex;
       align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px}
  .box{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);
       border-radius:20px;padding:34px;max-width:860px;width:100%;backdrop-filter:blur(12px)}
  h2{margin:0 0 6px}h2 span{color:#ff4d6d}
  small{color:#9aa7c7}
  input,textarea{width:100%;margin-top:12px;padding:12px;border-radius:10px;border:1px solid rgba(255,255,255,.2);
       background:#101729;color:#eef2ff;font-size:.95rem;box-sizing:border-box}
  textarea{height:420px;font-family:Consolas,monospace;font-size:.85rem;white-space:pre;resize:vertical}
  button{margin-top:14px;padding:12px 28px;border:none;border-radius:10px;background:#ff4d6d;
       color:#fff;font-weight:700;cursor:pointer;font-size:1rem}
  button:hover{background:#ff2f55}
  .msg{padding:10px 14px;border-radius:10px;margin-top:12px;font-size:.9rem}
  .err{background:rgba(255,77,109,.15);border:1px solid #ff4d6d}
  .ok{background:rgba(77,212,255,.12);border:1px solid #4dd4ff}
  a{color:#4dd4ff;text-decoration:none;display:inline-block;margin-top:14px}
</style>
</head>
<body>
<div class="box">
  <h2>UAP RAG DAY <span>Admin Panel</span></h2>

{% if not logged_in %}
    <small>Login to edit every piece of information on the website.</small>
    <form method="post">
      <input type="hidden" name="action" value="login">
      <input name="username" placeholder="Username" required autofocus>
      <input name="password" type="password" placeholder="Password" required>
      <button type="submit">Login</button>
    </form>
  {% else %}
    <small>Edit the JSON below and press Save. The live website updates within 30 seconds (or on refresh).</small>
    {% if error %}<div class="msg err">{{ error }}</div>{% endif %}
    {% if success %}<div class="msg ok">{{ success }}</div>{% endif %}
    <form method="post">
      <input type="hidden" name="action" value="save">
      <textarea name="data">{{ data_json }}</textarea>
      <button type="submit">💾 Save Changes</button>
    </form>
    <form method="post" style="display:inline">
      <input type="hidden" name="action" value="logout">
      <button type="submit" style="background:#4dd4ff">Logout</button>
    </form>
  {% endif %}
  <a href="/">← Back to website</a>
</div>
</body>
</html>
"""

REGS_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Registered Participants</title>
<style>
  body{font-family:'Segoe UI',sans-serif;background:#0b0f1a;color:#eef2ff;padding:30px;margin:0}
  h2 span{color:#ff4d6d}
  table{width:100%;border-collapse:collapse;margin-top:20px;font-size:.9rem}
  th,td{padding:10px 14px;border:1px solid rgba(255,255,255,.12);text-align:left}
  th{background:rgba(255,255,255,.08);color:#4dd4ff}
  tr:nth-child(even){background:rgba(255,255,255,.03)}
  a{color:#4dd4ff;text-decoration:none}
  .total{color:#ffd166;font-weight:700}
</style>
</head>
<body>
  <h2>Registered <span>Participants</span> — <span class="total">{{ total }}</span> total</h2>
  <table>
    <tr><th>#</th><th>Name</th><th>Email</th><th>Department</th><th>Student ID</th><th>Registered At</th></tr>
    {% for r in rows %}
      <tr><td>{{ r.id }}</td><td>{{ r.name }}</td><td>{{ r.email }}</td>
          <td>{{ r.department }}</td><td>{{ r.student_id }}</td><td>{{ r.registered_at }}</td></tr>
    {% else %}
      <tr><td colspan="6">No registrations yet.</td></tr>
    {% endfor %}
  </table>
  <p><a href="/admin">← Back to admin</a></p>
</body>
</html>
"""

if __name__ == "__main__":
    print("UAP RAG DAY website running at  http://127.0.0.1:5000")
    print("Admin panel at                    http://127.0.0.1:5000/admin")
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
