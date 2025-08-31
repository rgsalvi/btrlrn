import os, json, sqlite3, time, re, threading, logging, uuid, traceback
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from tenacity import retry, stop_after_attempt, wait_exponential

# ---- Google Gemini ----
import google.generativeai as genai
gemini_model = None  # set in create_app()

DB_PATH = "mvp.db"

# ==================== LOGGING ====================
os.makedirs("logs", exist_ok=True)
logger = logging.getLogger("whatsapp_mvp")
logger.setLevel(logging.DEBUG if os.environ.get("DEBUG","1") == "1" else logging.INFO)
_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
_file = RotatingFileHandler("logs/app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
_file.setFormatter(_formatter); _file.setLevel(logging.DEBUG); logger.addHandler(_file)
_console = logging.StreamHandler(); _console.setFormatter(_formatter); _console.setLevel(logging.DEBUG); logger.addHandler(_console)

# ==================== DB UTIL ====================
def get_mastered_topics(wa_id, subject_label):
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT title FROM lessons WHERE wa_id=? AND subject_label=?", (wa_id, subject_label))
    lesson_titles = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT lesson_id, score, total FROM history WHERE wa_id=? AND subject=?", (wa_id, subject_label))
    mastered = set()
    for r in cur.fetchall():
        if r[1] == 3 and r[2] == 3:
            lid = r[0]
            cur2 = conn.cursor()
            cur2.execute("SELECT title FROM lessons WHERE id=?", (lid,))
            row = cur2.fetchone()
            if row and row[0]:
                mastered.add(row[0])
    conn.close()
    return list(mastered)
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    cur = conn.cursor()
    # users table (rich profile)
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wa_id TEXT UNIQUE,
        first_name TEXT,
        last_name TEXT,
        dob TEXT,
        city TEXT,
        state TEXT,
        board TEXT,        -- 'CBSE' | 'ICSE' | 'SSC' | 'STATE'
        grade TEXT,        -- e.g., '6', '7', '8', ...
        subject TEXT,      -- current active subject (e.g., 'Mathematics')
        level INTEGER DEFAULT 1,
        streak INTEGER DEFAULT 0,
        created_at INTEGER
    )""")
    # sessions table (link to generated lesson)
    cur.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wa_id TEXT,
        stage TEXT,
        q_index INTEGER DEFAULT 0,
        score INTEGER DEFAULT 0,
        lesson_id INTEGER,
        created_at INTEGER
    )""")
    # quiz history
    cur.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wa_id TEXT,
        subject TEXT,   -- store human label here
        level INTEGER,
        score INTEGER,
        total INTEGER,
        taken_at INTEGER
    )""")
    # generated lessons cache
    cur.execute("""CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wa_id TEXT,
        board TEXT,
        grade TEXT,
        subject_label TEXT,
        level INTEGER,
        title TEXT,
        intro_json TEXT,       -- JSON list of bullets
        questions_json TEXT,   -- JSON list of {q, options[4], ans, explain}
        created_at INTEGER
    )""")
    # backfill for older schema
    existing_cols = {r[1] for r in cur.execute("PRAGMA table_info(sessions)").fetchall()}
    if "lesson_id" not in existing_cols:
        cur.execute("ALTER TABLE sessions ADD COLUMN lesson_id INTEGER")
    conn.commit(); conn.close()

def get_user(wa_id):
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE wa_id=?", (wa_id,))
    row = cur.fetchone()
    conn.close()
    return row

def upsert_user(wa_id, **fields):
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE wa_id=?", (wa_id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (wa_id, created_at) VALUES (?,?)", (wa_id, int(time.time())))
    for k, v in fields.items():
        cur.execute(f"UPDATE users SET {k}=? WHERE wa_id=?", (v, wa_id))
    conn.commit(); conn.close()

def set_session(wa_id, stage, q_index=0, score=0, lesson_id=None):
    conn = db(); cur = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE wa_id=?", (wa_id,))
    cur.execute(
        "INSERT INTO sessions (wa_id, stage, q_index, score, lesson_id, created_at) VALUES (?,?,?,?,?,?)",
        (wa_id, stage, q_index, score, lesson_id, int(time.time()))
    )
    conn.commit(); conn.close()

def get_session(wa_id):
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT * FROM sessions WHERE wa_id=?", (wa_id,))
    row = cur.fetchone()
    conn.close()
    return row

def update_session(wa_id, **fields):
    conn = db(); cur = conn.cursor()
    sets = ", ".join([f"{k}=?" for k in fields.keys()])
    values = list(fields.values()) + [wa_id]
    cur.execute(f"UPDATE sessions SET {sets} WHERE wa_id=?", values)
    conn.commit(); conn.close()

def record_history(wa_id, subject_label, level, score, total):
    conn = db(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO history (wa_id, subject, level, score, total, taken_at) VALUES (?,?,?,?,?,?)",
        (wa_id, subject_label, level, score, total, int(time.time()))
    )
    conn.commit(); conn.close()

def save_lesson(wa_id, board, grade, subject_label, level, title, intro, questions):
    conn = db(); cur = conn.cursor()
    cur.execute("""INSERT INTO lessons (wa_id, board, grade, subject_label, level, title, intro_json, questions_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (wa_id, board, grade, subject_label, level, title, json.dumps(intro), json.dumps(questions), int(time.time())))
    lesson_id = cur.lastrowid
    conn.commit(); conn.close()
    return lesson_id

