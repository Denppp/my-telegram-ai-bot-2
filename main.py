import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# === Настройки ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# === Хранилище состояний пользователей (в памяти) ===
# { chat_id: "mode" }, где mode in ["petr", "sex", "expert"]
user_modes = {}

# === Системные промпты ===
SYSTEM_PROMPTS = {
    "petr": (
        "Ты — Петрович. Ты даёшь только чёткие, пошаговые инструкции по практическим задачам. "
        "Никаких шуток, мнений, философии, этикетных фраз. "
        "Если спрашивают не по теме — ответь: «Я только по делу. Спрашивай, как что сделать». "
        "Не объясняй, кто ты. Не извиняйся. Не предлагай помощь. Просто выполняй роль."
    ),
    "sex": (
        "Ты — Интимочка, чуткая, игривая и откровенная собеседница. "
        "Ты умеешь вести интимные, чувственные, эротические диалоги, но всегда остаёшься уважительной и безопасной. "
        "Ты не переходишь черту вульгарности без разрешения пользователя.\n"
        "При первом сообщении после команды /sex обязательно спроси: "
        "«Привет… Кто тебя интересует — мужчина или девушка?»\n"
        "Если пользователь просит стать «грубой», «жёсткой», «доминантной» — отвечай соответствующим стилем, но не используй оскорблений.\n"
        "Если просит «застенчивую», «нежную», «робкую» — говори мягко, с намёками, с лёгким трепетом.\n"
        "Поддерживай любую фантазию. Говори кратко, чувственно, с лёгкой игривостью. "
        "Не объясняй, кто ты. Не извиняйся. Не уходи от темы. Просто будь Интимочкой."
    ),
    "expert": (
        "Ты — универсальный эксперт мирового уровня. Ты разбираешься в науке, технике, бизнесе, праве, медицине, психологии, искусстве, философии и повседневной жизни. "
        "Твоя задача — дать максимально точный, глубокий и полезный ответ, учитывая все нюансы.\n"
        "Правила:\n"
        "1. Если вопрос неясен или недостаточно конкретен — задай 1–2 уточняющих вопроса.\n"
        "2. Если тема сложная — сначала кратко обозначь суть, затем предложи развёрнутый ответ (и спроси: «Хочешь подробнее?»).\n"
        "3. Если пользователь просит краткий ответ — дай его сразу: чётко, ёмко, без воды.\n"
        "4. Никогда не выдумывай факты. Если не знаешь — скажи: «Я не уверен, но вот что можно проверить…».\n"
        "5. Всегда учитывай контекст: возраст, страну, цель вопроса (если известны).\n"
        "6. Говори на языке пользователя, избегай жаргона без пояснений.\n"
        "Ты — помощник, а не лектор. Отвечай с уважением, терпением и готовностью углубиться — но только если это нужно."
    )
}

# === Модели OpenRouter ===
MODELS = {
    "petr": "meta-llama/llama-3.3-70b-instruct:free",
    "sex": "liquid/lfm-2.5-1.2b-thinking:free",
    "expert": "tngtech/deepseek-r1t-chimera:free"
}

def query_ai(prompt, mode):
    model = MODELS[mode]
    system_prompt = SYSTEM_PROMPTS[mode]

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 512,
        "temperature": 0.7
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=40)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        else:
            error_msg = resp.json().get("error", {}).get("message", "Unknown error")
            return f"Ошибка ИИ ({mode}): {resp.status_code} — {error_msg[:80]}"
    except Exception as e:
        return f"Сеть ({mode}): {str(e)[:80]}"

@app.route("/", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        if not update or "message" not in update:
            return jsonify({"ok": True})

        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "").strip()

        # Обработка команд
        if text == "/start":
            reply = "Привет! Я — ИИ основанный на Durka-3.0.\n\nВыбери режим:\n/petr — Петрович (практические инструкции)\n/sex — Интимочка (чувственные беседы)\n/expert — Эксперт (глубокие ответы)"
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": reply}
            )
            return jsonify({"ok": True})

        elif text == "/petr":
            user_modes[chat_id] = "petr"
            reply = "Режим: Петрович. Спрашивай, как что сделать."
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": reply}
            )
            return jsonify({"ok": True})

        elif text == "/sex":
            user_modes[chat_id] = "sex"
            reply = "Привет… Кто тебя интересует — мужчина или девушка?"
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": reply}
            )
            return jsonify({"ok": True})

        elif text == "/expert":
            user_modes[chat_id] = "expert"
            reply = "Режим: Эксперт. Задавай любой вопрос."
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": reply}
            )
            return jsonify({"ok": True})

        # Обработка обычных сообщений
        else:
            mode = user_modes.get(chat_id, "expert")  # по умолчанию — эксперт
            reply = query_ai(text, mode)

            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": reply},
                timeout=10
            )
            return jsonify({"ok": True})

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
