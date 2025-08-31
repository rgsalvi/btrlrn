# telegram_adapter.py
import os
import sys
import re
import json
import asyncio
import logging
import requests
from dotenv import load_dotenv
import sqlite3
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest
from datetime import datetime, timezone
def _now_iso(): return datetime.now(timezone.utc).isoformat()

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

# ---------- Load engine (your app.py) ----------
import app as engine  # uses your DB, AI, helpers, logger
_engine_flask_app = engine.create_app()  # initializes DB, Gemini, logger, etc.
logger = engine.logger  # reuse same logger

load_dotenv()

# ---------- Small helpers ----------
def rowdict(row):
    return dict(row) if row is not None else None

# ---------- Constants ----------
LANGS = ["en", "hi", "mr"]  # English, Hindi, Marathi

IN_STATES = [
    "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa",
    "Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala",
    "Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland",
    "Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana","Tripura",
    "Uttar Pradesh","Uttarakhand","West Bengal","Andaman and Nicobar Islands",
    "Chandigarh","Dadra and Nagar Haveli and Daman and Diu","Delhi","Jammu and Kashmir",
    "Ladakh","Lakshadweep","Puducherry"
]

USER_AGENT = "btrlrn-edu-bot/1.0 (contact: support@example.com)"

ADMIN_IDS = {8140354366}

