import asyncio
import os
import tempfile
from telethon import TelegramClient
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto
import whisper
import google.generativeai as genai

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
CHANNEL = "PashaFm"
GEMINI_KEY = os.environ["GEMINI_API_KEY"]

print("🔄 Загружаю модель Whisper...")
whisper_model = whisper.load_model("base")

genai.configure(api_key=GEMINI_KEY)
gemini = genai.GenerativeModel("gemini-1.5-flash")

async def transcribe_video(client, message):
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            path = f.name
        await client.download_media(message, file=path)
        result = whisper_model.transcribe(path, language="ru")
        os.unlink(path)
        return result["text"].strip()
    except Exception as e:
        return f"[Ошибка: {e}]"

async def collect_all_content(client):
    print(f"📥 Читаю канал @{CHANNEL}...")
    all_content = []
    count = 0
    async for message in client.iter_messages(CHANNEL, reverse=True):
        count += 1
        date_str = message.date.strftime("%d.%m.%Y")
        text = message.text or message.caption or ""
        entry = {"date": date_str, "type": "text", "content": text}
        if message.media and isinstance(message.media, MessageMediaDocument):
            mime = getattr(message.media.document, "mime_type", "")
            if "video" in mime or "audio" in mime:
                print(f"  🎬 Транскрибирую {date_str} ({count})...")
                transcript = await transcribe_video(client, message)
                entry["type"] = "video"
                entry["content"] = transcript
                if text:
                    entry["content"] = f"{text}\n[Речь]: {transcript}"
        elif message.media and isinstance(message.media, MessageMediaPhoto):
            entry["type"] = "photo"
            if not text:
                continue
        if entry["content"]:
            all_content.append(entry)
    print(f"✅ Собрано {len(all_content)} из {count} сообщений")
    return all_content

def make_summary(all_content):
    print("🤖 Анализирую через Gemini...")
    digest = ""
    for item in all_content:
        digest += f"[{item['date']} | {item['type']}]\n{item['content']}\n\n"
    if len(digest) > 80000:
        digest = digest[:80000] + "\n\n[... обрезано ...]"
    prompt = f"""Ты анализируешь личный Telegram-канал Паши (@PashaFm).
Это его искренний видеодневник о жизни с Богом, событиях, фильмах и размышлениях.

{digest}

Сделай итоговую выжимку по блокам:
1. 🗓 ХРОНОЛОГИЯ — ключевые события по месяцам
2. 🙏 ДУХОВНЫЙ ПУТЬ — вера и от
