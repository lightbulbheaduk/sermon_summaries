# Sermon_summaries

Automated pipeline that:
- Checks configured podcast RSS feeds for new episodes
- Downloads audio, transcribes with OpenAI, summarises and extracts key info
- Publishes a static site to GitHub Pages with per-episode pages

Tech: Python, GitHub Actions, GitHub Pages, OpenAI API.

See config.example.yml and prompt.example.txt to get started. The site publishes from the `docs/` folder.

Security: Do NOT commit your OpenAI API key. Store it as a GitHub Secret named `OPENAI_API_KEY`.