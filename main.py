import os
import asyncio
import logging
import sqlite3
import re
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, 
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)

API_TOKEN = "9105764364:AAFiRKBccsL8oTPr_MUjHoHO0gZjpuhAE30"
CHANNEL_ID = "@DOST_kanal_official"
CHANNEL_LINK = "https://t.me/DOST_kanal_official"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- БАЗА ДАННЫХ (SQLite) ---
def init_db():
    conn = sqlite3.connect("job_base.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT,
            name TEXT,
            phone TEXT,
            role TEXT,
            city TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            salary TEXT,
            city TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_user(user_id, language, name, phone, role, city):
    conn = sqlite3.connect("job_base.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, language, name, phone, role, city)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, language, name, phone, role, city))
    conn.commit()
    conn.close()

# --- СОСТОЯНИЯ (FSM) ---
class RegisterGroup(StatesGroup):
    language = State()
    role = State()
    name = State()
    phone = State()
    city = State()

class CreateJobGroup(StatesGroup):
    title = State()
    description = State()
    salary = State()
    city = State()
    confirm_payment = State()

# --- ТЕКСТЫ НА 3 ЯЗЫКАХ С ОПЛАТОЙ НА КАРТУ ---
TEXTS = {
    'ru': {
        'choose_role': "👋 **Добро пожаловать в DOST!**\n\nЧто вы хотите сделать?",
        'btn_worker': "🔍 Ищу работу",
        'btn_employer': "📋 Ищу работника",
        'ask_name': "Напишите ваше имя:",
        'ask_phone': "Отправьте ваш номер телефона или напишите его текстом:",
        'btn_phone': "📱 Отправить номер",
        'ask_city': "Из какого вы города? Напишите название:",
        'role_worker': "Ищу работу",
        'role_employer': "Ищу работника",
        'success': "🎉 **Вы успешно зарегистрированы!**",
        'main_menu': "Главное меню:",
        'btn_create_job': "➕ Подать объявление",
        'btn_view_channel': "📢 Смотреть работу в канале",
        'ask_job_title': "Кого вы ищете? (Например: Автомойщик):",
        'ask_job_desc': "Напишите, что нужно делать:",
        'ask_job_salary': "Сколько вы заплатите? (Например: 200000):",
        'btn_send_check': "📩 Отправить чек менеджеру",
        'pay_info': (
            "💳 **Инструкция по оплате:**\n\n"
            "Переведите **{amount} сум** (20%) на карту:\n"
            "💳 `5614683400216925`\n"
            "👤 **Abdumomin abdurahmanov**\n\n"
            "После оплаты отправьте чек нашему менеджеру 👉 @abddumomin для публикации объявлений в канале!"
        )
    },
    'uz': {
        'choose_role': "👋 **DOST ga xush kelibsiz!**\n\nSizga nima kerak?",
        'btn_worker': "🔍 Ish qidiryapman",
        'btn_employer': "📋 Ishchi kerak",
        'ask_name': "Ismingizni yozing:",
        'ask_phone': "Telefon raqamingizni yuboring yoki yozing:",
        'btn_phone': "📱 Raqamni yuborish",
        'ask_city': "Qaysi shahardansiz? Shahar nomini yozing:",
        'role_worker': "Ish qidiryapman",
        'role_employer': "Ishchi kerak",
        'success': "🎉 **Ro'yxatdan o'tdingiz!**",
        'main_menu': "Asosiy menyu:",
        'btn_create_job': "➕ E'lon berish",
        'btn_view_channel': "📢 Kanaldagi ishlarni ko'rish",
        'ask_job_title': "Kim kerak? (Masalan: Avtomoychi):",
        'ask_job_desc': "Nima ish qilish kerakligini yozing:",
        'ask_job_salary': "Qancha haq berasiz? (Masalan: 200000):",
        'btn_send_check': "📩 Chekni menejerga yuborish",
        'pay_info': (
            "💳 **To'lov bo'yicha ko'rsatma:**\n\n"
            "Ushbu kartaga **{amount} so'm** (20%) o'tkazing:\n"
            "💳 `5614683400216925`\n"
            "👤 **Abdumomin abdurahmanov**\n\n"
            "To'lov qilgach, e'loningiz kanalda chiqishi uchun chekni menejerimizga yuboring 👉 @abddumomin"
        )
    },
    'en': {
        'choose_role': "👋 **Welcome to DOST!**\n\nWhat do you want to do?",
        'btn_worker': "🔍 Looking for work",
        'btn_employer': "📋 Looking for a worker",
        'ask_name': "Type your name:",
        'ask_phone': "Share your phone number or type it:",
        'btn_phone': "📱 Share phone number",
        'ask_city': "Which city are you from? Type the city name:",
        'role_worker': "Looking for work",
        'role_employer': "Looking for a worker",
        'success': "🎉 **Registration successful!**",
        'main_menu': "Main Menu:",
        'btn_create_job': "➕ Post a job",
        'btn_view_channel': "📢 Open jobs channel",
        'ask_job_title': "Who do you need? (e.g. Car washer):",
        'ask_job_desc': "Describe the work to be done:",
        'ask_job_salary': "How much will you pay? (e.g. 200000):",
        'btn_send_check': "📩 Send receipt to manager",
        'pay_info': (
            "💳 **Payment Instructions:**\n\n"
            "Transfer **{amount} UZS** (20%) to card:\n"
            "💳 `5614683400216925`\n"
            "👤 **Abdumomin abdurahmanov**\n\n"
            "After payment, send the receipt to our manager 👉 @abddumomin to publish your job!"
        )
    }
}

def get_user_lang(user_id):
    conn = sqlite3.connect("job_base.db")
    cursor = conn.cursor()
    cursor.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 'ru'

# --- 1. РЕГИСТРАЦИЯ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
            [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz")],
            [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
        ]
    )
    await message.answer("👋 **DOST | Выберите язык / Tilni tanlang / Choose language:**", reply_markup=keyboard, parse_mode="Markdown")
    await state.set_state(RegisterGroup.language)

@dp.callback_query(RegisterGroup.language, F.data.startswith("lang_"))
async def process_language(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await state.update_data(language=lang)
    t = TEXTS[lang]
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t['btn_worker'], callback_data="role_worker")],
            [InlineKeyboardButton(text=t['btn_employer'], callback_data="role_employer")]
        ]
    )
    await callback.message.answer(t['choose_role'], reply_markup=keyboard, parse_mode="Markdown")
    await state.set_state(RegisterGroup.role)
    await callback.answer()

