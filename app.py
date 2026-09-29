from flask import Flask, render_template_string, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "roblox.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

ADMIN_PASSWORD = "SUPER_SECRET_PASSWORD"


class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(255), unique=True, nullable=False)
    is_given = db.Column(db.Boolean, default=False)


class ClaimLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), nullable=False)
    claimed_at = db.Column(db.DateTime, default=datetime.utcnow)


MAIN_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Roblox Account Generator</title>
    <link href="https://googleapis.com" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Poppins', sans-serif; }
        body { 
            background: radial-gradient(circle at center, #1e2024 0%, #111215 100%); 
            color: #ffffff; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            padding: 40px 30px;
            max-width: 480px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 40px rgba(0,0,0,0.5);
            backdrop-filter: blur(10px);
        }
        .logo-box {
            font-size: 32px;
            font-weight: 700;
            letter-spacing: 1px;
            margin-bottom: 10px;
            color: #ffffff;
            text-transform: uppercase;
        }
        .logo-box span { color: #00b060; }
        .subtitle { color: #8a8f98; font-size: 14px; margin-bottom: 30px; }

        .counter-badge {
            background: rgba(0, 176, 96, 0.1);
            border: 1px solid rgba(0, 176, 96, 0.3);
            color: #00b060;
            padding: 8px 16px;
            border-radius: 50px;
            font-size: 14px;
            font-weight: 600;
            display: inline-block;
            margin-bottom: 30px;
        }

        .btn-claim {
            width: 100%;
            padding: 16px;
            font-size: 16px;
            font-weight: 600;
            background: #00b060;
            color: white;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 6px 20px rgba(0, 176, 96, 0.3);
        }
        .btn-claim:hover { background: #009652; transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0, 176, 96, 0.4); }
        .btn-claim:active { transform: translateY(1px); }

        .result-box {
            margin-top: 25px;
            padding: 15px;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 600;
            line-height: 1.6;
        }
        .success-box {
            background: rgba(0, 176, 96, 0.1);
            border: 1px solid #00b060;
            color: #ffffff;
        }
        .acc-display {
            background: rgba(0,0,0,0.3);
            border: 1px dashed rgba(255,255,255,0.2);
            padding: 10px;
            margin-top: 10px;
            font-family: monospace;
            font-size: 16px;
            color: #ffca28;
            border-radius: 6px;
            user-select: all;
        }
        .error-box {
            background: rgba(239, 83, 80, 0.1);
            border: 1px solid #ef5350;
            color: #ef5350;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo-box">ROBLOX<span>GEN</span></div>
        <p class="subtitle">Получай по 1 твинку каждые 24 часа в одни руки</p>

        <div class="counter-badge">Доступно аккаунтов: {{ count }} шт.</div>

        <form action="/claim" method="post">
            <button type="submit" class="btn-claim">🔥 Забрать аккаунт</button>
        </form>

        {% if message %}
            {% if 'Ошибка' in message %}
                <div class="result-box error-box">{{ message }}</div>
            {% else %}
                <div class="result-box success-box">
                    <div>Твой аккаунт успешно выдан! Копируй ниже:</div>
                    <div class="acc-display">{{ message }}</div>
                </div>
            {% endif %}
        {% endif %}
    </div>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Панель управления</title>
    <link href="https://googleapis.com" rel="stylesheet">
    <style>
        body { font-family: 'Poppins', sans-serif; background: #f4f6f9; color: #333; padding: 40px 20px; }
        .admin-card {
            background: white;
            max-width: 550px;
            margin: 0 auto;
            padding: 30px;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.05);
        }
        h2 { margin-bottom: 20px; font-size: 22px; color: #111; }
        input[type="password"], textarea {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 14px;
            box-sizing: border-box;
        }
        textarea { font-family: monospace; resize: vertical; }
        button {
            background: #111;
            color: white;
            border: none;
            padding: 14px 20px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            font-size: 15px;
        }
        button:hover { background: #222; }
        .status-msg {
            padding: 12px;
            border-radius: 8px;
            margin-top: 15px;
            font-size: 14px;
            font-weight: 600;
        }
        .status-success { background: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9; }
        .status-error { background: #ffebee; color: #c62828; border: 1px solid #ffcdd2; }
        .links { margin-top: 20px; text-align: center; }
        .links a { color: #666; text-decoration: none; font-size: 14px; }
        .links a:hover { color: #111; }
    </style>
</head>
<body>
    <div class="admin-card">
        <h2>📥 Загрузка новой партии аккаунтов</h2>
        <form action="/admin" method="post">
            <input type="password" name="password" placeholder="Введите секретный пароль" required>
            <textarea name="accounts" rows="8" placeholder="Вставьте список в формате логин:пароль&#10;Каждый аккаунт с новой строки" required></textarea>
            <button type="submit">Загрузить данные в базу</button>
        </form>

        {% if msg %}
            <div class="status-msg {% if 'Ошибка' in msg %}status-error{% else %}status-success{% endif %}">
                {{ msg }}
            </div>
        {% endif %}

        <div class="links">
            <a href="/">← На главную страницу раздачи</a>
        </div>
    </div>
</body>
</html>
"""


def get_avail_count():
    try:
        return Account.query.filter_by(is_given=False).count()
    except:
        return 0


@app.route('/')
def index():
    return render_template_string(MAIN_HTML, count=get_avail_count())


@app.route('/claim', methods=['POST'])
def claim_account():
    user_ip = request.remote_addr
    avail_count = get_avail_count()

    try:
        time_threshold = datetime.utcnow() - timedelta(hours=24)
        recent_claim = ClaimLog.query.filter(ClaimLog.ip_address == user_ip,
                                             ClaimLog.claimed_at > time_threshold).first()

        if recent_claim:
            return render_template_string(MAIN_HTML,
                                          message="Ошибка: Лимит! Вы уже забирали аккаунт сегодня. Возвращайтесь через 24 часа.",
                                          count=avail_count)

        available_acc = Account.query.filter_by(is_given=False).first()

        if not available_acc:
            return render_template_string(MAIN_HTML,
                                          message="Ошибка: Все аккаунты закончились! Подождите, пока админ добавит новые.",
                                          count=avail_count)

        available_acc.is_given = True
        new_log = ClaimLog(ip_address=user_ip)
        db.session.add(new_log)
        db.session.commit()

        # Обновляем счетчик после выдачи
        return render_template_string(MAIN_HTML, message=available_acc.data, count=get_avail_count())
    except Exception as e:
        return render_template_string(MAIN_HTML, message="Ошибка базы данных. Обновите страницу админки.",
                                      count=avail_count)


@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    msg = ""
    if request.method == 'POST':
        password = request.form.get('password')
        if password != ADMIN_PASSWORD:
            return "Неверный пароль админа!", 403

        raw_accounts = request.form.get('accounts', '')
        lines = raw_accounts.strip().split('\n')

        try:
            added_count = 0
            for line in lines:
                line = line.strip()
                if line:
                    exists = Account.query.filter_by(data=line).first()
                    if not exists:
                        new_acc = Account(data=line)
                        db.session.add(new_acc)
                        added_count += 1
            db.session.commit()
            msg = f"Успешно добавлено новых аккаунтов: {added_count} шт."
        except Exception as e:
            db.session.rollback()
            msg = f"Ошибка при сохранении: {str(e)}."

    return render_template_string(ADMIN_HTML, msg=msg)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port, debug=True)

