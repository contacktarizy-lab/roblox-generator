import os
import random
import string
import asyncio
import psycopg2
from datetime import datetime

import httpx
import uvicorn
import disnake
from disnake.ext import commands
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# =====================================================================
# 1. БЕЗОПАСНОЕ ПОДКЛЮЧЕНИЕ К POSTGRESQL (NEON)
# =====================================================================
# На Render обязательно добавьте переменную окружения DATABASE_URL
DB_URL = os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_dFOuDS6ImB9Z@ep-royal-brook-b1vi1tuf-pooler.c-5.eu-central-1.aws.neon.tech/neondb?sslmode=require")

def init_db():
    """Создает таблицу для хранения твинков в облаке Neon"""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                password VARCHAR(50) NOT NULL,
                cookie TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()
        print("⚡ [БД] Успешное подключение к Neon PostgreSQL. Таблицы проверены.")
    except Exception as e:
        print(f"❌ [БД] Ошибка инициализации PostgreSQL: {e}")

def save_account_to_db(username, password, cookie):
    """Сохраняет созданный аккаунт в облачную базу данных"""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO accounts (username, password, cookie) VALUES (%s, %s, %s)",
            (username, password, cookie)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ [БД] Ошибка сохранения в базу: {e}")

def get_total_accounts_count():
    """Возвращает актуальное количество аккаунтов из базы"""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM accounts")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception as e:
        print(f"❌ [БД] Ошибка получения статистики: {e}")
        return 0

# Запускаем проверку базы данных при старте скрипта
init_db()

# =====================================================================
# 2. МОДУЛЬ РЕАЛЬНОЙ РЕГИСТРАЦИИ В ROBLOX
# =====================================================================
def generate_random_string(length=12):
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join(random.choice(letters_and_digits) for _ in range(length))

async def solve_captcha():
    await asyncio.sleep(1)  # Имитация ожидания решения капчи
    return None

async def register_roblox_account():
    """Отправляет запрос на регистрацию аккаунта в Roblox"""
    username = "rbxgen_" + generate_random_string(8).lower()
    password = generate_random_string(14)
    birthday = f"{random.randint(1995, 2005)}-0{random.randint(1, 9)}-{random.randint(10, 28)}T00:00:00.000Z"
    gender = random.choice([1, 2])

    url = "https://roblox.com"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "username": username,
        "password": password,
        "birthday": birthday,
        "gender": gender,
        "isVerify": True
    }

    async with httpx.AsyncClient() as client:
        try:
            # На Render здесь крайне рекомендуется использовать ротируемые прокси
            response = await client.post(url, json=payload, headers=headers, timeout=15.0)
            
            if response.status_code == 200:
                cookie = response.cookies.get(".ROBLOSECURITY", "")
                save_account_to_db(username, password, cookie)
                return {"success": True, "username": username, "password": password, "cookie": cookie}
            else:
                error_data = response.json()
                # Извлекаем текст ошибки, если Roblox требует капчу (Token Validation Failed / Captcha Required)
                error_msg = error_data.get("errors", [{}])[0].get("message", "Требуется обход капчи")
                return {"success": False, "error": error_msg}
        except Exception as e:
            return {"success": False, "error": f"Ошибка сети: {str(e)}"}

# =====================================================================
# 3. НАСТРОЙКА DISCORD БОТА
# =====================================================================
bot = commands.InteractionBot()
RENDER_APP_URL = os.getenv("RENDER_EXTERNAL_URL")

class RegisterView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(label="🚀 Сгенерировать твинк", style=disnake.ButtonStyle.primary, custom_id="gen_account")
    async def generate_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer(ephemeral=True)
        
        result = await register_roblox_account()
        
        if result["success"]:
            embed = disnake.Embed(
                title="✅ Твинк успешно создан!",
                description="Данные успешно записаны в облачную базу данных Neon.",
                color=0x10b981  # Мятно-зеленый неон
            )
            embed.add_field(name="👤 Логин", value=f"`{result['username']}`", inline=True)
            embed.add_field(name="🔑 Пароль", value=f"`{result['password']}`", inline=True)
            embed.set_footer(text=f"rbxgen • Всего в базе Neon: {get_total_accounts_count()}")
            await interaction.edit_original_message(embed=embed)
        else:
            embed = disnake.Embed(
                title="❌ Ошибка создания",
                description=f"Roblox отклонил запрос.\nПричина: `{result['error']}`\n\n*Для полноценного обхода необходимо интегрировать сервис Capsolver и прокси.*",
                color=0xef4444  # Красный неон
            )
            await interaction.edit_original_message(embed=embed)

