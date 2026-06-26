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

print("Loading Whisper model...")
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
        return "[error: " + str(e) + "]"

async def collect_all_content(client):
    print("Reading channel @" + CHANNEL + "...")
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
                print("Transcribing " + date_str + " (" + str(count) + ")...")
                transcript = await transcribe_video(client, message)
                entry["type"] = "video"
                entry["content"] = transcript
                if text:
                    entry["content"] = text + "\n" + transcript
        elif message.media and isinstance(message.media, MessageMediaPhoto):
            entry["type"] = "photo"
            if not text:
                continue
        if entry["content"]:
            all_content.append(entry)
    print("Done: " + str(len(all_content)) + " items from " + str(count) + " messages")
    return all_content

def make_summary(all_content):
    print("Analyzing with Gemini...")
    digest = ""
    for item in all_content:
        digest += "[" + item["date"] + " | " + item["type"] + "]\n" + item["content"] + "\n\n"
    if len(digest) > 80000:
        digest = digest[:80000] + "\n\n[truncated]"
    
    prompt = (
        "You are analyzing a personal Telegram channel by Pavel (@PashaFm). "
        "This is his sincere video diary about life with God, personal events, movies and thoughts. "
        "Here is all the content:\n\n" + digest + "\n\n"
        "Please write a deep and warm summary IN RUSSIAN with these sections:\n"
        "1. ХРОНОЛОГИЯ - key life events by month\n"
        "2. ДУХОВНЫЙ ПУТЬ - faith and relationship with God\n"
        "3. ЗНАНИЯ И ИДЕИ - main thoughts and discoveries\n"
        "4. КИНО - movies watched and reviews\n"
        "5. НАПРАВЛЕНИЕ - where this person is heading\n\n"
        "Write warmly and sincerely, as if summarizing for Pavel himself."
    )
    
    response = gemini.generate_content(prompt)
    return response.text

async def main():
    print("Starting analysis of @PashaFm")
    async with TelegramClient("pasha_session", API_ID, API_HASH) as client:
        all_content = await collect_all_content(client)
        if not all_content:
            print("No content found")
            return
        summary = make_summary(all_content)
        with open("result.txt", "w", encoding="utf-8") as f:
            f.write(summary)
        print("DONE!")
        print(summary)

if __name__ == "__main__":
    asyncio.run(main())