# ---------- i18n ----------
CAT = {
    "en": {
        "LANG_PROMPT": "Choose your language 🌎",
        "LANG_EN": "English",
        "LANG_HI": "हिन्दी",
        "LANG_MR": "मराठी",
        "WELCOME": "👋 Welcome! I’m your Learning Buddy.",
        "STEP": "Step {n}/9 • {title}",
        "FIRST_NAME": "🧒 First Name",
        "ASK_FIRST": "What’s your *first name*?",
        "LAST_NAME": "👨‍👩‍👧 Last Name",
        "ASK_LAST": "Great, {first}! What’s your *last name*?",
        "DOB": "🎂 Date of Birth",
        "ASK_DOB": "Please send your date of birth in *DD-MM-YYYY* (e.g., 25-04-2012).",
        "DOB_BAD": "Oops! Use *DD-MM-YYYY* like *25-04-2012*.",
        "PHONE": "📱 Mobile Number",
        "ASK_PHONE": "Tap *Share my phone* or type your 10-digit mobile number.",
        "PHONE_BTN": "Share my phone",
        "PHONE_BAD": "Hmm… send a 10-digit Indian mobile (starts 6–9), e.g., 9876543210.",
        "CITY": "🏙️ City",
        "ASK_CITY": "Which *city* do you live in?",
        "BOARD": "📚 Curriculum",
        "ASK_BOARD": "Which curriculum do you study?\nA) CBSE\nB) ICSE\nC) State",
        "BOARD_BTN_CBSE": "CBSE",
        "BOARD_BTN_ICSE": "ICSE",
        "BOARD_BTN_STATE": "State",
        "STATE_GUESS": "🧭 We think your state is *{state}*. Is that right?",
        "YES": "Yes",
        "NO": "No",
        "PICK_STATE": "Please pick your *state*:",
        "GRADE": "🎓 Grade",
        "ASK_GRADE": "Choose your *grade*:",
        "SUBJECT": "🧠 Subject for today",
        "ASK_SUBJECT": "Pick a subject to learn today:",
        "PROFILE_SAVED": "Profile saved ✅",
        "CONTINUE": "Type START when ready, or SUBJECT to switch.",
        "HELP": (
            "Commands:\n"
            "START — begin today’s AI topic\n"
            "QUIZ — start questions\n"
            "SUBJECT — choose subject\n"
            "PROFILE — edit profile\n"
            "STATS — see your scores\n"
            "RESET — reset session"
        ),
        "FINISH_PROFILE": "Let’s finish your profile first. 👍",
        "GENERATING": "💡 Generating today’s topic…",
        "TOPIC": "📚 Today’s topic: {title} — Level {level}\n\n{intro}\n\nType *QUIZ* to begin.",
        "NO_LESSON": "Type START first to get today’s lesson.",
        "QUIZ_DONE": "You’ve completed today’s questions. Type START to begin again.",
        "SESSION_EXPIRED": "Session expired. Type START to begin again.",
        "INVALID_CHOICE": "Please choose a valid option.",
        "SUBJECT_SET": "Subject set to *{subject}*. Type START to begin.",
        "PROFILE_CMD": "What would you like to edit?\nA) Name  B) City  C) State/Curriculum  D) Grade  E) Subject",
        "PROFILE_UPDATED": "Profile updated. Type START to continue.",
        "PLEASE_ABCD": "Please tap A, B, C, or D.",
        "AI_ERROR": "Sorry, I couldn’t generate today’s topic. Please try START again.",
        "RANK": "🏆 Leaderboard (MVP mock):\n1) You — 3 pts\n2) Student B — 2 pts\n3) Student C — 1 pt",
        "RESET_OK": "Session reset. Type START to begin.",
        "STATS_HEADER": "📈 Recent quizzes:",
        "STATS_EMPTY": "No quiz history yet. Type START to begin!",
    },
    "hi": {
        "LANG_PROMPT": "अपनी भाषा चुनें 🌎",
        "LANG_EN": "English",
        "LANG_HI": "हिन्दी",
        "LANG_MR": "मराठी",
        "WELCOME": "👋 नमस्ते! मैं आपका Learning Buddy हूँ।",
        "STEP": "कदम {n}/9 • {title}",
        "FIRST_NAME": "🧒 पहला नाम",
        "ASK_FIRST": "आपका *पहला नाम* क्या है?",
        "LAST_NAME": "👨‍👩‍👧 उपनाम",
        "ASK_LAST": "शानदार, {first}! आपका *उपनाम* क्या है?",
        "DOB": "🎂 जन्मतिथि",
        "ASK_DOB": "*DD-MM-YYYY* में जन्मतिथि भेजें (जैसे 25-04-2012)।",
        "DOB_BAD": "ओह! कृपया *DD-MM-YYYY* जैसे *25-04-2012* भेजें।",
        "PHONE": "📱 मोबाइल नंबर",
        "ASK_PHONE": "*Share my phone* दबाएँ या 10 अंकों का मोबाइल नंबर लिखें।",
        "PHONE_BTN": "Share my phone",
        "PHONE_BAD": "कृपया 10 अंकों का भारतीय नंबर भेजें (6–9 से शुरू), जैसे 9876543210।",
        "CITY": "🏙️ शहर",
        "ASK_CITY": "आप किस *शहर* में रहते हैं?",
        "BOARD": "📚 पाठ्यक्रम",
        "ASK_BOARD": "आप कौन-सा पाठ्यक्रम पढ़ते हैं?\nA) CBSE\nB) ICSE\nC) State",
        "BOARD_BTN_CBSE": "CBSE",
        "BOARD_BTN_ICSE": "ICSE",
        "BOARD_BTN_STATE": "State",
        "STATE_GUESS": "🧭 हमें लगता है आपका राज्य *{state}* है। क्या यह सही है?",
        "YES": "हाँ",
        "NO": "नहीं",
        "PICK_STATE": "कृपया अपना *राज्य* चुनें:",
        "GRADE": "🎓 कक्षा",
        "ASK_GRADE": "अपनी *कक्षा* चुनें:",
        "SUBJECT": "🧠 आज का विषय",
        "ASK_SUBJECT": "आज कौन-सा विषय पढ़ना चाहेंगे?",
        "PROFILE_SAVED": "प्रोफ़ाइल सेव हो गई ✅",
        "CONTINUE": "तैयार हों तो START लिखें, या SUBJECT बदलें।",
        "HELP": (
            "Commands:\n"
            "START — आज का AI टॉपिक\n"
            "QUIZ — प्रश्न शुरू करें\n"
            "SUBJECT — विषय चुनें\n"
            "PROFILE — प्रोफ़ाइल बदलें\n"
            "STATS — आपके स्कोर\n"
            "RESET — सत्र रीसेट करें"
        ),
        "FINISH_PROFILE": "पहले आपकी प्रोफ़ाइल पूरी कर लें। 👍",
        "GENERATING": "💡 आज का टॉपिक बना रहा हूँ…",
        "TOPIC": "📚 आज का टॉपिक: {title} — Level {level}\n\n{intro}\n\nशुरू करने के लिए *QUIZ* लिखें।",
        "NO_LESSON": "पहले START लिखकर आज का लेसन लें।",
        "QUIZ_DONE": "आज के प्रश्न पूरे हो गए। नया शुरू करने के लिए START लिखें।",
        "SESSION_EXPIRED": "सत्र समाप्त। फिर से शुरू करने के लिए START लिखें।",
        "INVALID_CHOICE": "कृपया सही विकल्प चुनें।",
        "SUBJECT_SET": "*{subject}* विषय सेट हो गया। शुरू करने के लिए START लिखें।",
        "PROFILE_CMD": "क्या बदलना चाहेंगे?\nA) नाम  B) शहर  C) राज्य/पाठ्यक्रम  D) कक्षा  E) विषय",
        "PROFILE_UPDATED": "प्रोफ़ाइल अपडेट हुई। आगे बढ़ने के लिए START लिखें।",
        "PLEASE_ABCD": "कृपया A, B, C या D पर टैप करें।",
        "AI_ERROR": "क्षमा करें, अभी टॉपिक नहीं बना सका। कृपया START फिर से लिखें।",
        "RANK": "🏆 लीडरबोर्ड (MVP):\n1) आप — 3\n2) Student B — 2\n3) Student C — 1",
        "RESET_OK": "सत्र रीसेट हुआ। START लिखें।",
        "STATS_HEADER": "📈 हाल के क्विज़:",
        "STATS_EMPTY": "अभी कोई क्विज़ नहीं। START लिखें!",
    },
    "mr": {
        "LANG_PROMPT": "तुमची भाषा निवडा 🌎",
        "LANG_EN": "English",
        "LANG_HI": "हिन्दी",
        "LANG_MR": "मराठी",
        "WELCOME": "👋 नमस्कार! मी तुमचा Learning Buddy आहे.",
        "STEP": "पायरी {n}/9 • {title}",
        "FIRST_NAME": "🧒 पहिले नाव",
        "ASK_FIRST": "तुमचे *पहिले नाव* काय?",
        "LAST_NAME": "👨‍👩‍👧 आडनाव",
        "ASK_LAST": "छान, {first}! तुमचे *आडनाव* काय?",
        "DOB": "🎂 जन्मतारीख",
        "ASK_DOB": "*DD-MM-YYYY* या स्वरूपात जन्मतारीख पाठवा (उदा. 25-04-2012).",
        "DOB_BAD": "अरेरे! *DD-MM-YYYY* जसे *25-04-2012* वापरा.",
        "PHONE": "📱 मोबाईल क्रमांक",
        "ASK_PHONE": "*Share my phone* दाबा किंवा 10 अंकी मोबाईल क्रमांक टाइप करा.",
        "PHONE_BTN": "Share my phone",
        "PHONE_BAD": "कृपया 10 अंकी भारतीय क्रमांक पाठवा (6–9 ने सुरू), उदा. 9876543210.",
        "CITY": "🏙️ शहर",
        "ASK_CITY": "तुम्ही कोणत्या *शहरात* राहता?",
        "BOARD": "📚 अभ्यासक्रम",
        "ASK_BOARD": "तुमचा अभ्यासक्रम?\nA) CBSE\nB) ICSE\nC) State",
        "BOARD_BTN_CBSE": "CBSE",
        "BOARD_BTN_ICSE": "ICSE",
        "BOARD_BTN_STATE": "State",
        "STATE_GUESS": "🧭 आम्हाला वाटते तुमचे राज्य *{state}* आहे. बरोबर?",
        "YES": "होय",
        "NO": "नाही",
        "PICK_STATE": "कृपया तुमचे *राज्य* निवडा:",
        "GRADE": "🎓 इयत्ता",
        "ASK_GRADE": "तुमची *इयत्ता* निवडा:",
        "SUBJECT": "🧠 आजचा विषय",
        "ASK_SUBJECT": "आज कोणता विषय शिकायचा?",
        "PROFILE_SAVED": "प्रोफाइल सेव झाले ✅",
        "CONTINUE": "तयार झाल्यावर START, नाहीतर SUBJECT बदला.",
        "HELP": (
            "Commands:\n"
            "START — आजचा AI विषय\n"
            "QUIZ — प्रश्न सुरू\n"
            "SUBJECT — विषय निवडा\n"
            "PROFILE — प्रोफाइल बदला\n"
            "STATS — तुमचे स्कोअर्स\n"
            "RESET — सत्र रीसेट"
        ),
        "FINISH_PROFILE": "आधी तुमची प्रोफाइल पूर्ण करूया. 👍",
        "GENERATING": "💡 आजचा विषय तयार करत आहे…",
        "TOPIC": "📚 आजचा विषय: {title} — Level {level}\n\n{intro}\n\nसुरू करण्यासाठी *QUIZ* लिहा.",
        "NO_LESSON": "पहिले START लिहा आणि आजचा लेसन घ्या.",
        "QUIZ_DONE": "आजचे प्रश्न पूर्ण. नवीन सुरू करण्यासाठी START लिहा.",
        "SESSION_EXPIRED": "सत्र संपले. पुन्हा सुरू करण्यासाठी START लिहा.",
        "INVALID_CHOICE": "कृपया योग्य पर्याय निवडा.",
        "SUBJECT_SET": "*{subject}* विषय सेट. सुरू करण्यासाठी START लिहा.",
        "PROFILE_CMD": "काय बदलायचे?\nA) नाव  B) शहर  C) राज्य/अभ्यासक्रम  D) इयत्ता  E) विषय",
        "PROFILE_UPDATED": "प्रोफाइल अपडेट. पुढे जाण्यासाठी START लिहा.",
        "PLEASE_ABCD": "कृपया A, B, C किंवा D टॅप करा.",
        "AI_ERROR": "क्षमस्व, आत्ताच विषय तयार करू शकलो नाही. START पुन्हा लिहा.",
        "RANK": "🏆 लीडरबोर्ड (MVP):\n1) तुम्ही — 3\n2) Student B — 2\n3) Student C — 1",
        "RESET_OK": "सत्र रीसेट. START लिहा.",
        "STATS_HEADER": "📈 अलीकडील क्विझ:",
        "STATS_EMPTY": "अजून क्विझ नाही. START लिहा!",
    },
}

