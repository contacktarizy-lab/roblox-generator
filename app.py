import os
import io
import random
import string
import asyncio
import sqlite3
from datetime import datetime

import httpx
import uvicorn
import disnake
from disnake.ext import commands
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# =====================================================================
# 1. ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (SQLite)
# =====================================================================
DB_FILE = "database.db"

def init_db():
    """Создает таблицу для хранения твинков, если её еще нет"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            cookie TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_account_to_db(username, password, cookie):
    """Сохраняет созданный аккаунт в базу данных"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO accounts (username, password, cookie, created_at) VALUES (?, ?, ?, ?)",
        (username, password, cookie, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_total_accounts_count():
    """Возвращает общее количество аккаунтов в базе"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM accounts")
    count = cursor.fetchone()[0]
    conn.close()
    return count

init_db()

# =====================================================================
# 2. МОДУЛЬ РЕАЛЬНОЙ РЕГИСТРАЦИИ В ROBLOX
# =====================================================================
def generate_random_string(length=12):
    """Генерирует случайный пароль или часть никнейма"""
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join(random.choice(letters_and_digits) for _ in range(length))

async def solve_captcha():
    """
    Заглушка для интеграции сервиса решения капчи (Capsolver / Anti-Captcha).
    Roblox требует валидный токен FunCaptcha для успешного signup запроса.
    """
    # Здесь должен быть ваш API-запрос к сервису разгадывания капчи.
    # Пример для Capsolver (получение token):
    # return "your_arkose_labs_solved_token_here"
    await asyncio.sleep(2)  # Имитация ожидания решения капчи
    return None

async def register_roblox_account():
    """Отправляет реальный запрос на регистрацию аккаунта в Roblox"""
    # Генерируем случайные валидные данные
    username = "rbxgen_" + generate_random_string(8).lower()
    password = generate_random_string(14)
    birthday = f"{random.randint(1995, 2005)}-0{random.randint(1, 9)}-{random.randint(10, 28)}T00:00:00.000Z"
    gender = random.choice([1, 2]) # 1 - Женский, 2 - Мужской

    # Пытаемся решить капчу
    captcha_token = await solve_captcha()
    
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
        "isVerify": True,
        # "captchaToken": captcha_token,  # Раскомментировать, когда подключите решение капчи
        # "captchaProvider": "ARKOS_LABS"
    }

    # На Render крайне важно использовать Прокси, иначе Roblox заблокирует IP хостинга
    async with httpx.AsyncClient() as client:
        try:
            # Для реальной работы раскомментируйте строку с прокси:
            # client.proxies = {"all://": "http://user:pass@proxy_ip:port"}
            
            response = await client.post(url, json=payload, headers=headers, timeout=15.0)
            
            if response.status_code == 200:
                data = response.json()
                # Извлекаем куку .ROBLOSECURITY из ответа, если она пришла в заголовках set-cookie
                cookie = response.cookies.get(".ROBLOSECURITY", "")
                
                # Сохраняем в нашу базу данных
                save_account_to_db(username, password, cookie)
                return {"success": True, "username": username, "password": password, "cookie": cookie}
            else:
                # Если Roblox выдал ошибку (например, требуется капча)
                error_data = response.json()
                return {"success": False, "error": error_data.get("errors", [DefaultError])[0].get("message", "Unknown error")}
        except Exception as e:
            return {"success": False, "error": f"Ошибка запроса: {str(e)}"}

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
        # Переводим взаимодействие в режим ожидания, чтобы не было ошибки таймаута Discord (3 секунды)
        await interaction.response.defer(ephemeral=True)
        
        # Запуск функции реальной регистрации
        result = await register_roblox_account()
        
        if result["success"]:
            embed = disnake.Embed(
                title="✅ Твинк успешно создан!",
                description="Аккаунт добавлен в общую базу данных сайта.",
                color=0x10b981 # Мятно-зеленый неон
            )
            embed.add_field(name="👤 Логин", value=f"`{result['username']}`", inline=True)
            embed.add_field(name="🔑 Пароль", value=f"`{result['password']}`", inline=True)
            embed.set_footer(text=f"rbxgen • Всего в базе: {get_total_accounts_count()}")
            await interaction.edit_original_message(embed=embed)
        else:
            # Сообщение об ошибке (например, если заблокировал IP или не прошла капча)
            embed = disnake.Embed(
                title="❌ Ошибка создания",
                description=f"Не удалось зарегистрировать аккаунт.\nПричина: `{result['error']}`\n\n*Примечание: Для полноценного обхода требуется настроить прокси и токен капчи в коде.*",
                color=0xef4444 # Красный неон
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
# 4. НАСТРОЙКА ВЕБ-САЙТА (FASTAPI + ВЫВОД ИЗ DB)
# =====================================================================
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    # Перед загрузкой страницы берём свежие данные из нашей базы данных
    total_accs = get_total_accounts_count()
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>rbxgen | Dashboard</title>
        <script src="https://tailwindcss.com"></script>
    </head>
    <body class="bg-gradient-to-tr from-[#0b0c10] via-[#161224] to-[#0b0c10] min-h-screen text-white font-sans flex items-center justify-center">
        <div class="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-8 w-full max-w-md shadow-2xl shadow-purple-500/10">
            <div class="flex items-center justify-between mb-8">
                <h1 class="text-2xl font-bold tracking-wider text-purple-400">rbxgen <span class="text-xs text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded-full border border-emerald-500/20">v2.0</span></h1>
                <div class="text-sm text-gray-400">Панель твинков</div>
            </div>
            <div class="grid grid-cols-2 gap-4 mb-6">
                <div class="bg-[#12131a]/60 border border-white/5 rounded-2xl p-4">
                    <div class="text-xs text-gray-400 mb-1">Всего аккаунтов</div>
                    <div class="text-xl font-bold text-white">{total_accs}</div>
                </div>
                <div class="bg-[#12131a]/60 border border-white/5 rounded-2xl p-4">
                    <div class="text-xs text-gray-400 mb-1">База Данных</div>
                    <div class="text-xl font-bold text-purple-400">SQLite (OK)</div>
                </div>
            </div>
            <button onclick="alert('Для генерации через сайт настройте API эндпоинт, либо используйте кнопку в Discord боте!')" class="w-full bg-purple-600 hover:bg-purple-500 text-white font-medium py-3.5 px-4 rounded-xl transition duration-300 shadow-lg shadow-purple-600/30 active:scale-[0.98]">
                ⚡ Сгенерировать новый аккаунт
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
    if name == "main":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
