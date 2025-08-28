import os
import json
import feedparser
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from googleapiclient.discovery import build
from google.oauth2 import service_account

# -------------------------
# تنظیمات محیط
# -------------------------
BLOG_ID = os.getenv("BLOG_ID")
FEED_URL = os.getenv("FEED_URL")
IMG_PREFIX = os.getenv("IMG_PREFIX", "")
POSTED_FILE = os.getenv("POSTED_FILE", "posted_titles.json")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")  # متن JSON
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")  # مسیر فایل

print("🚀 شروع اجرای اسکریپت بلاگر")

# -------------------------
# احراز هویت گوگل
# -------------------------
def get_blogger_service():
    if SERVICE_ACCOUNT_FILE and os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"✅ استفاده از فایل سرویس: {SERVICE_ACCOUNT_FILE}")
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/blogger"]
        )
    elif GOOGLE_CREDENTIALS:
        print("✅ استفاده از متن JSON سرویس (GOOGLE_CREDENTIALS)")
        info = json.loads(GOOGLE_CREDENTIALS)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/blogger"]
        )
    else:
        raise RuntimeError("❌ هیچ کلید سرویس گوگل پیدا نشد (SERVICE_ACCOUNT_FILE یا GOOGLE_CREDENTIALS)")
    return build("blogger", "v3", credentials=creds)

# -------------------------
# مدیریت لیست پست‌های منتشرشده
# -------------------------
def load_posted_titles():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted_titles(titles):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(titles), f, ensure_ascii=False, indent=2)

# -------------------------
# پردازش محتوا
# -------------------------
def translate_text(text, target="fa"):
    try:
        return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception as e:
        print(f"⚠️ خطا در ترجمه: {e}")
        return text

def fetch_image(img_url):
    if not img_url:
        return None
    if IMG_PREFIX:
        return f"{IMG_PREFIX}{img_url}"
    return img_url

# -------------------------
# ارسال پست به بلاگر
# -------------------------
def post_to_blogger(service, title, content):
    body = {
        "kind": "blogger#post",
        "blog": {"id": BLOG_ID},
        "title": title,
        "content": content,
    }
    post = service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
    print(f"✅ پست منتشر شد: {post['url']}")

# -------------------------
# اجرای اصلی
# -------------------------
def main():
    try:
        posted_titles = load_posted_titles()
        service = get_blogger_service()

        feed = feedparser.parse(FEED_URL)
        if not feed.entries:
            print("⚠️ هیچ مطلبی در فید پیدا نشد")
            return

        for entry in feed.entries[:5]:  # فقط ۵ تا پست آخر
            title = entry.title
            if title in posted_titles:
                print(f"⏩ قبلاً منتشر شده: {title}")
                continue

            # ترجمه عنوان و محتوا
            translated_title = translate_text(title, "fa")

            summary = entry.get("summary", "")
            translated_summary = translate_text(summary, "fa")

            # تصویر اول (در صورت وجود)
            soup = BeautifulSoup(summary, "html.parser")
            img_tag = soup.find("img")
            img_url = fetch_image(img_tag["src"]) if img_tag else None
            img_html = f'<p><img src="{img_url}" /></p>' if img_url else ""

            content = f"<h2>{translated_title}</h2>\n{img_html}\n<p>{translated_summary}</p>"

            # ارسال به بلاگر
            post_to_blogger(service, translated_title, content)

            # ذخیره عنوان منتشرشده
            posted_titles.add(title)
            save_posted_titles(posted_titles)

    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
        raise

if __name__ == "__main__":
    main()