def t(key: str, lang: str, **kwargs) -> str:
    lang = lang if lang in CAT else "en"
    return (CAT[lang].get(key) or CAT["en"].get(key, key)).format(**kwargs)

# ---------- Keyboards ----------
def kb_lang():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(CAT["en"]["LANG_EN"], callback_data="LANG:en"),
         InlineKeyboardButton(CAT["hi"]["LANG_HI"], callback_data="LANG:hi"),
         InlineKeyboardButton(CAT["mr"]["LANG_MR"], callback_data="LANG:mr")]
    ])

def kb_boards(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("BOARD_BTN_CBSE", lang), callback_data="BOARD:CBSE"),
         InlineKeyboardButton(t("BOARD_BTN_ICSE", lang), callback_data="BOARD:ICSE")],
        [InlineKeyboardButton(t("BOARD_BTN_STATE", lang), callback_data="BOARD:STATE")]
    ])

def kb_yesno(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("YES", lang), callback_data="YN:Y"),
         InlineKeyboardButton(t("NO", lang), callback_data="YN:N")]
    ])

def kb_states_page(lang, start=0, size=8):
    chunk = IN_STATES[start:start+size]
    rows = [[InlineKeyboardButton(name, callback_data=f"STATE:{name}")]
            for name in chunk]
    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton("« Prev", callback_data=f"PG:{max(0,start-size)}"))
    if start + size < len(IN_STATES):
        nav.append(InlineKeyboardButton("Next »", callback_data=f"PG:{start+size}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(rows)

def kb_grades(lang):
    rows = []
    row = []
    for g in range(6, 13):  # 6..12
        row.append(InlineKeyboardButton(str(g), callback_data=f"GRADE:{g}"))
        if len(row) == 4:
            rows.append(row); row = []
    if row: rows.append(row)
    return InlineKeyboardMarkup(rows)

def kb_subjects(subs):
    return InlineKeyboardMarkup([[InlineKeyboardButton(name, callback_data=f"SUBJ:{i}")]
                                 for i, name in enumerate(subs)])

def kb_abcd():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("A", callback_data="ANS:A"), InlineKeyboardButton("B", callback_data="ANS:B")],
        [InlineKeyboardButton("C", callback_data="ANS:C"), InlineKeyboardButton("D", callback_data="ANS:D")],
    ])

