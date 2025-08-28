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
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")  # کلید سرویس از GitHub Secrets
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
GITHUB_REPO = os.getenv("MY_GITHUB_REPO")

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

# --- ترجمه متن ---
def translate_text(text, target="fa"):
    try:
        return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception as e:
        print(f"⚠️ خطا در ترجمه: {e}")
        return text

# --- دانلود و آپلود تصویر (فعلاً همان URL برگشت داده می‌شود) ---
def download_and_rehost_image(url, title, idx):
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return url
        # اگر میخوای تصویر روی GitHub آپلود بشه، اینجا اضافه کن
        ext = url.split(".")[-1].split("?")[0]
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{title[:20].replace(' ','_')}_{idx}_{timestamp}.{ext}"
        path_in_repo = f"images/{filename}"

        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path_in_repo}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        data = {"message": f"upload {filename}",
                "content": base64.b64encode(resp.content).decode("utf-8")}

        r = requests.put(api_url, headers=headers, json=data)
        if r.status_code in [200, 201]:
            print(f"✅ عکس آپلود شد: {filename}")
            return f"{IMG_PREFIX}/{filename}" if IMG_PREFIX else f"{filename}"
        else:
            print(f"⚠️ آپلود عکس {filename} موفق نبود: {r.text}")
            return url
    except Exception as e:
        print(f"⚠️ خطا در دریافت تصویر {url}: {e}")
        return url

# --- پردازش محتوا ---
def process_content(entry):
    content_de = getattr(entry, "summary", getattr(entry, "description", ""))
    soup = BeautifulSoup(content_de, "html.parser")

    # اصلاح لینک تصاویر
    for idx, img in enumerate(soup.find_all("img")):
        src = img.get("src")
        if src:
            img["src"] = download_and_rehost_image(src, entry.title, idx)

    # پاک کردن لینک‌ها
    for a in soup.find_all("a"):
        a.unwrap()

    return str(soup)

# --- انتشار پست در بلاگر ---
def post_to_blogger(service, title, content):
    body = {
        "kind": "blogger#post",
        "title": title,
        "content": content
    }
    try:
        post = service.posts().insert(blogId=BLOG_ID, body=body, isDraft=True).execute()
        print(f"✅ پست پیش‌نویس ایجاد شد: {post['url']}")
        return post
    except Exception as e:
        print(f"❌ خطا در انتشار پست: {e}")
        return None

# --- اجرای اصلی ---
def main():
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
        post_to_blogger(service, translated_title, content)
        posted_titles[translated_title] = True
        save_posted_titles(posted_titles)

    print("🏁 پایان اجرای اسکریپت")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
        exit(1)
