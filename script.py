from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    CallbackQueryHandler, ContextTypes, filters
)

import whisper
import requests
import os
import re
import unicodedata
import joblib
import sys
import io

# Виправляємо кодування для Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from rapidfuzz import fuzz

# ================== CONFIG ==================
BOT_TOKEN = "7955348332:AAFk8PV2qFcAc2j_0leFNDpNnBRblQje-lQ"
ESP32_IP = "http://192.168.31.152/cmd"

MODEL_FILE = "intent_model.pkl"

# ================== LOAD WHISPER ==================
print("[*] Loading Whisper model...")
# Використовуємо "small" модель замість "base" для кращого розпізнавання українського
whisper_model = whisper.load_model("small")

# ================== INTENT DATA ==================
INTENTS = {
    "on": [
        # Основні варіації
        "увімкни світло", "включи світло", "запали", "дай світло",
        "світло", "увімкни", "включи", "запали світло", "дай світла",
        "увімкни лампу", "включи лампу", "світло увімкни", "світло включи",
        "хочу світло", "потрібно світло", "зроби світло", "світло на",
        # Варіації з дієсловами
        "вмикай", "вмикайте", "вмикай світло", "вмикайте світло",
        "включити", "включити світло", "включити лампу",
        "запалити", "запалити світло", "запалити лампу",
        "зажги", "зажги світло", "загорись",
        # Короткі команди
        "вкл", "вк", "вмик", "вмі", "у", "і", "вн", "вно",
        # Лампи
        "неси світло", "лампа", "лампу", "лампочка", "лампи",
        # Інші варіації
        "світ", "світе", "світлинка", "більше світла", "усім світла",
        # Контекстні варіації
        "дай мені світло", "мені світло", "розпали", "розпали світло",
        "вмикай лампочку", "вмикай лампу", "включаються", "включається",
        # Типові помилки/вимови
        "вмі", "увмі", "уві", "вімкни", "вімі"
    ],
    "off": [
        # Основні варіації
        "вимкни світло", "загаси", "погаси", "вимкни", "загаси світло",
        "погаси світло", "вимкни лампу", "світло вимкни", "світло загаси",
        "не треба світло", "прибери світло", "світло геть", "світло виключи",
        # Варіації з дієсловами
        "вимикай", "вимикайте", "вимикай світло", "вимикайте світло",
        "выключи", "выключить", "выключить светло",
        "тушити", "туши", "туши світло", "тушіть",
        "гасіть", "гаси", "гаси світло", "гасити",
        "виключи", "виключити", "виключити світло",
        # Короткі команди
        "вик", "вмі", "выкл", "вки", "вимі", "вм", "з", "вимк", "вми",
        # Лампи
        "вимкни лампочку", "вимкни лампу", "лампу вимкни",
        # Контекстні варіації
        "прибери світло", "збери світло", "светло выключи",
        "выключи это", "выключи светло", "свет выключи",
        # Інші варіації
        "няй", "біс", "биш", "гасни", "туши вже", "гасити вже"
    ],
    "brighter": [
        # Основні варіації
        "зроби світліше", "додай світла", "яскравіше", "більше світла",
        "світліше", "яскраво", "додай яскравості", "зроби яскравіше",
        "світло більше", "посвітли", "яскравість більше", "світла більше",
        # Варіації з дієсловами
        "посилитися", "більш яскраво", "яскравіше будь",
        "посвітлити", "посвітли світло", "посилити світло",
        # Короткі команди
        "вісім", "виісм", "усім", "яскравість", "яскраво", "далі",
        # Контекстні
        "дай більше", "дай яскравості", "включи яскравість",
        "пустіше", "ясніше", "до максимума", "на максимум",
        "світло вище", "больше", "плюс", "вверх", "підніми"
    ],
    "dimmer": [
        # Основні варіації
        "зроби темніше", "менше світла", "приглуши", "темніше",
        "зменши світло", "світло менше", "приглуш світло", "тьмяніше",
        "зменши яскравість", "світло тьмяніше", "менш яскраво",
        # Варіації з дієсловами
        "приглушити", "приглуш", "приглушити світло",
        "зменшити", "зменш", "зменшити світло", "зменшити яскравість",
        # Контекстні
        "трошечку", "трошечко", "трішечко", "менше", "зроблю менше",
        "понижу", "снизить", "снижу", "убавити", "менше свет",
        # Короткі команди
        "теня", "тень", "вниз", "мінус", "менше", "приглуш", "зменш",
        # Фонетичні варіації Whisper помилок
        "манча", "манча свидла", "мени", "меніше", "зробити меніше",
        "те мені", "те мені жа", "ти мені", "ти мені іша",
        "тем нише", "тем ні ше", "темні ше",
        # Похідні "темніше"
        "темнеш", "темно", "тьмяно", "тьмана", "тема", "темна",
        # Похідні "менше"
        "мне", "мень", "мен", "мена", "менче", "мніш", "менш"
    ],
    "day": [
        # Основні варіації
        "денний режим", "максимальне світло", "на повну", "день",
        "повне світло", "максимум", "яскраво максимум", "на всю",
        "денне світло", "світло на максимум", "повна яскравість",
        # Варіації
        "денний", "день на", "денне", "сонячно", "сонячний",
        "на максимум", "максимальна яскравість", "все світло",
        "повностю", "п максимум", "мак", "максимум максимум",
        "світло максимум", "максимум світла", "яскравість максимум"
    ],
    "night": [
        # Основні варіації
        "нічний режим", "нічник", "нічне світло", "ніч", "тьмяно",
        "мінімум світла", "слабке світло", "приглушене світло",
        "нічна лампа", "світло на мінімум", "тихе світло",
        # Варіації
        "нічний", "ніч на", "ночной", "ноч", "нічка",
        "приглушено", "тьмяне", "темне", "мінімально",
        "мало світла", "слабо", "приглушене", "тихе",
        "нічна лампочка", "ночник", "ничник", "мінімум"
    ]
}