@bot.slash_command(description="Открыть панель генерации аккаунтов")
async def panel(inter: disnake.ApplicationCommandInteraction):
    embed = disnake.Embed(
        title="🔮 Панель управления rbxgen",
        description="Нажмите на кнопку ниже, чтобы запустить скрипт автоматической регистрации твинка.",
        color=0x8b5cf6
    )
    await inter.response.send_message(embed=embed, view=RegisterView())

# =====================================================================
# 4. НАСТРОЙКА НЕОНОВОГО ВЕБ-САЙТА (FASTAPI)
# =====================================================================
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Каждый раз при обновлении страницы берем точную цифру из Neon DB
    total_accs = get_total_accounts_count()
    
   # =====================================================================
# 4. НАСТРОЙКА НЕОНОВОГО ВЕБ-САЙТА (FASTAPI С ЧИСТЫМ CSS)
# =====================================================================
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    total_accs = get_total_accounts_count()
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>rbxgen | Dashboard</title>
        <style>
            /* Глубокий темный градиент на фоне */
            body {{
                margin: 0;
                padding: 0;
                font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background: radial-gradient(circle at top right, #161224 0%, #0b0c10 100%);
                min-height: min-content;
                height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #ffffff;
                overflow: hidden;
            }}

            /* Карточка с эффектом матового стекла (Glassmorphism) */
            .dashboard-card {{
                background: rgba(255, 255, 255, 0.03);
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 24px;
                padding: 35px;
                width: 100%;
                max-width: 380px;
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4), 0 0 40px rgba(139, 92, 246, 0.05);
            }}

            /* Шапка панели */
            .card-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 30px;
            }}

            .logo {{
                font-size: 24px;
                font-weight: 800;
                letter-spacing: 1px;
                color: #a78bfa;
                margin: 0;
            }}

            .version-tag {{
                font-size: 11px;
                color: #34d399;
                background: rgba(52, 211, 153, 0.1);
                padding: 3px 10px;
                border-radius: 50px;
                border: 1px solid rgba(52, 211, 153, 0.2);
                margin-left: 8px;
                vertical-align: middle;
            }}

            .subtitle {{
                font-size: 13px;
                color: #9ca3af;
            }}

            /* Сетка статистики */
            .stats-grid {{
                display: grid;
                grid-template-cols: 1fr 1fr;
                gap: 15px;
                margin-bottom: 25px;
            }}

            .stat-box {{
                background: rgba(18, 19, 26, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.03);
                border-radius: 16px;
                padding: 15px;
            }}

            .stat-label {{
                font-size: 11px;
                color: #9ca3af;
                margin-bottom: 5px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}

            .stat-value {{
                font-size: 20px;
                font-weight: 700;
            }}

            .text-emerald {{ color: #34d399; }}

            /* Пушечная фиолетовая кнопка с неоновым свечением */
            .gen-button {{
                width: 100%;
                background: #7c3aed;
                color: #ffffff;
                border: none;
                border-radius: 14px;
                padding: 14px 20px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                box-shadow: 0 10px 25px rgba(124, 58, 237, 0.3);
            }}

            .gen-button:hover {{
                background: #6d28d9;
                box-shadow: 0 12px 30px rgba(124, 58, 237, 0.5);
                transform: translateY(-1px);
            }}

            .gen-button:active {{
                transform: translateY(1px);
            }}
        </style>
    </head>
    <body>
        
        <div class="dashboard-card">
            <div class="card-header">
                <h1 class="logo">rbxgen<span class="version-tag">v2.0</span></h1>
                <div class="subtitle">Панель</div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-label">Всего акков</div>
                    <div class="stat-value">{total_accs}</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">База Данных</div>
                    <div class="stat-value text-emerald">Neon Cloud</div>
                </div>
            </div>
            
            <button onclick="alert('Используйте кнопки в вашем Discord боте для генерации твинков!')" class="gen-button">
                ⚡ Сгенерировать твинк
            </button>
        </div>

    </body>
    </html>
    """
    return html_template


@app.get("/health")
async def health_check():
    return {"status": "alive"}

async def keep_alive_pinger():
    await asyncio.sleep(30)
    if not RENDER_APP_URL: return
    async with httpx.AsyncClient() as client:
        while True:
            try: await client.get(f"{RENDER_APP_URL}/health")
            except: pass
            await asyncio.sleep(600)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(bot.start(os.getenv("BOT_TOKEN")))
    asyncio.create_task(keep_alive_pinger())

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
