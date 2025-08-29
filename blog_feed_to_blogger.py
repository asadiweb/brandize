import os
import json
import feedparser
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google.oauth2 import service_account
from deep_translator import GoogleTranslator

# 📝 ثابت‌ها
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json")
SCOPES = ["https://www.googleapis.com/auth/blogger"]
BLOG_ID = os.getenv("BLOG_ID")
FEED_URL = os.getenv("FEED_URL")
POSTED_FILE = os.getenv("POSTED_FILE", "posted_titles.json")
IMG_PREFIX = os.getenv("IMG_PREFIX", "")

print("🚀 شروع اجرای اسکریپت بلاگر")

# 📂 بارگذاری لیست پست‌های منتشرشده
if os.path.exists(POSTED_FILE):
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        posted_titles = json.load(f)
else:
    posted_titles = []

# 🔑 گرفتن credentials از service_account.json
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

# 📡 ساخت سرویس بلاگر
service = build("blogger", "v3", credentials=credentials)

# 📥 دریافت خوراک
feed = feedparser.parse(FEED_URL)

for entry in feed.entries:
    title = entry.title.strip()

    # جلوگیری از تکراری بودن
    if title in posted_titles:
        print(f"⏩ پست تکراری رد شد: {title}")
        continue

    # گرفتن محتوای اصلی
    content = entry.get("content", [{"value": entry.get("summary", "")}])[0]["value"]

    # پیدا کردن اولین عکس
    soup = BeautifulSoup(content, "html.parser")
    img_tag = soup.find("img")
    image_url = IMG_PREFIX + img_tag["src"] if img_tag else None

    # ترجمه عنوان و متن
    translated_title = GoogleTranslator(source="auto", target="fa").translate(title)
    translated_content = GoogleTranslator(source="auto", target="fa").translate(soup.get_text())

    # ساخت محتوای پست
    body = {
        "kind": "blogger#post",
        "blog": {"id": BLOG_ID},
        "title": translated_title,
        "content": f"<p>{translated_content}</p>",
    }

    if image_url:
        body["content"] = f'<img src="{image_url}" /><br>{body["content"]}'

    # 📤 ارسال به بلاگر (به صورت درفت)
    post = service.posts().insert(blogId=BLOG_ID, body=body, isDraft=True).execute()
    print(f"✅ پست درفت ایجاد شد: {translated_title}")

    # ذخیره عنوان برای جلوگیری از تکرار
    posted_titles.append(title)
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(posted_titles, f, ensure_ascii=False, indent=2)
