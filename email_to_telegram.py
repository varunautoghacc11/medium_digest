import imaplib
import email
from email.utils import parsedate_to_datetime
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')
BOT_API_URL = os.getenv('BOT_API_URL')
CHAT_ID = os.getenv('CHAT_ID')

def fetch_email_data():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(EMAIL, PASSWORD)
    mail.select('inbox')

    result, data = mail.search(None, '(FROM "varunchopra2003@gmail.com")')

    articles = []
    for num in data[0].split():
        result, email_data = mail.fetch(num, '(RFC822)')
        msg = email.message_from_bytes(email_data[0][1])
        if (datetime.now(timezone.utc) - parsedate_to_datetime(msg['Date'])).total_seconds() < 22 * 3600:
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/html':
                        html_content = part.get_payload(decode=True).decode()
                        articles = extract_content(html_content)

    return articles

def extract_content(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    articles = []

    # Skip non-article h2s (footer/promo)
    skip_keywords = ["see more", "read from", "become a member"]

    for h2 in soup.find_all("h2"):
        try:
            title = h2.get_text(strip=True)

            # Skip promo/footer blocks
            if any(kw in title.lower() for kw in skip_keywords):
                continue

            article = {}
            article["title"] = title

            parent_a = h2.find_parent("a")
            article["url"] = parent_a["href"] if parent_a and parent_a.has_attr("href") else None

            # Skip if no URL
            if not article["url"]:
                continue

            container = h2.find_parent()
            h3 = container.find_next("h3")
            article["subtitle"] = h3.get_text(strip=True) if h3 else None

            # Author
            prev_span = h2.find_previous("span")
            article["author"] = prev_span.get_text(strip=True) if prev_span else None

            # Metadata
            meta_spans = container.find_all_next("span", limit=6)
            meta_texts = [s.get_text(strip=True) for s in meta_spans]
            article["read_time"] = None
            article["claps"] = None
            article["responses"] = None
            for text in meta_texts:
                if "min read" in text:
                    article["read_time"] = text
                elif text.endswith("K") or text.isdigit():
                    if not article["claps"]:
                        article["claps"] = text
                    elif not article["responses"]:
                        article["responses"] = text

            articles.append(article)
        except Exception:
            continue

    return articles

def format_articles(articles):
    today = datetime.now().strftime("%A, %d %B %Y")
    messages = []

    # Header message
    header = (
        f"📰 *Medium Daily Digest*\n"
        f"📅 {today}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ *{len(articles)} articles curated for you today*"
    )
    messages.append(header)

    # Each article as its own message block
    for i, article in enumerate(articles, 1):
        title = article.get("title", "Untitled")
        subtitle = article.get("subtitle", "")
        author = article.get("author", "Unknown")
        read_time = article.get("read_time", "")
        claps = article.get("claps", "")
        url = article.get("url", "")

        # Build freedium URL
        freedium_url = f"https://freedium-mirror.cfd/{url}" if url else ""

        # Metadata line
        meta_parts = []
        if read_time:
            meta_parts.append(f"⏱ {read_time}")
        if claps:
            meta_parts.append(f"👏 {claps}")
        meta_line = "  |  ".join(meta_parts) if meta_parts else ""

        block = (
            f"*{i}.* 📖 *{title}*\n"
            f"_{subtitle}_\n"
            f"✍️ {author}\n"
        )
        if meta_line:
            block += f"{meta_line}\n"
        if freedium_url:
            block += f"🔗 [Read Article]({freedium_url})"

        messages.append(block)

    # Footer
    footer = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 _Powered by Hellum · Medium Digest Bot_"
    )
    messages.append(footer)

    return messages

def send_to_telegram(messages):
    for msg in messages:
        response = requests.post(BOT_API_URL, data={
            'chat_id': CHAT_ID,
            'text': msg,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        })
        if response.status_code != 200:
            print(f"Failed to send message: {response.text}")
            return False
    return True

def main():
    articles = fetch_email_data()
    if articles:
        messages = format_articles(articles)
        if send_to_telegram(messages):
            print(f"✅ Sent {len(articles)} articles to Telegram successfully.")
        else:
            print("❌ Failed to send some messages.")
    else:
        print("No new articles found in the last 22 hours.")

if __name__ == "__main__":
    main()
