"""
Модуль для работы с платежами через ЮKassa
"""

# Пакеты для пополнения баланса
PACKAGES = {
    "test_pack": {
        "title": "🧪 Тест",
        "desc": "(10₽ = 1 примерка)",
        "amount": 1000,  # в копейках
        "credits": 1  # количество примерок
    },
    "150_3photo": {
        "title": "📸 3 фото-примерки",
        "desc": "(150₽)",
        "amount": 15000,
        "credits": 3
    },
    "150_1video": {
        "title": "🎬 1 видео-примерка",
        "desc": "(150₽)",
        "amount": 15000,
        "credits": 150  # 150₽ на балансе для видео
    },
    "250_pack": {
        "title": "💎 Стартовый",
        "desc": "(250₽ = 5 примерок)",
        "amount": 25000,
        "credits": 5
    },
    "500_pack": {
        "title": "⭐ Популярный",
        "desc": "(500₽ = 10 примерок + 1 бонус)",
        "amount": 50000,
        "credits": 11
    },
    "1000_pack": {
        "title": "👑 Премиум",
        "desc": "(1000₽ = 20 примерок + 3 бонус)",
        "amount": 100000,
        "credits": 23
    }
}

def create_payment(package_id, user_id, return_url):
    """
    Создает платеж через ЮKassa
    
    Args:
        package_id: ID пакета из PACKAGES
        user_id: Telegram user ID
        return_url: URL для возврата после оплаты
    
    Returns:
        dict: {'payment_id': str, 'confirmation_url': str, 'amount': int}
        или None в случае ошибки
    """
    import os
    from yookassa import Configuration, Payment
    import uuid
    
    if package_id not in PACKAGES:
        print(f"ERROR: Неизвестный package_id: {package_id}")
        return None
    
    package = PACKAGES[package_id]
    
    # Настройка API ЮKassa
    Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
    Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")
    
    try:
        # Создаем платеж
        payment = Payment.create({
            "amount": {
                "value": f"{package['amount'] / 100:.2f}",
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
        }, uuid.uuid4())
        
        return {
            "payment_id": payment.id,
            "confirmation_url": payment.confirmation.confirmation_url,
            "amount": package['amount']
        }
        
    except Exception as e:
        print(f"ERROR creating payment: {e}")
        return None
