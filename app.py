"""
Закрытый веб-сервис с персональным ИИ-ассистентом.
Демо под заказ FL.ru #5528119 (Yandex AI Studio / Alice AI).

Функции:
- чат в браузере (моб + десктоп), история и контекст у каждого пользователя свои
- авторизация по логину/паролю, пользователей заводит админ
- кабинет администратора: добавить/отключить пользователя, сброс пароля, просмотр диалогов
- ответы через Yandex AI Studio (env YANDEX_API_KEY + YANDEX_FOLDER_ID);
  без ключей работает встроенный эхо-режим для проверки интерфейса

Запуск:  pip install flask requests
         python app.py   ->  http://127.0.0.1:5000
Админ по умолчанию: admin / admin123 (поменять через env ADMIN_PASSWORD)
"""
import os, sqlite3, time, functools
from flask import (Flask, request, session, redirect, jsonify,
                   render_template_string, abort, g)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get('DATABASE', os.path.join(APP_DIR, 'assist.db'))

YANDEX_API_KEY  = os.environ.get('YANDEX_API_KEY', '')
YANDEX_FOLDER   = os.environ.get('YANDEX_FOLDER_ID', '')
YANDEX_MODEL    = os.environ.get('YANDEX_MODEL', 'aliceai-llm')
# OpenAI-compatible backend (takes precedence when OPENAI_API_KEY is set):
# works with api.openai.com, OpenRouter, DeepSeek, local Ollama/vLLM, etc.
OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
OPENAI_API_KEY  = os.environ.get('OPENAI_API_KEY', '')
OPENAI_MODEL    = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
SYSTEM_PROMPT   = os.environ.get('SYSTEM_PROMPT',
    'Ты — вежливый персональный ассистент компании. Отвечай коротко и по делу.')

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-me')


# ---------- БД ----------
def db():
    if 'd' not in g:
        g.d = sqlite3.connect(DB)
        g.d.row_factory = sqlite3.Row
    return g.d

@app.teardown_appcontext
def _close(_e=None):
    d = g.pop('d', None)
    if d: d.close()

