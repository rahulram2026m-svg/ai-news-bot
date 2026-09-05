#!/usr/bin/env python3
"""
AI News Telegram Bot
---------------------
Har 15 minute chalao (Task Scheduler / cron se) — yeh script duniya bhar ki
AI news RSS feeds se uthata hai, sirf NAYI (pehle na bheji gayi) news filter
karta hai, har article ka photo + AI summary alag-alag Telegram message
(card) ki tarah bhej deta hai.

DUPLICATE PROTECTION: Script ek "sent_articles.json" file banati hai (isi
folder me jahan script hai) jisme already-bheji hui news ke links save
rehte hain. Har run pe naye articles usi list se compare hote hain.

SETUP: (README pehle jaisa hi hai, config neeche hai)
INSTALL:
   pip install feedparser requests --break-system-packages
RUN:
   python3 ai_news_telegram_bot.py
"""

import feedparser
import requests
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone

# ============ CONFIG (yahan apni details daalo) ============
# NOTE: GitHub Actions pe chalane ke liye ye values "Secrets" se aayengi
# (os.environ.get). Apne PC pe local test ke liye, seedha yahan bhi daal
# sakte ho (dusra argument default value hai).
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8642137967:AAEJBs4u5Uzw8z9Q6kX0IbblwZjOJNeaWJ4")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "5858336760")

# Kaunsa LLM summary ke liye use karna hai: "gemini", "groq", "claude", ya "none"
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6Lc8LDlc9XzihUQIs2GvHqLKHvFiuGFxlvu_79614isAQ")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
ANTHROPIC_API_KEY = ""

# Kitne ghante purani news check karni hai (dedup ke wajah se duplicate nahi
# aayegi, ye sirf feed padhne ka safety window hai)
HOURS_LOOKBACK = 2

# Ek run me max kitne naye articles bhejne hain (bahut zyada aa jaye toh
# Telegram flood limit se bachne ke liye)
MAX_ARTICLES_PER_RUN = 20

# In max articles me se, arXiv research papers ka max kitna hissa ho
# (arXiv me daily 100+ papers aate hain, isliye inhe alag se cap karte hain
# taaki company news/launches dab na jayein)
MAX_PAPERS_PER_RUN = 6

# Sent articles kaha track karein
SENT_ARTICLES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sent_articles.json")
MAX_TRACKED_LINKS = 3000