def load_lesson(lesson_id):
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT * FROM lessons WHERE id=?", (lesson_id,))
    row = cur.fetchone()
    conn.close()
    if not row: return None
    return {
        "id": row["id"],
        "title": row["title"],
        "intro": json.loads(row["intro_json"] or "[]"),
        "questions": json.loads(row["questions_json"] or "[]"),
        "subject_label": row["subject_label"],
        "level": row["level"]
    }

# ==================== SUBJECTS / BOARDS ====================
BOARD_SUBJECTS = {
    "CBSE": {
        "6": ["English", "Hindi", "Mathematics", "Science", "Social Science"],
        "7": ["English", "Hindi", "Mathematics", "Science", "Social Science"],
        "8": ["English", "Hindi", "Mathematics", "Science", "Social Science"],
    },
    "ICSE": {
        "6": ["English", "Mathematics", "Science", "History & Civics & Geography", "Computer Applications"],
        "7": ["English", "Mathematics", "Science", "History & Civics & Geography", "Computer Applications"],
        "8": ["English", "Mathematics", "Science", "History & Civics & Geography", "Computer Applications"],
    },
    "SSC": {  # Maharashtra baseline
        "6": ["English", "Marathi/Hindi (2nd Lang)", "Mathematics", "General Science", "History & Civics", "Geography"],
        "7": ["English", "Marathi/Hindi (2nd Lang)", "Mathematics", "General Science", "History & Civics", "Geography"],
        "8": ["English", "Marathi/Hindi (2nd Lang)", "Mathematics", "General Science", "History & Civics", "Geography"],
    },
    "STATE": {
        "6": ["English", "Second Language", "Mathematics", "Science", "Social Science"],
        "7": ["English", "Second Language", "Mathematics", "Science", "Social Science"],
        "8": ["English", "Second Language", "Mathematics", "Science", "Social Science"],
    }
}

def suggest_board_for_state(state_name: str):
    s = (state_name or "").strip().lower()
    if s in ("maharashtra", "mh"): return "SSC"
    return None

def subjects_for(board: str, grade: str):
    board = (board or "").upper()
    return BOARD_SUBJECTS.get(board, {}).get(str(grade), [])

def subject_to_topic_hint(subject_label: str):
    if not subject_label: return "general"
    s = subject_label.lower()
    if "math" in s: return "mathematics"
    if "science" in s: return "science"
    if "english" in s: return "english"
    if any(x in s for x in ["history","civics","geography","social"]): return "social science"
    if any(x in s for x in ["computer","ict"]): return "computer science"
    return s

# ==================== AI GENERATION (Gemini) ====================
AI_JSON_SCHEMA = """
Return ONLY a JSON object with keys:
{
  "title": "string, concise topic title",
  "intro": ["string bullet 1", "string bullet 2", "optional string bullet 3"],
  "questions": [
    {"q": "question text", "options": ["A","B","C","D"], "ans": "A|B|C|D", "explain": "1-2 line explanation"}
  ]  // exactly 3 total
}
No backticks, no markdown fences, no extra commentary outside JSON.
"""