# ================== ML MODEL ==================
def train_model():
    texts, labels = [], []
    for intent, examples in INTENTS.items():
        for e in examples:
            texts.append(e)
            labels.append(intent)

    # Використовуємо більш потужні параметри
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 3),  # Додали триграми для кращого розуміння фраз
        min_df=1,
        max_df=1.0,
        lowercase=True,
        strip_accents='unicode'
    )
    X = vectorizer.fit_transform(texts)

    # Логістична регресія з оптимізованими параметрами
    clf = LogisticRegression(
        max_iter=2000,
        C=0.5,
        random_state=42,
        solver='lbfgs'
    )
    clf.fit(X, labels)

    joblib.dump((vectorizer, clf), MODEL_FILE)
    return vectorizer, clf

if os.path.exists(MODEL_FILE):
    vectorizer, clf = joblib.load(MODEL_FILE)
else:
    vectorizer, clf = train_model()

# ================== STATE ==================
current_brightness = 50
last_intent = None
user_message_ids = {}  # Відслідкування повідомлень користувачів для редагування
user_voice_times = {}  # Відслідкування часу останнього голосового повідомлення

import time
VOICE_SPAM_COOLDOWN = 1.5  # Інтервал між голосовими повідомленнями (секунди)

# ================== UTILS ==================
# Ключові слова для кожного намісту - розширена версія з дублюванням
INTENT_KEYWORDS = {
    "on": [
        "увімк", "вклю", "запал", "дай", "світло", "лампа",
        "вкл", "вмик", "запали", "включ", "вмі", "уві", "розпал",
        # Дублювання критичних слів
        "світло", "світло", "увімк", "увімк",
        # Фонетичні варіації
        "ви", "вмі", "вці"
    ],
    "off": [
        "вимк", "загас", "погас", "туш", "гас", "виклю",
        "выключ", "вик", "виклю", "вимі", "гас",
        # Дублювання
        "вимк", "вимк", "загас", "загас",
        # Фонетичні варіації
        "гасна", "тушна"
    ],
    "brighter": [
        "світліш", "яскрав", "більш", "посвітл", "додай", "усім",
        "плюс", "вверх", "вище", "больш",
        # Дублювання
        "більш", "більш", "яскрав", "яскрав",
        # Фонетичні
        "лучше"
    ],
    "dimmer": [
        "темніш", "менш", "приглуш", "зменш", "тьмян", "мінус",
        "вниз", "менше", "убав",
        # Дублювання для критичного слова
        "менш", "менш", "менш", "темніш", "темніш", "темніш",
        # Фонетичні варіації помилок Whisper
        "манча", "мени", "мен", "мель", "ме", "тем", "тме",
        "тим", "тя", "те", "та", "ти"
    ],
    "day": [
        "денн", "максимум", "день", "максимал", "повн", "яскрав",
        "сонячн", "ясно",
        # Дублювання
        "день", "день", "максимум", "максимум",
        # Фонетичні
        "яскра"
    ],
    "night": [
        "ніч", "нічник", "нічн", "мінімум", "приглуш", "слаб",
        "темн", "ночн", "ночн",
        # Дублювання
        "ніч", "ніч", "мінімум", "мінімум",
        # Фонетичні
        "наднічний"
    ]
}