def kb_next_question():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Next Question", callback_data="NEXTQ")]
    ])

# ---------- Validation ----------
DOB_RE = re.compile(r"^(0[1-9]|[12][0-9]|3[01])-(0[1-9]|1[0-2])-(20\d{2}|19\d{2})$")
def valid_dob(ddmmyyyy: str) -> bool:
    return bool(DOB_RE.match(ddmmyyyy))

def clean_phone(s: str) -> str:
    digits = re.sub(r"\D", "", s or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return digits

def valid_indian_mobile10(s: str) -> bool:
    return bool(re.match(r"^[6-9]\d{9}$", s or ""))

# ---------- Geocoding ----------
def lookup_state_from_city(city: str) -> str | None:
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"city": city, "country": "India", "format": "json", "addressdetails": 1, "limit": 1}
        headers = {"User-Agent": USER_AGENT}
        r = requests.get(url, params=params, headers=headers, timeout=8)
        r.raise_for_status()
        arr = r.json()
        if not arr: return None
        addr = arr[0].get("address", {})
        state = addr.get("state") or addr.get("state_district")
        if state in IN_STATES:
            return state
        for s in IN_STATES:
            if s.lower() == (state or "").lower():
                return s
        return None
    except Exception as e:
        logger.warning(f"[TG] geocode fail city={city}: {e}")
        return None

# ---------- Language helpers ----------
def get_lang(wa_id: str) -> str:
    u = rowdict(engine.get_user(wa_id))
    return (u["language"] if u and "language" in u and u["language"] else "en")

def set_lang(wa_id: str, lang: str):
    if lang not in LANGS: lang = "en"
    engine.upsert_user(wa_id, language=lang)

# ---------- Translation using engine's Gemini ----------
def translate_lesson_if_needed(lesson: dict, lang: str) -> dict:
    if lang == "en":
        return lesson
    try:
        prompt = (
            "Translate the following lesson JSON to the target language. "
            "Keep JSON structure and options A-D exactly the same. "
            f"Target language code: {lang} "
            "Return JSON only.\n\n" + json.dumps(lesson, ensure_ascii=False)
        )
        resp = engine.gemini_model.generate_content(prompt, generation_config={"temperature": 0.2})
        txt = (resp.text or "").strip()
        m = re.search(r"(\{.*\})", txt, flags=re.S)
        raw = m.group(1) if m else txt
        data = json.loads(raw)
        if isinstance(data.get("questions"), list) and len(data["questions"]) == 3:
            return data
    except Exception as e:
        logger.warning(f"[TG] translate fail; using original EN. err={e}")
    return lesson

# ---------- ID helpers ----------
def uid_from_tg(update: Update) -> str:
    return f"telegram:{update.effective_chat.id}"

def step_header(lang: str, n: int, title_key: str) -> str:
    return f"{t('STEP', lang, n=n, title=t(title_key, lang))}"

# ---------- Flow: senders ----------
async def send_quiz_question(update_or_query, wa_id, lesson, q_index):
    q = lesson["questions"][q_index]
    textq = (
        f"{q['q']}\n"
        f"{q['options'][0]}\n"
        f"{q['options'][1]}\n"
        f"{q['options'][2]}\n"
        f"{q['options'][3]}"
    )
    if isinstance(update_or_query, Update) and update_or_query.message:
        return await update_or_query.message.reply_text(textq, reply_markup=kb_abcd())
    if isinstance(update_or_query, Update) and update_or_query.callback_query:
        return await update_or_query.callback_query.edit_message_text(textq, reply_markup=kb_abcd())

# ---------- Handlers ----------
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    wa_id = uid_from_tg(update)
    sess = rowdict(engine.get_session(wa_id))
    if not sess:
        engine.set_session(wa_id, "ask_lang")
    await update.message.reply_text(f"{t('WELCOME','en')}\n\n{t('LANG_PROMPT','en')}", reply_markup=kb_lang())

