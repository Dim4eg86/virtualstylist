import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    # Создаем таблицу пользователей и админку для тебя
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            balance INT DEFAULT 1,
            is_admin BOOLEAN DEFAULT FALSE
        );
    ''')
    # Делаем тебя админом (твой ID 610820340)
    await conn.execute("INSERT INTO users (user_id, is_admin, balance) VALUES (610820340, TRUE, 999) ON CONFLICT DO NOTHING")
    await conn.close()

async def get_user(user_id):
    conn = await asyncpg.connect(DATABASE_URL)
    user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    if not user:
        await conn.execute("INSERT INTO users (user_id) VALUES ($1)", user_id)
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    await conn.close()
    return user

async def update_balance(user_id, amount):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, user_id)
    await conn.close()