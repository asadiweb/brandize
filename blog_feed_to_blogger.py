import os
import json
import feedparser
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

# --- تنظیمات محیطی ---
FEED_URL = os.getenv("FEED_URL")
POSTED_FILE = os.getenv("POSTED_FILE", "posted_titles.json")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
BLOGGER_EMAIL = os.getenv("BLOGGER_EMAIL")

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

# --- پردازش محتوا ---
def process_content(entry):
    content_de = getattr(entry, "summary", getattr(entry, "description", ""))
    soup = BeautifulSoup(content_de, "html.parser")

    # پاک کردن لینک‌ها
    for a in soup.find_all("a"):
        a.unwrap()

    return str(soup)

# --- ارسال ایمیل ---
def send_email(subject, content):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = BLOGGER_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(content, 'html'))

        server = smtplib.SMTP('smtp.mail.yahoo.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print(f"✅ ایمیل پیش‌نویس ارسال شد: {subject}")
    except Exception as e:
        print(f"❌ خطا در ارسال ایمیل '{subject}': {e}")

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
            print(f"⏩ قبلاً ارسال شده: {translated_title}")
            continue

        content = process_content(entry)
        translated_content = translate_text(content, "fa")
        send_email(translated_title, translated_content)

        posted_titles[translated_title] = True
        save_posted_titles(posted_titles)

    print("🏁 پایان اجرای اسکریپت")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ خطای غیرمنتظره: {e}")
        exit(1)
