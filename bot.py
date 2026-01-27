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

# --- КЛАВИАТУРЫ ---

def get_main_menu():
    """Главное меню с эмодзи"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="👗 Примерить одежду")
    builder.button(text="📊 Мои примерки")
    builder.button(text="💎 Купить примерки")
    builder.button(text="👤 Профиль")
    builder.button(text="💬 Поддержка")
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)

def get_category_kb():
    """Выбор категории одежды"""
    builder = InlineKeyboardBuilder()
    builder.button(text="👕 Верх", callback_data="set_upper")
    builder.button(text="👖 Низ", callback_data="set_lower")
    builder.button(text="👗 Платье", callback_data="set_dresses")
    builder.adjust(3)
    return builder.as_markup()

def get_packages_kb():
    """Клавиатура с пакетами пополнения"""
    builder = InlineKeyboardBuilder()
    for package_id, info in yookassa.PACKAGES.items():
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
        "• Примеряю любую одежду по фото за 60 секунд\n"
        "• Работаю с AI-технологией последнего поколения\n"
        "• Создаю реалистичные фотографии\n\n"
        "✨ Просто отправь своё фото и фото одежды — "
        "я покажу, как это будет выглядеть на тебе!\n\n"
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
    videos_available = int(balance_rub / 100)
    
    profile_text = (
        f"<b>📱 Твой профиль</b>\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"💰 Баланс: <b>{balance_rub:.0f}₽</b>\n\n"
        f"📊 <b>Доступно:</b>\n"
        f"   📸 ~{photos_available} фото примерок\n"
        f"   🎬 ~{videos_available} видео анимаций\n\n"
        f"📈 <b>Создано:</b>\n"
        f"   📸 Фото: <b>{user['total_generations']}</b>\n"
        f"   🎬 Видео: <b>{user.get('total_videos', 0)}</b>\n\n"
        f"⭐ Статус: {status}\n\n"
        f"💡 <i>Фото = 50₽ | Видео = 100₽</i>"
    )
    
    if user['balance'] < 5000:
        profile_text += "\n\n⚠️ Недостаточно средств для примерки!\nПополни баланс 👇"
    
    await message.answer(profile_text)

@dp.message(F.text == "💎 Купить примерки")
async def show_packages(message: types.Message):
    packages_text = (
        "💎 <b>Пополни баланс:</b>\n\n"
        "🔹 <b>250₽</b>\n"
        "   → 5 фото примерок (50₽/шт)\n\n"
        "⭐ <b>500₽</b> - Выгодно!\n"
        "   → 12 фото или 5 видео (40₽/шт)\n\n"
        "💎 <b>1000₽</b> - Максимум!\n"
        "   → 25 фото или 10 видео (40₽/шт)\n\n"
        "💡 <i>Фото примерка: 50₽</i>\n"
        "💡 <i>Видео анимация: 100₽</i>\n\n"
        "Оплата через ЮKassa - быстро и безопасно 🔒"
    )
    
    await message.answer(packages_text, reply_markup=get_packages_kb())

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
    
    # Проверяем баланс: обычным нужно 50₽, админу 1₽
    min_balance = 100 if user['is_admin'] else 5000
    
    if user['balance'] < min_balance:
        builder = InlineKeyboardBuilder()
        builder.button(text="💎 Пополнить баланс", callback_data="buy_250_pack")
        
        price_text = "1₽" if user['is_admin'] else "50₽"
        
        await message.answer(
            "😔 <b>Недостаточно средств!</b>\n\n"
            f"💰 Твой баланс: <b>{user['balance'] / 100:.0f}₽</b>\n"
            f"💡 Нужно минимум: <b>{price_text}</b>\n\n"
            "Пополни баланс, чтобы создавать крутые образы:",
            reply_markup=builder.as_markup()
        )
        return
    
    await state.clear()
    
    price_text = "1₽ (админ-режим)" if user['is_admin'] else "50₽"
    
    await message.answer(
        "📸 <b>Шаг 1 из 3: Твоё фото</b>\n\n"
        "Отправь фото человека (в полный рост или по пояс).\n\n"
        "💡 <i>Совет: Лучше работает на фото с однотонным фоном</i>\n"
        f"💰 <i>Стоимость: {price_text}</i>"
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
    cat_map = {"upper": "upper_body", "lower": "lower_body", "dresses": "dresses"}
    key = callback.data.split("_")[1]
    await state.update_data(category=cat_map[key])
    
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
    
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    garment_url = f"https://api.telegram.org/file/bot{os.getenv('BOT_TOKEN')}/{file.file_path}"
    
    status_msg = await message.answer(
        "✨ <b>Создаю твой образ...</b>\n\n"
        "⏳ Обычно это занимает 40-60 секунд\n"
        "🎨 AI рисует реалистичную картинку\n"
        "💰 Стоимость: 50₽"
    )
    
    try:
        result_url = await generate_vton_image(data['human'], garment_url, data['category'])
        
        # Сохраняем в историю
        await db.save_generation(message.from_user.id, data['category'], result_url)
        
        photo_res = requests.get(result_url).content
        
        # Списываем 50₽ (5000 копеек) только у обычных пользователей
        if not user['is_admin']:
            await db.update_balance(message.from_user.id, -5000, is_video=False)
            new_balance = (user['balance'] - 5000) / 100
            caption = (
                f"✨ <b>Твой образ готов!</b>\n\n"
                f"💰 Баланс: <b>{new_balance:.0f}₽</b>\n\n"
                f"💡 Хочешь оживить фото?\n"
                f"Нажми 🎬 Создать видео (+100₽)"
            )
        else:
            # Админ платит 1₽ для тестирования
            await db.update_balance(message.from_user.id, -100, is_video=False)
            new_balance = (user['balance'] - 100) / 100
            caption = (
                f"✨ <b>Твой образ готов!</b>\n\n"
                f"👑 Админ-режим: 1₽ за фото\n"
                f"💰 Баланс: <b>{new_balance:.0f}₽</b>\n\n"
                f"💡 Хочешь оживить фото?\n"
                f"Нажми 🎬 Создать видео (+1₽)"
            )
        
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

# --- СИСТЕМА СОЗДАНИЯ ВИДЕО ---

@dp.callback_query(F.data == "create_video")
async def start_video_creation(callback: types.CallbackQuery, state: FSMContext):
    """Пользователь хочет создать видео"""
    user = await db.get_user(callback.from_user.id)
    
    # Проверяем баланс: обычным нужно 100₽, админу 1₽
    min_balance = 100 if user['is_admin'] else 10000
    
    if user['balance'] < min_balance:
        builder = InlineKeyboardBuilder()
        builder.button(text="💎 Пополнить баланс", callback_data="buy_250_pack")
        
        price_text = "1₽" if user['is_admin'] else "100₽"
        
        await callback.message.answer(
            "😔 <b>Недостаточно средств!</b>\n\n"
            f"💰 Твой баланс: <b>{user['balance'] / 100:.0f}₽</b>\n"
            f"💡 Нужно минимум: <b>{price_text}</b>\n\n"
            "Пополни баланс для создания видео:",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return
    
    # Проверяем, есть ли последний результат
    if not user.get('last_result_url'):
        await callback.answer("❌ Нет сохраненного результата примерки", show_alert=True)
        return
    
    price_text = "1₽ (админ-режим)" if user['is_admin'] else "100₽"
    
    # Показываем выбор типа анимации
    await callback.message.answer(
        "🎬 <b>Создание видео-анимации</b>\n\n"
        "Выбери тип движения:\n\n"
        "↩️ <b>Лёгкий поворот</b> — элегантный разворот на 180°\n"
        "🚶 <b>Шаг вперёд</b> — уверенный шаг к камере\n"
        "💃 <b>Модельная походка</b> — движение как на подиуме\n\n"
        "⏱ Создание займёт ~30-60 секунд\n"
        f"💰 Стоимость: <b>{price_text}</b>",
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
    
    # Проверяем баланс: обычным нужно 100₽, админу 1₽
    min_balance = 100 if user['is_admin'] else 10000
    
    if user['balance'] < min_balance:
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
        
        # Списываем 100₽ (10000 копеек) только у обычных пользователей
        if not user['is_admin']:
            await db.update_balance(callback.from_user.id, -10000, is_video=True)
            new_balance = (user['balance'] - 10000) / 100
            caption = (
                f"✨ <b>Твоё видео готово!</b>\n\n"
                f"Тип: {animation_names[animation_type]}\n"
                f"💰 Баланс: <b>{new_balance:.0f}₽</b>"
            )
        else:
            # Админ платит 1₽ для тестирования
            await db.update_balance(callback.from_user.id, -100, is_video=True)
            new_balance = (user['balance'] - 100) / 100
            caption = (
                f"✨ <b>Твоё видео готово!</b>\n\n"
                f"Тип: {animation_names[animation_type]}\n"
                f"👑 Админ-режим: 1₽ за видео\n"
                f"💰 Баланс: <b>{new_balance:.0f}₽</b>"
            )
        
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
