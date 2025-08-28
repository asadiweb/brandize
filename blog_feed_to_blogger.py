import os
import json
import feedparser
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google.oauth2 import service_account
from deep_translator import GoogleTranslator
import datetime
import base64

# --- تنظیمات محیطی ---
BLOG_ID = os.getenv("BLOG_ID")
FEED_URL = os.getenv("FEED_URL")
IMG_PREFIX = os.getenv("IMG_PREFIX", "")
POSTED_FILE = os.getenv("POSTED_FILE", "posted_titles.json")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")  # از GitHub Secrets

# --- مدیریت فایل عناوین منتشر شده ---
def load_posted_titles():
    if not os.path.exists(POSTED_FILE):
        return {}
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except Exception as e:
        print(f"⚠️ خطا در خواندن {POSTED_FILE}: {e}")
        return {}

def save_posted_titles(data):
    try:
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ خطا در ذخیره {POSTED_FILE}: {e}")

# --- آماده‌سازی Blogger API ---
def get_blogger_service():
    if GOOGLE_CREDENTIALS:
        info = json.loads(GOOGLE_CREDENTIALS)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/blogger"]
        )
        print("✅ استفاده از GOOGLE_CREDENTIALS")
    elif os.path.exists(SERVICE_ACCOUNT_FILE):
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/blogger"]
        )
        print(f"✅ استفاده از فایل سرویس: {SERVICE_ACCOUNT_FILE}")
    else:
        raise RuntimeError("❌ هیچ کلید سرویس Google پیدا نشد")
    return build("blogger", "v3", credentials=creds)

# --- ترجمه متن ---
def translate_text(text, target="fa"):
    try:
        return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception as e:
        print(f"⚠️ خطا در ترجمه: {e}")
        return text

# --- پاک کردن لینک‌ها ---
def clean_links(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    for a in soup.find_all("a"):
        a.unwrap()
    return str(soup)

# --- دانلود و آپلود تصویر ---
def download_and_rehost_image(url, title="", idx=0):
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            print(f"⚠️ دانلود عکس {url} موفق نبود")
            return url
        # filename و path می‌توان برای آپلود به GitHub یا CDN استفاده شود
        ext = url.split(".")[-1].split("?")[0]
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{title[:20].replace(' ','_')}_{idx}_{timestamp}.{ext}"
        # فعلاً همان URL اصلی برگردانده می‌شود
        return IMG_PREFIX + url if IMG_PREFIX else url
    except Exception as e:
        print(f"⚠️ خطا در دریافت تصویر {url}: {e}")
        return url

# --- پردازش محتوا ---
def process_content(entry):
    content_html = entry.summary if "summary" in entry else entry.description
    content_html = clean_links(content_html)
    soup = BeautifulSoup(content_html, "html.parser")
    for idx, img in enumerate(soup.find_all("img")):
        src = img.get("src")
        if src:
            img["src"] = download_and_rehost_image(src, entry.title, idx)
    return str(soup)

# --- انتشار پست در بلاگر ---
def post_to_blogger(service, title, content, draft=True):
    body = {
        "kind": "blogger#post",
        "blog": {"id": BLOG_ID},
        "title": title,
        "content": content
    }
    try:
        post = service.posts().insert(blogId=BLOG_ID, body=body, isDraft=draft).execute()
        print(f"✅ پست {'پیش‌نویس' if draft else 'منتشر شده'} ایجاد شد: {post['url']}")
        return post
    except Exception as e:
        print(f"❌ خطا در انتشار پست: {e}")
        return None

# --- اجرای اصلی ---
def main():
    try:
        print("🚀 شروع اجرای اسکریپت بلاگر")
        posted_titles = load_posted_titles()
        feed = feedparser.parse(FEED_URL)
        if not feed.entries:
            print("⚠️ هیچ مطلبی در فید پیدا نشد")
            return

        service = get_blogger_service()

        for entry in feed.entries[:5]:  # فقط ۵ پست آخر
            translated_title = translate_text(entry.title, "fa")
            if translated_title in posted_titles:
                print(f"⏩ قبلاً منتشر شده: {translated_title}")
                continue

            content = process_content(entry)
            post = post_to_blogger(service, translated_title, content, draft=True)
            if post:
                posted_titles[translated_title] = post["url"]
                save_posted_titles(posted_titles)

        print("🏁 پایان اجرای اسکریپت")

    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")

if __name__ == "__main__":
    main()