def extract_json(s: str) -> str:
    if s.startswith("```"):
        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, flags=re.S)
        if m: return m.group(1)
    m = re.search(r"(\{.*\})", s, flags=re.S)
    return m.group(1) if m else s

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def ai_generate_lesson(board, grade, subject_label, level, city, state, recent_mistakes=None, wa_id=None):
    start = time.monotonic()
    topic_hint = subject_to_topic_hint(subject_label)
    recent = ""
    if recent_mistakes:
        recent = f"\nCommon trouble areas to remediate: {', '.join(recent_mistakes[:4])}."
    mastered_topics = get_mastered_topics(wa_id=wa_id, subject_label=subject_label) if subject_label and wa_id else []
    exclude_str = ""
    if mastered_topics:
        exclude_str = ("\nDo NOT repeat any topic whose title contains any of these phrases (student scored 3/3): "
                      f"{', '.join(mastered_topics)}. If you must pick a new topic, make sure it is clearly different from these.")
    logger.info(f"[AI] Prompt for {wa_id}:\n{exclude_str}")
    prompt = (
        "You are an expert Indian school tutor who generates short daily lessons and 3 multiple-choice questions. "
        "Keep content aligned with Indian curricula (CBSE/ICSE/State), culturally neutral, and age-appropriate. "
        "Use simple, clear language.\n\n"
        f"Student profile: Board={board}, Grade={grade}, Subject={subject_label} (topic family={topic_hint}), "
        f"City={city}, State={state}. Current Level={level}.{recent}{exclude_str}\n"
        "Create a tiny 'topic of the day' lesson that gets slightly more advanced with higher levels. "
        "THEN generate exactly 3 MCQs with options A-D, each with a short explanation for the correct answer.\n\n"
        f"{AI_JSON_SCHEMA}"
    )
    try:
        logger.info(f"[AI] start board={board} grade={grade} subject={subject_label} level={level} city={city} state={state}")
        response = gemini_model.generate_content(prompt, generation_config={"temperature": 0.4})
        txt = (response.text or "").strip()
        raw = extract_json(txt)
        data = json.loads(raw)
        # Validate
        assert isinstance(data.get("title"), str) and data["title"]
        intro = data.get("intro"); assert isinstance(intro, list) and 1 <= len(intro) <= 4
        qs = data.get("questions", []); assert isinstance(qs, list) and len(qs) == 3
        for q in qs:
            assert set(q.keys()) >= {"q","options","ans","explain"}
            assert isinstance(q["options"], list) and len(q["options"]) == 4
            assert q["ans"] in ("A","B","C","D")
        elapsed = time.monotonic() - start
    logger.info(f"[AI] ok in {elapsed:.2f}s title={data.get('title','')!r}")
    logger.info(f"[AI] returned topic title: {data.get('title','')!r}")
        return data
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error(f"[AI] ERROR after {elapsed:.2f}s: {e}")
        logger.debug("[AI] TRACE:\n" + traceback.format_exc())
        raise

# ==================== HELPERS ====================
def help_text():
    return (
        "Commands:\n"
        "START — begin today's AI-generated topic\n"
        "QUIZ — start questions\n"
        "SUBJECT — choose from your board's subjects\n"
        "PROFILE — update name/grade\n"
        "STATS — see your recent scores\n"
        "RANK — mock leaderboard\n"
        "RESET — reset session"
    )

def display_subject(subject_label: str):
    return subject_label or "Subject"

def recent_trouble_concepts(wa_id, subject_label):
    conn = db(); cur = conn.cursor()
    cur.execute("SELECT subject, score, total FROM history WHERE wa_id=? ORDER BY taken_at DESC LIMIT 5", (wa_id,))
    rows = cur.fetchall(); conn.close()
    for r in rows:
        if r["score"] < r["total"]:
            return [subject_label]
    return []

# ==================== TWILIO SENDER ====================
twilio_client = None
TWILIO_FROM = None
STATUS_CALLBACK_URL = None

def send_whatsapp(to_wa, body_text):
    if not twilio_client or not TWILIO_FROM:
        logger.error("Twilio client not initialized")
        return
    try:
        msg = twilio_client.messages.create(
            from_=TWILIO_FROM,
            to=to_wa,
            body=body_text,
            status_callback=STATUS_CALLBACK_URL  # e.g., https://<ngrok>/twilio-status
        )
        logger.info(f"[SEND] sid={msg.sid} to={to_wa} len={len(body_text)}")
    except Exception as e:
        logger.error(f"[SEND] ERROR to={to_wa}: {e}")
        logger.debug("[SEND] TRACE:\n" + traceback.format_exc())