def has_intent_keywords(text: str, intent: str) -> bool:
    """Перевіряємо чи текст містить ключові слова для даного намісту"""
    keywords = INTENT_KEYWORDS.get(intent, [])
    return any(keyword in text for keyword in keywords)

def phonetic_distance(s1: str, s2: str) -> float:
    """Фонетична відстань для українських слів"""
    # Замінюємо схожі звуки
    replacements = {
        'і': 'и', 'ї': 'и', 'є': 'е', 'ю': 'у',
        'й': 'й', 'ь': '', 'ґ': 'г'
    }
    
    def normalize_phonetic(word):
        result = word.lower()
        for k, v in replacements.items():
            result = result.replace(k, v)
        return result
    
    s1_norm = normalize_phonetic(s1)
    s2_norm = normalize_phonetic(s2)
    
    return fuzz.token_sort_ratio(s1_norm, s2_norm) / 100.0

def is_valid_recognition(text: str) -> bool:
    """Перевіряємо чи було розпізнавання адекватним"""
    if not text or len(text.strip()) < 2:
        return False
    
    text = text.strip()
    
    ukrainian_count = sum(1 for c in text if 'а' <= c <= 'я' or c in 'іїєґ')
    latin_count = sum(1 for c in text if 'a' <= c <= 'z')
    other_count = sum(1 for c in text if c.isdigit())
    
    total_chars = ukrainian_count + latin_count + other_count
    
    if total_chars < 2:
        return False
    
    # Максимум 50% латинських букв
    if latin_count / total_chars > 0.5:
        return False
    
    # Мінімум 40% українських букв
    if ukrainian_count / total_chars < 0.4:
        return False
    
    return True