async def admin_stats_handler(update, context):
    if not (update.effective_user and update.effective_user.id in ADMIN_IDS):
        return await update.message.reply_text("Not authorized.")
    import sqlite3
    conn = engine.db(); conn.row_factory = sqlite3.Row; cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM users WHERE wa_id LIKE 'telegram:%'")
    total = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) AS online FROM users WHERE wa_id LIKE 'telegram:%' AND last_seen >= datetime('now','-10 minutes')")
    online = cur.fetchone()["online"]
    cur.execute("SELECT COUNT(*) AS dau FROM users WHERE wa_id LIKE 'telegram:%' AND last_seen >= date('now')")
    dau = cur.fetchone()["dau"]
    cur.execute("SELECT COUNT(*) AS wau FROM users WHERE wa_id LIKE 'telegram:%' AND last_seen >= date('now','-6 days')")
    wau = cur.fetchone()["wau"]
    conn.close()
    return await update.message.reply_text(
        f"👥 Total: {total}\n🟢 Online(10m): {online}\n📅 DAU: {dau}\n📈 WAU: {wau}"
    )

async def contact_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    wa_id = uid_from_tg(update)
    engine.upsert_user(wa_id, last_seen=_now_iso())
    u = rowdict(engine.get_user(wa_id))
    if not u or "first_seen" not in u or not u["first_seen"]:
        engine.upsert_user(wa_id, first_seen=_now_iso())
    lang = get_lang(wa_id)
    sess = rowdict(engine.get_session(wa_id))
    if not (sess and sess["stage"] == "ask_phone"):
        return
    contact = update.message.contact
    if not contact or not contact.phone_number:
        return
    phone = clean_phone(contact.phone_number)
    if not valid_indian_mobile10(phone):
        return await update.message.reply_text(t("PHONE_BAD", lang))
    engine.upsert_user(wa_id, phone=phone)
    engine.set_session(wa_id, "ask_city")
    return await update.message.reply_text(
        f"{step_header(lang, 5, 'CITY')}\n{t('ASK_CITY', lang)}",
        reply_markup=None
    )

def profile_missing_for_flow(u) -> bool:
    if not u: return True
    required = ("first_name","last_name","dob","phone","city","board","grade")
    return any((k not in u or u[k] is None or u[k] == "") for k in required)

def parse_board_choice(text: str) -> str | None:
    if not text: return None
    tt = text.strip().upper()
    if tt in ("A","CBSE"): return "CBSE"
    if tt in ("B","ICSE"): return "ICSE"
    if tt in ("C","STATE","STATE BOARD","STATEBOARD"): return "STATE"
    return None

def best_match_state(s: str) -> str | None:
    s = (s or "").strip().lower()
    for st in IN_STATES:
        if st.lower() == s:
            return st
    for st in IN_STATES:
        if s and st.lower().startswith(s):
            return st
    return None