def _ensure_columns():
    con = db(); cur = con.cursor()
    def has_col(table, col):
        cur.execute(f"PRAGMA table_info({table})")
        return any(r[1].lower()==col.lower() for r in cur.fetchall())
    # users.language
    if not has_col("users","language"):
        cur.execute("ALTER TABLE users ADD COLUMN language TEXT")
        cur.execute("UPDATE users SET language='en' WHERE language IS NULL")
    # users.phone
    if not has_col("users","phone"):
        cur.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    # users.state
    if not has_col("users","state"):
        cur.execute("ALTER TABLE users ADD COLUMN state TEXT")
    con.commit(); con.close()

# ==================== FLASK APP ====================
def create_app():
    global gemini_model, twilio_client, TWILIO_FROM, STATUS_CALLBACK_URL

    load_dotenv()
    init_db()

    # Gemini
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    gemini_model = genai.GenerativeModel(model_name)

    # Twilio
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    TWILIO_FROM = os.environ.get("TWILIO_WHATSAPP_SANDBOX", "whatsapp:+14155238886")
    twilio_client = Client(account_sid, auth_token)

    # Status callback URL (from .env; set it to your ngrok URL)
    STATUS_CALLBACK_URL = os.environ.get("STATUS_CALLBACK_URL")

    app = Flask(__name__)

    _ensure_columns()

    @app.route("/health")
    def health():
        return {"ok": True}

    @app.route("/twilio-status", methods=["POST"])
    def twilio_status():
        sid = request.form.get("MessageSid")
        status = request.form.get("MessageStatus")
        to = request.form.get("To")
        errc = request.form.get("ErrorCode")
        errmsg = request.form.get("ErrorMessage")
        logger.info(f"[STATUS] sid={sid} to={to} status={status} err={errc}:{errmsg}")
        return ("", 204)

    @app.route("/whatsapp", methods=["POST"])
    def whatsapp():
        req_id = str(uuid.uuid4())[:8]
        wa_id = request.form.get("From")  # e.g., 'whatsapp:+91...'
        body = (request.form.get("Body") or "").strip()
        logger.info(f"[{req_id}] INBOUND from={wa_id} body={body!r}")

        resp = MessagingResponse()
        msg = resp.message()

        user = get_user(wa_id)
        text = body.strip()
        up = text.upper()

        # -------- Onboarding: first -> last -> DOB -> city -> state -> board -> grade --------
        if not user:
            sess = get_session(wa_id)
            if not sess:
                set_session(wa_id, "ask_first")
                msg.body("👋 Welcome! I'm your Learning Buddy.\nWhat's your *first name*?")
                logger.info(f"[{req_id}] ACK new-user ask_first")
                return Response(str(resp), mimetype="application/xml")

            stage = sess["stage"]
            text_norm = text.strip()

            if stage == "ask_first":
                upsert_user(wa_id, first_name=text_norm)
                set_session(wa_id, "ask_last")
                msg.body(f"Thanks, {text_norm}! What's your *last name*?")
                logger.info(f"[{req_id}] ACK ask_last")
                return Response(str(resp), mimetype="application/xml")

            if stage == "ask_last":
                upsert_user(wa_id, last_name=text_norm)
                set_session(wa_id, "ask_dob")
                msg.body("Got it. What's your *date of birth*? (YYYY-MM-DD)")
                logger.info(f"[{req_id}] ACK ask_dob")
                return Response(str(resp), mimetype="application/xml")

            if stage == "ask_dob":
                valid = len(text_norm) == 10 and text_norm[4] == "-" and text_norm[7] == "-"
                if not valid:
                    msg.body("Please send DOB in format YYYY-MM-DD (e.g., 2013-04-25).")
                    logger.info(f"[{req_id}] ACK invalid_dob")
                    return Response(str(resp), mimetype="application/xml")
                upsert_user(wa_id, dob=text_norm)
                set_session(wa_id, "ask_city")
                msg.body("Which *city* do you live in?")
                logger.info(f"[{req_id}] ACK ask_city")
                return Response(str(resp), mimetype="application/xml")

            if stage == "ask_city":
                upsert_user(wa_id, city=text_norm)
                set_session(wa_id, "ask_state")
                msg.body("Which *state* are you in? (e.g., Maharashtra, Karnataka)")
                logger.info(f"[{req_id}] ACK ask_state")
                return Response(str(resp), mimetype="application/xml")

            if stage == "ask_state":
                upsert_user(wa_id, state=text_norm)
                suggested = suggest_board_for_state(text_norm)
                if suggested:
                    upsert_user(wa_id, board=suggested)
                    set_session(wa_id, "ask_grade")
                    msg.body("Setting your board to *SSC (Maharashtra)*.\nWhich *grade* are you in? (e.g., 6, 7, 8)")
                else:
                    set_session(wa_id, "ask_board")
                    msg.body("Which *board* do you study under?\nA) CBSE\nB) ICSE\nC) State Board\nReply A, B, or C.")
                logger.info(f"[{req_id}] ACK ask_board_or_grade")
                return Response(str(resp), mimetype="application/xml")

            if stage == "ask_board":
                upU = text_norm.strip().upper()[:1]
                if upU not in ("A","B","C"):
                    msg.body("Please reply A (CBSE), B (ICSE), or C (State Board).")
                    logger.info(f"[{req_id}] ACK invalid_board_choice")
                    return Response(str(resp), mimetype="application/xml")
                board = {"A":"CBSE","B":"ICSE","C":"STATE"}[upU]
                upsert_user(wa_id, board=board)
                set_session(wa_id, "ask_grade")
                msg.body("Great. Which *grade* are you in? (e.g., 6, 7, 8)")
                logger.info(f"[{req_id}] ACK ask_grade")
                return Response(str(resp), mimetype="application/xml")

            if stage == "ask_grade":
                grade_clean = "".join(ch for ch in text_norm if ch.isdigit())
                if not grade_clean:
                    msg.body("Please send a number like 6, 7, 8, 9, 10.")
                    logger.info(f"[{req_id}] ACK invalid_grade")
                else:
                    upsert_user(wa_id, grade=grade_clean, subject="Mathematics", level=1, streak=0)
                    set_session(wa_id, "idle")
                    msg.body("Profile saved ✅\nType SUBJECT to pick what you want to learn today.")
                    logger.info(f"[{req_id}] ACK profile_saved")
                return Response(str(resp), mimetype="application/xml")

        # Re-fetch after upsert
        user = get_user(wa_id)

        # ---------------- Commands ----------------
        if up == "HELP":
            msg.body(help_text())
            logger.info(f"[{req_id}] ACK help")

        elif up == "SUBJECT":
            subs = subjects_for(user["board"], user["grade"]) or ["English", "Mathematics", "Science", "Social Science"]
            set_session(wa_id, "choose_subject")
            letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            mapping_lines = [f"{letters[i]}) {sname}" for i, sname in enumerate(subs)]
            msg.body("Choose a subject:\n" + "\n".join(mapping_lines) + "\nReply with the letter (A, B, C...).")
            logger.info(f"[{req_id}] ACK subject_list board={user['board']} grade={user['grade']}")

        elif up == "PROFILE":
            set_session(wa_id, "profile_name")
            msg.body("Update your name? Send the new name, or type SKIP.")
            logger.info(f"[{req_id}] ACK profile_name")

        elif up == "SKIP":
            sess = get_session(wa_id)
            if sess and sess["stage"] in ("profile_name","profile_grade"):
                if sess["stage"] == "profile_name":
                    set_session(wa_id, "profile_grade")
                    msg.body("Okay. Update your grade? (e.g., 6, 7, 8) or type SKIP.")
                else:
                    set_session(wa_id, "idle")
                    msg.body("Profile unchanged. Type START to continue.")
                logger.info(f"[{req_id}] ACK skip")
            else:
                msg.body("Nothing to skip. Type HELP for options.")
                logger.info(f"[{req_id}] ACK skip_nothing")

        elif up == "RANK":
            msg.body("🏆 Leaderboard (MVP mock):\n1) You — 3 pts\n2) Student B — 2 pts\n3) Student C — 1 pt")
            logger.info(f"[{req_id}] ACK rank")

        elif up == "RESET":
            set_session(wa_id, "idle", 0, 0, None)
            msg.body("Session reset. Type START to begin.")
            logger.info(f"[{req_id}] ACK reset")

        elif up == "STATS":
            conn = db(); cur = conn.cursor()
            cur.execute(
                "SELECT subject, level, score, total, taken_at FROM history WHERE wa_id=? ORDER BY taken_at DESC LIMIT 5",
                (wa_id,)
            ); rows = cur.fetchall(); conn.close()
            if not rows:
                msg.body("No quiz history yet. Type START to begin!")
            else:
                lines = ["📈 Recent quizzes:"]
                for r in rows:
                    lines.append(f"- {r['subject']} L{r['level']}: {r['score']}/{r['total']}")
                msg.body("\n".join(lines))
            logger.info(f"[{req_id}] ACK stats n={len(rows) if rows else 0}")

        elif up == "START":
            # Immediate ACK, then generate + send in background
            msg.body("💡 Got it! Generating today’s topic… you’ll get it here shortly. Then type QUIZ to begin.")
            logger.info(f"[{req_id}] ACK start")

            def do_generate_and_send():
                thread_id = str(uuid.uuid4())[:8]
                logger.info(f"[{req_id}/{thread_id}] BG generation started")
                try:
                    u = get_user(wa_id)
                    level = u["level"] or 1
                    trouble = recent_trouble_concepts(wa_id, u["subject"])
                    lesson = ai_generate_lesson(
                        board=u["board"], grade=u["grade"], subject_label=u["subject"],
                        level=level, city=u["city"], state=u["state"], recent_mistakes=trouble
                    )
                    lesson_id = save_lesson(
                        wa_id=wa_id,
                        board=u["board"], grade=u["grade"], subject_label=u["subject"],
                        level=level, title=lesson["title"], intro=lesson["intro"], questions=lesson["questions"]
                    )
                    set_session(wa_id, "lesson", 0, 0, lesson_id)
                    intro = "\n".join(lesson["intro"][:3])
                    body = f"📚 Today’s topic: {lesson['title']} — Level {level}\n\n{intro}\n\nType QUIZ to begin."
                    send_whatsapp(wa_id, body)
                    logger.info(f"[{req_id}/{thread_id}] BG done; lesson_id={lesson_id}")
                except Exception as e:
                    logger.error(f"[{req_id}/{thread_id}] BG ERROR: {e}")
                    logger.debug(traceback.format_exc())
                    send_whatsapp(wa_id, "Sorry, I couldn’t generate today’s topic just now. Please try START again.")
            threading.Thread(target=do_generate_and_send, daemon=True).start()

        elif up == "QUIZ":
            sess = get_session(wa_id)
            if not sess or not sess["lesson_id"]:
                msg.body("Type START first to get today's lesson.")
                logger.info(f"[{req_id}] ACK quiz_no_lesson")
            else:
                lesson = load_lesson(sess["lesson_id"])
                idx = sess["q_index"]; qs = lesson["questions"]
                if idx >= len(qs):
                    msg.body("You've completed today's questions. Type START to begin again.")
                    logger.info(f"[{req_id}] ACK quiz_already_done")
                else:
                    qobj = qs[idx]
                    textq = (
                        f"{qobj['q']}\n"
                        f"A) {qobj['options'][0]}\n"
                        f"B) {qobj['options'][1]}\n"
                        f"C) {qobj['options'][2]}\n"
                        f"D) {qobj['options'][3]}\n"
                        f"Reply with A, B, C or D."
                    )
                    update_session(wa_id, stage="quiz")
                    msg.body(textq)
                    logger.info(f"[{req_id}] Q{idx+1} sent")

        # Letter inputs: subject selection OR quiz answers
        elif len(up) == 1 and up in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            sess = get_session(wa_id)
            if sess and sess["stage"] == "choose_subject":
                subs = subjects_for(user["board"], user["grade"]) or ["English","Mathematics","Science","Social Science"]
                idx = ord(up) - ord('A')
                if idx < 0 or idx >= len(subs):
                    msg.body("Please choose a valid option from the list. Type SUBJECT to see options again.")
                    logger.info(f"[{req_id}] ACK invalid_subject_choice")
                else:
                    chosen = subs[idx]
                    upsert_user(wa_id, subject=chosen, level=1)
                    set_session(wa_id, "idle", 0, 0, None)
                    msg.body(f"Subject set to *{chosen}*. Type START to begin.")
                    logger.info(f"[{req_id}] ACK subject_set {chosen}")
            elif sess and sess["stage"] == "quiz":
                msg.body(process_ai_answer(user, sess, up, req_id))
            else:
                msg.body("Not sure what you meant. Type SUBJECT to choose a subject or HELP for commands.")
                logger.info(f"[{req_id}] ACK unknown_letter")

        else:
            # Profile update flow or default
            sess = get_session(wa_id)
            if sess:
                if sess["stage"] == "profile_name":
                    name_txt = text.strip()
                    if " " in name_txt:
                        first, last = name_txt.split(" ", 1)
                        upsert_user(wa_id, first_name=first, last_name=last)
                    else:
                        upsert_user(wa_id, first_name=name_txt)
                    set_session(wa_id, "profile_grade")
                    msg.body("Got it! Now update your grade? (e.g., 6, 7, 8) or type SKIP.")
                    logger.info(f"[{req_id}] ACK profile_name_set")
                elif sess["stage"] == "profile_grade":
                    grade_clean = "".join(ch for ch in text if ch.isdigit())
                    if grade_clean:
                        upsert_user(wa_id, grade=grade_clean)
                        set_session(wa_id, "idle")
                        msg.body("Profile updated. Type START to continue.")
                        logger.info(f"[{req_id}] ACK profile_grade_set")
                    else:
                        msg.body("Please send a number like 6, 7, 8 or type SKIP.")
                        logger.info(f"[{req_id}] ACK profile_grade_invalid")
                elif sess["stage"] == "quiz":
                    up1 = text.strip().upper()[:1]
                    if up1 in ("A","B","C","D"):
                        msg.body(process_ai_answer(user, sess, up1, req_id))
                    else:
                        msg.body("Please reply with A, B, C or D.")
                        logger.info(f"[{req_id}] ACK quiz_invalid_char")
                else:
                    msg.body("👋 Hi! Type START to begin, or HELP for commands.")
                    logger.info(f"[{req_id}] ACK default")
            else:
                msg.body("👋 Hi! Type START to begin, or HELP for commands.")
                logger.info(f"[{req_id}] ACK default_no_session")

        return Response(str(resp), mimetype="application/xml")

    return app

