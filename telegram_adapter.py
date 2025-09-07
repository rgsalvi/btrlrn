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
from typing import Optional
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

# ---------- Add mastered_topics table if not exists ----------
def ensure_mastered_topics_table():
    conn = engine.db(); cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS mastered_topics (
            wa_id TEXT,
            board TEXT,
            grade INTEGER,
            subject TEXT,
            topic TEXT,
            mastered_at TEXT,
            PRIMARY KEY (wa_id, board, grade, subject, topic)
        )
    ''')
    conn.commit(); conn.close()
ensure_mastered_topics_table()

# Helper: get mastered topics for user
def get_mastered_topics(wa_id, board, grade, subject):
    conn = engine.db(); cur = conn.cursor()
    cur.execute("SELECT topic FROM mastered_topics WHERE wa_id=? AND board=? AND grade=? AND subject=?", (wa_id, board, grade, subject))
    rows = cur.fetchall(); conn.close()
    return set(r[0] for r in rows)

# Helper: mark topic as mastered
def mark_topic_mastered(wa_id, board, grade, subject, topic):
    conn = engine.db(); cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO mastered_topics (wa_id, board, grade, subject, topic, mastered_at) VALUES (?, ?, ?, ?, ?, datetime('now'))", (wa_id, board, grade, subject, topic))
    conn.commit(); conn.close()

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
    "WELCOME": "🦉 Welcome to btrlrn!",
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
    "CONTINUE": "Choose an option below to continue.",
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
    "WELCOME": "🦉 btrlrn में आपका स्वागत है!",
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
    "CONTINUE": "आगे बढ़ने के लिए नीचे विकल्प चुनें।",
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
    "WELCOME": "🦉 btrlrn मध्ये तुमचे स्वागत आहे!",
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
    "CONTINUE": "पुढे जाण्यासाठी खालील पर्याय निवडा.",
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

def kb_continue():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Start", callback_data="START"),
            InlineKeyboardButton("Change Subject", callback_data="SUBJECT")
        ]
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
    if update and getattr(update, 'effective_chat', None) and getattr(update.effective_chat, 'id', None):
        if update and getattr(update, 'effective_chat', None):
            chat = update.effective_chat
            if chat is not None and hasattr(chat, 'id') and chat.id is not None:
                return f"telegram:{chat.id}"
        return ""
    return ""

def step_header(lang: str, n: int, title_key: str) -> str:
    return f"{t('STEP', lang, n=n, title=t(title_key, lang))}"

# ---------- Flow: senders ----------
async def send_quiz_question(update_or_query, wa_id, lesson, q_index):
    if not lesson or "questions" not in lesson or lesson["questions"] is None:
        return
    if q_index is None or q_index >= len(lesson["questions"]):
        return
    q = lesson["questions"][q_index]
    textq = (
        f"{q['q']}\n"
        f"{q['options'][0]}\n"
        f"{q['options'][1]}\n"
        f"{q['options'][2]}\n"
        f"{q['options'][3]}"
    )
    image_url = q.get("image_url")
    valid_image = False
    if image_url and isinstance(image_url, str):
        image_url_lower = image_url.lower()
        valid_image = image_url_lower.startswith("http") and image_url_lower.split('?')[0].endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp"))
    if isinstance(update_or_query, Update):
        if update_or_query.message is not None:
            if valid_image:
                try:
                    await update_or_query.message.reply_photo(photo=image_url, caption=q['q'])
                    return await update_or_query.message.reply_text(
                        "\n".join(q['options']), reply_markup=kb_abcd()
                    )
                except Exception as e:
                    logger.warning(f"[TG] Failed to send image: {image_url} error: {e}")
                    # fallback to text only
                    return await update_or_query.message.reply_text(textq, reply_markup=kb_abcd())
            else:
                return await update_or_query.message.reply_text(textq, reply_markup=kb_abcd())
        if update_or_query.callback_query is not None:
            return await update_or_query.callback_query.edit_message_text(textq, reply_markup=kb_abcd())
    # fallback: do nothing if neither is available
    return

# ---------- Handlers ----------
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    wa_id = uid_from_tg(update)
    user = rowdict(engine.get_user(wa_id))
    sess = rowdict(engine.get_session(wa_id))
    lang = get_lang(wa_id)
    # If user does not exist or profile is incomplete, start onboarding
    if not user or profile_missing_for_flow(user):
        engine.set_session(wa_id, "ask_lang")
        if update.message is not None:
            await update.message.reply_text(f"{t('WELCOME','en')}\n\n{t('LANG_PROMPT','en')}", reply_markup=kb_lang())
        return
    # If user exists and has a session, resume from last stage
    if sess and sess.get("stage") and sess["stage"] != "idle":
        if update.message is not None:
            subj = user.get('subject', 'a subject')
            lvl = user.get('level', 1)
            msg = f"🦉 Welcome back, {user.get('first_name','')}!\nYour last subject was {subj} at Level {lvl}."
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("Continue Learning", callback_data="CONTINUE_LEARNING"),
                 InlineKeyboardButton("Change Subject", callback_data="SUBJECT")]
            ])
            await update.message.reply_text(msg, reply_markup=kb)
        return
    # If user exists, profile complete, but no session or idle, show welcome back and main menu/subject selection
    if update.message is not None:
        subj = user.get('subject', 'a subject')
        lvl = user.get('level', 1)
        msg = f"🦉 Welcome back, {user.get('first_name','')}!\nYour last subject was {subj} at Level {lvl}."
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Continue Learning", callback_data="CONTINUE_LEARNING"),
             InlineKeyboardButton("Change Subject", callback_data="SUBJECT")]
        ])
        await update.message.reply_text(msg, reply_markup=kb)

async def admin_stats_handler(update, context):
    if not (update.effective_user and update.effective_user.id in ADMIN_IDS):
        if getattr(update, 'message', None):
            return await update.message.reply_text("Not authorized.")
        return
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
    if getattr(update, 'message', None):
        return await update.message.reply_text(
            f"👥 Total: {total}\n🟢 Online(10m): {online}\n📅 DAU: {dau}\n📈 WAU: {wau}"
        )
    return

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):

    wa_id = uid_from_tg(update)
    lang = 'en'
    sess = rowdict(engine.get_session(wa_id))
    if sess and 'lang' in sess:
        lang = sess['lang']
    if update.message:
        return await update.message.reply_text(t("HELP", lang))
    return

async def quiz_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await text_handler(update, ctx, forced_text="QUIZ")

async def subject_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await text_handler(update, ctx, forced_text="SUBJECT")

async def profile_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await text_handler(update, ctx, forced_text="PROFILE")

async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await text_handler(update, ctx, forced_text="STATS")

async def reset_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await text_handler(update, ctx, forced_text="RESET")
    return

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
    contact = update.message.contact if update.message and getattr(update.message, 'contact', None) else None
    if not contact or not getattr(contact, 'phone_number', None):
        return
    phone = clean_phone(contact.phone_number)
    if not valid_indian_mobile10(phone):
        if update.message:
            return await update.message.reply_text(t("PHONE_BAD", lang))
        return
    engine.upsert_user(wa_id, phone=phone)
    engine.set_session(wa_id, "ask_city")
    if update.message:
        return await update.message.reply_text(
            f"{step_header(lang, 5, 'CITY')}\n{t('ASK_CITY', lang)}",
            reply_markup=None
        )
    return

def profile_missing_for_flow(u) -> bool:
    if not u: return True
    required = ("first_name","last_name","dob","city","board","grade")
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
    # Query subjects from syllabus table for this board and grade
    subs = []
    try:
        conn = engine.db(); cur = conn.cursor()
        cur.execute("SELECT DISTINCT subject FROM syllabus WHERE board=? AND grade=?", (board, grade))
        subs = [r[0] for r in cur.fetchall()]
        conn.close()
    except Exception as e:
        logger.error(f"[TG] subjects_for_user error: {e}")
        subs = []
    # Fallback to defaults if none found or error
    if not subs:
        subs = ["English","Mathematics","Science","Social Science"]
    return subs

# Helper: get topics for subject/grade/board, excluding mastered
def topics_for_user(wa_id, board, grade, subject):
    # Get all topics from syllabus_db (no mastery check)
    conn = engine.db(); cur = conn.cursor()
    cur.execute("SELECT topic FROM syllabus WHERE board=? AND grade=? AND subject=?", (board, grade, subject))
    all_topics = [r[0] for r in cur.fetchall()]
    conn.close()
    return all_topics

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE, forced_text: Optional[str] = None):
    wa_id = uid_from_tg(update)
    engine.upsert_user(wa_id, last_seen=_now_iso())
    u = rowdict(engine.get_user(wa_id))
    if not u or not u.get("first_seen"):
        engine.upsert_user(wa_id, first_seen=_now_iso())

    # Use forced_text if provided, else use message text
    if forced_text is not None:
        text = forced_text
        up = forced_text.upper()
    else:
        text = (update.message.text.strip() if update.message and update.message.text else "")
        up = text.upper()
    logger.info(f"[TG] INBOUND from={wa_id} body={text!r}")

    user = rowdict(engine.get_user(wa_id))
    sess = rowdict(engine.get_session(wa_id))
    lang = get_lang(wa_id)


    # ----------- Onboarding & Guard -----------
    if not user or (sess and (sess["stage"] or "").startswith("ask_")) or profile_missing_for_flow(user):
        stage = (sess["stage"] if sess else "ask_lang")

        # Onboarding logic uses text, not up
        if stage == "ask_lang":
            engine.set_session(wa_id, "ask_lang")
            if update.message:
                return await update.message.reply_text(f"{t('WELCOME','en')}\n\n{t('LANG_PROMPT','en')}", reply_markup=kb_lang())
            return

        if stage == "ask_first" or (user and not user.get("first_name")):
            if not text:
                if update.message:
                    return await update.message.reply_text(f"{step_header(lang, 1, 'FIRST_NAME')}\n{t('ASK_FIRST', lang)}")
                return
            engine.upsert_user(wa_id, first_name=text)
            engine.set_session(wa_id, "ask_last")
            if update.message:
                return await update.message.reply_text(
                    f"{step_header(lang, 2, 'LAST_NAME')}\n{t('ASK_LAST', lang, first=text)}"
                )
            return

        if stage == "ask_last" or (user and not user.get("last_name")):
            if not text:
                first = (user or {}).get("first_name","")
                if update.message:
                    return await update.message.reply_text(f"{step_header(lang, 2, 'LAST_NAME')}\n{t('ASK_LAST', lang, first=first)}")
                return
            engine.upsert_user(wa_id, last_name=text)
            engine.set_session(wa_id, "ask_dob")
            if update.message:
                return await update.message.reply_text(f"{step_header(lang, 3, 'DOB')}\n{t('ASK_DOB', lang)}")
            return

        if stage == "ask_dob" or (user and not user.get("dob")):
            if not text or not valid_dob(text):
                if update.message:
                    return await update.message.reply_text(f"{step_header(lang, 3, 'DOB')}\n{t('DOB_BAD', lang)}")
                return
            engine.upsert_user(wa_id, dob=text)
            engine.set_session(wa_id, "ask_city")
            if update.message:
                return await update.message.reply_text(f"{step_header(lang, 5, 'CITY')}\n{t('ASK_CITY', lang)}", reply_markup=None)
            return

        if stage == "ask_city" or (user and not user.get("city")):
            if not text:
                if update.message:
                    return await update.message.reply_text(f"{step_header(lang, 5, 'CITY')}\n{t('ASK_CITY', lang)}")
                return
            engine.upsert_user(wa_id, city=text)
            engine.set_session(wa_id, "ask_board")
            if update.message:
                return await update.message.reply_text(
                    f"{step_header(lang, 6, 'BOARD')}\n{t('ASK_BOARD', lang)}",
                    reply_markup=kb_boards(lang)
                )
            return

        if stage == "ask_board" or (user and not user.get("board")):
            choice = parse_board_choice(text)
            if not choice:
                if update.message:
                    return await update.message.reply_text(t("INVALID_CHOICE", lang), reply_markup=kb_boards(lang))
                return
            if choice in ("CBSE","ICSE"):
                engine.upsert_user(wa_id, board=choice)
                engine.set_session(wa_id, "ask_grade")
                if update.message:
                    return await update.message.reply_text(f"{step_header(lang, 8, 'GRADE')}\n{t('ASK_GRADE', lang)}", reply_markup=kb_grades(lang))
                return
            city = (rowdict(engine.get_user(wa_id)) or {}).get("city","")
            guessed = lookup_state_from_city(city)
            engine.upsert_user(wa_id, board="STATE")  # temporary until confirmation
            if guessed:
                engine.set_session(wa_id, f"confirm_state:{guessed}")
                if update.message:
                    return await update.message.reply_text(
                        f"{step_header(lang, 7, 'BOARD')}\n{t('STATE_GUESS', lang, state=guessed)}",
                        reply_markup=kb_yesno(lang),
                    )
                return
            else:
                engine.set_session(wa_id, "pick_state:0")
                if update.message:
                    return await update.message.reply_text(
                        f"{step_header(lang, 7, 'BOARD')}\n{t('PICK_STATE', lang)}",
                        reply_markup=kb_states_page(lang, 0),
                    )
                return

        if stage.startswith("confirm_state:"):
            guessed = stage.split(":",1)[1]
            affirmative = text.strip().lower() in ("y","yes","ha","haan","haanji","ho","hoi","हो","हाँ")
            if affirmative:
                engine.upsert_user(wa_id, board=f"STATE: {guessed}", state=guessed)
                engine.set_session(wa_id, "ask_grade")
                if update.message:
                    return await update.message.reply_text(f"{step_header(lang, 8, 'GRADE')}\n{t('ASK_GRADE', lang)}", reply_markup=kb_grades(lang))
                return
            engine.set_session(wa_id, "pick_state:0")
            if update.message:
                return await update.message.reply_text(f"{step_header(lang, 7, 'BOARD')}\n{t('PICK_STATE', lang)}", reply_markup=kb_states_page(lang, 0))
            return

        if stage.startswith("pick_state:"):
            pick = best_match_state(text)
            if not pick:
                if update.message:
                    return await update.message.reply_text(t("INVALID_CHOICE", lang), reply_markup=kb_states_page(lang, 0))
                return
            engine.upsert_user(wa_id, board=f"STATE: {pick}", state=pick)
            engine.set_session(wa_id, "ask_grade")
            if update.message:
                return await update.message.reply_text(f"{step_header(lang, 8, 'GRADE')}\n{t('ASK_GRADE', lang)}", reply_markup=kb_grades(lang))
            return

        if stage == "ask_grade" or (user and not user.get("grade")):
            # Show profile summary and ask for confirmation
            u = rowdict(engine.get_user(wa_id))
            profile_lines = []
            profile_lines.append("Please review your profile:")
            if u:
                profile_lines.append(f"A) Name: {u.get('first_name','')} {u.get('last_name','')}")
                profile_lines.append(f"B) City: {u.get('city','')}")
                profile_lines.append(f"C) State/Curriculum: {u.get('state','') or u.get('board','')}")
                profile_lines.append(f"D) Grade: {u.get('grade','')}")
                profile_lines.append(f"E) Subject: {u.get('subject','')}")
            else:
                profile_lines.append("(Profile data not found)")
            profile_lines.append("")
            profile_lines.append("Is this correct?")
            msg = "\n".join(profile_lines)
            # Inline buttons: Confirm / Edit Profile
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirm", callback_data="PROFILE_CONFIRM"),
                 InlineKeyboardButton("✏️ Edit", callback_data="PROFILE_EDIT")]
            ])
            engine.set_session(wa_id, "profile_confirm")
            if update.message:
                return await update.message.reply_text(msg, reply_markup=kb)
            return

        if update.message:
            return await update.message.reply_text(t("FINISH_PROFILE", lang))
        return

    # ---------- Commands (post-onboarding) ----------
    # up is already set above

    if up == "HELP":
        if update.message:
            return await update.message.reply_text(t("HELP", lang))
        return

    if up == "PROFILE":
        engine.set_session(wa_id, "profile_menu")
        u = rowdict(engine.get_user(wa_id))
        profile_lines = []
        if u:
            profile_lines.append("Your current profile:")
            profile_lines.append(f"A) Name: {u.get('first_name','')} {u.get('last_name','')}")
            profile_lines.append(f"B) City: {u.get('city','')}")
            profile_lines.append(f"C) State/Curriculum: {u.get('state','') or u.get('board','')}")
            profile_lines.append(f"D) Grade: {u.get('grade','')}")
            profile_lines.append(f"E) Subject: {u.get('subject','')}")
            profile_lines.append("")
        profile_lines.append(t("PROFILE_CMD", lang))
        msg = "\n".join(profile_lines)
        if update.message:
            return await update.message.reply_text(msg)
        return

    if up == "RESET":
        engine.set_session(wa_id, "idle", 0, 0, None)
        if update.message:
            return await update.message.reply_text(t("RESET_OK", lang))
        return

    if up == "RANK":
        if update.message:
            return await update.message.reply_text(t("RANK", lang))
        return

    if up == "STATS":
        conn = engine.db(); cur = conn.cursor()
        cur.execute("SELECT subject, level, score, total FROM history WHERE wa_id=? ORDER BY taken_at DESC LIMIT 5", (wa_id,))
        rows = cur.fetchall(); conn.close()
        if not rows:
            if update.message:
                return await update.message.reply_text(t("STATS_EMPTY", lang))
            return
        lines = [t("STATS_HEADER", lang)] + [f"- {r['subject']} L{r['level']}: {r['score']}/{r['total']}" for r in rows]
        if update.message:
            return await update.message.reply_text("\n".join(lines))
        return



    if up == "SUBJECT":
        # After subject is chosen, show profile summary and ask for confirmation
        u = rowdict(engine.get_user(wa_id))
        profile_lines = []
        profile_lines.append("Please review your profile:")
        if u:
            profile_lines.append(f"A) Name: {u.get('first_name','')} {u.get('last_name','')}")
            profile_lines.append(f"B) City: {u.get('city','')}")
            profile_lines.append(f"C) State/Curriculum: {u.get('state','') or u.get('board','')}")
            profile_lines.append(f"D) Grade: {u.get('grade','')}")
            profile_lines.append(f"E) Subject: {u.get('subject','')}")
        else:
            profile_lines.append("(Profile data not found)")
        profile_lines.append("")
        profile_lines.append("Is this correct?")
        msg = "\n".join(profile_lines)
        # Inline buttons: Confirm / Edit Profile
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm", callback_data="PROFILE_CONFIRM"),
             InlineKeyboardButton("✏️ Edit", callback_data="PROFILE_EDIT")]
        ])
        engine.set_session(wa_id, "profile_confirm")
        if update.message:
            return await update.message.reply_text(msg, reply_markup=kb)
        return

    # Remove explicit topic selection after subject pick. After subject is chosen, set session to idle and prompt user to type START.
    if up == "TOPIC":
        engine.set_session(wa_id, "idle", 0, 0, None)
        if update.message:
            return await update.message.reply_text(t("CONTINUE", lang), reply_markup=kb_continue())
        return

    if up == "START":
        if update.message:
            await update.message.reply_text(t("GENERATING", lang))
        try:
            user = rowdict(engine.get_user(wa_id))
            level = user.get("level") if user and "level" in user else 1
            trouble = engine.recent_trouble_concepts(wa_id, user.get("subject")) if user else None
            raw_lesson = engine.ai_generate_lesson(
                board=user.get("board") if user else None,
                grade=user.get("grade") if user else None,
                subject_label=user.get("subject") if user else None,
                level=level,
                city=user.get("city") if user else None,
                state=user.get("state") if user else None,
                recent_mistakes=trouble,
                wa_id=wa_id
            ) if user else None
            lesson = translate_lesson_if_needed(raw_lesson, lang) if raw_lesson else None
            lesson_id = engine.save_lesson(
                wa_id=wa_id,
                board=user.get("board") if user else None,
                grade=user.get("grade") if user else None,
                subject_label=user.get("subject") if user else None,
                level=level,
                title=lesson["title"] if lesson else None,
                intro=lesson["intro"] if lesson else None,
                questions=lesson["questions"] if lesson else None
            ) if lesson else None
            engine.set_session(wa_id, "lesson", 0, 0, lesson_id)
            intro = "\n".join(lesson["intro"][:3]) if lesson and "intro" in lesson else ""
            if update.message:
                return await update.message.reply_text(t("TOPIC", lang, title=lesson["title"] if lesson else "", level=level, intro=intro), parse_mode="Markdown")
            return
        except Exception as e:
            logger.error(f"[TG] AI generation error: {e}")
            if update.message:
                return await update.message.reply_text(t("AI_ERROR", lang))
            return

    if up == "QUIZ":
        sess = rowdict(engine.get_session(wa_id))
        if not sess or "lesson_id" not in sess or not sess["lesson_id"]:
            if update.message:
                return await update.message.reply_text(t("NO_LESSON", lang))
            return
        lesson = engine.load_lesson(sess["lesson_id"])
        idx = sess["q_index"] if sess and "q_index" in sess else 0
        qs = lesson["questions"] if lesson and "questions" in lesson else []
        if idx >= len(qs):
            if update.message:
                return await update.message.reply_text(t("QUIZ_DONE", lang))
            return
        engine.update_session(wa_id, stage="quiz")
        return await send_quiz_question(update, wa_id, lesson, idx)

    # Handle editing each profile field (accept any input when stage starts with 'edit_')
    sess = rowdict(engine.get_session(wa_id))
    if sess and "stage" in sess and sess["stage"].startswith("edit_"):
        field = sess["stage"].replace("edit_", "")
        value = text
        # Validate grade
        if field == "grade":
            g = re.sub(r"\D", "", value)
            if not g or not (6 <= int(g) <= 12):
                if update.message:
                    return await update.message.reply_text("Invalid grade. Please enter a number between 6 and 12.")
                return
            value = g
        # Validate subject
        if field == "subject":
            subs = subjects_for_user(wa_id)
            if value not in subs:
                if update.message:
                    return await update.message.reply_text(f"Invalid subject. Please pick one of: {', '.join(subs)}")
                return
        # Update user profile
        engine.upsert_user(wa_id, **{field: value})

        # If city is edited, re-guess state and prompt for confirmation or selection
        if field == "city":
            guessed = lookup_state_from_city(value)
            if guessed:
                engine.set_session(wa_id, f"confirm_state:{guessed}")
                if update.message:
                    return await update.message.reply_text(
                        f"We think your state is *{guessed}*. Is that right?",
                        reply_markup=kb_yesno(lang),
                        parse_mode="Markdown"
                    )
                return
            else:
                engine.set_session(wa_id, "pick_state:0")
                if update.message:
                    return await update.message.reply_text(
                        t("PICK_STATE", lang),
                        reply_markup=kb_states_page(lang, 0)
                    )
                return

        engine.set_session(wa_id, "idle", 0, 0, None)
        if update.message:
            return await update.message.reply_text(t("PROFILE_UPDATED", lang))
        return

    # A/B/C/D/E via text for subject/quiz/profile
    if len(up) == 1 and up in "ABCDE":
        # Profile editing menu
        if sess and "stage" in sess and sess["stage"] == "profile_menu":
            # Map A-E to profile fields
            field_map = {
                "A": ("first_name", "Please enter your first name:"),
                "B": ("city", "Please enter your city:"),
                "C": ("state", "Please enter your state/curriculum (e.g., Maharashtra, CBSE, ICSE):"),
                "D": ("grade", "Please enter your grade (6-12):"),
                "E": ("subject", "Please enter your subject (e.g., Mathematics, Science):"),
            }
            if up in field_map:
                field, prompt = field_map[up]
                engine.set_session(wa_id, f"edit_{field}")
                if update.message:
                    return await update.message.reply_text(prompt)
                return
            if update.message:
                return await update.message.reply_text(t("INVALID_CHOICE", lang))
            return
        # Subject selection menu
        if sess and "stage" in sess and sess["stage"] == "choose_subject":
            subs = subjects_for_user(wa_id)
            i = ord(up) - ord('A')
            if 0 <= i < len(subs):
                engine.upsert_user(wa_id, subject=subs[i], level=1)
                engine.set_session(wa_id, "idle", 0, 0, None)
                kb_start = InlineKeyboardMarkup([[InlineKeyboardButton("START", callback_data="START")]])
                if update.message:
                    return await update.message.reply_text(
                        f"Subject set to *{subs[i]}*. Tap START when you're ready to begin.",
                        parse_mode="Markdown",
                        reply_markup=kb_start
                    )
                return
            if update.message:
                return await update.message.reply_text(t("INVALID_CHOICE", lang))
            return
        # Quiz answer
        if sess and "stage" in sess and sess["stage"] == "quiz":
            user = rowdict(engine.get_user(wa_id))
            reply = engine.process_ai_answer(user, sess, up)
            if update.message:
                if "🎉" in reply:
                    return await update.message.reply_text(reply)
                # After feedback, prompt for next question
                await update.message.reply_text(reply)
                return await update.message.reply_text("Tap below for the next question:", reply_markup=kb_next_question())
            return
        if update.message:
            return await update.message.reply_text(t("PLEASE_ABCD", lang))
        return

    if update.message:
        return await update.message.reply_text("👋")
    return

async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Handle Continue Learning and Change Subject buttons simply
    query = update.callback_query if hasattr(update, 'callback_query') else None
    data = query.data if query and hasattr(query, 'data') else ""
    if data == "CONTINUE_LEARNING":
        # Simulate sending '/start' as if user typed it
        await text_handler(update, ctx, forced_text="/start")
        return
    if data == "SUBJECT":
        # Just call subject_cmd logic for subject change
        await subject_cmd(update, ctx)
        return
    query = update.callback_query if hasattr(update, 'callback_query') else None
    data = query.data if query and hasattr(query, 'data') else ""
    # Profile confirmation step
    if data == "PROFILE_CONFIRM":
        wa_id = ""
        if query and getattr(query, 'message', None):
            chat_obj = getattr(query.message, 'chat', None)
            if chat_obj and hasattr(chat_obj, 'id'):
                wa_id = f"telegram:{chat_obj.id}"
        lang = get_lang(wa_id)
        engine.set_session(wa_id, "choose_subject")
        subs = subjects_for_user(wa_id)
        if query:
            await query.edit_message_text(t("PROFILE_SAVED", lang))
            chat_id = None
            if query.message and getattr(query.message, 'chat', None) and hasattr(query.message.chat, 'id'):
                chat_id = query.message.chat.id
            if chat_id:
                return await ctx.bot.send_message(chat_id=chat_id,
                    text=f"{step_header(lang, 9, 'SUBJECT')}\n{t('ASK_SUBJECT', lang)}",
                    reply_markup=kb_subjects(subs))
        return

    if data == "PROFILE_EDIT":
        wa_id = ""
        if query and getattr(query, 'message', None):
            chat_obj = getattr(query.message, 'chat', None)
            if chat_obj and hasattr(chat_obj, 'id'):
                wa_id = f"telegram:{chat_obj.id}"
        lang = get_lang(wa_id)
        engine.set_session(wa_id, "profile_menu")
        u = rowdict(engine.get_user(wa_id))
        profile_lines = []
        if u:
            profile_lines.append("Your current profile:")
            profile_lines.append(f"A) Name: {u.get('first_name','')} {u.get('last_name','')}")
            profile_lines.append(f"B) City: {u.get('city','')}")
            profile_lines.append(f"C) State/Curriculum: {u.get('state','') or u.get('board','')}")
            profile_lines.append(f"D) Grade: {u.get('grade','')}")
            profile_lines.append(f"E) Subject: {u.get('subject','')}")
            profile_lines.append("")
        else:
            profile_lines.append("(Profile data not found)")
        profile_lines.append(t("PROFILE_CMD", lang))
        msg = "\n".join(profile_lines)
        if query:
            return await query.edit_message_text(msg)
        return
    # Handle START button callback
    if update and getattr(update, 'callback_query', None) and getattr(update.callback_query, 'data', None) == "START":
        query = update.callback_query
        wa_id = ""
        if query and getattr(query, 'message', None):
            chat_obj = getattr(query.message, 'chat', None)
            if chat_obj and hasattr(chat_obj, 'id'):
                wa_id = f"telegram:{chat_obj.id}"
        lang = get_lang(wa_id)
        user = rowdict(engine.get_user(wa_id))
        if not user:
            if query and getattr(query, 'edit_message_text', None):
                return await query.edit_message_text("Profile not found. Please restart.")
            return
        # Show 'Generating your lesson...' message
        if query and getattr(query, 'edit_message_text', None):
            gen_msg = await query.edit_message_text("💡 Generating your lesson, please wait…")
        # Show typing indicator
        chat_id = None
        if query and getattr(query, 'message', None):
            chat_obj = getattr(query.message, 'chat', None)
            if chat_obj and hasattr(chat_obj, 'id'):
                chat_id = chat_obj.id
        if chat_id and hasattr(ctx, 'bot'):
            await ctx.bot.send_chat_action(chat_id=chat_id, action="typing")
        # Generate lesson
        level = user["level"] if user and "level" in user and user["level"] else 1
        subject = user["subject"] if user and "subject" in user else None
        trouble = engine.recent_trouble_concepts(wa_id, subject)
        raw_lesson = engine.ai_generate_lesson(
            board=user.get("board") if user else None,
            grade=user.get("grade") if user else None,
            subject_label=subject,
            level=level,
            city=user.get("city") if user else None,
            state=user.get("state") if user else None,
            recent_mistakes=trouble,
            wa_id=wa_id
        ) if subject else None
        if not raw_lesson:
            if query and getattr(query, 'edit_message_text', None):
                return await query.edit_message_text("Could not generate lesson. Please try again.")
            return
        lesson = translate_lesson_if_needed(raw_lesson, lang) if raw_lesson else None
        lesson_id = engine.save_lesson(
            wa_id=wa_id,
            board=user.get("board") if user else None,
            grade=user.get("grade") if user else None,
            subject_label=subject,
            level=level,
            title=lesson["title"] if lesson else None,
            intro=lesson["intro"] if lesson else None,
            questions=lesson["questions"] if lesson else None
        ) if lesson else None
        engine.set_session(wa_id, "lesson", 0, 0, lesson_id)
        intro = "\n".join(lesson["intro"][:3]) if lesson and "intro" in lesson else ""
        if query and getattr(query, 'edit_message_text', None):
            return await query.edit_message_text(
                t("TOPIC", lang, title=lesson["title"] if lesson else "", level=level, intro=intro),
                parse_mode="Markdown"
            )
        return
    query = update.callback_query
    data = query.data if query and query.data else ""
    if query:
        await query.answer()
    
    wa_id = ""
    if query and getattr(query, 'message', None):
        chat_obj = getattr(query.message, 'chat', None)
        if chat_obj and hasattr(chat_obj, 'id'):
            wa_id = f"telegram:{chat_obj.id}"
    user = rowdict(engine.get_user(wa_id))
    sess = rowdict(engine.get_session(wa_id))
    lang = get_lang(wa_id)

    # Handle Next Question button
    if data == "NEXTQ":
        if not sess or "lesson_id" not in sess or not sess["lesson_id"]:
            if query and getattr(query, 'edit_message_text', None):
                return await query.edit_message_text(t("NO_LESSON", lang))
            return
        lesson = engine.load_lesson(sess["lesson_id"])
        idx = sess["q_index"] if sess and "q_index" in sess else 0
        qs = lesson["questions"] if lesson and "questions" in lesson else []
        if idx >= len(qs):
            if query and getattr(query, 'edit_message_text', None):
                return await query.edit_message_text(t("QUIZ_DONE", lang))
            return
        return await send_quiz_question(update, wa_id, lesson, idx)

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
            # Instead of reply_text, send a new message using bot context
            if query.message and hasattr(ctx, 'bot'):
                chat_id = query.message.chat.id if hasattr(query.message, 'chat') and hasattr(query.message.chat, 'id') else None
                if chat_id:
                    await ctx.bot.send_message(chat_id=chat_id,
                        text=f"{step_header(lang, 9, 'SUBJECT')}\n{t('ASK_SUBJECT', lang)}",
                        reply_markup=kb_subjects(subs))
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
            # Show continue options as buttons
            if query:
                return await query.edit_message_text(t("CONTINUE", lang), reply_markup=kb_continue())
            return
        if query:
            return await query.answer(t("INVALID_CHOICE", lang), show_alert=True)
        return
    
    # Topic pick (no mastery, always allow new topic)
    if data.startswith("TOPIC:"):
        # This block is now obsolete, but kept for future extensibility if needed
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
            # Instead of reply_text, send a new message using bot context
            if query.message and hasattr(ctx, 'bot'):
                chat_id = query.message.chat.id if hasattr(query.message, 'chat') and hasattr(query.message.chat, 'id') else None
                if chat_id:
                    await ctx.bot.send_message(chat_id=chat_id,
                        text="Tap below for the next question:",
                        reply_markup=kb_next_question())
            return
        return

    if query:
        return await query.answer("OK")

# ---------- Launcher (Windows-friendly + tolerant HTTP client) ----------
if __name__ == "__main__":

    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    token = os.environ["TELEGRAM_BOT_TOKEN"].strip()
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
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    app.add_handler(CommandHandler("subject", subject_cmd))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(on_button))

    print("🤖 Telegram bot is running… press Ctrl+C to stop.")
    app.run_polling()