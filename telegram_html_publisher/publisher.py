import base64
import datetime as dt
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request


TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
GITHUB_API = "https://api.github.com"


class ConfigError(RuntimeError):
    pass


def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"Missing environment variable: {name}")
    return value


def request_json(method, url, headers=None, data=None):
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    req.add_header("User-Agent", "kerwin-telegram-html-publisher")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = resp.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            details = json.loads(payload)
            message = details.get("message", payload)
        except json.JSONDecodeError:
            message = payload
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code}: {message}") from exc


def telegram_call(token, method, data):
    url = TELEGRAM_API.format(token=token, method=method)
    return request_json("POST", url, data=data)


def send_message(token, chat_id, text):
    return telegram_call(
        token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": False,
        },
    )


def github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def slugify(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value)
    value = value.strip("-")
    if not value:
        value = "html-page"
    ascii_only = re.sub(r"[^a-z0-9-]+", "", value)
    return (ascii_only or "html-page")[:48].strip("-") or "html-page"


def extract_title_and_html(text):
    title = "Kerwin HTML Page"
    title_match = re.search(r"^\s*(?:标题|title)\s*[:：]\s*(.+)$", text, re.I | re.M)
    if title_match:
        title = title_match.group(1).strip()

    html_start = re.search(r"(?is)<!doctype html|<html[\s>]", text)
    if html_start:
        document = text[html_start.start():].strip()
    else:
        document = text.strip()

    if "<html" not in document.lower():
        escaped = html.escape(document)
        document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
</head>
<body>
{escaped}
</body>
</html>
"""
    return title, ensure_brand_footer(document)


def ensure_brand_footer(document):
    if os.environ.get("BRAND_FOOTER", "1") != "1":
        return document
    if "Kerwin 团队自动化呈现" in document or "Kerwin Team x OpenClaw Enya" in document:
        return document
    footer = """
<section style="margin:32px auto 0;max-width:960px;padding:18px;border:1px solid #dfcfae;background:#f8e5c1;color:#1f1a17;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',Arial,sans-serif;line-height:1.65;">
  <strong>本文由 Kerwin 团队自动化呈现：</strong>Kerwin 确定研究主题、判断框架与校对逻辑；OpenClaw 打造的 Enya 完成自动化编码、GitHub Pages 发布与 Telegram 交付。底层 AI 模型采用 GPT-5.5 及 Claude 付费版。Enya 是香港首个由 OpenClaw 打造的女性投顾 Agent。本文不构成严谨投资建议；严谨投资建议请与 Kerwin 联系。GitHub 生成公开可流转的网页链接，便于直接分享。
</section>
"""
    if "</body>" in document.lower():
        return re.sub(r"(?i)</body>", footer + "\n</body>", document, count=1)
    return document + footer


def repo_name(prefix, title):
    mode = os.environ.get("PUBLISH_MODE", "unique").strip().lower()
    if mode == "fixed":
        return prefix
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{slugify(title)}-{stamp}"[:100].strip("-")


def create_repo(token, owner, name, title):
    data = {
        "name": name,
        "description": title,
        "private": False,
        "auto_init": False,
    }
    return request_json("POST", f"{GITHUB_API}/user/repos", github_headers(token), data)


def get_repo(token, owner, name):
    try:
        return request_json("GET", f"{GITHUB_API}/repos/{owner}/{name}", github_headers(token))
    except RuntimeError as exc:
        if "HTTP 404" in str(exc):
            return None
        raise


def put_file(token, owner, repo, path, content, message):
    existing = None
    try:
        existing = request_json(
            "GET",
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{urllib.parse.quote(path)}?ref=main",
            github_headers(token),
        )
    except RuntimeError as exc:
        if "HTTP 404" not in str(exc):
            raise

    data = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": "main",
    }
    if existing and existing.get("sha"):
        data["sha"] = existing["sha"]
    return request_json(
        "PUT",
        f"{GITHUB_API}/repos/{owner}/{repo}/contents/{urllib.parse.quote(path)}",
        github_headers(token),
        data,
    )


def ensure_pages(token, owner, repo):
    pages_url = f"{GITHUB_API}/repos/{owner}/{repo}/pages"
    try:
        return request_json("GET", pages_url, github_headers(token))
    except RuntimeError as exc:
        if "HTTP 404" not in str(exc):
            raise
    data = {"source": {"branch": "main", "path": "/"}}
    return request_json("POST", pages_url, github_headers(token), data)


def publish_html(title, document):
    github_token = require_env("GITHUB_TOKEN")
    owner = require_env("GITHUB_OWNER")
    prefix = os.environ.get("REPO_PREFIX", "kerwin-html").strip() or "kerwin-html"
    name = repo_name(prefix, title)

    repo = get_repo(github_token, owner, name)
    if repo is None:
        create_repo(github_token, owner, name, title)

    readme = f"# {title}\n\nPublished automatically by Kerwin Team x OpenClaw Enya.\n"
    put_file(github_token, owner, name, "README.md", readme, "Add README")
    put_file(github_token, owner, name, "index.html", document, "Publish HTML page")
    pages = ensure_pages(github_token, owner, name)
    return pages.get("html_url") or f"https://{owner}.github.io/{name}/"


def handle_message(token, allowed_chat_id, message):
    chat = message.get("chat", {})
    chat_id = str(chat.get("id", ""))
    text = message.get("text") or message.get("caption") or ""
    if chat_id != str(allowed_chat_id):
        return
    if not text.strip():
        send_message(token, chat_id, "请发送 HTML 文本。")
        return
    if "/start" in text:
        send_message(token, chat_id, "发送 HTML 给我，我会自动发布到 GitHub Pages 并返回公开链接。")
        return

    send_message(token, chat_id, "收到 HTML，开始自动发布。")
    try:
        title, document = extract_title_and_html(text)
        url = publish_html(title, document)
        send_message(token, chat_id, f"发布完成：\n{url}")
    except Exception as exc:
        send_message(token, chat_id, f"发布失败：{exc}")


def run():
    load_dotenv()
    token = require_env("TELEGRAM_BOT_TOKEN")
    allowed_chat_id = require_env("TELEGRAM_ALLOWED_CHAT_ID")
    offset = None
    send_message(token, allowed_chat_id, "Telegram HTML Publisher 已启动。")
    while True:
        data = {"timeout": 50}
        if offset is not None:
            data["offset"] = offset
        try:
            updates = telegram_call(token, "getUpdates", data)
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message")
                if message:
                    handle_message(token, allowed_chat_id, message)
        except Exception as exc:
            print(f"[publisher] {exc}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    run()
