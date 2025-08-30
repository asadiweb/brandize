import os
import smtplib
from email.mime.text import MIMEText
from deep_translator import GoogleTranslator
import feedparser
from bs4 import BeautifulSoup

FEED_URL = os.getenv("FEED_URL")
EMAIL_USER = os.getenv("EMAIL_USER")  # ایمیل فرستنده
EMAIL_PASS = os.getenv("EMAIL_APP_PASSWORD")  # App Password
BLOGGER_EMAIL = "xiaomist.com.brandize@blogger.com"

def clean_content(content):
    soup = BeautifulSoup(content, "html.parser")
    for a in soup.find_all("a"):
        a.unwrap()
    return str(soup)

def translate_text(text):
    return GoogleTranslator(source="auto", target="fa").translate(text)

feed = feedparser.parse(FEED_URL)

for entry in feed.entries[:5]:  # فقط ۵ پست آخر
    title_fa = translate_text(entry.title)
    content = getattr(entry, "summary", getattr(entry, "description", ""))
    content_fa = clean_content(translate_text(content))

    msg = MIMEText(content_fa, "html")
    msg["Subject"] = title_fa
    msg["From"] = EMAIL_USER
    msg["To"] = BLOGGER_EMAIL

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print(f"✅ ایمیل ارسال شد: {title_fa}")
    except Exception as e:
        print(f"❌ خطا در ارسال ایمیل '{title_fa}': {e}")