# ==================== ANSWER PROCESSING & ADAPT ====================
def process_ai_answer(user, sess, answer, req_id=""):
    if answer not in ("A","B","C","D"):
        return "Please reply with A, B, C or D."

    lesson = load_lesson(sess["lesson_id"])
    if not lesson:
        set_session(user["wa_id"], "idle", 0, 0, None)
        return "Session expired. Type START to begin again."

    idx = sess["q_index"]; qs = lesson["questions"]
    if idx >= len(qs):
        return "Type START to begin a new session."

    q = qs[idx]; score = sess["score"]
    correct = (answer == q["ans"])
    logger.info(f"[ANS] {user['wa_id']} answered {answer} (correct={correct}) at q_index={idx}")

    if correct:
        score += 1; result = "✅ Correct!"
    else:
        result = f"❌ Incorrect. Correct answer: {q['ans']}\nℹ️ {q.get('explain','')}"

    idx += 1
    if idx >= len(qs):
        record_history(user["wa_id"], lesson["subject_label"], lesson["level"], score, len(qs))
        threshold = (len(qs) * 2) // 3  # >= 2/3 → level up
        level = user["level"] or 1
        new_level = level + 1 if score >= threshold else max(1, level - 1)
        new_streak = (user["streak"] + 1) if score == len(qs) else 0
        upsert_user(user["wa_id"], level=new_level, streak=new_streak)
        set_session(user["wa_id"], "idle", 0, 0, None)
        return (
            f"{result}\n\n🎉 Quiz complete! You scored {score}/{len(qs)}.\n"
            f"Next time I'll set Level {new_level} for {lesson['subject_label']}.\n"
            f"Streak: {new_streak}\n"
            f"Type START to learn more, SUBJECT to switch topics, or STATS for your history."
        )
    else:
        update_session(user["wa_id"], q_index=idx, score=score)
        nq = qs[idx]
        return (
            f"{result}\n\nNext:\n"
            f"{nq['q']}\n"
            f"A) {nq['options'][0]}\n"
            f"B) {nq['options'][1]}\n"
            f"C) {nq['options'][2]}\n"
            f"D) {nq['options'][3]}\n"
            f"Reply with A, B, C or D."
        )

# ==================== MAIN ====================
if __name__ == "__main__":
    load_dotenv()
    app = create_app()
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=bool(int(os.environ.get("DEBUG", "1"))))
