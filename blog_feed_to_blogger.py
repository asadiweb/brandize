import os
import json
import time
import hashlib
import feedparser
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

# -------------------
# تنظیمات
# -------------------
FEED_URL = os.getenv("FEED_URL")
ZAPIER_WEBHOOK_URL = os.getenv("ZAPIER_WEBHOOK_URL")  # Catch Hook
POSTED_FILE = os.getenv("POSTED_FILE", "posted_titles.json")
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "5"))  # چند پست اخیر
SLEEP_BETWEEN = float(os.getenv("SLEEP_BETWEEN", "0.7"))  # فاصله بین ترجمه‌ها (ثانیه)

if not FEED_URL or not ZAPIER_WEBHOOK_URL:
    raise RuntimeError("FEED_URL یا ZAPIER_WEBHOOK_URL تنظیم نشده‌اند.")

translator = GoogleTranslator(source="auto", target="fa")

# -------------------
# فایل ثبت عناوین/آیتم‌های ارسال‌شده
# -------------------
def load_posted():
    if not os.path.exists(POSTED_FILE):
        return {}
    try:
        with open(POSTED_FILE, "r", encoding="utf-8") as f:
            txt = f.read().strip()
            return json.loads(txt) if txt else {}
    except Exception as e:
        print(f"⚠️ خطا در خواندن {POSTED_FILE}: {e}")
        return {}

