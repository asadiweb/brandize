import os
import json
import feedparser
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google.oauth2 import service_account
from deep_translator import GoogleTranslator

# --- تنظیمات محیطی ---
BLOG_ID = os.getenv("BLOG_ID")
FEED_URL = os.getenv("FEED_URL")
IMG_PREFIX = os.getenv("IMG_PREFIX", "")
POSTED_FILE = os.getenv("POSTED_FILE", "posted_titles.json")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")  # کلید سرویس از GitHub Secrets

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
    if not GOOGLE_CREDENTIALS:
        raise RuntimeError("❌ GOOGLE_CREDENTIALS در محیط تعریف نشده است")
    info = json.loads(GOOGLE_CREDENTIALS)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/blogger"]
    )
    return build("blogger", "v3", credentials=creds)

# --- ترجمه متن (اختیاری) ---
def translate_text(text, target="fa"):
    try:
        return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception as e:
        print(f"⚠️ خطا در ترجمه: {e}")
        return text

# --- دانلود و آپلود تصویر ---
def download_and_rehost_image(url):
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return url  # فعلاً همان URL اصلی برمی‌گرده
    except Exception as e:
        print(f"⚠️ خطا در دریافت تصویر {url}: {e}")
    return url

# --- پردازش محتوا ---
def process_content(entry):
    soup = BeautifulSoup(entry.summary, "html.parser")

    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            new_src = download_and_rehost_image(src)
            img["src"] = IMG_PREFIX + new_src if IMG_PREFIX else new_src

    return str(soup)

# --- انتشار پست در بلاگر ---
def post_to_blogger(service, title, content):
    body = {
        "kind": "blogger#post",
        "blog": {"id": BLOG_ID},
        "title": title,
        "content": content,
    }
    try:
        post = service.posts().insert(blogId=BLOG_ID, body=body, isDraft=False).execute()
        print(f"✅ پست منتشر شد: {post['url']}")
        return post
    except Exception as e:
        print(f"❌ خطا در انتشار پست: {e}")
        return None

# --- اجرای اصلی ---
if __name__ == "__main__":
    try:
        print("🚀 شروع اجرای اسکریپت بلاگر")

        posted_titles = load_posted_titles()
        feed = feedparser.parse(FEED_URL)

        if not feed.entries:
            print("⚠️ هیچ مطلبی در فید پیدا نشد")
            exit(0)

        service = get_blogger_service()

        for entry in feed.entries[:5]:
            title = translate_text(entry.title, "fa")
            if title in posted_titles:
                print(f"⏩ قبلاً منتشر شده: {title}")
                continue

            content = process_content(entry)
            post = post_to_blogger(service, title, content)
            if post:
                posted_titles[title] = post["url"]
                save_posted_titles(posted_titles)

        print("🏁 پایان اجرای اسکریپت")

    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
        exit(1)
