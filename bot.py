import asyncio
import os
import requests
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

import database as db
from replicate_api import generate_vton_image
from video_animation import animate_image
import yookassa

# Инициализация бота
bot = Bot(
    token=os.getenv("BOT_TOKEN"), 
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

# URL для возврата после оплаты (замени на свой домен Railway)
RETURN_URL = "https://t.me/your_bot_username"  # TODO: Заменить на реальный URL

class VTONState(StatesGroup):
    wait_human = State()
    wait_category = State()
    wait_garment = State()
    wait_broadcast = State()
    wait_support_message = State()
    wait_admin_reply = State()
    wait_animation_choice = State()  # Новое состояние для выбора анимации
    # Новые состояния для прямой видео-примерки
    wait_video_human = State()
    wait_video_category = State()
    wait_video_garment = State()
    wait_video_animation_type = State()

# --- КЛАВИАТУРЫ ---

def get_main_menu():
    """Главное меню с эмодзи"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="👗 Примерить одежду")
    builder.button(text="🎬 Видео примерка")
    builder.button(text="📊 Мои примерки")
    builder.button(text="💎 Купить примерки")
    builder.button(text="👤 Профиль")
    builder.button(text="💬 Поддержка")
    builder.adjust(2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_category_kb():
    """Выбор категории одежды"""
    builder = InlineKeyboardBuilder()
    builder.button(text="👕 Верх (рубашки, футболки, свитера)", callback_data="set_upper")
    builder.button(text="👖 Низ (брюки, юбки, шорты)", callback_data="set_lower")
    builder.adjust(2)
    return builder.as_markup()

def get_packages_kb(is_admin=False):
    """Клавиатура с пакетами пополнения"""
    builder = InlineKeyboardBuilder()
    for package_id, info in yookassa.PACKAGES.items():
        # Тестовый пакет показываем только админу
        if package_id == "test_pack" and not is_admin:
            continue
        price = info['amount'] / 100
        builder.button(
            text=f"{info['title']} {info['desc']}",
            callback_data=f"buy_{package_id}"
        )
    builder.adjust(1)
    return builder.as_markup()

def get_result_actions():
    """Действия после генерации фото"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎬 Создать видео (100₽)", callback_data="create_video")
    builder.button(text="🔄 Другую одежду на это фото", callback_data="same_photo")
    builder.button(text="🆕 Новое фото", callback_data="new_photo")
    builder.adjust(1, 2)
    return builder.as_markup()

def get_animation_type_kb():
    """Выбор типа анимации"""
    builder = InlineKeyboardBuilder()
    builder.button(text="↩️ Лёгкий поворот (3 сек)", callback_data="anim_turn")
    builder.button(text="🚶 Шаг вперёд (3 сек)", callback_data="anim_step")
    builder.button(text="💃 Модельная походка (5 сек)", callback_data="anim_walk")
    builder.button(text="❌ Отмена", callback_data="anim_cancel")
    builder.adjust(1)
    return builder.as_markup()

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message(Command("start"))
async def start(message: types.Message):
    await db.get_user(message.from_user.id)
    
    welcome_text = (
        "👗 <b>Добро пожаловать в Virtual Stylist AI!</b>\n\n"
        "🎯 <b>Что я умею:</b>\n"
        "• Примеряю любую одежду по фото за 20-30 секунд\n"
        "• Работаю с AI-технологией IDM-VTON последнего поколения\n"
        "• Создаю реалистичные фотографии с сохранением деталей\n\n"
        "👕 <b>Типы одежды:</b>\n"
        "• <b>Верх</b>: рубашки, футболки, свитера, топы, платья\n"
        "• <b>Низ</b>: брюки, юбки, шорты, джинсы\n\n"
        "💡 <i>Для платьев и длинных топов выбирай категорию \"Верх\"</i>\n\n"
        "📱 Используй меню ниже, чтобы начать ⤵️"
    )
    
    await message.answer(welcome_text, reply_markup=get_main_menu())

@dp.message(F.text == "👤 Профиль")
async def profile(message: types.Message):
    user = await db.get_user(message.from_user.id)
    status = "👑 Администратор" if user['is_admin'] else "👤 Пользователь"
    balance_rub = user['balance'] / 100  # Копейки в рубли
    
    # Рассчитываем доступное количество
    photos_available = int(balance_rub / 50)
    videos_from_photo = int(balance_rub / 100)
    video_tryons = int(balance_rub / 150)
    
    profile_text = (
        f"<b>📱 Твой профиль</b>\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"💰 Баланс: <b>{balance_rub:.0f}₽</b>\n\n"
        f"📊 <b>Доступно:</b>\n"
        f"   📸 ~{photos_available} фото примерок\n"
        f"   🎬 ~{videos_from_photo} видео из фото\n"
        f"   🎥 ~{video_tryons} видео-примерок\n\n"
        f"📈 <b>Создано:</b>\n"
        f"   📸 Фото: <b>{user['total_generations']}</b>\n"
        f"   🎬 Видео: <b>{user.get('total_videos', 0)}</b>\n\n"
        f"⭐ Статус: {status}\n\n"
        f"💡 <i>Фото = 50₽ | Видео из фото = 100₽ | Видео-примерка = 150₽</i>"
    )
    
    if user['balance'] < 5000:
        profile_text += "\n\n⚠️ Недостаточно средств для примерки!\nПополни баланс 👇"
    
    await message.answer(profile_text)