def subjects_for_user(wa_id: str):
    u = rowdict(engine.get_user(wa_id))
    board = (u["board"] if u and "board" in u and u["board"] else "")
    grade = str(u["grade"] if u and "grade" in u and u["grade"] else "")
    key = "STATE" if board.startswith("STATE:") else board
    subs = engine.subjects_for(key, grade) or ["English","Mathematics","Science","Social Science"]
    return subs

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    wa_id = uid_from_tg(update)
    engine.upsert_user(wa_id, last_seen=_now_iso())
    u = rowdict(engine.get_user(wa_id))
    if not u or not u.get("first_seen"):
        engine.upsert_user(wa_id, first_seen=_now_iso())
    text = (update.message.text.strip() if update.message and update.message.text else "")
    logger.info(f"[TG] INBOUND from={wa_id} body={text!r}")

    user = rowdict(engine.get_user(wa_id))
    sess = rowdict(engine.get_session(wa_id))
    lang = get_lang(wa_id)

    # ----------- Onboarding & Guard -----------
    if not user or (sess and (sess["stage"] or "").startswith("ask_")) or profile_missing_for_flow(user):
        stage = (sess["stage"] if sess else "ask_lang")
        up = text.upper()

        if stage == "ask_lang":
            engine.set_session(wa_id, "ask_lang")
            return await update.message.reply_text(f"{t('WELCOME','en')}\n\n{t('LANG_PROMPT','en')}", reply_markup=kb_lang())

        if stage == "ask_first" or (user and not user.get("first_name")):
            if not text:
                return await update.message.reply_text(f"{step_header(lang, 1, 'FIRST_NAME')}\n{t('ASK_FIRST', lang)}")
            engine.upsert_user(wa_id, first_name=text)
            engine.set_session(wa_id, "ask_last")
            return await update.message.reply_text(
                f"{step_header(lang, 2, 'LAST_NAME')}\n{t('ASK_LAST', lang, first=text)}"
            )

        if stage == "ask_last" or (user and not user.get("last_name")):
            if not text:
                first = (user or {}).get("first_name","")
                return await update.message.reply_text(f"{step_header(lang, 2, 'LAST_NAME')}\n{t('ASK_LAST', lang, first=first)}")
            engine.upsert_user(wa_id, last_name=text)
            engine.set_session(wa_id, "ask_dob")
            return await update.message.reply_text(f"{step_header(lang, 3, 'DOB')}\n{t('ASK_DOB', lang)}")

        if stage == "ask_dob" or (user and not user.get("dob")):
            if not text or not valid_dob(text):
                return await update.message.reply_text(f"{step_header(lang, 3, 'DOB')}\n{t('DOB_BAD', lang)}")
            engine.upsert_user(wa_id, dob=text)
            engine.set_session(wa_id, "ask_phone")
            kb = ReplyKeyboardMarkup([[KeyboardButton(t("PHONE_BTN", lang), request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
            return await update.message.reply_text(f"{step_header(lang, 4, 'PHONE')}\n{t('ASK_PHONE', lang)}", reply_markup=kb)

        if stage == "ask_phone" or (user and not user.get("phone")):
            digits = re.sub(r"\D","", text or "")
            if digits.startswith("91") and len(digits) == 12:
                digits = digits[2:]
            if not valid_indian_mobile10(digits):
                kb = ReplyKeyboardMarkup([[KeyboardButton(t("PHONE_BTN", lang), request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
                return await update.message.reply_text(t("PHONE_BAD", lang), reply_markup=kb)
            engine.upsert_user(wa_id, phone=digits)
            engine.set_session(wa_id, "ask_city")
            return await update.message.reply_text(f"{step_header(lang, 5, 'CITY')}\n{t('ASK_CITY', lang)}", reply_markup=None)

        if stage == "ask_city" or (user and not user.get("city")):
            if not text:
                return await update.message.reply_text(f"{step_header(lang, 5, 'CITY')}\n{t('ASK_CITY', lang)}")
            engine.upsert_user(wa_id, city=text)
            engine.set_session(wa_id, "ask_board")
            return await update.message.reply_text(
                f"{step_header(lang, 6, 'BOARD')}\n{t('ASK_BOARD', lang)}",
                reply_markup=kb_boards(lang)
            )

        if stage == "ask_board" or (user and not user.get("board")):
            choice = parse_board_choice(text)
            if not choice:
                return await update.message.reply_text(t("INVALID_CHOICE", lang), reply_markup=kb_boards(lang))
            if choice in ("CBSE","ICSE"):
                engine.upsert_user(wa_id, board=choice)
                engine.set_session(wa_id, "ask_grade")
                return await update.message.reply_text(f"{step_header(lang, 8, 'GRADE')}\n{t('ASK_GRADE', lang)}", reply_markup=kb_grades(lang))
            city = (rowdict(engine.get_user(wa_id)) or {}).get("city","")
            guessed = lookup_state_from_city(city)
            engine.upsert_user(wa_id, board="STATE")  # temporary until confirmation
            if guessed:
                engine.set_session(wa_id, f"confirm_state:{guessed}")
                return await update.message.reply_text(
                    f"{step_header(lang, 7, 'BOARD')}\n{t('STATE_GUESS', lang, state=guessed)}",
                    reply_markup=kb_yesno(lang),
                )
            else:
                engine.set_session(wa_id, "pick_state:0")
                return await update.message.reply_text(
                    f"{step_header(lang, 7, 'BOARD')}\n{t('PICK_STATE', lang)}",
                    reply_markup=kb_states_page(lang, 0),
                )

        if stage.startswith("confirm_state:"):
            guessed = stage.split(":",1)[1]
            affirmative = text.strip().lower() in ("y","yes","ha","haan","haanji","ho","hoi","हो","हाँ")
            if affirmative:
                engine.upsert_user(wa_id, board=f"STATE: {guessed}", state=guessed)
                engine.set_session(wa_id, "ask_grade")
                return await update.message.reply_text(f"{step_header(lang, 8, 'GRADE')}\n{t('ASK_GRADE', lang)}", reply_markup=kb_grades(lang))
            engine.set_session(wa_id, "pick_state:0")
            return await update.message.reply_text(f"{step_header(lang, 7, 'BOARD')}\n{t('PICK_STATE', lang)}", reply_markup=kb_states_page(lang, 0))

        if stage.startswith("pick_state:"):
            pick = best_match_state(text)
            if not pick:
                return await update.message.reply_text(t("INVALID_CHOICE", lang), reply_markup=kb_states_page(lang, 0))
            engine.upsert_user(wa_id, board=f"STATE: {pick}", state=pick)
            engine.set_session(wa_id, "ask_grade")
            return await update.message.reply_text(f"{step_header(lang, 8, 'GRADE')}\n{t('ASK_GRADE', lang)}", reply_markup=kb_grades(lang))

        if stage == "ask_grade" or (user and not user.get("grade")):
            g = re.sub(r"\D","", text or "")
            if not g or not (6 <= int(g) <= 12):
                return await update.message.reply_text(t("INVALID_CHOICE", lang), reply_markup=kb_grades(lang))
            engine.upsert_user(wa_id, grade=g, subject="Mathematics", level=1, streak=0)
            subs = subjects_for_user(wa_id)
            engine.set_session(wa_id, "choose_subject")
            await update.message.reply_text(f"{t('PROFILE_SAVED', lang)}")
            return await update.message.reply_text(
                f"{step_header(lang, 9, 'SUBJECT')}\n{t('ASK_SUBJECT', lang)}",
                reply_markup=kb_subjects(subs)
            )

        return await update.message.reply_text(t("FINISH_PROFILE", lang))

    # ---------- Commands (post-onboarding) ----------
    up = (update.message.text or "").strip().upper()

    if up == "HELP":
        return await update.message.reply_text(t("HELP", lang))

    if up == "PROFILE":
        engine.set_session(wa_id, "profile_menu")
        return await update.message.reply_text(t("PROFILE_CMD", lang))

    if up == "RESET":
        engine.set_session(wa_id, "idle", 0, 0, None)
        return await update.message.reply_text(t("RESET_OK", lang))

    if up == "RANK":
        return await update.message.reply_text(t("RANK", lang))

    if up == "STATS":
        conn = engine.db(); cur = conn.cursor()
        cur.execute("SELECT subject, level, score, total FROM history WHERE wa_id=? ORDER BY taken_at DESC LIMIT 5", (wa_id,))
        rows = cur.fetchall(); conn.close()
        if not rows:
            return await update.message.reply_text(t("STATS_EMPTY", lang))
        lines = [t("STATS_HEADER", lang)] + [f"- {r['subject']} L{r['level']}: {r['score']}/{r['total']}" for r in rows]
        return await update.message.reply_text("\n".join(lines))

    if up == "SUBJECT":
        subs = subjects_for_user(wa_id)
        engine.set_session(wa_id, "choose_subject")
        return await update.message.reply_text(t("ASK_SUBJECT", lang), reply_markup=kb_subjects(subs))

    if up == "START":
        await update.message.reply_text(t("GENERATING", lang))
        try:
            user = rowdict(engine.get_user(wa_id))
            level = user.get("level") or 1
            trouble = engine.recent_trouble_concepts(wa_id, user.get("subject"))
            raw_lesson = engine.ai_generate_lesson(
                board=user.get("board"), grade=user.get("grade"), subject_label=user.get("subject"),
                level=level, city=user.get("city"), state=user.get("state"), recent_mistakes=trouble
            )
            lesson = translate_lesson_if_needed(raw_lesson, lang)
            lesson_id = engine.save_lesson(
                wa_id=wa_id,
                board=user.get("board"), grade=user.get("grade"), subject_label=user.get("subject"),
                level=level, title=lesson["title"], intro=lesson["intro"], questions=lesson["questions"]
            )
            engine.set_session(wa_id, "lesson", 0, 0, lesson_id)
            intro = "\n".join(lesson["intro"][:3])
            return await update.message.reply_text(t("TOPIC", lang, title=lesson["title"], level=level, intro=intro), parse_mode="Markdown")
        except Exception as e:
            logger.error(f"[TG] AI generation error: {e}")
            return await update.message.reply_text(t("AI_ERROR", lang))

    if up == "QUIZ":
        sess = rowdict(engine.get_session(wa_id))
        if not sess or not sess["lesson_id"]:
            return await update.message.reply_text(t("NO_LESSON", lang))
        lesson = engine.load_lesson(sess["lesson_id"])
        idx = sess["q_index"]; qs = lesson["questions"]
        if idx >= len(qs):
            return await update.message.reply_text(t("QUIZ_DONE", lang))
        engine.update_session(wa_id, stage="quiz")
        return await send_quiz_question(update, wa_id, lesson, idx)

    # A/B/C/D via text
    if len(up) == 1 and up in "ABCD":
        sess = rowdict(engine.get_session(wa_id))
        if sess and sess["stage"] == "choose_subject":
            subs = subjects_for_user(wa_id)
            i = ord(up) - ord('A')
            if 0 <= i < len(subs):
                engine.upsert_user(wa_id, subject=subs[i], level=1)
                engine.set_session(wa_id, "idle", 0, 0, None)
                return await update.message.reply_text(t("SUBJECT_SET", lang, subject=subs[i]), parse_mode="Markdown")
            return await update.message.reply_text(t("INVALID_CHOICE", lang))
        if sess and sess["stage"] == "quiz":
            user = rowdict(engine.get_user(wa_id))
            reply = engine.process_ai_answer(user, sess, up)
            if "🎉" in reply:
                return await update.message.reply_text(reply)
            # After feedback, prompt for next question
            await update.message.reply_text(reply)
            return await update.message.reply_text("Tap below for the next question:", reply_markup=kb_next_question())
        return await update.message.reply_text(t("PLEASE_ABCD", lang))

    return await update.message.reply_text("👋")

async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data if query and query.data else ""
    # Handle Next Question button
    if data == "NEXTQ":
        sess = rowdict(engine.get_session(wa_id))
        if not sess or not sess["lesson_id"]:
            if query:
                return await query.edit_message_text(t("NO_LESSON", lang))
            return
        lesson = engine.load_lesson(sess["lesson_id"])
        idx = sess["q_index"]
        if idx >= len(lesson["questions"]):
            if query:
                return await query.edit_message_text(t("QUIZ_DONE", lang))
            return
        return await send_quiz_question(update, wa_id, lesson, idx)
    if query:
        await query.answer()
    wa_id = f"telegram:{query.message.chat.id}" if query and query.message and query.message.chat else ""
    user = rowdict(engine.get_user(wa_id))
    sess = rowdict(engine.get_session(wa_id))
    lang = get_lang(wa_id)

    # Language selection
    if data.startswith("LANG:"):
        lang_sel = data.split(":",1)[1]
        set_lang(wa_id, lang_sel)
        engine.set_session(wa_id, "ask_first")
        if query:
            return await query.edit_message_text(
                f"{t('WELCOME', lang_sel)}\n\n{step_header(lang_sel, 1, 'FIRST_NAME')}\n{t('ASK_FIRST', lang_sel)}",
                parse_mode="Markdown"
            )
        return

    # Board selection
    if data.startswith("BOARD:"):
        board = data.split(":",1)[1]
        if board in ("CBSE","ICSE"):
            engine.upsert_user(wa_id, board=board)
            engine.set_session(wa_id, "ask_grade")
            if query:
                return await query.edit_message_text(f"{step_header(lang, 8, 'GRADE')}\n{t('ASK_GRADE', lang)}", reply_markup=kb_grades(lang))
            return
        city = (rowdict(engine.get_user(wa_id)) or {}).get("city","")
        engine.upsert_user(wa_id, board="STATE")
        guessed = lookup_state_from_city(city) if city else None
        if guessed:
            engine.set_session(wa_id, f"confirm_state:{guessed}")
            if query:
                return await query.edit_message_text(
                    f"{step_header(lang, 7, 'BOARD')}\n{t('STATE_GUESS', lang, state=guessed)}",
                    reply_markup=kb_yesno(lang),
                    parse_mode="Markdown"
                )
            return
        else:
            engine.set_session(wa_id, "pick_state:0")
            if query:
                return await query.edit_message_text(
                    f"{step_header(lang, 7, 'BOARD')}\n{t('PICK_STATE', lang)}",
                    reply_markup=kb_states_page(lang, 0)
                )
            return

    # Yes/No for state guess
    if data.startswith("YN:"):
        yn = data.split(":",1)[1]
        stage = sess["stage"] if sess else ""
        if not stage.startswith("confirm_state:"):
            if query:
                return await query.edit_message_text(t("SESSION_EXPIRED", lang))
            return
        guessed = stage.split(":",1)[1]
        if yn == "Y":
            engine.upsert_user(wa_id, board=f"STATE: {guessed}", state=guessed)
            engine.set_session(wa_id, "ask_grade")
            if query:
                return await query.edit_message_text(f"{step_header(lang, 8, 'GRADE')}\n{t('ASK_GRADE', lang)}", reply_markup=kb_grades(lang))
            return
        else:
            engine.set_session(wa_id, "pick_state:0")
            if query:
                return await query.edit_message_text(f"{step_header(lang, 7, 'BOARD')}\n{t('PICK_STATE', lang)}", reply_markup=kb_states_page(lang, 0))
            return

    # State paging
    if data.startswith("PG:"):
        start = int(data.split(":",1)[1])
        engine.set_session(wa_id, f"pick_state:{start}")
        if query:
            return await query.edit_message_text(t("PICK_STATE", lang), reply_markup=kb_states_page(lang, start))
        return

    # Pick state
    if data.startswith("STATE:"):
        pick = data.split(":",1)[1]
        if pick not in IN_STATES:
            if query:
                return await query.answer(t("INVALID_CHOICE", lang), show_alert=True)
            return
        engine.upsert_user(wa_id, board=f"STATE: {pick}", state=pick)
        engine.set_session(wa_id, "ask_grade")
        if query:
            return await query.edit_message_text(f"{step_header(lang, 8, 'GRADE')}\n{t('ASK_GRADE', lang)}", reply_markup=kb_grades(lang))
        return

    # Grade pick
    if data.startswith("GRADE:"):
        g = data.split(":",1)[1]
        if not g.isdigit() or not (6 <= int(g) <= 12):
            if query:
                return await query.answer(t("INVALID_CHOICE", lang), show_alert=True)
            return
        engine.upsert_user(wa_id, grade=g, subject="Mathematics", level=1, streak=0)
        subs = subjects_for_user(wa_id)
        engine.set_session(wa_id, "choose_subject")
        if query:
            await query.edit_message_text(t("PROFILE_SAVED", lang))
            if query.message:
                return await query.message.reply_text(f"{step_header(lang, 9, 'SUBJECT')}\n{t('ASK_SUBJECT', lang)}", reply_markup=kb_subjects(subs))
            return
        return

    # Subject pick
    if data.startswith("SUBJ:"):
        i = int(data.split(":",1)[1])
        subs = subjects_for_user(wa_id)
        if 0 <= i < len(subs):
            chosen = subs[i]
            engine.upsert_user(wa_id, subject=chosen, level=1)
            engine.set_session(wa_id, "idle", 0, 0, None)
            if query:
                return await query.edit_message_text(t("SUBJECT_SET", lang, subject=chosen), parse_mode="Markdown")
            return
        if query:
            return await query.answer(t("INVALID_CHOICE", lang), show_alert=True)
        return

    # Answer buttons
    if data.startswith("ANS:"):
        choice = data.split(":",1)[1]
        sess = rowdict(engine.get_session(wa_id))
        if not (sess and sess["stage"] == "quiz"):
            if query:
                return await query.edit_message_text(t("SESSION_EXPIRED", lang))
            return
        reply = engine.process_ai_answer(user, sess, choice)
        if query:
            if "🎉" in reply:
                return await query.edit_message_text(reply)
            await query.edit_message_text(reply)
            lesson = engine.load_lesson(sess["lesson_id"])
            idx = rowdict(engine.get_session(wa_id))["q_index"]
            return await send_quiz_question(update, wa_id, lesson, idx)
        return

    if query:
        return await query.answer("OK")

# ---------- Launcher (Windows-friendly + tolerant HTTP client) ----------
if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
    # More forgiving HTTP client (fixes intermittent timeouts)
    req = HTTPXRequest(
        connection_pool_size=20,
        connect_timeout=20.0,
        read_timeout=60.0,
        write_timeout=20.0,
        pool_timeout=20.0,
        http_version="1.1",
    )

    app = Application.builder().token(token).request(req).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("adminstats", admin_stats_handler))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(on_button))

    print("🤖 Telegram bot is running… press Ctrl+C to stop.")
    app.run_polling()