# Duniya bhar ki AI news RSS feeds (30+ sources)
RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "https://arstechnica.com/ai/feed/",
    "https://www.artificialintelligence-news.com/feed/",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://www.zdnet.com/topic/artificial-intelligence/rss.xml",
    "https://www.theregister.com/software/ai_ml/headlines.atom",
    "https://www.marktechpost.com/feed/",
    "https://syncedreview.com/feed/",
    "https://bair.berkeley.edu/blog/feed.xml",
    "https://openai.com/blog/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://www.deepmind.com/blog/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://www.microsoft.com/en-us/research/feed/",
    "https://ai.meta.com/blog/rss/",
    "https://blogs.nvidia.com/feed/",
    "https://stability.ai/news?format=rss",
    "https://www.forbes.com/ai/feed/",
    "https://www.reuters.com/technology/artificial-intelligence/rss",
    "https://www.axios.com/technology/artificial-intelligence/feed.rss",
    "https://siliconangle.com/category/ai/feed/",
    "https://www.analyticsinsight.net/feed/",
    "https://www.unite.ai/feed/",
    "https://thenewstack.io/feed/",
    "https://www.infoworld.com/category/artificial-intelligence/index.rss",
    "https://www.therundown.ai/feed",

    # ===== Top AI/LLM company blogs & official research (model launches, papers) =====
    "https://tim-hilde.github.io/anthropic-rss/rss.xml",   # Anthropic/Claude blog (unofficial daily mirror, official RSS is broken)
    "https://deepmind.google/blog/rss.xml",                 # Google DeepMind (new domain)
    "https://blogs.microsoft.com/ai/feed/",                 # Microsoft AI blog
    "https://developer.nvidia.com/blog/feed",               # NVIDIA Developer blog
    "https://aws.amazon.com/blogs/machine-learning/feed/",  # AWS Machine Learning blog
    "https://www.amazon.science/index.rss",                 # Amazon Science
    "https://machinelearning.apple.com/rss.xml",            # Apple Machine Learning Research
    "https://research.ibm.com/blog/rss",                    # IBM Research
    "https://txt.cohere.com/rss/",                          # Cohere
    "https://mistral.ai/news/rss.xml",                      # Mistral AI
    "https://blog.langchain.dev/rss/",                      # LangChain
    "https://allenai.org/blog/rss.xml",                     # Allen Institute for AI (AI2)
    "https://news.mit.edu/rss/topic/artificial-intelligence2",  # MIT News - AI
    "https://hai.stanford.edu/rss.xml",                     # Stanford HAI
    "https://www.deeplearning.ai/the-batch/rss.xml",        # The Batch (Andrew Ng)
    "https://importai.substack.com/feed",                   # Import AI newsletter (Jack Clark)
    "https://www.interconnects.ai/feed",                    # Interconnects (AI research analysis)
    "https://simonwillison.net/atom/everything/",           # Simon Willison (heavy LLM coverage)

    # ===== Research paper feeds (naye papers seedhe arXiv se) =====
    "https://rss.arxiv.org/rss/cs.AI",   # arXiv - Artificial Intelligence
    "https://rss.arxiv.org/rss/cs.CL",   # arXiv - Computation & Language (LLMs)
    "https://rss.arxiv.org/rss/cs.LG",   # arXiv - Machine Learning

    # ===== Chinese AI companies/labs (jinke pass working RSS hai) =====
    "https://qwenlm.github.io/blog/feed.xml",     # Alibaba Qwen (Tongyi)
    "https://www.jiqizhixin.com/rss",             # Jiqizhixin - China's top AI news site (English+Chinese)

    # ===== Chinese AI ko English me track karne wale newsletters =====
    # (Zyada tar Chinese companies - DeepSeek, Baidu, Moonshot, Zhipu, MiniMax,
    # ByteDance - WeChat pe post karte hain jahan RSS support hi nahi hota,
    # isliye inhe seedha track karne wale English newsletters use kar rahe hain)
    "https://www.chinatalk.media/feed",           # ChinaTalk - China tech/AI newsletter
    "https://interconnects.ai/feed",              # (duplicate-safe) AI research analysis incl. Chinese labs
    "https://www.turingpost.com/feed",            # Turing Post - global AI incl. Chinese labs coverage
    "https://www.scmp.com/rss/318198/feed",       # South China Morning Post - China Tech

    # ===== Aur global frontier / open-source AI companies =====
    "https://www.databricks.com/blog/feed",       # Databricks (Mosaic/DBRX)
    "https://www.snowflake.com/blog/feed/",       # Snowflake (Arctic)
    "https://blog.eleuther.ai/index.xml",         # EleutherAI (open source)
    "https://laion.ai/rss.xml",                   # LAION (open source datasets/models)
    "https://www.together.ai/blog/rss.xml",       # Together AI
    "https://www.ai21.com/blog/rss.xml",          # AI21 Labs (Jamba)
    "https://aleph-alpha.com/feed/",              # Aleph Alpha (Germany)
    "https://sakana.ai/rss.xml",                  # Sakana AI (Japan)
    "https://www.adept.ai/blog/rss.xml",          # Adept AI
    "https://replicate.com/blog/rss",             # Replicate
    "https://elevenlabs.io/blog/rss.xml",         # ElevenLabs (voice AI)
    "https://runwayml.com/research/rss.xml",      # Runway (video/gen AI)
]
# =============================================================

