# Skill Confluence - instrukcja użytkowania
Skill Confluence pozwala czytać i wyszukiwać strony z wewnętrznego serwera Confluence.

## Konfiguracja
Wymagana jest zmienna środowiskowa Windows `CONFLUENCE_TOKEN`.

## Najważniejsze komendy
- `check` - Sprawdzenie tokenu i konfiguracji
- `search "<fraza>" --limit 10` - Wyszukiwanie stron
- `read <ID>` - Odczyt treści strony po ID

## Uruchamianie w Windows
`%USERPROFILE%\.agents\skills\confluence\scripts\confluence_api.cmd <komenda>`
