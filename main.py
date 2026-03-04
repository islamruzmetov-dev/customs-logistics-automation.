import os
import time
import threading
import telebot
from telebot import types
from PIL import Image
import pytesseract
from fpdf import FPDF
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

# === Enterprise Configuration & Setup ===
load_dotenv()
# Secure placeholders. Real credentials must be injected via .env file.
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
GROUP_CHAT_ID = int(os.getenv('LOGISTICS_HUB_ID', '-1000000000000'))
MAX_FILES = 26
UPLOAD_TIMEOUT = 60  # seconds

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# Tesseract OCR cross-platform path mapping
# Defaults to system PATH if TESSERACT_PATH is not specified in .env
TESSERACT_PATH = os.getenv('TESSERACT_PATH')
if TESSERACT_PATH:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# === Global State & Session Management ===
user_language = {}
user_state = {}
user_contact_info = {}
user_files = defaultdict(list)
user_timers = {}
user_last_upload = {}
user_history = defaultdict(list)
user_processing = set()

# === Localization Engine ===
LANG = {
    'ru': {
        'welcome': """👋 Добро пожаловать в <b>Bojxona Hamkor</b>!\nСервис онлайн-оформления транзитных и таможенных деклараций.\n\n🌐 Сайт: https://caravan-broker.uz/bojxona-hamkor\n📥 <a href='https://play.google.com/store/apps/details?id=com.eskishahar.app.bojxonahamkor'>Скачать приложение</a>\n\n🔻 Выберите действие:""",
        'menu': ["/send 📄 Отправить документ", "/info 📘 Инструкция", "/help 📞 Связаться с нами", "/clear 🗑 Очистить очередь"],
        'send_doc': "📤 Пожалуйста, отправьте фото или документ.",
        'instruction': "📘 Перечень необходимых документов: паспорт, техпаспорт, CMR, инвойс и др.",
        'contact': "📞 Контакт: +998917020099, +998975556803",
        'thanks': "✅ Спасибо! Теперь отправьте документы.",
        'ask_phone': "📱 Укажите свой номер телефона или отправьте контакт кнопкой ниже:",
        'ask_email': "📧 Введите свой email (например, example@mail.com):",
        'wait': "⏳ Ждём ещё документы...",
        'pdf_ready': "✅ Ваши документы отправлены операторам!",
        'cleared': "🗑 Все ваши загруженные документы очищены!",
        'from_post_q': "🛃 С какого поста вы въезжаете в Узбекистан? (например, Яллама, Даут-ата, Дустлик)",
        'to_post_q': "🛃 На какой пост вы едете дальше? (например, выездной — Чиназ, Олот, или внутренний пост для растаможки — Ташкент, Янгиёр и т.д.)"
    },
    'uz_latin': {
        'welcome': """🇺🇿 <b>Bojxona Hamkor</b> xizmatiga xush kelibsiz!\n\n🌐 Sayt: https://caravan-broker.uz/bojxona-hamkor\n📥 <a href='https://play.google.com/store/apps/details?id=com.eskishahar.app.bojxonahamkor'>Ilovani yuklab olish</a>\n\n🔻 Harakatni tanlang:""",
        'menu': ["/send 📄 Hujjat yuborish", "/info 📘 Yo‘riqnoma", "/help 📞 Bog‘lanish", "/clear 🗑 Tozalash"],
        'send_doc': "📤 Iltimos, hujjatni yuboring.",
        'instruction': "📘 Kerakli hujjatlar ro‘yxati: pasport, tex. pasport, CMR, invoice va boshqalar.",
        'contact': "📞 Bog‘lanish: +998917020099, +998975556803",
        'thanks': "✅ Rahmat! Endi hujjatlaringizni yuboring.",
        'ask_phone': "📱 Telefon raqamingizni kiriting yoki pastdagi tugma orqali yuboring:",
        'ask_email': "📧 Email manzilingizni kiriting (masalan, example@mail.com):",
        'wait': "⏳ Yana hujjatlar kutilyapti...",
        'pdf_ready': "✅ Hujjatlaringiz operatorlarga yuborildi!",
        'cleared': "🗑 Barcha yuklangan fayllaringiz tozalandi!",
        'from_post_q': "🛃 Qaysi postdan O‘zbekistonga kiryapsiz? (masalan, Yallama, Daut-ota, Do‘stlik)",
        'to_post_q': "🛃 Keyingi boradigan post qaysi? (masalan, chiqish posti — Chinaz, Olot yoki ichki bojxona posti — Toshkent, Yangiyer va h.k.)"
    },
    'uz_cyril': {
        'welcome': """🇺🇿 <b>Bojxona Hamkor</b> хизматига хуш келибсиз!\n\n🌐 Сайт: https://caravan-broker.uz/bojxona-hamkor\n📥 <a href='https://play.google.com/store/apps/details?id=com.eskishahar.app.bojxonahamkor'>Иловани юклаб олиш</a>\n\n🔻 Ҳаракатни танланг:""",
        'menu': ["/send 📄 Ҳужжат юбориш", "/info 📘 Йўриқнома", "/help 📞 Богланиш", "/clear 🗑 Тозалаш"],
        'send_doc': "📤 Илтимос, ҳужжат юборинг.",
        'instruction': "📘 Керакли ҳужжатлар: паспорт, техник паспорт, CMR, инвойс ва бошқалар.",
        'contact': "📞 Богланиш: +998917020099, +998975556803",
        'thanks': "✅ Раҳмат! Энди ҳужжатларни юборинг.",
        'ask_phone': "📱 Телефон рақамингизни киритинг ёки пастдаги тугмани босинг:",
        'ask_email': "📧 Email манзилингизни киритинг (масалан, example@mail.com):",
        'wait': "⏳ Яна ҳужжатлар кутиляпти...",
        'pdf_ready': "✅ Ҳужжатларингиз операторларга юборилди!",
        'cleared': "🗑 Барча юкланган файлларингиз тозаланди!",
        'from_post_q': "🛃 Қайси постдан Ўзбекистонга кираяпсиз? (масалан, Яллама, Даут-ота, Дўстлик)",
        'to_post_q': "🛃 Кейинги борадиган пост қайси? (масалан, чиқиш пости — Чиназ, Олот ёки ички божхона пости — Тошкент, Янгиёр ва ҳ.к.)"
    },
    'en': {
        'welcome': """🇬🇧 <b>Welcome to Bojxona Hamkor</b>!\nSubmit your customs documents online easily.\n\n🌐 Website: https://caravan-broker.uz/bojxona-hamkor\n📥 <a href='https://play.google.com/store/apps/details?id=com.eskishahar.app.bojxonahamkor'>Download app</a>\n\n🔻 Choose an action:""",
        'menu': ["/send 📄 Send document", "/info 📘 Instructions", "/help 📞 Contact", "/clear 🗑 Clear queue"],
        'send_doc': "📤 Please send your document.",
        'instruction': "📘 Required documents: passport, tech passport, CMR, invoice, etc.",
        'contact': "📞 Contact: +998917020099, +998975556803",
        'thanks': "✅ Thank you! Now you can upload your documents.",
        'ask_phone': "📱 Enter your phone number or send contact by button:",
        'ask_email': "📧 Enter your email (e.g., example@mail.com):",
        'wait': "⏳ Waiting for more documents...",
        'pdf_ready': "✅ Your documents have been sent to the operators!",
        'cleared': "🗑 All your uploaded files have been cleared!",
        'from_post_q': "🛃 Which post are you ENTERING Uzbekistan through? (e.g., Yallama, Daut-ata, Dustlik)",
        'to_post_q': "🛃 Which post are you going to next? (e.g., exit post — Chinaz, Olot, or internal customs post — Tashkent, Yangiyer, etc.)"
    }
}

