"""Self-contained reports: local assets only, embedded data escaped for HTML."""
import json
from pathlib import Path

WEB = Path(__file__).with_name("web")

def report_html(summary):
    data = json.dumps(summary).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    data = data.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = (WEB / "index.html").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="/style.css">', "<style>" + (WEB / "style.css").read_text(encoding="utf-8") + "</style>")
    script = "<script>window.__PULSEPROOF_REPORT__=" + data + ";</script>"
    html = html.replace('<script src="/app.js" defer></script>', script)
    # Inline scripts do not honor defer: execute after the report DOM exists.
    return html.replace("</body>", "<script>" + (WEB / "app.js").read_text(encoding="utf-8") + "</script></body>")
