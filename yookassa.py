import os
import uuid
import aiohttp
import base64
from typing import Optional

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")

# Пакеты пополнения баланса (в копейках)
PACKAGES = {
    "250_pack": {"amount": 25000, "title": "250₽", "desc": "→ 5 фото примерок"},
    "500_pack": {"amount": 50000, "title": "500₽", "desc": "→ 12 фото или 5 видео"},
    "1000_pack": {"amount": 100000, "title": "1000₽", "desc": "→ 25 фото или 10 видео"}
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
        package_id: ID пакета (например, "250_pack")
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
            "value": f"{package['amount'] / 100:.2f}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": return_url
        },
        "capture": True,
        "description": f"{package['title']} на баланс Virtual Stylist AI",
        "metadata": {
            "user_id": str(user_id),
            "package_id": package_id,
            "amount": package['amount']
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
                        "amount": package['amount']
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
