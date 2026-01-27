import os
import uuid
import aiohttp
import base64
from typing import Optional

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")

# Пакеты примерок
PACKAGES = {
    "5_pack": {"credits": 5, "price": 25000, "title": "5 примерок", "desc": "Базовый пакет"},
    "15_pack": {"credits": 15, "price": 60000, "title": "15 примерок", "desc": "⭐ Популярный выбор"},
    "50_pack": {"credits": 50, "price": 150000, "title": "50 примерок", "desc": "💎 Максимальная выгода"}
}

def get_auth_header():
    """Генерирует заголовок авторизации для Юкассы"""
    credentials = f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"

async def create_payment(package_id: str, user_id: int, return_url: str) -> Optional[dict]:
    """
    Создает платеж в Юкассе
    
    Args:
        package_id: ID пакета (например, "5_pack")
        user_id: Telegram ID пользователя
        return_url: URL для возврата после оплаты
    
    Returns:
        dict с payment_id и confirmation_url или None при ошибке
    """
    if package_id not in PACKAGES:
        return None
    
    package = PACKAGES[package_id]
    payment_id = str(uuid.uuid4())
    
    payload = {
        "amount": {
            "value": f"{package['price'] / 100:.2f}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": return_url
        },
        "capture": True,
        "description": f"{package['title']} для Virtual Stylist AI",
        "metadata": {
            "user_id": str(user_id),
            "package_id": package_id,
            "credits": package['credits']
        }
    }
    
    headers = {
        "Authorization": get_auth_header(),
        "Idempotence-Key": payment_id,
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.yookassa.ru/v3/payments",
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "payment_id": data['id'],
                        "confirmation_url": data['confirmation']['confirmation_url'],
                        "amount": package['price'],
                        "credits": package['credits']
                    }
                else:
                    error_text = await response.text()
                    print(f"Ошибка создания платежа: {response.status} - {error_text}")
                    return None
    except Exception as e:
        print(f"Ошибка при обращении к Юкассе: {e}")
        return None

async def check_payment_status(payment_id: str) -> Optional[dict]:
    """
    Проверяет статус платежа в Юкассе
    
    Returns:
        dict со статусом или None при ошибке
    """
    headers = {
        "Authorization": get_auth_header(),
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.yookassa.ru/v3/payments/{payment_id}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "status": data['status'],
                        "paid": data['paid'],
                        "metadata": data.get('metadata', {})
                    }
                return None
    except Exception as e:
        print(f"Ошибка проверки статуса: {e}")
        return None