# Extra safety net: chahe feed se kuch bhi aaye, sirf in AI-related keywords
# wali news hi pass hogi. Case-insensitive match hota hai title+excerpt me.
AI_KEYWORDS = [
    "ai ", " ai,", " ai.", " ai)", "(ai", "artificial intelligence",
    "machine learning", "deep learning", "neural network", "llm", "genai",
    "generative ai", "chatbot", "gpt", "openai", "chatgpt", "anthropic",
    "claude", "gemini", "deepmind", "copilot", "llama", "mistral ai",
    "stability ai", "hugging face", "midjourney", "nvidia ai", "agentic",
    "autonomous agent", "foundation model", "transformer model",
    "computer vision", "natural language processing", "reinforcement learning",
]


def is_ai_related(title, excerpt):
    text = f"{title} {excerpt}".lower()
    return any(keyword in text for keyword in AI_KEYWORDS)


def load_sent_links():
    if not os.path.exists(SENT_ARTICLES_FILE):
        return set()
    try:
        with open(SENT_ARTICLES_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception as e:
        print(f"Sent-links file padhne me error (nayi shuru karte hain): {e}")
        return set()


def save_sent_links(links):
    links_list = list(links)[-MAX_TRACKED_LINKS:]
    try:
        with open(SENT_ARTICLES_FILE, "w", encoding="utf-8") as f:
            json.dump(links_list, f)
    except Exception as e:
        print(f"Sent-links file save karne me error: {e}")


def strip_html(raw_html):
    text = re.sub(r"<[^>]+>", " ", raw_html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_image(entry):
    """RSS entry se photo/thumbnail URL nikaalne ki koshish karo (kai formats me ho sakta hai)."""
    # media:content / media:thumbnail (sabse common)
    for key in ("media_content", "media_thumbnail"):
        media = entry.get(key)
        if media and isinstance(media, list):
            for m in media:
                url = m.get("url")
                if url:
                    return url

    # RSS enclosures (image/* type)
    for enc in entry.get("enclosures", []) or []:
        if enc.get("type", "").startswith("image") and enc.get("href"):
            return enc["href"]

    # links list me image type dhundo
    for link_obj in entry.get("links", []) or []:
        if link_obj.get("type", "").startswith("image") and link_obj.get("href"):
            return link_obj["href"]

    # Summary/content ke HTML me <img src="..."> dhundo
    raw_html = entry.get("summary", "") or entry.get("description", "")
    match = re.search(r'<img[^>]+src="([^"]+)"', raw_html or "")
    if match:
        return match.group(1)

    return None


def fetch_recent_articles(already_sent):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_LOOKBACK)
    articles = []
    seen_this_run = set()

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            source_name = feed.feed.get("title", feed_url)
            for entry in feed.entries:
                link = entry.get("link", "")
                if not link or link in already_sent or link in seen_this_run:
                    continue

                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if not published:
                    continue
                pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                if pub_dt >= cutoff:
                    title = entry.get("title", "No title")
                    raw_summary = entry.get("summary", "") or entry.get("description", "")
                    clean_summary = strip_html(raw_summary)[:600]

                    if not is_ai_related(title, clean_summary):
                        continue  # AI-related nahi hai, skip kar do

                    articles.append({
                        "source": source_name,
                        "title": title,
                        "link": link,
                        "excerpt": clean_summary,
                        "image": extract_image(entry),
                        "pub_dt": pub_dt,
                        "is_paper": "arxiv.org" in feed_url,
                    })
                    seen_this_run.add(link)
        except Exception as e:
            print(f"Feed fetch failed for {feed_url}: {e}")

    # Sabse nayi news pehle (asli publish time ke hisaab se, na ki link string se)
    articles.sort(key=lambda a: a["pub_dt"], reverse=True)

    # arXiv papers bahut zyada aate hain (100+/din) - unhe cap kar do taaki
    # company news/launches dabein na. Baaki (non-paper) news unlimited hai
    # MAX_ARTICLES_PER_RUN tak.
    papers = [a for a in articles if a["is_paper"]][:MAX_PAPERS_PER_RUN]
    company_news = [a for a in articles if not a["is_paper"]]
    combined = (company_news + papers)
    combined.sort(key=lambda a: a["pub_dt"], reverse=True)

    return combined[:MAX_ARTICLES_PER_RUN]


def build_single_prompt(article):
    return (
        "Yeh ek AI news article hai duniya bhar se, abhi tak na dekha gaya. "
        "Isका ek chota, saaf 2-3 line ka summary banao (Hinglish me) — kya hua, "
        "kis company/product ka hai, kya impact hai. Sirf summary do, koi heading "
        "ya extra text mat likho:\n\n"
        f"Title: {article['title']}\n"
        f"Source: {article['source']}\n"
        f"Excerpt: {article['excerpt']}"
    )


def call_gemini(prompt):
    if not GEMINI_API_KEY:
        return None
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/interactions"
        response = requests.post(
            url,
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Api-Revision": "2026-05-20",
                "Content-Type": "application/json",
            },
            json={"model": "gemini-3-flash", "input": prompt},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("output_text")
    except Exception as e:
        print(f"Gemini call failed: {e}")
        return None


def call_groq(prompt):
    if not GROQ_API_KEY:
        return None
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-oss-20b",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Groq call failed: {e}")
        return None


