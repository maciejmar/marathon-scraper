import os
import subprocess
import sys
import asyncio
from copilot import CopilotClient


# Wskazanie na globalny katalog skilla w folderze domowym użytkownika
CONFLUENCE_SCRIPT = os.path.expanduser(r"~\.agents\skills\confluence\scripts\confluence_api.py")

def run_confluence_tool(args):
    """Uruchamia skrypt confluence_api.py z wymuszonym kodowaniem UTF-8."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [sys.executable, CONFLUENCE_SCRIPT] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env
    )
    if result.returncode != 0:
        print(f"Błąd narzędzia Confluence: {result.stderr or result.stdout}")
        sys.exit(1)
    return result.stdout


async def _call_copilot(prompt):
    client = CopilotClient()
    await client.start()
    session = await client.create_session({"model": "gpt-4o"})
    response = await session.send_and_wait({"prompt": prompt})
    await client.stop()
    return response.data.content

def ask_llm(context_data, user_goal):
    prompt = f"""Jesteś analitykiem wiedzy technicznej. Na podstawie poniższych danych z wewnętrznego Confluence:
1. Podsumuj krótko, jakie dokumenty, projekty lub narzędzia są tam opisane.
2. Wskaż konkretne sposoby, jak mogę wykorzystać te informacje lub technologie w swojej pracy.

DANE Z CONFLUENCE:
{context_data}

DODATKOWY CEL UŻYTKOWNIKA: {user_goal}
"""
    return asyncio.run(_call_copilot(prompt))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Użycie: python conflu-agent.py "<szukana_fraza_lub_technologia>"')
        sys.exit(1)

    topic = sys.argv
    print(f"1. Przeszukuję Confluence dla hasła: '{topic}'...")
    search_output = run_confluence_tool(["search", topic, "--limit", "5"])
    
    if "Brak wyników" in search_output:
        print("Nie znaleziono żadnych stron dla tego hasła.")
        sys.exit(0)

    print("Znalezione strony:\n" + search_output)
    
    # Wyciągnięcie ID stron z wyników (format: (SPACE) Tytuł)
    page_ids = []
    for line in search_output.splitlines():
        if line.startswith("[") and "]" in line:
            page_ids.append(line.split("]").replace("[", ""))

    # Pobranie treści maksymalnie 3 pierwszych stron
    full_context = f"Lista znalezionych stron:\n{search_output}\n\nTreść głównych stron:\n"
    for pid in page_ids[:3]:
        print(f"2. Pobieram treść strony ID: {pid}...")
        page_content = run_confluence_tool(["read", pid])
        full_context += f"\n--- STRONA {pid} ---\n{page_content[:6000]}\n"

    print("3. Wysyłam dane do LLM w celu analizy i podsumowania...\n")
    summary = ask_llm(full_context, f"Chcę się dowiedzieć, co mamy w organizacji na temat: {topic} i jak to wykorzystać.")
    
    print("=" * 50)
    print("PODSUMOWANIE AI:")
    print("=" * 50)
    print(summary)