@dp.callback_query(RegisterGroup.role, F.data.startswith("role_"))
async def process_role(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    t = TEXTS[data['language']]
    role = t['role_worker'] if callback.data == "role_worker" else t['role_employer']
    await state.update_data(role=role)
    await callback.message.answer(t['ask_name'])
    await state.set_state(RegisterGroup.name)
    await callback.answer()

@dp.message(RegisterGroup.name)
async def process_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    t = TEXTS[data['language']]
    await state.update_data(name=message.text)
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t['btn_phone'], request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await message.answer(t['ask_phone'], reply_markup=kb)
    await state.set_state(RegisterGroup.phone)

@dp.message(RegisterGroup.phone)
async def process_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    t = TEXTS[data['language']]
    
    phone_number = message.contact.phone_number if message.contact else message.text
    await state.update_data(phone=phone_number)
    
    await message.answer(t['ask_city'], reply_markup=ReplyKeyboardRemove())
    await state.set_state(RegisterGroup.city)

@dp.message(RegisterGroup.city)
async def process_city(message: types.Message, state: FSMContext):
    city = message.text
    user_data = await state.get_data()
    lang = user_data['language']
    t = TEXTS[lang]
    
    save_user(message.from_user.id, lang, user_data['name'], user_data['phone'], user_data['role'], city)
    await state.clear()

    menu_buttons = []
    if user_data['role'] in ["Ищу работника", "Ishchi kerak", "Looking for a worker"]:
        menu_buttons.append([KeyboardButton(text=t['btn_create_job'])])
    
    menu_buttons.append([KeyboardButton(text=t['btn_view_channel'])])

    menu_kb = ReplyKeyboardMarkup(keyboard=menu_buttons, resize_keyboard=True)
    
    channel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Открыть канал DOST", url=CHANNEL_LINK)]
        ]
    )
    
    await message.answer(f"{t['success']}\n\n{t['main_menu']}", reply_markup=menu_kb, parse_mode="Markdown")
    await message.answer("👇 Нажмите на кнопку ниже, чтобы перейти в официальный канал DOST:", reply_markup=channel_kb)

