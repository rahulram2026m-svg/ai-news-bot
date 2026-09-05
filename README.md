# AI News Telegram Bot 🤖

Duniya bhar ki AI news (companies, research papers, model launches) automatically
fetch karke Telegram par photo cards ki tarah bhejta hai — har 15 minute,
GitHub Actions ke through, bilkul **free**, PC on rakhne ki zaroorat nahi.

## Kaise kaam karta hai

1. **Fetch** — 70+ RSS feeds se (AI news sites, company blogs, arXiv research
   papers, Chinese AI trackers) latest articles uthata hai
2. **Filter** — sirf AI-related news rakhta hai, aur pehle bheji hui news
   dobara skip kar deta hai (`sent_articles.json` me history save hoti hai)
3. **Summarize** — Groq (free LLM) se har article ka chota Hinglish summary
   banata hai
4. **Send** — Telegram par har article ek alag card (photo + summary + link)
   ki tarah bhejta hai

## Local setup (apne computer pe test karne ke liye)

```bash
pip install -r requirements.txt
python3 ai_news_telegram_bot.py
```

Config `ai_news_telegram_bot.py` ke top me hai — Telegram bot token, chat ID,
aur LLM API key waha daal sakte ho (ya environment variables se bhi le sakta
hai, neeche dekho).

## GitHub Actions se 24/7 free automation (PC band ho tab bhi chalega)

1. Is poore folder ko ek naye **GitHub repository** me push karo (public
   rakhna, isse Actions minutes unlimited free milte hain)

2. Repo ke **Settings → Secrets and variables → Actions** me ye secrets add
   karo:

   | Secret name          | Value                                    |
   |-----------------------|-------------------------------------------|
   | `TELEGRAM_BOT_TOKEN`  | Apna Telegram bot token (@BotFather se)   |
   | `TELEGRAM_CHAT_ID`    | Apna Telegram chat ID                     |
   | `GROQ_API_KEY`        | Free key: https://console.groq.com        |
   | `GEMINI_API_KEY`      | (optional) https://aistudio.google.com/apikey |

3. **Actions** tab me jao, workflow dikhega ("AI News Telegram Bot"). Pehli
   baar manually **Run workflow** dabao test karne ke liye.

4. Uske baad automatically har 15 minute chalega (`.github/workflows/ai-news-bot.yml`
   me `cron: "*/15 * * * *"` set hai) — chahe PC on ho ya off.

## Config badalna ho toh

`ai_news_telegram_bot.py` file ke top me `CONFIG` section me:
- `LLM_PROVIDER` — `"groq"`, `"gemini"`, `"claude"`, ya `"none"`
- `HOURS_LOOKBACK` — kitni purani news tak check kare
- `MAX_ARTICLES_PER_RUN` / `MAX_PAPERS_PER_RUN` — ek run me max kitni news/papers
- `RSS_FEEDS` — feeds list, yahan se add/remove kar sakte ho
- `AI_KEYWORDS` — filter keywords, yahan se adjust kar sakte ho

## Folder structure

```
ai-news-bot/
├── ai_news_telegram_bot.py       # Main script
├── requirements.txt              # Python dependencies
├── .gitignore
├── README.md
└── .github/
    └── workflows/
        └── ai-news-bot.yml       # GitHub Actions schedule (har 15 min)
```

## Security note

Agar aapne kabhi apni API keys kisi ke saath share ki hain (chat me, screenshot
me, etc.), unhe turant **revoke/regenerate** kar do:
- Telegram: @BotFather → `/revoke`
- Groq: console.groq.com → API Keys → delete + naya banao
- Gemini: aistudio.google.com/apikey → delete + naya banao
