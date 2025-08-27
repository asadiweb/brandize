import feedparser
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from deep_translator import GoogleTranslator
import os
import base64
import datetime
import json

# -------------------
# تنظیمات از محیط
# -------------------
BLOG_ID = os.environ.get("BLOG_ID")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
IMG_PREFIX = os.environ.get("IMG_PREFIX")
FEED_URL = os.environ.get("FEED_URL")
POSTED_TITLES_FILE = "posted_titles.json"  # فایل ذخیره عنوان‌ها

# -------------------
# اتصال به Blogger API
# -------------------
def get_service():
    creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/blogger"])
    return build("blogger", "v3", credentials=creds)

service = get_service()
translator = GoogleTranslator(source='de', target='fa')

# -------------------
# پاک کردن لینک‌ها
# -------------------
def clean_links(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    for a in soup.find_all("a"):
        a.unwrap()
    return str(soup)

# -------------------
# آپلود عکس روی GitHub
# -------------------
def upload_image(img_url, title, idx):
    try:
        resp = requests.get(img_url)
        if resp.status_code != 200:
            print(f"⚠️ دانلود عکس {img_url} موفق نبود")
            return img_url
    except:
        return img_url

    ext = img_url.split('.')[-1].split("?")[0]
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{title[:20].replace(' ','_')}_{idx}_{timestamp}.{ext}"
    path_in_repo = f"images/{filename}"

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path_in_repo}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    data = {
        "message": f"upload {filename}",
        "content": base64.b64encode(resp.content).decode("utf-8")
    }

    r = requests.put(api_url, headers=headers, json=data)
    if r.status_code in [200, 201]:
        print(f"✅ عکس آپلود شد: {filename}")
        return f"{IMG_PREFIX}/{filename}"
    else:
        print(f"⚠️ آپلود عکس {filename} موفق نبود")
        return img_url

# -------------------
# بارگذاری/ذخیره عنوان‌های ارسال‌شده
# -------------------
def load_posted_titles():
    if os.path.exists(POSTED_TITLES_FILE):
        with open(POSTED_TITLES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_posted_titles(titles):
    with open(POSTED_TITLES_FILE, "w", encoding="utf-8") as f:
        json.dump(titles, f, ensure_ascii=False, indent=2)

# -------------------
# پردازش فید
# -------------------
posted_titles = load_posted_titles()
feed = feedparser.parse(FEED_URL)

for entry in feed.entries:
    title_de = entry.title
    if title_de in posted_titles:
        print(f"⚠️ پست '{title_de}' قبلاً ارسال شده. رد شد.")
        continue

    content_de = entry.summary if "summary" in entry else entry.description

    # پاک کردن لینک‌ها
    content_clean = clean_links(content_de)

    # آپلود تصاویر
    soup = BeautifulSoup(content_clean, "html.parser")
    imgs = soup.find_all("img")
    for idx, img in enumerate(imgs):
        new_url = upload_image(img["src"], title_de, idx)
        img["src"] = new_url
    final_content = str(soup)

    # ترجمه عنوان و متن
    title_fa = translator.translate(title_de)
    content_fa = translator.translate(final_content)

    # ارسال پیش‌نویس به بلاگر
    post_body = {
        "kind": "blogger#post",
        "title": title_fa,
        "content": content_fa
    }

    post = service.posts().insert(
        blogId=BLOG_ID,
        body=post_body,
        isDraft=True
    ).execute()

    print(f"✅ پست پیش‌نویس ایجاد شد: {post['url']}")

    # ذخیره عنوان در فایل JSON
    posted_titles[title_de] = True
    save_posted_titles(posted_titles)