def init_db():
    d = sqlite3.connect(DB)
    d.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY, login TEXT UNIQUE, pwd TEXT,
      is_admin INTEGER DEFAULT 0, active INTEGER DEFAULT 1,
      created_at TEXT DEFAULT (datetime('now')));
    CREATE TABLE IF NOT EXISTS messages(
      id INTEGER PRIMARY KEY, user_id INTEGER, role TEXT, text TEXT,
      created_at TEXT DEFAULT (datetime('now')));
    """)
    if not d.execute("SELECT 1 FROM users WHERE login='admin'").fetchone():
        d.execute("INSERT INTO users(login,pwd,is_admin) VALUES('admin',?,1)",
                  (os.environ.get('ADMIN_PASSWORD', 'admin123'),))
    d.commit(); d.close()


# ---------- LLM ----------
def llm_reply(user_id, text):
    hist = db().execute(
        "SELECT role,text FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 20",
        (user_id,)).fetchall()
    msgs = [{'role': 'system', 'text': SYSTEM_PROMPT}]
    msgs += [{'role': r['role'], 'text': r['text']} for r in reversed(hist)]
    msgs.append({'role': 'user', 'text': text})

    if OPENAI_API_KEY:
        try:
            import requests
            r = requests.post(
                OPENAI_BASE_URL.rstrip('/') + '/chat/completions',
                headers={'Authorization': 'Bearer ' + OPENAI_API_KEY},
                json={'model': OPENAI_MODEL,
                      'messages': [{'role': m['role'], 'content': m['text']}
                                   for m in msgs],
                      'temperature': 0.5, 'max_tokens': 1000,
                      'stream': False}, timeout=60)
            r.raise_for_status()
            return r.json()['choices'][0]['message']['content']
        except Exception as e:
            return 'Ошибка обращения к модели: %s' % e
    if not (YANDEX_API_KEY and YANDEX_FOLDER):
        time.sleep(0.4)
        return ('[эхо-режим, ключи модели не заданы] Принял: «%s». '
                'После подключения OPENAI_API_KEY или YANDEX_API_KEY/'
                'YANDEX_FOLDER_ID здесь будут ответы модели %s с учётом '
                'истории диалога.' % (text[:200], YANDEX_MODEL))
    try:
        import requests
        r = requests.post(
            'https://llm.api.cloud.yandex.net/foundationModels/v1/completion',
            headers={'Authorization': 'Api-Key ' + YANDEX_API_KEY},
            json={'modelUri': 'gpt://%s/%s' % (YANDEX_FOLDER, YANDEX_MODEL),
                  'completionOptions': {'stream': False, 'temperature': 0.5,
                                        'maxTokens': '1000'},
                  'messages': msgs}, timeout=60)
        r.raise_for_status()
        return r.json()['result']['alternatives'][0]['message']['text']
    except Exception as e:
        return 'Ошибка обращения к модели: %s' % e


# ---------- страницы ----------
BASE = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<title>Ассистент</title>
<style>
body{margin:0;font:15px/1.45 -apple-system,Segoe UI,Arial,sans-serif;background:#0f1117;color:#e8eaf0}
a{color:#7aa2ff}
.hdr{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:#171a23;border-bottom:1px solid #262b3a}
.hdr b{font-size:16px}.hdr a{font-size:13px;margin-left:14px;text-decoration:none}
.chat{max-width:760px;margin:0 auto;padding:14px 12px 90px}
.msg{max-width:82%;padding:10px 13px;border-radius:14px;margin:8px 0;white-space:pre-wrap;word-wrap:break-word}
.u{margin-left:auto;background:#2b5cff;border-bottom-right-radius:4px}
.a{background:#1e2230;border-bottom-left-radius:4px}
.inp{position:fixed;bottom:0;left:0;right:0;display:flex;gap:8px;padding:10px;background:#171a23;border-top:1px solid #262b3a}
.inp input{flex:1;padding:12px 14px;border-radius:10px;border:1px solid #333a4d;background:#0f1117;color:#e8eaf0;font-size:15px}
.inp button{padding:12px 20px;border:0;border-radius:10px;background:#2b5cff;color:#fff;font-size:15px;cursor:pointer}
.box{max-width:360px;margin:12vh auto;padding:26px;background:#171a23;border:1px solid #262b3a;border-radius:14px}
.box input{width:100%;box-sizing:border-box;padding:11px;margin:6px 0;border-radius:9px;border:1px solid #333a4d;background:#0f1117;color:#e8eaf0}
.box button{width:100%;padding:11px;margin-top:8px;border:0;border-radius:9px;background:#2b5cff;color:#fff;cursor:pointer}
table{width:100%;border-collapse:collapse;margin:10px 0}td,th{padding:8px 10px;border-bottom:1px solid #262b3a;text-align:left;font-size:14px}
.badge{padding:2px 8px;border-radius:8px;font-size:12px}.on{background:#14351f;color:#7be495}.off{background:#3a1720;color:#ff8d8d}
.adm{max-width:900px;margin:0 auto;padding:16px}
button.mini{padding:5px 10px;border:0;border-radius:7px;background:#333a4d;color:#e8eaf0;cursor:pointer;font-size:12px}
.err{color:#ff8d8d;font-size:13px}
</style>"""

LOGIN = BASE + """<div class=box><h2 style="margin:0 0 4px">Вход</h2>
<p style="color:#8b91a5;font-size:13px;margin:0 0 14px">Закрытый сервис. Доступ выдаёт администратор.</p>
{% if err %}<p class=err>{{err}}</p>{% endif %}
<form method=post>
<input name=login placeholder="Логин" required>
<input name=pwd type=password placeholder="Пароль" required>
<button>Войти</button></form></div>"""

CHAT = BASE + """<div class=hdr><b>Ассистент</b><div>
<span style="color:#8b91a5;font-size:13px">{{u.login}}</span>
<a href="/logout">Выйти</a></div></div>
<div class=chat id=c>{% for m in msgs %}
<div class="msg {{m.role}}">{{m.text}}</div>{% endfor %}</div>
<form class=inp id=f><input id=t autocomplete=off placeholder="Сообщение…" required autofocus>
<button>➤</button></form>
<script>
const c=document.getElementById('c');c.scrollTop=c.scrollHeight;
document.getElementById('f').onsubmit=async e=>{
 e.preventDefault();const t=document.getElementById('t');if(!t.value.trim())return;
 c.insertAdjacentHTML('beforeend','<div class="msg u">'+t.value.replace(/</g,'&lt;')+'</div>');
 const w=document.createElement('div');w.className='msg a';w.textContent='…';c.append(w);
 c.scrollTop=c.scrollHeight;const q=t.value;t.value='';
 const r=await fetch('/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:q})});
 const d=await r.json();w.textContent=d.text;c.scrollTop=c.scrollHeight;t.focus();}
</script>"""

