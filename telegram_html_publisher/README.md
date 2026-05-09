# Telegram HTML Publisher

Telegram HTML Publisher lets Kerwin publish an HTML page from a phone.

Send HTML to the Telegram bot. The service creates a public GitHub repository, uploads `index.html` and `README.md`, enables GitHub Pages from the `main` branch root, and replies with the public URL.

## Environment

Copy `.env.example` to `.env` and set:

- `TELEGRAM_BOT_TOKEN`: Telegram bot token from BotFather.
- `TELEGRAM_ALLOWED_CHAT_ID`: only this chat can publish.
- `GITHUB_TOKEN`: GitHub token with repo and Pages administration permissions.
- `GITHUB_OWNER`: GitHub username or org, for example `Kerwin7081`.
- `REPO_PREFIX`: prefix for generated repositories.
- `PUBLISH_MODE`: `unique` creates a new repo per page. `fixed` updates one repo.
- `BRAND_FOOTER`: `1` appends Kerwin production and risk note if the HTML does not already include it.

## Run

```powershell
python .\publisher.py
```

On a VPS, run it with systemd, pm2, Docker, or your OpenClaw Gateway process supervisor.

## Telegram Usage

Send one message containing a full HTML document:

```html
<!doctype html>
<html>
...
</html>
```

Optional title line before the HTML:

```text
标题：未来手机与个人 Agent 架构
<!doctype html>
<html>
...
</html>
```

The bot returns the GitHub Pages URL, for example:

```text
https://kerwin7081.github.io/kerwin-html-20260509-103000/
```

## Notes

The GitHub Pages build may take 30 seconds to a few minutes after the bot replies.
