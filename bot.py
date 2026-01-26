import asyncio
import os
import requests
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from replicate_api import generate_vton_image

# Инициализация
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

class VTONState(StatesGroup):
    wait_human = State()
    wait_category = State()
    wait_garment = State()

def get_category_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="👕 Верх (футболки, куртки)", callback_data="set_upper")
    builder.button(text="👖 Низ (брюки, юбки)", callback_data="set_lower")
    builder.button(text="👗 Платье / Комбинезон", callback_data="set_dresses")
    builder.adjust(1)
    return builder.as_markup()

@dp.message(Command("start"))
async def start(message: types.Message):
    user = await db.get_user(message.from_user.id)
    await message.answer(f"Привет! Это AI Стилист 👗\nТвой баланс: {user['balance']} примерок.\n\n"
                         "Пришли фото человека в полный рост.")

@dp.message(Command("buy"))
async def buy(message: types.Message):
    await message.answer_invoice(
        title="5 примерок",
        description="Пополнение баланса в AI Стилисте",
        payload="5_pack",
        provider_token=os.getenv("PAYMENT_TOKEN"),
        currency="RUB",
        prices=[types.LabeledPrice(label="5 примерок", amount=25000)] # 250.00 RUB
    )

@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.successful_payment)
async def success_payment(message: types.Message):
    await db.update_balance(message.from_user.id, 5)
    await message.answer("Оплата прошла! Вам начислено 5 примерок. Пользуйтесь на здоровье!")

@dp.callback_query(F.data.startswith("set_"))
async def callbacks_category(callback: types.CallbackQuery, state: FSMContext):
    cat_map = {"upper": "upper_body", "lower": "lower_body", "dresses": "dresses"}
    cat_name = {"upper": "Верх", "lower": "Низ", "dresses": "Платье"}
    key = callback.data.split("_")[1]
    
    await state.update_data(category=cat_map[key], category_name=cat_name[key])
    await callback.message.edit_text(f"Выбрано: {cat_name[key]}. Теперь пришли фото ОДЕЖДЫ.")
    await state.set_state(VTONState.wait_garment)

@dp.message(F.photo)
async def handle_photos(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if user['balance'] <= 0:
        return await message.answer("У вас 0 примерок. Купите пакет через /buy")

    data = await state.get_data()
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    # Прямая ссылка для Replicate
    url = f"https://api.telegram.org/file/bot{os.getenv('BOT_TOKEN')}/{file.file_path}"

    if 'human' not in data:
        await state.update_data(human=url)
        await message.answer("Фото человека принято. Что будем примерять?", reply_markup=get_category_kb())
        await state.set_state(VTONState.wait_category)
    else:
        # Если это второе фото (одежда)
        cat = data.get('category', 'upper_body')
        await message.answer(f"Запускаю нейросеть (категория: {data.get('category_name')})... Подождите около минуты ⏳")
        
        try:
            result_url = await generate_vton_image(data['human'], url, cat)
            if result_url:
                # Скачиваем и отправляем для надежности
                photo_res = requests.get(result_url).content
                await message.answer_photo(
                    types.BufferedInputFile(photo_res, filename="result.jpg"),
                    caption="Твой новый образ готов! ✨"
                )
                if not user['is_admin']:
                    await db.update_balance(message.from_user.id, -1)
            await state.clear()
        except Exception as e:
            await message.answer("Ошибка нейросети. Попробуйте другое фото одежды.")
            print(f"Error: {e}")
            await state.clear()

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
