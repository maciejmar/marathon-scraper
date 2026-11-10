import sys
import os
import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
import re

BASE_URL = os.environ.get("CONFLUENCE_BASE_URL", "https://oneadr.net").rstrip("/")
TOKEN = os.environ.get("CONFLUENCE_TOKEN", "")
SSL_VERIFY = os.environ.get("CONFLUENCE_SSL_VERIFY", "true").lower() != "false"
CA_BUNDLE = os.environ.get("CONFLUENCE_CA_BUNDLE", "")

def get_ssl_context():
    if not SSL_VERIFY:
        return ssl._create_unverified_context()
    if CA_BUNDLE:
        return ssl.create_default_context(cafile=CA_BUNDLE)
    return ssl.create_default_context()

def api_request(endpoint):
    if not TOKEN:
        print("Błąd: Brak ustawionej zmiennej środowiskowej CONFLUENCE_TOKEN.")
        sys.exit(1)
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, context=get_ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Błąd HTTP {e.code}: {e.reason} ({url})")
        sys.exit(1)
    except Exception as e:
        print(f"Błąd połączenia: {e}")
        sys.exit(1)

def clean_html(raw_html):
    text = re.sub(r'<[^>]+>', ' ', raw_html)
    return re.sub(r'\s+', ' ', text).strip()

def cmd_check():
    print(f"Adres usługi: {BASE_URL}")
    print(f"Status tokenu: {'USTAWIONY' if TOKEN else 'BRAK'}")
    if TOKEN:
        data = api_request("/rest/api/user/current")
        print(f"Połączono pomyślnie jako: {data.get('displayName', 'Nieznany użytkownik')}")

def cmd_search(query, limit=10):
    cql = urllib.parse.quote(f'text ~ "{query}"')
    data = api_request(f"/rest/api/content/search?cql={cql}&limit={limit}")
    results = data.get("results", [])
    if not results:
        print("Brak wyników.")
        return
    for item in results:
        page_id = item.get("id")
        title = item.get("title")
        space = item.get("space", {}).get("key", "")
        print(f"[{page_id}] ({space}) {title}")

def cmd_read(page_id):
    data = api_request(f"/rest/api/content/{page_id}?expand=body.storage,space")
    print(f"Tytuł: {data.get('title')}")
    print(f"Przestrzeń: {data.get('space', {}).get('key')}")
    print("-" * 40)
    html_body = data.get("body", {}).get("storage", {}).get("value", "")
    print(clean_html(html_body))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Użycie: confluence_api.py [check | search <fraza> | read <ID>]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    if cmd == "check":
        cmd_check()
    elif cmd == "search" and len(sys.argv) >= 3:
        limit = 10
        if "--limit" in sys.argv:
            idx = sys.argv.index("--limit")
            limit = int(sys.argv[idx + 1])
        cmd_search(sys.argv[2], limit)
    elif cmd == "read" and len(sys.argv) >= 3:
        cmd_read(sys.argv[2])
    else:
        print("Nieprawidłowa komenda lub brak argumentów.")
