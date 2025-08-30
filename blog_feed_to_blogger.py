import os
import json
import feedparser
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import smtplib
from email.message import EmailMessage
import base64
import datetime

# --- تنظیمات محیطی ---
FEED_URL = os.getenv("FEED_URL")
POSTED_FILE = os.getenv("POSTED_FILE", "posted_titles.json")
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN")
GITHUB_REPO = os.getenv("MY_GITHUB_REPO")
IMG_PREFIX = os.getenv("IMG_PREFIX", "")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
BLOGGER_EMAIL = os.getenv("BLOGGER_EMAIL")  # مثلا 

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

# --- ترجمه متن ---
def translate_text(text, target="fa"):
    try:
        return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception as e:
        print(f"⚠️ خطا در ترجمه: {e}")
        return text

# --- دانلود و آپلود تصویر به GitHub ---
def download_and_rehost_image(url, title, idx):
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return url
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

    # پاک کردن تمام لینک‌ها
    for a in soup.find_all("a"):
        a.unwrap()

    return str(soup)

# --- ارسال ایمیل به بلاگر ---
def send_email(title, content):
    try:
        msg = EmailMessage()
        msg["Subject"] = title
        msg["From"] = EMAIL_USER
        msg["To"] = BLOGGER_EMAIL
        msg.set_content(content, subtype="html")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print(f"✅ ایمیل ارسال شد: {title}")
    except Exception as e:
        print(f"❌ خطا در ارسال ایمیل '{title}': {e}")

# --- اجرای اصلی ---
def main():
    print("🚀 شروع اجرای اسکریپت بلاگر از طریق ایمیل")
    posted_titles = load_posted_titles()
    feed = feedparser.parse(FEED_URL)
    if not feed.entries:
        print("⚠️ هیچ مطلبی در فید پیدا نشد")
        return

    for entry in feed.entries[:5]:  # فقط ۵ پست آخر
        translated_title = translate_text(entry.title, "fa")
        if translated_title in posted_titles:
            print(f"⏩ قبلاً منتشر شده: {translated_title}")
            continue

        content = process_content(entry)
        send_email(translated_title, content)
        posted_titles[translated_title] = True
        save_posted_titles(posted_titles)

    print("🏁 پایان اجرای اسکریپت")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
        exit(1)
