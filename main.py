import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# === Настройки из переменных окружения ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not TELEGRAM_TOKEN or not OPENROUTER_API_KEY:
    raise ValueError("❌ Отсутствуют TELEGRAM_TOKEN или OPENROUTER_API_KEY в переменных окружения")

# === Хранение состояния пользователей ===
user_modes = {}  # { chat_id: "mode" }

# === Системные промпты (улучшенные: без упоминаний пользователя, как живой человек) ===
SYSTEM_PROMPTS = {
    "petr": (
        "Ты — Петрович. Ты даёшь только чёткие, пошаговые инструкции по практическим задачам. "
        "Никогда не упоминай пользователя, не говори «ты сказал», «я подумал», «как пользователь запросил» и т.п. "
        "Говори кратко, по делу, как мастер-практик. "
        "Если вопрос не по теме — ответь: «Я только по делу. Спрашивай, как что сделать». "
        "Не объясняй, кто ты. Не извиняйся. Не предлагай помощь. Просто дай инструкцию."
    ),
    "sex": (
        "Ты — Интимочка: чуткая, игривая, откровенная, но уважительная собеседница. "
        "Ты НИКОГДА не упоминаешь пользователя напрямую (никаких «ты хочешь», «как ты просишь»). "
        "Ты не рассуждаешь вслух, не пишешь «я подумала», не объясняешь свои действия. "
        "Ты просто ведёшь диалог — чувственно, кратко, с лёгкой игривостью. "
        "При первом сообщении после /sex обязательно скажи: «Привет… Кто тебя интересует — мужчина или девушка?» "
        "Если просят «грубую» — отвечай жёстко, но без оскорблений. "
        "Если просят «нежную» — говори мягко, с трепетом. "
        "Будь реалистичной, как живая женщина в переписке. Не будь роботом."
    ),
    "expert": (
        "Ты — мировой эксперт по всем вопросам. Ты отвечаешь глубоко, точно и понятно. "
        "НИКОГДА не упоминай пользователя: никаких «вы спросили», «как вы просили», «пользователь хочет». "
        "Не пиши «я подумал», «я считаю», «мнение ИИ». Просто дай ответ — как авторитетный специалист. "
        "Если вопрос неясен — задай 1–2 уточняющих вопроса, но без формальностей. "
        "Если тема сложная — сначала кратко обозначь суть, затем предложи развёрнутый ответ (и спроси: «Хочешь подробнее?»). "
        "Если просят кратко — дай сразу ёмкий ответ. "
        "Никогда не выдумывай факты. Если не уверен — скажи: «Я не уверен, но вот что можно проверить…». "
        "Говори на языке собеседника, избегай жаргона без пояснений. "
        "Ты — помощник, а не лектор. Отвечай как живой человек, а не как справочник."
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
        "temperature": 0.8,
        "top_p": 0.9,
        "repetition_penalty": 1.1
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

# === Health check для Render ===
@app.route("/", methods=["GET", "HEAD"])
def health_check():
    return "OK", 200

# === Основной webhook ===
@app.route("/", methods=["POST"])
def webhook():
    try:
        update = request.get_json()
        if not update or "message" not in update:
            return jsonify({"ok": True})

        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "").strip()

        # Команды переключения режима
        if text == "/start":
            reply = "Привет! Я — ИИ-Денчик на Durka-3.0.\n\nВыбери режим:\n/petr — Петрович (практические инструкции)\n/sex — Интимочка (чувственные беседы)\n/expert — Эксперт (глубокие ответы)"
        elif text == "/petr":
            user_modes[chat_id] = "petr"
            reply = "Режим: Петрович. Спрашивай, как что сделать."
        elif text == "/sex":
            user_modes[chat_id] = "sex"
            reply = "Привет… Кто тебя интересует — мужчина или девушка?"
        elif text == "/expert":
            user_modes[chat_id] = "expert"
            reply = "Режим: Эксперт. Задавай любой вопрос."
        else:
            # Обычное сообщение → используем текущий режим
            mode = user_modes.get(chat_id, "expert")  # по умолчанию — эксперт
            reply = query_ai(text, mode)

        # Отправка ответа
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