# --- Utility Functions ---
def get_lang(user_id):
    return user_language.get(user_id, 'ru')

def main_menu(user_id):
    code = get_lang(user_id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in LANG[code]['menu']:
        markup.add(row)
    return markup

# === Registration & Onboarding Flow ===
@bot.message_handler(commands=['start'])
def start_handler(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(
        types.KeyboardButton("🇷🇺 Русский"),
        types.KeyboardButton("🇺🇿 Oʻzbek"),
        types.KeyboardButton("🇺🇿 Ўзбекча"),
        types.KeyboardButton("🇬🇧 English")
    )
    bot.send_message(message.chat.id, "🌍 Choose your language / Tilni tanlang / Языкни танланг:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["🇷🇺 Русский", "🇺🇿 Oʻzbek", "🇺🇿 Ўзбекча", "🇬🇧 English"])
def set_language(m):
    code = {
        "🇷🇺 Русский": 'ru',
        "🇺🇿 Oʻzbek": 'uz_latin',
        "🇺🇿 Ўзбекча": 'uz_cyril',
        "🇬🇧 English": 'en'
    }[m.text]
    user_language[m.from_user.id] = code
    user_state[m.from_user.id] = 'phone'
    
    # Contact request button
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton(LANG[code]['ask_phone'], request_contact=True))
    bot.send_message(m.chat.id, LANG[code]['ask_phone'], reply_markup=markup)

@bot.message_handler(content_types=['contact'])
def handle_contact(msg):
    phone = msg.contact.phone_number
    user_contact_info[msg.from_user.id] = {'phone': phone}
    user_state[msg.from_user.id] = 'email'
    code = get_lang(msg.from_user.id)
    markup = types.ReplyKeyboardRemove()
    bot.send_message(msg.chat.id, LANG[code]['ask_email'], reply_markup=markup)

@bot.message_handler(func=lambda msg: user_state.get(msg.from_user.id) == 'phone')
def get_phone(msg):
    user_contact_info[msg.from_user.id] = {'phone': msg.text}
    user_state[msg.from_user.id] = 'email'
    code = get_lang(msg.from_user.id)
    markup = types.ReplyKeyboardRemove()
    bot.send_message(msg.chat.id, LANG[code]['ask_email'], reply_markup=markup)

@bot.message_handler(func=lambda msg: user_state.get(msg.from_user.id) == 'email')
def get_email(msg):
    user_contact_info[msg.from_user.id]['email'] = msg.text
    user_state[msg.from_user.id] = 'from_post'
    code = get_lang(msg.from_user.id)
    bot.send_message(msg.chat.id, LANG[code]['from_post_q'], reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda msg: user_state.get(msg.from_user.id) == 'from_post')
def get_from_post(msg):
    user_contact_info[msg.from_user.id]['from_post'] = msg.text
    user_state[msg.from_user.id] = 'to_post'
    code = get_lang(msg.from_user.id)
    bot.send_message(msg.chat.id, LANG[code]['to_post_q'])

@bot.message_handler(func=lambda msg: user_state.get(msg.from_user.id) == 'to_post')
def get_to_post(msg):
    user_contact_info[msg.from_user.id]['to_post'] = msg.text
    user_state[msg.from_user.id] = 'menu'
    code = get_lang(msg.from_user.id)
    bot.send_message(msg.chat.id, LANG[code]['thanks'], reply_markup=main_menu(msg.from_user.id))

# === Main Menu Commands ===
@bot.message_handler(commands=['send'])
def send_cmd(m):
    code = get_lang(m.from_user.id)
    bot.send_message(m.chat.id, LANG[code]['send_doc'])

@bot.message_handler(commands=['info'])
def info_cmd(m):
    code = get_lang(m.from_user.id)
    bot.send_message(m.chat.id, LANG[code]['instruction'])

@bot.message_handler(commands=['help'])
def help_cmd(m):
    code = get_lang(m.from_user.id)
    bot.send_message(m.chat.id, LANG[code]['contact'])

@bot.message_handler(commands=['clear'])
def clear_files(m):
    user_files[m.from_user.id].clear()
    user_history[m.from_user.id].clear()
    code = get_lang(m.from_user.id)
    bot.send_message(m.chat.id, LANG[code]['cleared'], reply_markup=main_menu(m.from_user.id))

# === File Processing & OCR Engine ===
def ocr_text(image_path):
    try:
        print(f'[DEBUG] OCR executing for: {image_path}')
        img = Image.open(image_path).convert('L')
        text = pytesseract.image_to_string(img, lang='rus+eng+uzb')
        return text.strip()
    except Exception as e:
        print(f'[ERROR] OCR processing failed: {e}')
        return f"OCR error: {str(e)}"

def send_pdf(user_id):
    print(f'[DEBUG] Synthesizing PDF for user {user_id}')
    user_processing.add(user_id)

    files = user_files.get(user_id, [])
    if not files:
        print(f'[DEBUG] No active files found for user {user_id}')
        user_processing.discard(user_id)
        return
        
    pdf = FPDF()
    ocr_results = []
    temp_files = []
    
    for idx, img_file in enumerate(files):
        try:
            ext = os.path.splitext(img_file)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png']:
                temp_path = img_file
            else:
                temp_path = f'temp_{user_id}_{idx}.jpg'
                Image.open(img_file).convert('RGB').save(temp_path)
                temp_files.append(temp_path)
                
            pdf.add_page()
            pdf.image(temp_path, x=10, y=10, w=190)
            ocr_results.append(ocr_text(temp_path))
        except Exception as e:
            print(f'[ERROR] PDF synthesis error (page {idx+1}): {e}')
            
    pdf_file = f'{user_id}_combined.pdf'
    pdf.output(pdf_file)
    contact_info = user_contact_info.get(user_id, {})

    # Constructing operational dossier
    caption = (
        f"📥 Client Dossier\n"
        f"ID: {user_id}\n"
        f"Phone: {contact_info.get('phone', '—')}\n"
        f"Email: {contact_info.get('email', '—')}\n"
        f"Entry Post: {contact_info.get('from_post', '—')}\n"
        f"Destination Post: {contact_info.get('to_post', '—')}"
    )
    
    ocr_caption = ""
    if ocr_results:
        ocr_short = [text[:200] + ('...' if len(text) > 200 else '') for text in ocr_results[:2]]
        ocr_caption = "\n\nOCR Extraction:\n" + "\n---\n".join(ocr_short)
    caption += ocr_caption
    
    if len(caption) > 1000:
        caption = caption[:990] + '...'

    try:
        with open(pdf_file, 'rb') as f:
            bot.send_document(GROUP_CHAT_ID, f, caption=caption)
        print(f'[DEBUG] PDF {pdf_file} successfully dispatched to operational hub {GROUP_CHAT_ID}')
    except Exception as e:
        print(f'[ERROR] Dispatch failure: {e}')
        
    # File cleanup routines
    for temp_file in temp_files:
        try:
            os.remove(temp_file)
        except Exception as e:
            print(f'[ERROR] Temp file deletion failed {temp_file}: {e}')
    try:
        os.remove(pdf_file)
    except Exception as e:
        print(f'[ERROR] PDF deletion failed: {e}')
        
    user_files[user_id].clear()
    if user_id in user_timers:
        user_timers[user_id].cancel()
        del user_timers[user_id]
        
    code = get_lang(user_id)
    bot.send_message(user_id, LANG[code]['pdf_ready'], reply_markup=main_menu(user_id))
    user_processing.discard(user_id)

# === Auto-dispatch Timer ===
def schedule_pdf(user_id):
    if user_id in user_timers:
        user_timers[user_id].cancel()
    timer = threading.Timer(UPLOAD_TIMEOUT, lambda: send_pdf(user_id))
    user_timers[user_id] = timer
    timer.start()
    user_last_upload[user_id] = datetime.now()
    print(f'[DEBUG] Active timer initialized for user {user_id}')

@bot.message_handler(content_types=['photo', 'document'])
def handle_docs(message):
    user_id = message.from_user.id
    
    # Block uploads if user is not fully registered
    if user_state.get(user_id) != 'menu':
        code = get_lang(user_id)
        bot.send_message(user_id, LANG[code]['ask_phone'])
        return
        
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    try:
        print(f'[DEBUG] Incoming document payload from user {user_id}')
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        filename = file_info.file_path.split('/')[-1]
        
        with open(filename, 'wb') as f:
            f.write(downloaded_file)
            
        user_files[user_id].append(filename)
        user_history[user_id].append(filename)
        
        if len(user_files[user_id]) >= MAX_FILES:
            print(f'[DEBUG] Max file limit reached, triggering synthesis')
            send_pdf(user_id)
        else:
            schedule_pdf(user_id)
            code = get_lang(user_id)
            bot.send_message(user_id, f"✅ {len(user_files[user_id])}/{MAX_FILES} {LANG[code]['wait']}", reply_markup=main_menu(user_id))
    except Exception as e:
        print(f'[ERROR] handle_docs exception: {e}')
        bot.reply_to(message, f"❌ Validation error: {str(e)}")

# === Operator Reply Mechanism ===
@bot.message_handler(commands=['reply'], func=lambda m: m.chat.id == GROUP_CHAT_ID)
def reply_to_client(message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "❗ Syntax: /reply user_id message_text")
        return
    try:
        user_id = int(parts[1])
        bot.send_message(user_id, f"💬 Operational Hub: {parts[2]}")
        bot.reply_to(message, "✅ Reply successfully relayed to client.")
    except Exception as e:
        print(f'[ERROR] Group-to-client routing failed: {e}')
        bot.reply_to(message, f"❌ Routing error: {str(e)}")

# === Garbage Collection & Auto-cleanup ===
def auto_cleanup():
    print('[DEBUG] Background garbage collection initialized')
    while True:
        now = datetime.now()
        for user_id in list(user_files.keys()):
            if user_id in user_processing:
                continue
            last_time = user_last_upload.get(user_id)
            if last_time and (now - last_time).total_seconds() > UPLOAD_TIMEOUT:
                print(f'[DEBUG] Purging stale session files for user {user_id}')
                user_files[user_id].clear()
                if user_id in user_timers:
                    user_timers[user_id].cancel()
                    del user_timers[user_id]
        time.sleep(10)

threading.Thread(target=auto_cleanup, daemon=True).start()

# === General Fallback Handler ===
@bot.message_handler(func=lambda m: True)
def fallback_handler(m):
    bot.send_message(
        m.chat.id,
        "💬 Message received. For operational support, please use /help."
    )

# === System Entry Point ===
if __name__ == '__main__':
    print('[SYSTEM] Customs Logistics Automation Engine is fully operational.')
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f'[CRITICAL ERROR] Polling mechanism failed: {e}')
        time.sleep(10)
