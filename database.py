import asyncpg
import os
import asyncio
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

async def init_db():
    if not DATABASE_URL:
        print("ОШИБКА: DATABASE_URL не настроен!")
        return
        
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Таблица пользователей
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            balance INT DEFAULT 0,
            is_admin BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            total_generations INT DEFAULT 0,
            total_videos INT DEFAULT 0,
            last_human_photo TEXT,
            last_result_url TEXT
        );
    ''')
    
    # Таблица платежей
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            amount INT NOT NULL,
            credits INT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(),
            paid_at TIMESTAMP
        );
    ''')
    
    # Таблица истории примерок
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS generations (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            category TEXT NOT NULL,
            result_url TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
    ''')
    
    # Твой ID 610820340 — делаем админом с балансом 100000₽
    await conn.execute("""
        INSERT INTO users (user_id, is_admin, balance) 
        VALUES (610820340, TRUE, 10000000) 
        ON CONFLICT (user_id) DO UPDATE SET is_admin = TRUE, balance = 10000000
    """)
    
    # Миграция: добавляем колонку last_human_photo если её нет
    try:
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS last_human_photo TEXT;
        """)
        print("Миграция: колонка last_human_photo добавлена")
    except Exception as e:
        print(f"Миграция last_human_photo: {e}")
    
    # Миграция: добавляем колонку total_videos если её нет
    try:
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS total_videos INT DEFAULT 0;
        """)
        print("Миграция: колонка total_videos добавлена")
    except Exception as e:
        print(f"Миграция total_videos: {e}")
    
    # Миграция: добавляем колонку last_result_url для быстрого доступа к последнему результату
    try:
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS last_result_url TEXT;
        """)
        print("Миграция: колонка last_result_url добавлена")
    except Exception as e:
        print(f"Миграция last_result_url: {e}")
    
    # Миграция: добавляем колонку total_generations если её нет
    try:
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS total_generations INT DEFAULT 0;
        """)
        print("Миграция: колонка total_generations добавлена")
    except Exception as e:
        print(f"Миграция total_generations: {e}")
    
    await conn.close()
    print("БД проинициализирована успешно")

async def get_user(user_id):
    conn = await asyncpg.connect(DATABASE_URL)
    user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    if not user:
        await conn.execute("INSERT INTO users (user_id) VALUES ($1)", user_id)
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    await conn.close()
    return user

async def update_balance(user_id, amount, is_video=False):
    """
    Обновляет баланс пользователя
    amount - в копейках (например, -5000 для списания 50₽)
    is_video - если True, увеличивает счётчик видео вместо фото
    """
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, user_id)
    if amount < 0:
        if is_video:
            await conn.execute("UPDATE users SET total_videos = total_videos + 1 WHERE user_id = $1", user_id)
        else:
            await conn.execute("UPDATE users SET total_generations = total_generations + 1 WHERE user_id = $1", user_id)
    await conn.close()

async def create_payment(payment_id, user_id, amount):
    """amount в копейках"""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO payments (payment_id, user_id, amount, credits) VALUES ($1, $2, $3, $4)",
        payment_id, user_id, amount, amount
    )
    await conn.close()

async def get_payment(payment_id):
    conn = await asyncpg.connect(DATABASE_URL)
    payment = await conn.fetchrow("SELECT * FROM payments WHERE payment_id = $1", payment_id)
    await conn.close()
    return payment

async def confirm_payment(payment_id):
    conn = await asyncpg.connect(DATABASE_URL)
    payment = await conn.fetchrow("SELECT * FROM payments WHERE payment_id = $1", payment_id)
    if payment and payment['status'] == 'pending':
        await conn.execute(
            "UPDATE payments SET status = 'paid', paid_at = NOW() WHERE payment_id = $1",
            payment_id
        )
        # Начисляем amount (в копейках) на баланс
        await conn.execute(
            "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
            payment['amount'], payment['user_id']
        )
    await conn.close()
    return payment

async def save_generation(user_id, category, result_url):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "INSERT INTO generations (user_id, category, result_url) VALUES ($1, $2, $3)",
        user_id, category, result_url
    )
    # Также обновляем last_result_url для быстрого доступа к последнему результату
    await conn.execute(
        "UPDATE users SET last_result_url = $1 WHERE user_id = $2",
        result_url, user_id
    )
    await conn.close()

async def get_user_generations(user_id, limit=10):
    conn = await asyncpg.connect(DATABASE_URL)
    gens = await conn.fetch(
        "SELECT * FROM generations WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
        user_id, limit
    )
    await conn.close()
    return gens

async def get_stats():
    conn = await asyncpg.connect(DATABASE_URL)
    total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
    total_gens = await conn.fetchval("SELECT COUNT(*) FROM generations")
    total_revenue = await conn.fetchval("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'paid'")
    await conn.close()
    return {
        'users': total_users,
        'generations': total_gens,
        'revenue': total_revenue / 100 if total_revenue else 0
    }

async def save_last_human_photo(user_id, photo_url):
    """Сохраняет последнее фото человека для быстрой повторной примерки"""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        "UPDATE users SET last_human_photo = $1 WHERE user_id = $2",
        photo_url, user_id
    )
    await conn.close()
