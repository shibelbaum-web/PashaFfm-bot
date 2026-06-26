import asyncio
import os
import json
import tempfile
from telethon import TelegramClient
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto
import anthropic
import whisper

# ─── НАСТРОЙКИ ───────────────────────────────────────────────
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
CHANNEL = "PashaFm"
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
# ─────────────────────────────────────────────────────────────

print("🔄 Загружаю модель Whisper...")
whisper_model = whisper.load_model("base")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)


async def transcribe_video(client, message):
    """Скачивает видео/кружочек и транскрибирует через Whisper"""
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            path = f.name
        await client.download_media(message, file=path)
        result = whisper_model.transcribe(path, language="ru")
        os.unlink(path)
        return result["text"].strip()
    except Exception as e:
        return f"[Ошибка транскрибации: {e}]"


async def collect_all_content(client):
    """Собирает весь контент канала"""
    print(f"📥 Читаю канал @{CHANNEL}...")
    all_content = []
    count = 0

    async for message in client.iter_messages(CHANNEL, reverse=True):
        count += 1
        date_str = message.date.strftime("%d.%m.%Y")
        text = message.text or message.caption or ""

        entry = {"date": date_str, "type": "text", "content": text}

        # Видеокружочки и видеофайлы
        if message.media and isinstance(message.media, MessageMediaDocument):
            mime = getattr(message.media.document, "mime_type", "")
            if "video" in mime or "audio" in mime:
                print(f"  🎬 Транскрибирую сообщение от {date_str} ({count})...")
                transcript = await transcribe_video(client, message)
                entry["type"] = "video"
                entry["content"] = transcript
                if text:
                    entry["content"] = f"{text}\n[Речь]: {transcript}"

        # Фото — пропускаем, берём только подпись
        elif message.media and isinstance(message.media, MessageMediaPhoto):
            entry["type"] = "photo"
            if not text:
                continue  # фото без подписи пропускаем

        if entry["content"]:
            all_content.append(entry)

    print(f"✅ Собрано {len(all_content)} единиц контента из {count} сообщений")
    return all_content


def make_summary(all_content):
    """Отправляет всё в Claude и получает итоговую выжимку"""
    print("🤖 Анализирую через AI...")

    # Формируем текст для анализа
    digest = ""
    for item in all_content:
        digest += f"[{item['date']} | {item['type']}]\n{item['content']}\n\n"

    # Если контента очень много — берём по частям
    # Ограничиваем до ~80 000 символов (примерно 20 000 слов)
    if len(digest) > 80000:
        digest = digest[:80000] + "\n\n[... контент обрезан для анализа ...]"

    prompt = f"""Ты анализируешь личный Telegram-канал человека по имени Паша (@PashaFm).
Это его искренний видеодневник о жизни с Богом, личных событиях, фильмах и размышлениях.

Вот весь контент канала за период существования:

{digest}

Сделай глубокую и красивую итоговую выжимку по следующим блокам:

1. 🗓 ХРОНОЛОГИЯ — ключевые события и моменты жизни по месяцам
2. 🙏 ДУХОВНЫЙ ПУТЬ — как развивалась тема веры и отношений с Богом
3. 💡 ЗНАНИЯ И ИДЕИ — главные мысли, открытия, умозаключения
4. 🎬 КИНО И КУЛЬТУРА — какие фильмы смотрел, что думал о них
5. 🧭 НАПРАВЛЕНИЕ ДВИЖЕНИЯ — куда движется человек, что меняется в нём

Пиши тепло, искренне, как будто подводишь итог для самого Паши.
Объём: подробный, но ёмкий. На русском языке."""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


async def main():
    print("🚀 Запускаю бота для анализа канала @PashaFm")
    print("=" * 50)

    async with TelegramClient("pasha_session", API_ID, API_HASH) as client:
        all_content = await collect_all_content(client)

        if not all_content:
            print("❌ Контент не найден")
            return

        summary = make_summary(all_content)

        # Сохраняем результат
        with open("итог_канала.txt", "w", encoding="utf-8") as f:
            f.write(summary)

        print("\n" + "=" * 50)
        print("✅ ГОТОВО! Выжимка сохранена в файл 'итог_канала.txt'")
        print("=" * 50)
        print("\n" + summary)


if __name__ == "__main__":
    asyncio.run(main())