def call_claude(prompt):
    if not ANTHROPIC_API_KEY:
        return None
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-5",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return "".join(b.get("text", "") for b in data.get("content", []))
    except Exception as e:
        print(f"Claude call failed: {e}")
        return None


def get_article_summary(article):
    """Har article ke liye chhota AI summary banwao, fail ho toh excerpt use karo."""
    if LLM_PROVIDER == "none":
        return article["excerpt"] or article["title"]

    prompt = build_single_prompt(article)
    result = None
    if LLM_PROVIDER == "gemini":
        result = call_gemini(prompt)
    elif LLM_PROVIDER == "groq":
        result = call_groq(prompt)
    elif LLM_PROVIDER == "claude":
        result = call_claude(prompt)

    if result:
        return result.strip()
    return article["excerpt"] or article["title"]


def escape_html(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_article_card(article, summary_text):
    """Ek article ko ek alag Telegram message (photo ke saath agar mile) ki tarah bhejo."""
    icon = "📄" if article.get("is_paper") else "🤖"
    label = "Research paper" if article.get("is_paper") else article["source"]
    caption = (
        f"{icon} <b>{escape_html(article['title'])}</b>\n\n"
        f"{escape_html(summary_text)}\n\n"
        f"📰 {escape_html(label)}\n"
        f"<a href=\"{article['link']}\">Read full {'paper' if article.get('is_paper') else 'article'}</a>"
    )
    caption = caption[:1024]  # Telegram photo caption limit

    try:
        if article.get("image"):
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "photo": article["image"],
                    "caption": caption,
                    "parse_mode": "HTML",
                },
                timeout=20,
            )
            # Agar image URL invalid nikla ya Telegram ne reject kiya, plain text bhej do
            if not resp.ok:
                raise ValueError(f"sendPhoto failed: {resp.text[:200]}")
        else:
            full_text = caption[:4000]
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": full_text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
                timeout=15,
            )
    except Exception as e:
        print(f"Card send failed for {article['link']}, falling back to text: {e}")
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": caption[:4000],
                    "parse_mode": "HTML",
                },
                timeout=15,
            )
        except Exception as e2:
            print(f"Fallback text send bhi fail hua: {e2}")


def main():
    already_sent = load_sent_links()
    articles = fetch_recent_articles(already_sent)

    if not articles:
        print("Koi nayi (pehle na bheji) AI news nahi mili.")
        return

    for article in articles:
        summary_text = get_article_summary(article)
        send_article_card(article, summary_text)
        already_sent.add(article["link"])
        time.sleep(1.5)  # Telegram flood limit se bachne ke liye chhota gap

    save_sent_links(already_sent)
    print(f"Sent {len(articles)} NEW article cards to Telegram.")


if __name__ == "__main__":
    main()