def normalize(text: str) -> str:
    text = text.lower()
    # Нормалізація Unicode
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    # Корекція типових помилок Whisper
    text = text.replace("ії", "і").replace("йй", "й")
    text = text.replace("єє", "є").replace("її", "ї").replace("юю", "ю")
    # Видалення спецсимволів
    text = re.sub(r"[^a-zа-яіїєґ\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def detect_intent(text, voice_mode=False):
    """
    Трирівневий алгоритм детекції:
    1. ML модель (TF-IDF + LogisticRegression)
    2. Fuzzy matching (rapidfuzz)
    3. Фонетичне порівняння (для акцентів/опечаток)
    """
    # ===== РІВЕНЬ 1: ML модель =====
    X = vectorizer.transform([text])
    probs = clf.predict_proba(X)[0]
    idx = probs.argmax()
    ml_intent, ml_score = clf.classes_[idx], probs[idx]
    
    # ===== РІВЕНЬ 2: Fuzzy matching =====
    best_fuzzy_intent = None
    best_fuzzy_score = 0
    
    for intent, examples in INTENTS.items():
        for example in examples:
            similarity = fuzz.token_sort_ratio(text, example) / 100.0
            if similarity > best_fuzzy_score:
                best_fuzzy_score = similarity
                best_fuzzy_intent = intent
    
    # ===== РІВЕНЬ 3: Фонетичне порівняння =====
    best_phonetic_intent = None
    best_phonetic_score = 0
    
    for intent, examples in INTENTS.items():
        for example in examples:
            similarity = phonetic_distance(text, example)
            if similarity > best_phonetic_score:
                best_phonetic_score = similarity
                best_phonetic_intent = intent
    
    # ===== SPECIAL: Перевіра ключових слів з бустом для звичайних помилок =====
    # Якщо текст містить ключові слова dimmer - це часто спотворюється
    if any(kw in text for kw in INTENT_KEYWORDS.get("dimmer", [])):
        dimmer_boost = 0.15
        if best_fuzzy_intent == "dimmer":
            best_fuzzy_score = min(0.99, best_fuzzy_score + dimmer_boost)
        if ml_intent == "dimmer":
            ml_score = min(0.99, ml_score + dimmer_boost)
    
    # ===== СТРАТЕГІЯ ПРИЙНЯТТЯ РІШЕННЯ =====
    
    if voice_mode:
        # СТРОГИЙ режим для голосу
        
        # 1. Якщо ML дуже впевнена (>0.65) + ключові слова
        if ml_score >= 0.65 and has_intent_keywords(text, ml_intent):
            return ml_intent, ml_score
        
        # 2. Якщо всі три методи вказують на один намір - це гарантія
        if ml_intent == best_fuzzy_intent == best_phonetic_intent:
            avg_score = (ml_score + best_fuzzy_score + best_phonetic_score) / 3
            if has_intent_keywords(text, ml_intent):
                return ml_intent, min(0.95, avg_score + 0.15)
        
        # 3. ML + Fuzzy згідні + ключові слова
        if ml_intent == best_fuzzy_intent and ml_score >= 0.4 and best_fuzzy_score >= 0.75:
            if has_intent_keywords(text, ml_intent):
                return ml_intent, (ml_score + best_fuzzy_score) / 2
        
        # 4. Дуже хороший fuzzy + ключові слова
        if best_fuzzy_score >= 0.85 and has_intent_keywords(text, best_fuzzy_intent):
            return best_fuzzy_intent, best_fuzzy_score
        
        # 5. Дуже хороший phonetic + ключові слова
        if best_phonetic_score >= 0.80 and has_intent_keywords(text, best_phonetic_intent):
            return best_phonetic_intent, best_phonetic_score
        
        # 6. СПЕЦІАЛЬНА ОБРОБКА: Якщо це "dimmer" з ключовими словами - понизимо поріг
        if has_intent_keywords(text, "dimmer"):
            if best_fuzzy_score >= 0.60 or best_phonetic_score >= 0.65:
                return "dimmer", max(best_fuzzy_score, best_phonetic_score)
            if ml_score >= 0.30:
                return "dimmer", ml_score
        
        # Якщо нічого не підійшло - невідомо
        return "unknown", 0.0
    
    else:
        # НОРМАЛЬНИЙ режим для тексту
        
        # 1. Якщо ML впевнена (>0.5)
        if ml_score >= 0.5 and has_intent_keywords(text, ml_intent):
            return ml_intent, ml_score
        
        # 2. Якщо fuzzy дуже гарний (>0.75)
        if best_fuzzy_score >= 0.75 and has_intent_keywords(text, best_fuzzy_intent):
            return best_fuzzy_intent, best_fuzzy_score
        
        # 3. Якщо обидва методи згідні
        if ml_intent == best_fuzzy_intent and ml_score >= 0.3 and best_fuzzy_score >= 0.6:
            if has_intent_keywords(text, ml_intent):
                return ml_intent, (ml_score + best_fuzzy_score) / 2
        
        # 4. Хороший fuzzy
        if best_fuzzy_score >= 0.65 and has_intent_keywords(text, best_fuzzy_intent):
            return best_fuzzy_intent, best_fuzzy_score
        
        # 5. Хороший phonetic
        if best_phonetic_score >= 0.70 and has_intent_keywords(text, best_phonetic_intent):
            return best_phonetic_intent, best_phonetic_score
        
        # 6. ML з ключовими словами
        if ml_score >= 0.35 and has_intent_keywords(text, ml_intent):
            return ml_intent, ml_score
        
        return ml_intent, ml_score

def auto_learn_text(text, intent):
    """Обучаємо модель ТІЛЬКИ НА ТЕКСТОВОМУ ВВОДІ - голос занадто помилковий"""
    INTENTS[intent].append(text)
    global vectorizer, clf
    vectorizer, clf = train_model()  # Перетренуємо модель
    print(f"📚 Навчився новій команді з тексту: '{text}' -> {intent}")

# ================== ESP ==================
def send_cmd(cmd, value=None):
    """Надійно відправляємо команду з повторами"""
    params = {"cmd": cmd}
    if value is not None:
        params["value"] = value
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            requests.get(ESP32_IP, params=params, timeout=3)
            print(f"✅ Команда {cmd} відправлена успішно")
            return True
        except Exception as e:
            print(f"⚠️ Спроба {attempt+1}/{max_retries} невдала: {str(e)}")
            if attempt < max_retries - 1:
                continue
    
    print(f"❌ Не вдалося надіслати команду {cmd} після {max_retries} спроб")
    return False

def get_temp_humidity():
    """Отримуємо температуру та вологість з ESP32"""
    try:
        response = requests.get(ESP32_IP, params={"cmd": "get_temp"}, timeout=3)
        return response.text
    except Exception as e:
        print(f"❌ Помилка при отриманні температури: {str(e)}")
        return "❌ Помилка при отриманні даних"

# ================== CORE ==================
async def process_intent(intent, update):
    global current_brightness, last_intent
    last_intent = intent

    try:
        if intent == "brighter":
            current_brightness = min(100, current_brightness + 10)
            send_cmd("set_brightness", current_brightness)

        elif intent == "dimmer":
            # Зменшення: до 5% по -10%, потім по -1%
            if current_brightness > 5:
                current_brightness = max(5, current_brightness - 10)
            else:
                current_brightness = max(1, current_brightness - 1)
            send_cmd("set_brightness", current_brightness)

        elif intent == "day":
            send_cmd("day")

        elif intent == "night":
            send_cmd("night")

        elif intent == "temp":
            await update.message.reply_text(f"🌡️ {get_temp_humidity()}")
            return

        elif intent in ["on", "off"]:
            send_cmd(intent)

        await update.message.reply_text(
            f"✅ Готово. Яскравість {current_brightness}%"
        )
    except Exception as e:
        print(f"❌ Помилка при виконанні команди {intent}: {str(e)}")
        try:
            await update.message.reply_text(f"⚠️ Помилка виконання команди")
        except:
            pass

# ================== VOICE ==================
async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    current_time = time.time()
    
    # 🚫 Спам-захист: перевіряємо часовий інтервал
    if user_id in user_voice_times:
        time_diff = current_time - user_voice_times[user_id]
        if time_diff < VOICE_SPAM_COOLDOWN:
            print(f"⏱️ Спам від користувача {user_id}, пропущено ({time_diff:.1f}s)")
            return
    
    user_voice_times[user_id] = current_time
    
    try:
        # Завантажуємо голосовий файл з обробкою таймаутів
        file = await update.message.voice.get_file()
        path = "voice.ogg"
        await file.download_to_drive(path)

        # Розпізнаємо голос
        result = whisper_model.transcribe(path, language="uk")
        
        # Видаляємо файл
        try:
            os.remove(path)
        except:
            pass

        raw_text = result["text"]
        text = normalize(raw_text)
        
        # 🔍 Перевіряємо якість розпізнавання (строгіше для голосу)
        if not is_valid_recognition(text):
            print(f"⚠️ Погане розпізнавання: '{raw_text[:50]}'...")
            
            message = await update.message.reply_text(
                f"😕 Не розумів розпізнавання.\n\n"
                f"💡 Спробуйте ще раз, розмовляйте по-українськи:\n\n"
                f"✅ 'УВІМКНИ світло'\n"
                f"✅ 'ВИМКНИ світло'\n"
                f"✅ 'ЯСКРАВІШЕ'"
            )
            user_message_ids[user_id] = message.message_id
            return
        
        print(f"🎤 Розпізнано голос: '{text}'")
        
        # Передаємо voice_mode=True для більш строгої перевірки
        intent, score = detect_intent(text, voice_mode=True)
        print(f"🎯 Розпізнано намір: {intent} (впевненість: {score:.2f})")

        # 🔥 АДАПТИВНИЙ КОНТЕКСТ
        # Якщо впевненість низька, але ми в режимі brightness/dimmer - контекст допомагає
        if score < 0.50 and last_intent in ["brighter", "dimmer"]:
            # Шукаємо слова для "ще"
            if any(word in text for word in ["ще", "трошки", "більше", "менше", "трошечко", "ще раз"]):
                intent = last_intent
                score = 0.70  # Підвищуємо впевненість через контекст
                print(f"🔄 Контекстна корекція: {intent} (контекст вказав на продовження)")

        # АДАПТИВНИЙ ПОРІГ ЗАЛЕЖНО ВІД НАМІСТУ
        intent_thresholds = {
            "on": 0.50,      # Критично - не хочемо включати помилково
            "off": 0.50,     # Критично - не хочемо вимикати помилково
            "brighter": 0.35,  # Менш критично - безпечніше
            "dimmer": 0.35,    # Менш критично - безпечніше, часто спотворюється
            "day": 0.48,       # Критично
            "night": 0.48,     # Критично
        }
        
        threshold = intent_thresholds.get(intent, 0.50)
        
        if score >= threshold and intent != "unknown":
            await process_intent(intent, update)
        else:
            text_msg = (
                f"🤔 Не впевнений: '{text}' ({score:.0%})\n\n"
                f"💡 Спробуйте ще раз:\n"
                f"✅ 'УВІМКНИ світло'\n"
                f"✅ 'ВИМКНИ світло'\n"
                f"✅ 'ЯСКРАВІШЕ' або 'ТЕМНІШЕ'\n"
                f"✅ 'ДЕНЬ' або 'НІЧ'"
            )
            
            # Редагуємо попереднє повідомлення якщо існує
            if user_id in user_message_ids:
                try:
                    await context.bot.edit_message_text(
                        text=text_msg,
                        chat_id=user_id,
                        message_id=user_message_ids[user_id]
                    )
                except:
                    message = await update.message.reply_text(text_msg)
                    user_message_ids[user_id] = message.message_id
            else:
                message = await update.message.reply_text(text_msg)
                user_message_ids[user_id] = message.message_id
    
    except Exception as e:
        print(f"❌ Помилка при обробці голосу: {str(e)}")
        try:
            await update.message.reply_text(
                "❌ Помилка при обробці голосу. Спробуйте ще раз."
            )
        except:
            print(f"⚠️ Не вдалося відправити повідомлення про помилку")

# ================== TEXT ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    
    try:
        text = normalize(update.message.text)
        print(f"📝 Отримано текст: '{text}'")
        
        # Для тексту voice_mode=False (м'якші вимоги)
        intent, score = detect_intent(text, voice_mode=False)
        print(f"🎯 Розпізнано: {intent} (впевненість: {score:.2f})")

        # Поріг для текстового введення - 0.40 (має ключові слова)
        if score >= 0.40 and intent != "unknown":
            auto_learn_text(text, intent)
            await process_intent(intent, update)
        else:
            text_msg = (
                f"🤔 Не впевнений у команді '{text}'\n"
                f"Вгадання: {intent} ({score:.0%})\n\n"
                f"💡 Приклади команд:\n"
                f"✅ світло, увімкни, включи\n"
                f"✅ вимкни, загаси, погаси\n"
                f"✅ яскравіше, більше світла\n"
                f"✅ темніше, менше світла\n"
                f"✅ день, ніч"
            )
            
            # Редагуємо попереднє повідомлення якщо існує
            if user_id in user_message_ids:
                try:
                    await context.bot.edit_message_text(
                        text=text_msg,
                        chat_id=user_id,
                        message_id=user_message_ids[user_id]
                    )
                except:
                    message = await update.message.reply_text(text_msg)
                    user_message_ids[user_id] = message.message_id
            else:
                message = await update.message.reply_text(text_msg)
                user_message_ids[user_id] = message.message_id
    except Exception as e:
        print(f"❌ Помилка при обробці тексту: {str(e)}")
        try:
            await update.message.reply_text(
                "❌ Помилка при обробці команди. Спробуйте ще раз."
            )
        except:
            print(f"⚠️ Не вдалося відправити повідомлення про помилку")

# ================== UI ==================
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("💡 Вкл", callback_data="on"),
         InlineKeyboardButton("❌ Викл", callback_data="off")],
        [InlineKeyboardButton("🔆 +", callback_data="brighter"),
         InlineKeyboardButton("🔅 -", callback_data="dimmer")],
        [InlineKeyboardButton("☀️ День", callback_data="day"),
         InlineKeyboardButton("🌙 Ніч", callback_data="night")],
        [InlineKeyboardButton("🌡️ Температура", callback_data="temp")]
    ]
    await update.message.reply_text("🏠 Український Smart Home", reply_markup=InlineKeyboardMarkup(kb))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        q = update.callback_query
        await q.answer()
        await process_intent(q.data, q)
    except Exception as e:
        print(f"❌ Помилка при обробці кнопки: {str(e)}")

# ================== MAIN ==================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 Український Alexa запущений")
    app.run_polling()
