import asyncio
import os
import requests
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties # Добавили новый импорт

import database as db
from replicate_api import generate_vton_image

# Инициализация бота с учетом новых правил aiogram 3.7+
bot = Bot(
    token=os.getenv("BOT_TOKEN"), 
    default=DefaultBotProperties(parse_mode="HTML") # Теперь это пишется так
)
dp = Dispatcher()

class VTONState(StatesGroup):
    wait_human = State()
    wait_category = State()
    wait_garment = State()
    wait_broadcast = State()

# --- КЛАВИАТУРЫ ---

def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.button(text="👗 Примерить одежду")
    builder.button(text="💰 Пополнить баланс")
    builder.button(text="👤 Мой профиль")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_category_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="👕 Верх", callback_data="set_upper")
    builder.button(text="👖 Низ", callback_data="set_lower")
    builder.button(text="👗 Платье", callback_data="set_dresses")
    builder.adjust(3)
    return builder.as_markup()

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message(Command("start"))
async def start(message: types.Message):
    await db.get_user(message.from_user.id)
    await message.answer(
        f"<b>Добро пожаловать в Virtual Stylist AI!</b> 👗✨\n\n"
        f"Я помогу тебе примерить любую одежду по фото.\n"
        f"Используй меню ниже, чтобы начать.",
        reply_markup=get_main_menu()
    )

@dp.message(F.text == "👤 Мой профиль")
async def profile(message: types.Message):
    user = await db.get_user(message.from_user.id)
    status = "Администратор 👑" if user['is_admin'] else "Пользователь"
    await message.answer(
        f"<b>Твой профиль:</b>\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"🔋 Баланс: <b>{user['balance']}</b> примерок\n"
        f"⭐ Статус: {status}"
    )

@dp.message(F.text == "💰 Пополнить баланс")
@dp.message(Command("buy"))
async def buy(message: types.Message):
    await message.answer_invoice(
        title="5 AI-примерок",
        description="Пополнение баланса для виртуальной примерочной",
        payload="5_pack",
        provider_token=os.getenv("PAYMENT_TOKEN"),
        currency="RUB",
        prices=[types.LabeledPrice(label="5 примерок", amount=25000)]
    )

# --- АДМИН-ПАНЕЛЬ ---

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user['is_admin']:
        return

    conn = await db.asyncpg.connect(db.DATABASE_URL)
    count = await conn.fetchval("SELECT COUNT(*) FROM users")
    await conn.close()

    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Сделать рассылку", callback_data="admin_broadcast")
    await message.answer(
        f"<b>Панель администратора</b> ⚙️\n\n"
        f"Всего пользователей: <b>{count}</b>",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите текст рассылки. Его получат ВСЕ пользователи бота.")
    await state.set_state(VTONState.wait_broadcast)
    await callback.answer()

@dp.message(VTONState.wait_broadcast)
async def perform_broadcast(message: types.Message, state: FSMContext):
    conn = await db.asyncpg.connect(db.DATABASE_URL)
    users = await conn.fetch("SELECT user_id FROM users")
    await conn.close()

    count = 0
    for u in users:
        try:
            await bot.send_message(u['user_id'], message.text)
            count += 1
            await asyncio.sleep(0.05)
        except:
            continue
    
    await message.answer(f"✅ Рассылка завершена! Сообщение получили {count} человек.")
    await state.clear()

# --- ЛОГИКА ГЕНЕРАЦИИ ---

@dp.message(F.text == "👗 Примерить одежду")
async def start_vton(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("<b>Шаг 1:</b> Пришли фото человека (в полный рост или по пояс).")
    await state.set_state(VTONState.wait_human)

@dp.message(VTONState.wait_human, F.photo)
async def human_step(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{os.getenv('BOT_TOKEN')}/{file.file_path}"
    
    await state.update_data(human=url)
    await message.answer("<b>Шаг 2:</b> Выбери категорию одежды:", reply_markup=get_category_kb())

@dp.callback_query(F.data.startswith("set_"))
async def set_cat(callback: types.CallbackQuery, state: FSMContext):
    cat_map = {"upper": "upper_body", "lower": "lower_body", "dresses": "dresses"}
    key = callback.data.split("_")[1]
    await state.update_data(category=cat_map[key])
    await callback.message.edit_text("<b>Шаг 3:</b> Пришли фото одежды (на белом фоне или манекене).")
    await state.set_state(VTONState.wait_garment)

@dp.message(VTONState.wait_garment, F.photo)
async def garment_step(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    data = await state.get_data()
    
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    garment_url = f"https://api.telegram.org/file/bot{os.getenv('BOT_TOKEN')}/{file.file_path}"
    
    status_msg = await message.answer("⏳ <b>Идет генерация...</b>\nОбычно это занимает 40-60 секунд.")
    
    try:
        result_url = await generate_vton_image(data['human'], garment_url, data['category'])
        photo_res = requests.get(result_url).content
        await message.answer_photo(
            types.BufferedInputFile(photo_res, filename="res.jpg"),
            caption="✨ <b>Ваш образ готов!</b>\n\nНравится результат? Попробуйте еще раз!",
            reply_markup=get_main_menu()
        )
        if not user['is_admin']:
            await db.update_balance(message.from_user.id, -1)
    except Exception as e:
        await message.answer("❌ Произошла ошибка. Попробуйте другие фото.")
        print(e)
    finally:
        if status_msg:
            await status_msg.delete()
        await state.clear()

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