@dp.message(F.text == "💎 Купить примерки")
async def show_packages(message: types.Message):
    user = await db.get_user(message.from_user.id)
    
    if user.get('is_admin'):
        packages_text = (
            "💎 <b>Пополни баланс:</b>\n\n"
            "🧪 <b>5₽ ТЕСТ</b> - для админа\n"
            "   → Тестовый пакет\n\n"
            "🔹 <b>250₽</b>\n"
            "   → 5 фото или 1-2 видео-примерки\n\n"
            "⭐ <b>500₽</b> - Выгодно!\n"
            "   → 10 фото или 3 видео-примерки\n\n"
            "💎 <b>1000₽</b> - Максимум!\n"
            "   → 20 фото или 6 видео-примерок\n\n"
            "💡 <b>Цены:</b>\n"
            "   📸 Фото: 50₽\n"
            "   🎬 Видео из фото: 100₽\n"
            "   🎥 Видео-примерка: 150₽ (всё сразу!)\n\n"
            "Оплата через ЮKassa - быстро и безопасно 🔒"
        )
    else:
        packages_text = (
            "💎 <b>Пополни баланс:</b>\n\n"
            "🔹 <b>250₽</b>\n"
            "   → 5 фото или 1-2 видео-примерки\n\n"
            "⭐ <b>500₽</b> - Выгодно!\n"
            "   → 10 фото или 3 видео-примерки\n\n"
            "💎 <b>1000₽</b> - Максимум!\n"
            "   → 20 фото или 6 видео-примерок\n\n"
            "💡 <b>Цены:</b>\n"
            "   📸 Фото: 50₽\n"
            "   🎬 Видео из фото: 100₽\n"
            "   🎥 Видео-примерка: 150₽ (всё сразу!)\n\n"
            "Оплата через ЮKassa - быстро и безопасно 🔒"
        )
    
    await message.answer(packages_text, reply_markup=get_packages_kb(user.get('is_admin', False)))

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(callback: types.CallbackQuery):
    package_id = callback.data.replace("buy_", "")
    
    payment_data = await yookassa.create_payment(
        package_id=package_id,
        user_id=callback.from_user.id,
        return_url=RETURN_URL
    )
    
    if not payment_data:
        await callback.message.answer("❌ Ошибка создания платежа. Попробуйте позже.")
        await callback.answer()
        return
    
    # Сохраняем платеж в БД
    await db.create_payment(
        payment_data['payment_id'],
        callback.from_user.id,
        payment_data['amount']
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить", url=payment_data['confirmation_url'])
    builder.button(text="🔍 Проверить оплату", callback_data=f"check_{payment_data['payment_id']}")
    builder.adjust(1)
    
    await callback.message.answer(
        f"💳 <b>Платеж создан!</b>\n\n"
        f"Сумма: <b>{payment_data['amount'] / 100:.0f}₽</b>\n\n"
        f"Нажми кнопку ниже для оплаты:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("check_"))
async def check_payment(callback: types.CallbackQuery):
    payment_id = callback.data.replace("check_", "")
    
    status = await yookassa.check_payment_status(payment_id)
    
    if not status:
        await callback.answer("❌ Ошибка проверки платежа", show_alert=True)
        return
    
    if status['status'] == 'succeeded' and status['paid']:
        payment = await db.confirm_payment(payment_id)
        if payment:
            balance_added = payment['amount'] / 100
            await callback.message.answer(
                f"✅ <b>Оплата прошла успешно!</b>\n\n"
                f"На твой баланс зачислено <b>{balance_added:.0f}₽</b>!\n"
                f"Спасибо за покупку! 💚"
            )
            await callback.answer("✅ Оплата подтверждена!", show_alert=True)
        else:
            await callback.answer("❌ Платеж не найден", show_alert=True)
    elif status['status'] == 'pending':
        await callback.answer("⏳ Платеж еще не завершен. Попробуйте через минуту.", show_alert=True)
    else:
        await callback.answer("❌ Платеж не прошел", show_alert=True)

@dp.message(F.text == "📊 Мои примерки")
async def my_generations(message: types.Message):
    gens = await db.get_user_generations(message.from_user.id, limit=5)
    
    if not gens:
        await message.answer(
            "📊 У тебя пока нет примерок.\n\n"
            "Нажми 👗 Примерить одежду, чтобы создать первую!"
        )
        return
    
    await message.answer(
        f"📊 <b>Твои последние {len(gens)} примерок:</b>\n\n"
        "Вот твои последние результаты:"
    )
    
    for gen in gens[:3]:  # Показываем последние 3
        try:
            cat_emoji = {"upper_body": "👕", "lower_body": "👖", "dresses": "👗"}
            cat_name = {"upper_body": "Верх", "lower_body": "Низ", "dresses": "Платье"}
            
            emoji = cat_emoji.get(gen['category'], "👗")
            name = cat_name.get(gen['category'], "Одежда")
            
            photo_res = requests.get(gen['result_url']).content
            await message.answer_photo(
                types.BufferedInputFile(photo_res, filename="gen.jpg"),
                caption=f"{emoji} {name}\n🕐 {gen['created_at'].strftime('%d.%m.%Y %H:%M')}"
            )
        except:
            continue

# --- АДМИН-ПАНЕЛЬ ---

@dp.message(Command("addbalance"))
async def add_balance_command(message: types.Message):
    """
    Команда для начисления баланса пользователю
    Формат: /addbalance USER_ID СУММА_В_РУБЛЯХ
    Пример: /addbalance 123456789 100 (начислит 100₽)
    """
    user = await db.get_user(message.from_user.id)
    if not user['is_admin']:
        await message.answer("❌ Доступно только администраторам")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer(
                "❌ <b>Неверный формат!</b>\n\n"
                "Используй: <code>/addbalance USER_ID СУММА</code>\n\n"
                "Пример: <code>/addbalance 123456789 100</code> (начислит 100₽)"
            )
            return
        
        target_user_id = int(parts[1])
        amount_rub = int(parts[2])
        amount_kopeks = amount_rub * 100  # Переводим в копейки
        
        # Проверяем, существует ли пользователь
        target_user = await db.get_user(target_user_id)
        
        # Начисляем баланс
        await db.update_balance(target_user_id, amount_kopeks)
        
        # Получаем обновленные данные
        updated_user = await db.get_user(target_user_id)
        new_balance = updated_user['balance'] / 100
        
        await message.answer(
            f"✅ <b>Баланс начислен!</b>\n\n"
            f"👤 Пользователь: <code>{target_user_id}</code>\n"
            f"➕ Начислено: <b>{amount_rub}₽</b>\n"
            f"💰 Новый баланс: <b>{new_balance:.0f}₽</b>"
        )
        
        # Уведомляем пользователя
        try:
            await bot.send_message(
                target_user_id,
                f"🎁 <b>Тебе начислено {amount_rub}₽!</b>\n\n"
                f"Твой новый баланс: <b>{new_balance:.0f}₽</b>\n"
                f"Спасибо, что пользуешься нашим сервисом! 💚"
            )
        except:
            pass
            
    except ValueError:
        await message.answer(
            "❌ <b>Ошибка!</b>\n\n"
            "USER_ID и СУММА должны быть числами"
        )
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {str(e)}")

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user['is_admin']:
        return

    stats = await db.get_stats()

    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.adjust(2)
    
    await message.answer(
        f"<b>⚙️ Панель администратора</b>\n\n"
        f"👥 Пользователей: <b>{stats['users']}</b>\n"
        f"✨ Примерок создано: <b>{stats['generations']}</b>\n"
        f"💰 Выручка: <b>{stats['revenue']:.0f}₽</b>\n\n"
        f"<b>Команды:</b>\n"
        f"• <code>/addbalance USER_ID СУММА</code> - начислить рубли\n"
        f"  Пример: /addbalance 123456789 100",
        reply_markup=builder.as_markup()
    )

@dp.message(Command("makeadmin"))
async def make_admin(message: types.Message):
    """Экстренная команда для установки админ-статуса"""
    # Только для твоего ID
    if message.from_user.id != 610820340:
        return
    
    conn = await db.asyncpg.connect(db.DATABASE_URL)
    await conn.execute("""
        UPDATE users 
        SET is_admin = TRUE, balance = GREATEST(balance, 10000000)
        WHERE user_id = 610820340
    """)
    await conn.close()
    
    await message.answer(
        "✅ <b>Админ-статус установлен!</b>\n\n"
        "👑 Теперь ты администратор\n"
        "💰 Баланс пополнен до 100000₽\n"
        "🎯 Цены: фото 1₽, видео 1₽\n\n"
        "Перезапусти бота: /start"
    )

@dp.message(Command("checkadmin"))
async def check_admin(message: types.Message):
    """Проверка статуса администратора"""
    user = await db.get_user(message.from_user.id)
    
    is_admin_value = user.get('is_admin', False)
    is_admin_type = str(type(is_admin_value).__name__)
    
    await message.answer(
        f"<b>🔍 Проверка статуса:</b>\n\n"
        f"🆔 User ID: <code>{message.from_user.id}</code>\n"
        f"👑 is_admin: <code>{is_admin_value}</code>\n"
        f"💰 Баланс: <code>{user['balance']} копеек = {user['balance']/100:.0f}₽</code>\n"
        f"📊 Тип: {is_admin_type}\n\n"
        f"<b>Все поля пользователя:</b>\n"
        f"• user_id: {user.get('user_id')}\n"
        f"• balance: {user.get('balance')}\n"
        f"• is_admin: {user.get('is_admin')}\n"
        f"• total_generations: {user.get('total_generations')}\n"
        f"• total_videos: {user.get('total_videos')}"
    )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    stats = await db.get_stats()
    
    await callback.message.answer(
        f"📊 <b>Детальная статистика:</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['users']}</b>\n"
        f"✨ Всего примерок: <b>{stats['generations']}</b>\n"
        f"💰 Общая выручка: <b>{stats['revenue']:.2f}₽</b>\n\n"
        f"📈 Средняя выручка на пользователя: <b>{stats['revenue'] / stats['users']:.2f}₽</b>"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📝 Введите текст рассылки. Его получат ВСЕ пользователи бота.")
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
    
    await message.answer(f"✅ Рассылка завершена! Сообщение получили <b>{count}</b> человек.")
    await state.clear()

# --- ЛОГИКА ГЕНЕРАЦИИ ---

@dp.message(F.text == "👗 Примерить одежду")
async def start_vton(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    
    # Проверяем баланс: всем нужно минимум 50₽ (5000 копеек)
    if user['balance'] < 5000:
        builder = InlineKeyboardBuilder()
        builder.button(text="💎 Пополнить баланс", callback_data="buy_test_pack" if user.get('is_admin') else "buy_250_pack")
        
        await message.answer(
            "😔 <b>Недостаточно средств!</b>\n\n"
            f"💰 Твой баланс: <b>{user['balance'] / 100:.0f}₽</b>\n"
            f"💡 Нужно минимум: <b>50₽</b>\n\n"
            "Пополни баланс, чтобы создавать крутые образы:",
            reply_markup=builder.as_markup()
        )
        return
    
    await state.clear()
    
    await message.answer(
        "📸 <b>Шаг 1 из 3: Твоё фото</b>\n\n"
        "Отправь фото человека (в полный рост или по пояс).\n\n"
        "💡 <i>Совет: Лучше работает на фото с однотонным фоном</i>\n"
        f"💰 <i>Стоимость: 50₽</i>"
    )
    await state.set_state(VTONState.wait_human)

@dp.message(VTONState.wait_human, F.photo)
async def human_step(message: types.Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{os.getenv('BOT_TOKEN')}/{file.file_path}"
    
    # Сохраняем URL фото в состоянии и в БД
    await state.update_data(human=url)
    await db.save_last_human_photo(message.from_user.id, url)
    
    await message.answer(
        "👗 <b>Шаг 2 из 3: Категория</b>\n\n"
        "Выбери, что хочешь примерить:",
        reply_markup=get_category_kb()
    )

@dp.callback_query(F.data.startswith("set_"))
async def set_cat(callback: types.CallbackQuery, state: FSMContext):
    """Выбор категории для обычной ФОТО-примерки"""
    # Проверяем что мы в правильном состоянии
    current_state = await state.get_state()
    
    print(f"DEBUG set_cat: Текущее состояние = {current_state}")
    
    # Если мы в процессе видео-примерки, пропускаем этот обработчик
    if current_state and 'video' in current_state:
        print(f"DEBUG set_cat: Пропускаем, это видео-примерка")
        return
    
    # Маппинг для IDM-VTON (передаём на русском в replicate_api.py)
    cat_map = {
        "upper": "верх",
        "lower": "низ",
        "dresses": "платье"
    }
    key = callback.data.split("_")[1]
    category = cat_map[key]
    
    print(f"DEBUG set_cat (ФОТО): Выбрана категория - кнопка='{key}', передаём='{category}'")
    
    await state.update_data(category=category)
    
    # DEBUG лог для отслеживания
    print(f"DEBUG bot.py: Выбрана категория - кнопка='{key}', передаём='{category}'")
    
    await callback.message.edit_text(
        "📷 <b>Шаг 3 из 3: Фото одежды</b>\n\n"
        "Отправь фото одежды (на белом фоне или манекене).\n\n"
        "💡 <i>Совет: Четкое фото с хорошим освещением даст лучший результат</i>"
    )
    await state.set_state(VTONState.wait_garment)

@dp.message(VTONState.wait_garment, F.photo)
async def garment_step(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    data = await state.get_data()
    
    # DEBUG: Проверяем статус админа
    print(f"DEBUG garment_step: user_id={message.from_user.id}, is_admin={user.get('is_admin')}, balance={user['balance']}")
    
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    garment_url = f"https://api.telegram.org/file/bot{os.getenv('BOT_TOKEN')}/{file.file_path}"
    
    status_msg = await message.answer(
        "✨ <b>Создаю твой образ...</b>\n\n"
        "⏳ Обычно это занимает 20-30 секунд\n"
        "🎨 AI IDM-VTON рисует реалистичную картинку\n"
        f"💰 Стоимость: 50₽"
    )
    
    try:
        result_url = await generate_vton_image(data['human'], garment_url, data['category'])
        
        # Сохраняем в историю
        await db.save_generation(message.from_user.id, data['category'], result_url)
        
        photo_res = requests.get(result_url).content
        
        # Списываем 50₽ (5000 копеек) у всех пользователей
        await db.update_balance(message.from_user.id, -5000, is_video=False)
        new_balance = (user['balance'] - 5000) / 100
        
        admin_badge = "👑 " if user.get('is_admin') else ""
        
        caption = (
            f"✨ <b>Твой образ готов!</b>\n\n"
            f"{admin_badge}💰 Баланс: <b>{new_balance:.0f}₽</b>\n\n"
            f"💡 Хочешь оживить фото?\n"
            f"Нажми 🎬 Создать видео (+100₽)"
        )
        print(f"DEBUG: Списано 50₽, новый баланс: {new_balance}₽")
        
        await message.answer_photo(
            types.BufferedInputFile(photo_res, filename="result.jpg"),
            caption=caption,
            reply_markup=get_result_actions()
        )
            
    except Exception as e:
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Попробуй другие фото или повтори попытку.\n"
            "Деньги не были списаны с баланса."
        )
        print(f"Ошибка генерации: {e}")
    finally:
        if status_msg:
            await status_msg.delete()
        await state.clear()

@dp.callback_query(F.data == "same_photo")
async def same_photo_tryagain(callback: types.CallbackQuery, state: FSMContext):
    """Примерка другой одежды на то же фото"""
    user = await db.get_user(callback.from_user.id)
    
    if not user['last_human_photo']:
        await callback.answer("❌ Нет сохраненного фото. Загрузите новое.", show_alert=True)
        return
    
    # Загружаем последнее фото в состояние
    await state.update_data(human=user['last_human_photo'])
    
    await callback.message.answer(
        "👗 <b>Выбери категорию одежды:</b>",
        reply_markup=get_category_kb()
    )
    await callback.answer()

@dp.callback_query(F.data == "new_photo")
async def new_photo_tryagain(callback: types.CallbackQuery, state: FSMContext):
    """Начать примерку с нового фото"""
    await callback.message.answer(
        "📸 <b>Шаг 1 из 3: Твоё фото</b>\n\n"
        "Отправь фото человека (в полный рост или по пояс).\n\n"
        "💡 <i>Совет: Лучше работает на фото с однотонным фоном</i>\n"
        "💰 <i>Стоимость: 50₽</i>"
    )
    await state.set_state(VTONState.wait_human)
    await callback.answer()

# --- ПРЯМАЯ ВИДЕО-ПРИМЕРКА (150₽) ---

@dp.message(F.text == "🎬 Видео примерка")
async def start_video_vton(message: types.Message, state: FSMContext):
    """Начало прямой видео-примерки за 150₽"""
    user = await db.get_user(message.from_user.id)
    
    # Проверяем баланс: нужно минимум 150₽ (15000 копеек)
    if user['balance'] < 15000:
        builder = InlineKeyboardBuilder()
        builder.button(text="💎 Пополнить баланс", callback_data="buy_test_pack" if user.get('is_admin') else "buy_250_pack")
        
        await message.answer(
            "😔 <b>Недостаточно средств для видео-примерки!</b>\n\n"
            f"💰 Твой баланс: <b>{user['balance'] / 100:.0f}₽</b>\n"
            f"💡 Нужно минимум: <b>150₽</b>\n\n"
            "🎬 <b>Видео-примерка включает:</b>\n"
            "   • Фото примерка\n"
            "   • Анимация видео 6 сек\n"
            "   • Всё за один раз!\n\n"
            "Пополни баланс:",
            reply_markup=builder.as_markup()
        )
        return
    
    await state.clear()
    
    await message.answer(
        "🎬 <b>Видео-примерка за 150₽</b>\n\n"
        "📸 <b>Шаг 1 из 4: Твоё фото</b>\n\n"
        "Отправь фото человека (в полный рост или по пояс).\n\n"
        "💡 <i>Совет: Лучше работает на фото с однотонным фоном</i>\n"
        "🎬 <i>Получишь: Фото + Видео анимацию!</i>"
    )
    await state.set_state(VTONState.wait_video_human)

@dp.message(VTONState.wait_video_human, F.photo)
async def video_human_step(message: types.Message, state: FSMContext):
    """Получили фото человека для видео-примерки"""
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{os.getenv('BOT_TOKEN')}/{file.file_path}"
    
    await state.update_data(human=url)
    await db.save_last_human_photo(message.from_user.id, url)
    
    await message.answer(
        "👗 <b>Шаг 2 из 4: Категория</b>\n\n"
        "Выбери, что хочешь примерить:",
        reply_markup=get_category_kb()
    )
    # Меняем состояние на ожидание категории
    await state.set_state(VTONState.wait_video_category)

@dp.callback_query(F.data.startswith("set_"), VTONState.wait_video_category)
async def video_set_cat(callback: types.CallbackQuery, state: FSMContext):
    """Выбор категории для видео-примерки"""
    cat_map = {
        "upper": "верх",
        "lower": "низ",
        "dresses": "платье"
    }
    key = callback.data.split("_")[1]
    category = cat_map[key]
    
    await state.update_data(category=category)
    
    print(f"DEBUG bot.py (VIDEO): Выбрана категория - кнопка='{key}', передаём='{category}'")
    
    await callback.message.edit_text(
        "📷 <b>Шаг 3 из 4: Фото одежды</b>\n\n"
        "Отправь фото одежды (на белом фоне или манекене).\n\n"
        "💡 <i>Совет: Чёткое фото с хорошим освещением</i>"
    )
    await state.set_state(VTONState.wait_video_garment)
    await callback.answer()

@dp.message(VTONState.wait_video_garment, F.photo)
async def video_garment_step(message: types.Message, state: FSMContext):
    """Получили фото одежды - выбор типа анимации"""
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    garment_url = f"https://api.telegram.org/file/bot{os.getenv('BOT_TOKEN')}/{file.file_path}"
    
    await state.update_data(garment=garment_url)
    
    # Предлагаем выбрать тип анимации
    await message.answer(
        "🎬 <b>Шаг 4 из 4: Выбери анимацию</b>\n\n"
        "Какое движение хочешь видеть в видео?",
        reply_markup=get_animation_type_kb()
    )
    await state.set_state(VTONState.wait_video_animation_type)

@dp.callback_query(F.data.startswith("anim_"), VTONState.wait_video_animation_type)
async def video_create_final(callback: types.CallbackQuery, state: FSMContext):
    """Финальная генерация видео-примерки"""
    user = await db.get_user(callback.from_user.id)
    data = await state.get_data()
    
    # Отмена
    if callback.data == "anim_cancel":
        await callback.message.edit_text("❌ Видео-примерка отменена")
        await state.clear()
        await callback.answer()
        return
    
    # Проверка баланса ещё раз
    if user['balance'] < 15000:
        await callback.message.edit_text(
            "😔 <b>Недостаточно средств!</b>\n\n"
            f"💰 Твой баланс: <b>{user['balance'] / 100:.0f}₽</b>\n"
            f"💡 Нужно: <b>150₽</b>"
        )
        await state.clear()
        await callback.answer()
        return
    
    # Определяем тип анимации
    anim_type_map = {
        "anim_turn": "turn",
        "anim_step": "step",
        "anim_walk": "walk"
    }
    animation_type = anim_type_map.get(callback.data, "walk")
    
    status_msg = await callback.message.edit_text(
        "✨ <b>Создаём твою видео-примерку...</b>\n\n"
        "⏳ Это займёт 2-3 минуты\n"
        "🎨 Сначала создаём фото, потом анимацию\n"
        f"💰 Стоимость: 150₽"
    )
    
    try:
        # ШАГ 1: Создаём фото примерку
        print(f"DEBUG VIDEO-FINAL: ========== НАЧАЛО ==========")
        print(f"DEBUG VIDEO-FINAL: Данные из state: {data}")
        print(f"DEBUG VIDEO-FINAL: Категория = '{data['category']}'")
        print(f"DEBUG VIDEO-FINAL: Шаг 1 - создание фото через IDM-VTON")
        
        result_url = await generate_vton_image(data['human'], data['garment'], data['category'])
        
        print(f"DEBUG VIDEO-FINAL: Фото создано успешно: {result_url[:100]}")
        
        # ШАГ 2: Создаём видео из фото
        print(f"DEBUG VIDEO-FINAL: Шаг 2 - создание видео из фото")
        print(f"DEBUG VIDEO: Шаг 2 - создание видео из фото")
        video_url = await animate_image(result_url, animation_type)
        
        # Загружаем видео
        video_res = requests.get(video_url).content
        
        # Списываем 150₽ (15000 копеек)
        await db.update_balance(message.from_user.id, -15000, is_video=True)
        new_balance = (user['balance'] - 15000) / 100
        
        # Сохраняем в историю
        await db.save_generation(message.from_user.id, data['category'], result_url)
        
        admin_badge = "👑 " if user.get('is_admin') else ""
        
        caption = (
            f"🎬 <b>Твоя видео-примерка готова!</b>\n\n"
            f"{admin_badge}💰 Баланс: <b>{new_balance:.0f}₽</b>\n\n"
            f"✨ Видео включает фото + анимацию!\n"
            f"📱 Сохрани и поделись с друзьями"
        )
        
        print(f"DEBUG: Списано 150₽ за видео-примерку, новый баланс: {new_balance}₽")
        
        # Отправляем видео
        await message.answer_video(
            types.BufferedInputFile(video_res, filename="video_tryoन.mp4"),
            caption=caption,
            reply_markup=get_main_menu()
        )
        
        # Удаляем статусное сообщение
        await status_msg.delete()
        await callback.answer("🎬 Видео-примерка готова!", show_alert=True)
        
    except Exception as e:
        await status_msg.edit_text(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Попробуй ещё раз или создай обычную примерку.\n"
            "Деньги не были списаны."
        )
        print(f"Ошибка создания видео-примерки: {e}")
        await callback.answer()
    finally:
        await state.clear()

# --- СИСТЕМА СОЗДАНИЯ ВИДЕО ---

@dp.callback_query(F.data == "create_video")
async def start_video_creation(callback: types.CallbackQuery, state: FSMContext):
    """Пользователь хочет создать видео"""
    user = await db.get_user(callback.from_user.id)
    
    # Проверяем баланс: всем нужно минимум 100₽ (10000 копеек)
    if user['balance'] < 10000:
        builder = InlineKeyboardBuilder()
        builder.button(text="💎 Пополнить баланс", callback_data="buy_test_pack" if user.get('is_admin') else "buy_250_pack")
        
        await callback.message.answer(
            "😔 <b>Недостаточно средств!</b>\n\n"
            f"💰 Твой баланс: <b>{user['balance'] / 100:.0f}₽</b>\n"
            f"💡 Нужно минимум: <b>100₽</b>\n\n"
            "Пополни баланс для создания видео:",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return
    
    # Проверяем, есть ли последний результат
    if not user.get('last_result_url'):
        await callback.answer("❌ Нет сохраненного результата примерки", show_alert=True)
        return
    
    # Показываем выбор типа анимации
    await callback.message.answer(
        "🎬 <b>Создание видео-анимации</b>\n\n"
        "Выбери тип движения:\n\n"
        "↩️ <b>Лёгкий поворот</b> — элегантный разворот на 180°\n"
        "🚶 <b>Шаг вперёд</b> — уверенный шаг к камере\n"
        "💃 <b>Модельная походка</b> — движение как на подиуме\n\n"
        "⏱ Создание займёт ~30-60 секунд\n"
        f"💰 Стоимость: <b>100₽</b>",
        reply_markup=get_animation_type_kb()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("anim_"))
async def process_animation(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора типа анимации"""
    
    if callback.data == "anim_cancel":
        await callback.message.edit_text("❌ Создание видео отменено")
        await callback.answer()
        return
    
    user = await db.get_user(callback.from_user.id)
    
    # Проверяем баланс: всем нужно минимум 100₽
    if user['balance'] < 10000:
        await callback.answer("❌ Недостаточно средств!", show_alert=True)
        return
    
    # Определяем тип анимации
    animation_map = {
        "anim_turn": "turn",
        "anim_step": "step", 
        "anim_walk": "walk"
    }
    animation_type = animation_map.get(callback.data, "turn")
    animation_names = {
        "turn": "Лёгкий поворот",
        "step": "Шаг вперёд",
        "walk": "Модельная походка"
    }
    
    # Обновляем сообщение на статус создания
    await callback.message.edit_text(
        f"🎬 <b>Создаю анимацию...</b>\n\n"
        f"Тип: {animation_names[animation_type]}\n"
        f"⏳ Обычно это занимает 30-60 секунд\n"
        f"🎨 AI создаёт реалистичное видео"
    )
    
    try:
        # Генерируем видео
        video_url = await animate_image(user['last_result_url'], animation_type)
        
        # Скачиваем видео
        import requests
        video_data = requests.get(video_url).content
        
        # Списываем 100₽ (10000 копеек) у всех пользователей
        await db.update_balance(callback.from_user.id, -10000, is_video=True)
        new_balance = (user['balance'] - 10000) / 100
        
        admin_badge = "👑 " if user.get('is_admin') else ""
        
        caption = (
            f"✨ <b>Твоё видео готово!</b>\n\n"
            f"Тип: {animation_names[animation_type]}\n"
            f"{admin_badge}💰 Баланс: <b>{new_balance:.0f}₽</b>"
        )
        print(f"DEBUG: Списано 100₽ за видео, новый баланс: {new_balance}₽")
        
        # Отправляем видео
        await callback.message.answer_video(
            types.BufferedInputFile(video_data, filename="animation.mp4"),
            caption=caption,
            reply_markup=get_result_actions()
        )
        
        # Удаляем статусное сообщение
        await callback.message.delete()
        await callback.answer("✅ Видео создано!", show_alert=True)
        
    except Exception as e:
        await callback.message.edit_text(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Попробуйте ещё раз или создайте новую примерку.\n"
            "Деньги не были списаны."
        )
        print(f"Ошибка создания видео: {e}")
        await callback.answer()

# --- ADMIN PANEL (keeping existing code) ---

@dp.message(F.text == "💬 Поддержка")
async def support_start(message: types.Message, state: FSMContext):
    """Начало диалога с поддержкой"""
    await message.answer(
        "💬 <b>Служба поддержки</b>\n\n"
        "Опишите вашу проблему или задайте вопрос.\n"
        "Администратор ответит в ближайшее время.\n\n"
        "Напишите ваше сообщение:"
    )
    await state.set_state(VTONState.wait_support_message)

@dp.message(VTONState.wait_support_message)
async def support_message_received(message: types.Message, state: FSMContext):
    """Пользователь отправил сообщение в поддержку"""
    user = await db.get_user(message.from_user.id)
    balance_rub = user['balance'] / 100
    
    # Формируем сообщение для админа
    admin_text = (
        f"💬 <b>Новое обращение в поддержку</b>\n\n"
        f"👤 От: {message.from_user.first_name or 'Пользователь'}\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"👤 Username: @{message.from_user.username or 'нет'}\n"
        f"💰 Баланс: {balance_rub:.0f}₽\n\n"
        f"📝 <b>Сообщение:</b>\n{message.text}"
    )
    
    # Кнопка для ответа
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Написать ответ", callback_data=f"reply_{message.from_user.id}")
    
    # Отправляем админу (твой ID)
    try:
        await bot.send_message(610820340, admin_text, reply_markup=builder.as_markup())
        await message.answer(
            "✅ <b>Ваше сообщение отправлено!</b>\n\n"
            "Администратор ответит в ближайшее время.",
            reply_markup=get_main_menu()
        )
    except Exception as e:
        await message.answer(
            "❌ Ошибка отправки сообщения. Попробуйте позже.",
            reply_markup=get_main_menu()
        )
        print(f"Ошибка отправки в поддержку: {e}")
    
    await state.clear()

@dp.callback_query(F.data.startswith("reply_"))
async def admin_reply_button(callback: types.CallbackQuery, state: FSMContext):
    """Админ нажал кнопку 'Написать ответ'"""
    user = await db.get_user(callback.from_user.id)
    if not user['is_admin']:
        await callback.answer("❌ Доступно только администраторам", show_alert=True)
        return
    
    user_id = int(callback.data.replace("reply_", ""))
    
    # Сохраняем ID пользователя в состояние
    await state.update_data(reply_to_user=user_id)
    await state.set_state(VTONState.wait_admin_reply)
    
    await callback.message.answer(
        f"✍️ <b>Напиши ответ для пользователя</b> <code>{user_id}</code>\n\n"
        f"Твоё сообщение будет отправлено ему в бот.\n"
        f"Отправь /cancel для отмены."
    )
    await callback.answer()

@dp.message(VTONState.wait_admin_reply)
async def admin_send_reply(message: types.Message, state: FSMContext):
    """Админ отправляет ответ пользователю"""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Ответ отменён.")
        return
    
    data = await state.get_data()
    target_user_id = data.get('reply_to_user')
    
    if not target_user_id:
        await message.answer("❌ Ошибка: не найден ID пользователя")
        await state.clear()
        return
    
    try:
        # Отправляем ответ пользователю с кнопкой для продолжения диалога
        user_builder = InlineKeyboardBuilder()
        user_builder.button(text="💬 Ответить", callback_data="continue_support")
        
        await bot.send_message(
            target_user_id,
            f"💬 <b>Ответ от службы поддержки:</b>\n\n{message.text}",
            reply_markup=user_builder.as_markup()
        )
        
        # Подтверждаем админу с возможностью продолжить диалог
        admin_builder = InlineKeyboardBuilder()
        admin_builder.button(text="✍️ Написать ещё", callback_data=f"reply_{target_user_id}")
        
        await message.answer(
            f"✅ Ответ отправлен пользователю <code>{target_user_id}</code>",
            reply_markup=admin_builder.as_markup()
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {str(e)}")
    
    await state.clear()

@dp.callback_query(F.data == "continue_support")
async def user_continue_support(callback: types.CallbackQuery, state: FSMContext):
    """Пользователь хочет продолжить диалог с поддержкой"""
    await callback.message.answer(
        "💬 <b>Продолжение диалога</b>\n\n"
        "Напишите ваше сообщение:"
    )
    await state.set_state(VTONState.wait_support_message)
    await callback.answer()

@dp.message(Command("reply"))
async def admin_reply_command(message: types.Message):
    """Альтернативный способ - админ отвечает через команду (если кнопка не работает)"""
    user = await db.get_user(message.from_user.id)
    if not user['is_admin']:
        return
    
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.answer(
                "❌ <b>Неверный формат!</b>\n\n"
                "Используй: <code>/reply USER_ID текст ответа</code>\n\n"
                "Пример: <code>/reply 123456789 Здравствуйте! Ваша проблема решена.</code>\n\n"
                "💡 Или используй кнопку '✍️ Написать ответ' под сообщением пользователя."
            )
            return
        
        target_user_id = int(parts[1])
        reply_text = parts[2]
        
        # Отправляем ответ пользователю с кнопкой
        user_builder = InlineKeyboardBuilder()
        user_builder.button(text="💬 Ответить", callback_data="continue_support")
        
        await bot.send_message(
            target_user_id,
            f"💬 <b>Ответ от службы поддержки:</b>\n\n{reply_text}",
            reply_markup=user_builder.as_markup()
        )
        
        # Подтверждаем админу
        admin_builder = InlineKeyboardBuilder()
        admin_builder.button(text="✍️ Написать ещё", callback_data=f"reply_{target_user_id}")
        
        await message.answer(
            f"✅ Ответ отправлен пользователю <code>{target_user_id}</code>",
            reply_markup=admin_builder.as_markup()
        )
        
    except ValueError:
        await message.answer("❌ USER_ID должен быть числом")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {str(e)}")

# --- WEBHOOK ДЛЯ ЮKASSA (если будешь использовать) ---

async def yookassa_webhook(request):
    """Обработка webhook от ЮKassa для автоматического подтверждения платежей"""
    try:
        data = await request.json()
        
        if data.get('event') == 'payment.succeeded':
            payment_id = data['object']['id']
            payment = await db.confirm_payment(payment_id)
            
            if payment:
                # Отправляем уведомление пользователю
                await bot.send_message(
                    payment['user_id'],
                    f"✅ <b>Оплата прошла успешно!</b>\n\n"
                    f"На твой счет зачислено <b>{payment['credits']}</b> примерок!\n"
                    f"Спасибо за покупку! 💚"
                )
        
        return web.Response(text="OK")
    except Exception as e:
        print(f"Ошибка webhook: {e}")
        return web.Response(status=500)

async def main():
    await db.init_db()
    
    # Если хочешь использовать webhook для автоподтверждения платежей
    # app = web.Application()
    # app.router.add_post('/webhook/yookassa', yookassa_webhook)
    # runner = web.AppRunner(app)
    # await runner.setup()
    # site = web.TCPSite(runner, '0.0.0.0', 8080)
    # await site.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