ADMIN = BASE + """<div class=hdr><b>Админка</b><div><a href="/">Чат</a><a href="/logout">Выйти</a></div></div>
<div class=adm>
<h3 style="margin:6px 0">Пользователи</h3>
<form method=post action="/admin/add" style="display:flex;gap:8px;margin-bottom:8px">
<input name=login placeholder="логин" required style="padding:8px;border-radius:7px;border:1px solid #333a4d;background:#0f1117;color:#e8eaf0">
<input name=pwd placeholder="пароль" required style="padding:8px;border-radius:7px;border:1px solid #333a4d;background:#0f1117;color:#e8eaf0">
<button class=mini style="background:#2b5cff">Добавить</button></form>
<table><tr><th>Логин</th><th>Статус</th><th>Сообщений</th><th></th></tr>
{% for u in users %}<tr><td>{{u.login}}{% if u.is_admin %} 👑{% endif %}</td>
<td><span class="badge {{'on' if u.active else 'off'}}">{{'активен' if u.active else 'отключён'}}</span></td>
<td>{{u.cnt}}</td>
<td>{% if not u.is_admin %}
<a href="/admin/toggle/{{u.id}}"><button class=mini>{{'Отключить' if u.active else 'Включить'}}</button></a>
<a href="/admin/dialog/{{u.id}}"><button class=mini>Диалог</button></a>{% endif %}</td></tr>{% endfor %}
</table></div>"""

DIALOG = BASE + """<div class=hdr><b>Диалог: {{u.login}}</b><div><a href="/admin">← Админка</a></div></div>
<div class=chat>{% for m in msgs %}<div class="msg {{m.role}}">{{m.text}}</div>{% endfor %}</div>"""


# ---------- маршруты ----------
def auth(fn):
    @functools.wraps(fn)
    def w(*a, **k):
        u = db().execute("SELECT * FROM users WHERE id=?", (session.get('uid'),)).fetchone()
        if not u or not u['active']: return redirect('/login')
        g.user = u
        return fn(*a, **k)
    return w

def admin_only(fn):
    @functools.wraps(fn)
    @auth
    def w(*a, **k):
        if not g.user['is_admin']: abort(403)
        return fn(*a, **k)
    return w

@app.route('/login', methods=['GET', 'POST'])
def login():
    err = None
    if request.method == 'POST':
        u = db().execute("SELECT * FROM users WHERE login=? AND pwd=?",
                         (request.form['login'], request.form['pwd'])).fetchone()
        if u and u['active']:
            session['uid'] = u['id']; return redirect('/')
        err = 'Неверный логин/пароль или аккаунт отключён'
    return render_template_string(LOGIN, err=err)

@app.route('/logout')
def logout():
    session.clear(); return redirect('/login')

@app.route('/')
@auth
def chat():
    msgs = db().execute("SELECT role,text FROM messages WHERE user_id=? ORDER BY id",
                        (g.user['id'],)).fetchall()
    return render_template_string(CHAT, u=g.user, msgs=msgs)

@app.route('/send', methods=['POST'])
@auth
def send():
    text = (request.json or {}).get('text', '').strip()[:4000]
    if not text: return jsonify(text='')
    d = db()
    d.execute("INSERT INTO messages(user_id,role,text) VALUES(?,?,?)",
              (g.user['id'], 'u', text))
    d.commit()
    reply = llm_reply(g.user['id'], text)
    d.execute("INSERT INTO messages(user_id,role,text) VALUES(?,?,?)",
              (g.user['id'], 'a', reply))
    d.commit()
    return jsonify(text=reply)

@app.route('/admin')
@admin_only
def admin():
    users = db().execute(
        "SELECT u.*, (SELECT COUNT(*) FROM messages m WHERE m.user_id=u.id) cnt "
        "FROM users u ORDER BY u.id").fetchall()
    return render_template_string(ADMIN, users=users)

@app.route('/admin/add', methods=['POST'])
@admin_only
def admin_add():
    try:
        db().execute("INSERT INTO users(login,pwd) VALUES(?,?)",
                     (request.form['login'], request.form['pwd']))
        db().commit()
    except sqlite3.IntegrityError:
        pass
    return redirect('/admin')

@app.route('/admin/toggle/<int:uid>')
@admin_only
def admin_toggle(uid):
    db().execute("UPDATE users SET active=1-active WHERE id=? AND is_admin=0", (uid,))
    db().commit()
    return redirect('/admin')

@app.route('/admin/dialog/<int:uid>')
@admin_only
def admin_dialog(uid):
    u = db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    msgs = db().execute("SELECT role,text FROM messages WHERE user_id=? ORDER BY id",
                        (uid,)).fetchall()
    return render_template_string(DIALOG, u=u, msgs=msgs)


if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=5000)
