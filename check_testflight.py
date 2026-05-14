import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


LINKS_FILE = Path("links.json")
STATE_FILE = Path("state.json")
REQUEST_TIMEOUT_SECONDS = 20

USER_AGENT = (
    "Mozilla/5.0 (compatible; TestFlightMonitor/1.0; "
    "+https://github.com/actions)"
)

FULL_PATTERNS = [
    "this beta is full",
    "beta is full",
    "this beta isn't accepting any new testers right now",
    "this beta is not accepting any new testers right now",
    "isn't accepting any new testers",
    "is not accepting any new testers",
    "no longer accepting new testers",
    "not accepting new testers",
    "no acepta nuevos testers",
    "no acepta mas testers",
    "no acepta más testers",
    "beta llena",
    "la beta esta llena",
    "la beta está llena",
    "this beta is no longer available",
    "this beta is not available",
    "beta is not available",
    "beta isn't available",
    "not available",
    "no disponible",
    "this beta has expired",
    "this beta has ended",
    "this invite is no longer valid",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_links(path: Path = LINKS_FILE) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as file:
        raw_links = json.load(file)

    links: list[dict[str, str]] = []
    for index, item in enumerate(raw_links, start=1):
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        if not name or not url:
            print(f"[WARN] Link #{index} ignorado: falta name o url")
            continue
        links.append({"name": name, "url": url})

    return links


def load_state(path: Path = STATE_FILE) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        print("[WARN] state.json no es JSON valido. Se reinicia el estado.")
        return {}


def save_state(state: dict[str, Any], path: Path = STATE_FILE) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write("\n")


def normalize_text(text: str) -> str:
    decoded = html.unescape(text)
    return " ".join(decoded.lower().split())


def detect_status(response: requests.Response) -> tuple[str, str | None]:
    if response.status_code >= 400:
        return "error", f"HTTP {response.status_code}"

    body = normalize_text(response.text)
    if not body:
        return "error", "Respuesta vacia"

    for pattern in FULL_PATTERNS:
        if pattern in body:
            return "full", f"Patron encontrado: {pattern}"

    return "open", None


def check_link(link: dict[str, str]) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9,es;q=0.8"}
    url = link["url"]

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
        status, reason = detect_status(response)
        return {
            "name": link["name"],
            "url": url,
            "status": status,
            "http_status": response.status_code,
            "final_url": response.url,
            "reason": reason,
            "checked_at": utc_now_iso(),
        }
    except requests.RequestException as exc:
        return {
            "name": link["name"],
            "url": url,
            "status": "error",
            "http_status": None,
            "final_url": None,
            "reason": str(exc),
            "checked_at": utc_now_iso(),
        }


def should_alert(previous_status: str | None, current_status: str) -> bool:
    return previous_status == "full" and current_status == "open"


def send_telegram_alert(name: str, url: str, checked_at: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[WARN] No se envia Telegram: faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")
        return False

    message = (
        "Posible hueco en TestFlight\n\n"
        f"App: {name}\n"
        f"URL: {url}\n"
        f"Hora UTC: {checked_at}"
    )

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": True,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            print(f"[ERROR] Telegram fallo: HTTP {response.status_code} - {response.text}")
            return False
        return True
    except requests.RequestException as exc:
        print(f"[ERROR] Telegram fallo: {exc}")
        return False


def update_state_entry(
    state: dict[str, Any],
    result: dict[str, Any],
    previous_entry: dict[str, Any],
) -> None:
    url = result["url"]
    previous_status = previous_entry.get("status")
    previous_changed_at = previous_entry.get("last_changed_at")
    status_changed = previous_status != result["status"]

    state[url] = {
        "name": result["name"],
        "url": url,
        "status": result["status"],
        "http_status": result["http_status"],
        "final_url": result["final_url"],
        "reason": result["reason"],
        "checked_at": result["checked_at"],
        "last_changed_at": result["checked_at"] if status_changed else previous_changed_at,
    }


def main() -> int:
    print("[INFO] Iniciando monitor de TestFlight")
    links = load_links()
    state = load_state()

    if not links:
        print("[WARN] No hay links en links.json")
        save_state(state)
        return 0

    for link in links:
        previous_entry = state.get(link["url"], {})
        previous_status = previous_entry.get("status")

        print(f"[INFO] Revisando: {link['name']} - {link['url']}")
        result = check_link(link)
        current_status = result["status"]

        print(
            "[INFO] Resultado: "
            f"{link['name']} | anterior={previous_status or 'none'} | "
            f"actual={current_status} | http={result['http_status']} | "
            f"motivo={result['reason'] or 'sin patrones de lleno/no disponible'}"
        )

        if should_alert(previous_status, current_status):
            print(f"[ALERT] Posible hueco detectado: {link['name']}")
            sent = send_telegram_alert(link["name"], link["url"], result["checked_at"])
            print(f"[INFO] Telegram enviado={sent}")

        update_state_entry(state, result, previous_entry)

    save_state(state)
    print("[INFO] state.json actualizado")
    print("[INFO] Fin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