def save_posted(d):
    try:
        with open(POSTED_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ خطا در ذخیره {POSTED_FILE}: {e}")

# کلید یکتا برای هر آیتم (ترجیحاً لینک یا id)
def entry_key(entry):
    base = getattr(entry, "id", "") or getattr(entry, "link", "") or getattr(entry, "title", "")
    if not base:
        base = repr(entry)[:200]
    return hashlib.sha1(base.encode("utf-8")).hexdigest()

# -------------------
# پاکسازی HTML: حذف لینک‌ها و نگه‌داشتن متن و تصاویر
# -------------------
def clean_links(html):
    soup = BeautifulSoup(html or "", "html.parser")
    for a in soup.find_all("a"):
        a.unwrap()  # فقط متنِ داخل لینک می‌ماند
    return str(soup)

# -------------------
# ترجمه عنوان
# -------------------
def translate_title(title):
    try:
        return translator.translate(title) if title else title
    except Exception as e:
        print(f"⚠️ خطا در ترجمه عنوان: {e}")
        return title

# -------------------
# ترجمه محتوا با شکستن به بلوک‌های کوتاه (برای عبور از محدودیت 5000 کاراکتر)
# رویکرد: متن‌های داخل تگ‌ها (NavigableString) را جداگانه ترجمه می‌کنیم
# -------------------
def translate_html_blocks(html):
    soup = BeautifulSoup(html or "", "html.parser")

    # تگ‌هایی که نباید ترجمه شوند
    skip_tags = {"code", "pre", "script", "style"}
    text_nodes = []

    for elem in soup.find_all(text=True):
        parent = elem.parent.name if elem.parent else ""
        txt = str(elem)
        if parent in skip_tags:
            continue
        # بی‌معناها رو رد کن
        if not txt.strip():
            continue
        text_nodes.append((elem, txt))

    for node, txt in text_nodes:
        # بلوک‌های بزرگ رو به پاراگراف/جمله بشکنیم
        parts = split_text_safely(txt, max_len=4000)
        out = []
        for p in parts:
            tr = safe_translate(p)
            out.append(tr)
            time.sleep(SLEEP_BETWEEN)
        node.replace_with("".join(out))

    return str(soup)

def split_text_safely(text, max_len=4000):
    """
    تلاش می‌کند متن را از روی خطوط/جملات به قطعات <= max_len بشکند.
    """
    if len(text) <= max_len:
        return [text]

    chunks = []
    buf = []
    buf_len = 0

    # اول با \n بشکنیم
    paragraphs = text.split("\n")
    for para in paragraphs:
        if not para:
            unit = "\n"
        else:
            unit = para + "\n"

        if buf_len + len(unit) > max_len and buf:
            chunks.append("".join(buf))
            buf = [unit]
            buf_len = len(unit)
        elif len(unit) > max_len:
            # خیلی بزرگه؛ به جمله بشکن
            sentences = split_sentences(unit, limit=max_len)
            for s in sentences:
                if buf_len + len(s) > max_len and buf:
                    chunks.append("".join(buf))
                    buf = [s]
                    buf_len = len(s)
                else:
                    buf.append(s)
                    buf_len += len(s)
        else:
            buf.append(unit)
            buf_len += len(unit)

    if buf:
        chunks.append("".join(buf))
    return chunks

def split_sentences(text, limit=4000):
    # شکستن ساده بر اساس نقطه/علامت تعجب/سؤال
    import re
    sents = re.split(r'([\.!\?]+[\s]*)', text)
    merged = []
    for i in range(0, len(sents), 2):
        core = sents[i]
        tail = sents[i+1] if i+1 < len(sents) else ""
        merged.append(core + tail)

    chunks = []
    cur = ""
    for s in merged:
        if len(cur) + len(s) > limit and cur:
            chunks.append(cur)
            cur = s
        else:
            cur += s
    if cur:
        chunks.append(cur)
    return chunks

def safe_translate(text):
    try:
        return translator.translate(text)
    except Exception as e:
        print(f"⚠️ خطا در ترجمه بلوک: {e}")
        return text

# -------------------
# ارسال به Zapier Webhook (که اونجا ایمیل به Blogger ارسال می‌شود)
# -------------------
def send_to_zapier(title_fa, html_fa, source_url=None, published=None):
    payload = {
        "title": title_fa,
        "html": html_fa,            # بدنه HTML کامل
        "source_url": source_url or "",
        "published": str(published or ""),
    }
    try:
        r = requests.post(ZAPIER_WEBHOOK_URL, json=payload, timeout=30)
        if 200 <= r.status_code < 300:
            print(f"✅ ارسال به Zapier موفق بود: {title_fa}")
            return True
        print(f"❌ خطا در Zapier [{r.status_code}]: {r.text[:300]}")
        return False
    except Exception as e:
        print(f"❌ استثناء در ارسال به Zapier: {e}")
        return False

# -------------------
# اجرا
# -------------------
def main():
    print("🚀 شروع پردازش فید و ارسال به Zapier")
    posted = load_posted()

    feed = feedparser.parse(FEED_URL)
    if not feed.entries:
        print("⚠️ هیچ مطلبی در فید نیست.")
        return

    count = 0
    for entry in feed.entries[:MAX_ITEMS]:
        key = entry_key(entry)
        if key in posted:
            print(f"⏩ ردِ تکراری: {getattr(entry, 'title', '')[:80]}")
            continue

        raw_title = getattr(entry, "title", "").strip()
        raw_html = getattr(entry, "summary", "") or getattr(entry, "description", "")
        raw_html = raw_html or ""

        # 1) حذف لینک‌ها
        html_no_links = clean_links(raw_html)

        # 2) ترجمه عنوان و محتوا (با بلوک‌بندی ایمن)
        title_fa = translate_title(raw_title)
        html_fa = translate_html_blocks(html_no_links)

        # 3) ارسال به Zapier (Zap آن را ایمیل HTML به آدرس @blogger.com می‌فرستد)
        ok = send_to_zapier(
            title_fa=title_fa,
            html_fa=html_fa,
            source_url=getattr(entry, "link", ""),
            published=getattr(entry, "published", ""),
        )
        if ok:
            posted[key] = {
                "title_de": raw_title,
                "title_fa": title_fa,
                "link": getattr(entry, "link", ""),
                "sent_at": int(time.time()),
            }
            save_posted(posted)
            count += 1
            time.sleep(0.5)  # کمی تنفس بین ایمیل‌ها

    print(f"🏁 پایان. ارسال‌های جدید: {count}")

if __name__ == "__main__":
    main()
