import asyncio
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import database as db
from replicate_api import generate_vton_image

# Инициализация бота
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

class VTONState(StatesGroup):
    wait_human = State()
    wait_garment = State()

@dp.message(Command("start"))
async def start(message: types.Message):
    user = await db.get_user(message.from_user.id)
    await message.answer(f"Привет! Твой баланс: {user['balance']} примерок.\n\n"
                         f"Чтобы начать, просто пришли фото человека в полный рост.")

@dp.message(Command("buy"))
async def buy_cmd(message: types.Message):
    await message.answer_invoice(
        title="5 примерок",
        description="Пакет генераций для AI Стилиста",
        payload="5_pack",
        provider_token=os.getenv("PAYMENT_TOKEN"),
        currency="RUB",
        prices=[types.LabeledPrice(label="5 примерок", amount=25000)] # 250 руб
    )

@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.successful_payment)
async def success_payment(message: types.Message):
    await db.update_balance(message.from_user.id, 5)
    await message.answer("Оплата прошла успешно! Вам начислено 5 попыток.")

@dp.message(F.photo)
async def handle_photos(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if user['balance'] <= 0:
        return await message.answer("У вас закончились попытки. Нажмите /buy чтобы пополнить.")

    data = await state.get_data()
    # Получаем прямую ссылку на фото через сервер Telegram
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{os.getenv('BOT_TOKEN')}/{file.file_path}"

    if 'human' not in data:
        await state.update_data(human=url)
        await message.answer("Фото человека принято. Теперь пришли фото ОДЕЖДЫ (на белом фоне или манекене).")
    else:
        await message.answer("Запускаю нейросеть... Это займет около 40-60 секунд. Пожалуйста, подождите ⏳")
        try:
            result_url = await generate_vton_image(data['human'], url)
            await message.answer_photo(result_url, caption="Готово! Как вам такой образ?")
            if not user['is_admin']:
                await db.update_balance(message.from_user.id, -1)
            await state.clear()
        except Exception as e:
            await message.answer(f"Произошла ошибка при генерации. Попробуйте позже.")
            print(f"Error: {e}")
            await state.clear()

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())