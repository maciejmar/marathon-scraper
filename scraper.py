#!/usr/bin/env python3
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from playwright.sync_api import sync_playwright


BASE_URL = "https://live.sts-timing.pl/pw2026/index.php?dystans=2"
TARGET_TEAM = "Bractwo biegowe BGK"
OUTPUT_DIR = Path("/app/output")
OUTPUT_CSV = OUTPUT_DIR / "bgk_results.csv"
OUTPUT_JSON = OUTPUT_DIR / "bgk_results.json"


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def lower_norm(text: str) -> str:
    return normalize_spaces(text).casefold()


def text_matches_team(text: str, team: str) -> bool:
    return lower_norm(text) == lower_norm(team)


def guess_headers_from_table(table) -> List[str]:
    headers = []
    header_cells = table.locator("thead th")
    for i in range(header_cells.count()):
        txt = normalize_spaces(header_cells.nth(i).inner_text())
        if txt:
            headers.append(txt)

    if headers:
        return headers

    first_row_cells = table.locator("tbody tr").first.locator("td")
    return [f"col_{i+1}" for i in range(first_row_cells.count())]


def table_to_records(table) -> List[Dict[str, str]]:
    headers = guess_headers_from_table(table)
    rows = table.locator("tbody tr")
    records: List[Dict[str, str]] = []

    for i in range(rows.count()):
        row = rows.nth(i)
        cells = row.locator("td")
        values = [normalize_spaces(cells.nth(j).inner_text()) for j in range(cells.count())]

        if not any(values):
            continue

        record = {}
        for idx, header in enumerate(headers):
            record[header] = values[idx] if idx < len(values) else ""
        records.append(record)

    return records


def detect_team_column(records: List[Dict[str, str]]) -> Optional[str]:
    if not records:
        return None

    keys = list(records[0].keys())

    preferred = []
    for key in keys:
        kn = key.casefold()
        if "team" in kn or "druż" in kn or "druz" in kn:
            preferred.append(key)

    if preferred:
        return preferred[0]

    return None


def filter_records_by_team(records: List[Dict[str, str]], team: str) -> List[Dict[str, str]]:
    team_col = detect_team_column(records)
    if team_col:
        exact = [r for r in records if text_matches_team(r.get(team_col, ""), team)]
        if exact:
            return exact

    fallback = []
    for r in records:
        blob = " | ".join(r.values())
        if team.casefold() in blob.casefold():
            fallback.append(r)

    return fallback


def try_open_generate_results(page) -> bool:
    candidates = [
        page.locator("a", has_text="Generuj wyniki"),
        page.locator("text=Generuj wyniki"),
    ]

    for loc in candidates:
        try:
            if loc.count() > 0:
                loc.first.click(timeout=5000)
                page.wait_for_load_state("networkidle", timeout=15000)
                print("[INFO] Otworzono 'Generuj wyniki'")
                return True
        except Exception as e:
            print(f"[WARN] Nie udało się kliknąć linku: {e}")

    print("[WARN] Nie znaleziono lub nie otwarto strony 'Generuj wyniki'")
    return False


def try_set_team_filter(page, team_name: str) -> bool:
    selectors = [
        'select[name*="team" i]',
        'select[id*="team" i]',
        'select[name*="druz" i]',
        'select[id*="druz" i]',
    ]

    for selector in selectors:
        sel = page.locator(selector)
        if sel.count() == 0:
            continue

        try:
            options = sel.first.locator("option")
            for i in range(options.count()):
                txt = normalize_spaces(options.nth(i).inner_text())
                if text_matches_team(txt, team_name):
                    value = options.nth(i).get_attribute("value")
                    if value is not None:
                        sel.first.select_option(value=value)
                    else:
                        sel.first.select_option(label=txt)
                    print(f"[INFO] Ustawiono filtr team: {txt}")
                    return True
        except Exception as e:
            print(f"[WARN] Problem przy select_option({selector}): {e}")

    input_candidates = [
        page.locator('input[name*="team" i]'),
        page.locator('input[id*="team" i]'),
        page.locator('input[name*="druz" i]'),
        page.locator('input[id*="druz" i]'),
    ]

    for loc in input_candidates:
        try:
            if loc.count() > 0:
                loc.first.fill(team_name)
                print(f"[INFO] Wpisano team do inputa: {team_name}")
                return True
        except Exception as e:
            print(f"[WARN] Problem przy fill(): {e}")

    print("[WARN] Nie udało się ustawić filtra team")
    return False


def try_submit_filters(page) -> bool:
    candidates = [
        page.locator('input[type="submit"]'),
        page.locator('button[type="submit"]'),
        page.locator("button"),
        page.locator("text=Pokaż"),
        page.locator("text=Filtruj"),
        page.locator("text=Generuj"),
        page.locator("text=Szukaj"),
    ]

    for loc in candidates:
        try:
            if loc.count() > 0:
                loc.first.click(timeout=5000)
                page.wait_for_load_state("networkidle", timeout=15000)
                print("[INFO] Wysłano formularz filtrów")
                return True
        except Exception:
            pass

    print("[WARN] Nie udało się wysłać formularza filtrów")
    return False


def collect_all_tables(page) -> List[Dict[str, str]]:
    tables = page.locator("table")
    all_records: List[Dict[str, str]] = []

    print(f"[INFO] Liczba tabel na stronie: {tables.count()}")

    for i in range(tables.count()):
        try:
            table = tables.nth(i)
            records = table_to_records(table)
            if records:
                print(f"[INFO] Tabela {i}: {len(records)} rekordów")
                all_records.extend(records)
        except Exception as e:
            print(f"[WARN] Nie udało się odczytać tabeli {i}: {e}")

    return all_records


def save_csv(records: List[Dict[str, str]], output_path: Path) -> None:
    if not records:
        return

    fieldnames = list(records[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"[INFO] Otwieram: {BASE_URL}")
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        try_open_generate_results(page)
        page.wait_for_timeout(2000)

        team_set = try_set_team_filter(page, TARGET_TEAM)
        if team_set:
            try_submit_filters(page)
            page.wait_for_timeout(3000)

        all_records = collect_all_tables(page)
        browser.close()

    print(f"[INFO] Łącznie odczytanych rekordów z tabel: {len(all_records)}")

    filtered = filter_records_by_team(all_records, TARGET_TEAM)

    OUTPUT_JSON.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
    if filtered:
        save_csv(filtered, OUTPUT_CSV)

    if not filtered:
        print("[ERROR] Nie znaleziono rekordów dla teamu.")
        print(json.dumps({
            "status": "no_results",
            "team": TARGET_TEAM,
            "rows_seen": len(all_records),
            "json_saved_to": str(OUTPUT_JSON),
        }, ensure_ascii=False, indent=2))
        return 1

    print(f"[INFO] Znaleziono rekordów: {len(filtered)}")
    print(f"[INFO] CSV:  {OUTPUT_CSV}")
    print(f"[INFO] JSON: {OUTPUT_JSON}")
    print(json.dumps(filtered, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())