@dp.message(F.text.in_(["📢 Смотреть работу в канале", "📢 Kanaldagi ishlarni ko'rish", "📢 Open jobs channel"]))
async def open_channel(message: types.Message):
    channel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👉 Открыть канал DOST", url=CHANNEL_LINK)]
        ]
    )
    await message.answer("Официальный канал **DOST**:", reply_markup=channel_kb, parse_mode="Markdown")

# --- 2. СОЗДАНИЕ ОБЪЯВЛЕНИЯ И ОПЛАТА НА КАРТУ ---
@dp.message(F.text.in_(["➕ Подать объявление", "➕ E'lon berish", "➕ Post a job"]))
async def start_job_creation(message: types.Message, state: FSMContext):
    lang = get_user_lang(message.from_user.id)
    t = TEXTS[lang]
    await message.answer(t['ask_job_title'])
    await state.set_state(CreateJobGroup.title)

@dp.message(CreateJobGroup.title)
async def process_job_title(message: types.Message, state: FSMContext):
    lang = get_user_lang(message.from_user.id)
    t = TEXTS[lang]
    await state.update_data(title=message.text)
    await message.answer(t['ask_job_desc'])
    await state.set_state(CreateJobGroup.description)

@dp.message(CreateJobGroup.description)
async def process_job_desc(message: types.Message, state: FSMContext):
    lang = get_user_lang(message.from_user.id)
    t = TEXTS[lang]
    await state.update_data(description=message.text)
    await message.answer(t['ask_job_salary'])
    await state.set_state(CreateJobGroup.salary)

@dp.message(CreateJobGroup.salary)
async def process_job_salary(message: types.Message, state: FSMContext):
    lang = get_user_lang(message.from_user.id)
    t = TEXTS[lang]
    
    salary_text = message.text
    await state.update_data(salary=salary_text)
    
    numbers = re.findall(r'\d+', salary_text)
    if numbers:
        salary_value = int(''.join(numbers))
        commission = int(salary_value * 0.20)
    else:
        commission = 0

    await state.update_data(commission=commission)
    job_data = await state.get_data()
    
    formatted_commission = f"{commission:,}".replace(',', ' ')
    
    pay_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t['btn_send_check'], url="https://t.me/abddumomin")]
        ]
    )
    pay_text = t['pay_info'].format(amount=formatted_commission)
    
    preview_text = (
        f"📋 **DOST | Ваше объявление:**\n\n"
        f"📌 **Работа:** {job_data['title']}\n"
        f"📝 **Описание:** {job_data['description']}\n"
        f"💰 **Оплата работнику:** {job_data['salary']}\n\n"
        f"──────────────────\n"
        f"{pay_text}"
    )
    
    await message.answer(preview_text, reply_markup=pay_kb, parse_mode="Markdown")
    await state.clear()


# === 1. ВЕБ-СЕРВЕР ДЛЯ UPTIMEROBOT ===
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_background_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# === 2. ЕДИНАЯ ТОЧКА ЗАПУСКА БОТА ===
async def main():
    init_db()
    
    # Фоном запускаем веб-сервер
    asyncio.create_task(start_background_web_server())
    
    print("🚀 [DOST v5.0] Бот успешно запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
