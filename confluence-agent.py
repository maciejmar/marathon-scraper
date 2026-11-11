import os
import subprocess
import sys
from openai import OpenAI

# Ścieżka do Twojego deterministycznego narzędzia
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFLUENCE_SCRIPT = os.path.join(SCRIPT_DIR, "confluence_api.py")

def run_confluence_tool(args):
    """Uruchamia Twój skrypt confluence_api.py i zwraca jego wynik tekstowy."""
    result = subprocess.run(
        [sys.executable, CONFLUENCE_SCRIPT] + args,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    if result.returncode != 0:
        print(f"Błąd narzędzia Confluence: {result.stderr or result.stdout}")
        sys.exit(1)
    return result.stdout

def ask_llm(context_data, user_goal):
    """Wysyła pobrane dane z Confluence do modelu LLM przez GitHub Models API."""
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("Błąd: Brak zmiennej środowiskowej GITHUB_TOKEN.")
        sys.exit(1)

    client = OpenAI(
        base_url="https://github.ai",
        api_key=github_token,
    )

    prompt = f"""Na podstawie poniższych danych pobranych z wewnętrznego Confluence naszej organizacji:
1. Podsumuj krótko, jakie dokumenty, projekty lub narzędzia są tam opisane.
2. Wskaż konkretne sposoby, jak mogę wykorzystać te informacje lub technologie w swojej pracy.

DANE Z CONFLUENCE:
{context_data}

DODATKOWY CEL UŻYTKOWNIKA: {user_goal}
"""

    response = client.chat.completions.create(
        model="openai/gpt-4o",
        messages=[
            {"role": "system", "content": "Jesteś analitykiem wiedzy technicznej. Odpowiadaj wyłącznie na podstawie dostarczonego kontekstu z Confluence."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    return response.choices.message.content

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Użycie: python confluence_ai.py "<szukana_fraza_lub_technologia>"')
        sys.exit(1)

    topic = sys.argv
    print(f"1. Przeszukuję Confluence dla hasła: '{topic}'...")
    search_output = run_confluence_tool(["search", topic, "--limit", "5"])
    
    if "Brak wyników" in search_output:
        print("Nie znaleziono żadnych stron dla tego hasła.")
        sys.exit(0)

    print("Znalezione strony:\n" + search_output)
    
    # Wyciągnięcie ID stron z wyników (format: [123456] (SPACE) Tytuł)
    page_ids = []
    for line in search_output.splitlines():
        if line.startswith("[") and "]" in line:
            page_ids.append(line.split("]")[0].replace("[", ""))

    # Pobranie treści maksymalnie 3 pierwszych stron, aby nie przekroczyć limitu znaków
    full_context = f"Lista znalezionych stron:\n{search_output}\n\nTreść głównych stron:\n"
    for pid in page_ids[:3]:
        print(f"2. Pobieram treść strony ID: {pid}...")
        page_content = run_confluence_tool(["read", pid])
        # Ograniczenie do 6000 znaków na stronę dla bezpieczeństwa limitu tokenów
        full_context += f"\n--- STRONA {pid} ---\n{page_content[:6000]}\n"

    print("3. Wysyłam dane do LLM w celu analizy i podsumowania...\n")
    summary = ask_llm(full_context, f"Chcę się dowiedzieć, co mamy w organizacji na temat: {topic} i jak to wykorzystać.")
    
    print("=" * 50)
    print("PODSUMOWANIE AI:")
    print("=" * 50)
    print(summary)
