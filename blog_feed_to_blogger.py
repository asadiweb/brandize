import feedparser
import json
import os
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from google.oauth2 import service_account
from googleapiclient.discovery import build

# 📌 تنظیمات اولیه
BLOG_ID = os.environ.get("BLOG_ID")
FEED_URL = os.environ.get("FEED_URL")
POSTED_FILE = os.environ.get("POSTED_FILE", "posted_titles.json")
SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE", "service_account.json")

print("🚀 شروع اجرای اسکریپت بلاگر")

# 📌 احراز هویت با Google API
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=["https://www.googleapis.com/auth/blogger"]
)
service = build("blogger", "v3", credentials=credentials)

# 📌 فایل ذخیره عناوین قبلی
if os.path.exists(POSTED_FILE):
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        posted_titles = set(json.load(f))
else:
    posted_titles = set()

# 📌 دریافت RSS
feed = feedparser.parse(FEED_URL)

for entry in feed.entries:
    original_title = entry.title.strip()

    # اگر قبلاً پست شده، رد می‌کنیم
    if original_title in posted_titles:
        print(f"⏭ پست '{original_title}' قبلاً ارسال شده. رد شد.")
        continue

    # استخراج متن محتوا
    if "content" in entry:
        content_html = entry.content[0].value
    elif "summary" in entry:
        content_html = entry.summary
    else:
        content_html = ""

    soup = BeautifulSoup(content_html, "html.parser")
    text_content = soup.get_text(separator="\n")

    # 📌 ترجمه عنوان و محتوا
    translated_title = GoogleTranslator(source="auto", target="fa").translate(original_title)
    translated_content = GoogleTranslator(source="auto", target="fa").translate(text_content)

    # ساختار بدنه پست (الزامی)
    body = {
        "kind": "blogger#post",
        "blog": {"id": BLOG_ID},
        "title": translated_title,
        "content": translated_content
    }

    try:
        # 📌 ارسال پست به صورت پیش‌نویس
        post = service.posts().insert(
            blogId=BLOG_ID,
            body=body,
            isDraft="true"
        ).execute()

        print(f"✅ پست جدید ساخته شد: {translated_title}")

        # ذخیره عنوان برای جلوگیری از تکرار
        posted_titles.add(original_title)
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(list(posted_titles), f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"❌ خطا در ارسال پست '{original_title}': {e}")
