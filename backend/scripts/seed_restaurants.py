"""
Seed script: загружает все рестораны из Server.xlsx,
привязывает пресеты, загружает нормы из group_rate_restaurant.xlsx.

Запуск (из корня проекта):
  docker compose exec backend python scripts/seed_restaurants.py
"""
import re
import sys
import os

# Нужно добавить /app в path для импорта app.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from app.core.database import SessionLocal
from app.models.restaurant import Restaurant, PresetDefinition, restaurant_presets
from app.models.catalog import WasteRate, ProductGroup
from sqlalchemy import insert, select


# ── Константы ──────────────────────────────────────────────────────────────
LOGIN = "WasteControl"
PASSWORD_HASH = "e8248cf8c7f36594cee948694f1d85b4aef3b9bb"

# Пути к Excel файлам (монтируются через volume /workspace в docker-compose,
# или используем локальный путь при запуске напрямую)
WASTECONTROL_DIR = os.environ.get(
    "WASTECONTROL_DIR",
    "/workspace"   # docker volume
)
SERVER_XLSX  = os.path.join(WASTECONTROL_DIR, "Server.xlsx")
RATES_XLSX   = os.path.join(WASTECONTROL_DIR, "data", "rules", "group_rate_restaurant.xlsx")


def extract_code(name: str, url: str) -> str:
    """Извлекаем 5-значный код из названия или URL."""
    parts = name.strip().split()
    if parts and re.match(r'^\d{5}$', parts[0]):
        return parts[0]
    # В URL бывает код: im-cafe-mega-alm02202 → 02202
    match = re.search(r'(\d{5})', url.split(".")[0])
    if match:
        return match.group(1)
    # Fallback: сокращение из имени (для Café Mega Park)
    clean = re.sub(r"[^A-Za-zА-Яа-я0-9]", "", name)
    return clean[:8].upper()


def build_restaurants_from_server(server_xlsx: str) -> list[dict]:
    df = pd.read_excel(server_xlsx)
    restaurants = []
    for _, row in df.iterrows():
        name = str(row["Название"]).strip()
        url = str(row["Адрес"]).strip()
        proto = str(row.get("Протокол", "HTTPS")).strip().lower()

        # Пропускаем ЦО
        if "ЦО" in name or "fskz-co" in url:
            continue

        code = extract_code(name, url)
        base_url = f"{proto}://{url}"
        # department_name: берём как есть для числовых кодов
        # для кафе без кода — тоже name
        restaurants.append({
            "code": code,
            "name": name,
            "department_name": name,
            "base_url": base_url,
        })
    return restaurants


def build_dept_to_code_map(restaurants: list[dict]) -> dict[str, str]:
    """
    Из group_rate_restaurant.xlsx Department → код ресторана.
    Формат Department: "02005 I'M Maxima" или "02005 Maxima"
    """
    mapping = {}
    for r in restaurants:
        code = r["code"]
        mapping[code] = code  # прямое совпадение

    # Дополнительный маппинг для dept-строк из xlsx
    dept_map = {
        "01001 I'M Kabanbay": "01001",
        "01002 I'M Mega Silk Way": "01002",
        "01003 I'M SAB": "01003",
        "01004 I'M Keruen": "01004",
        "01005 I'M Kenesary": "01005",
        "01006 I'M Eurasia": "01006",
        "1006 I'M Eurasia": "01006",   # опечатка в источнике
        "01007 I'M M36": "01007",
        "01008 I'M Imanova": "01008",
        "02001 I'M Alatau": "02001",
        "02002 I'M Mega Park": "02002",
        "02003 I'M Mega Almaty": "02003",
        "02004 I'M Mamyr": "02004",
        "02005 I'M Maxima": "02005",
        "02007 I'M Baikonur": "02007",
        "02008 I'M Bukhar Zhyrau": "02008",
        "02009 I'M ADK": "02009",
        "02010 I'M Atakent": "02010",
        "02011 I'M Aksay": "02011",
        "02012 I'M Dinamo": "02012",
        "02013 I'M APORT": "02013",
        "02014 I'M Park Seifullin": "02014",
        "02019 Dostyk Plaza": "02019",
        "04001 I'M 1st President Park": "04001",
        "06001 I'M Satpayev": "06001",
        "09001 I'M Quarter 45": "09001",
        "9002 I'M Quarter 45": "09002",
        "10001 I'M Abay": "10001",
    }
    return dept_map


def main():
    db = SessionLocal()
    try:
        # ── 1. Читаем Server.xlsx ─────────────────────────────────────────
        print(f"Читаем {SERVER_XLSX}...")
        restaurant_data = build_restaurants_from_server(SERVER_XLSX)
        print(f"Найдено в Server.xlsx: {len(restaurant_data)} ресторанов")

        # ── 2. Получаем все пресеты из БД ────────────────────────────────
        all_presets = db.query(PresetDefinition).all()
        preset_ids = [p.id for p in all_presets]
        print(f"Пресетов в БД: {len(preset_ids)}")

        # ── 3. Существующие коды ресторанов в БД ─────────────────────────
        existing_codes = {r.code for r in db.query(Restaurant.code).all()}
        print(f"Уже в БД: {sorted(existing_codes)}")

        # ── 4. Вставляем новые рестораны ──────────────────────────────────
        new_restaurants = []
        for r in restaurant_data:
            if r["code"] in existing_codes:
                print(f"  [SKIP] {r['code']} — уже существует")
                continue

            rest = Restaurant(
                code=r["code"],
                name=r["name"],
                department_name=r["department_name"],
                base_url=r["base_url"],
                iiko_login=LOGIN,
                iiko_password_hash=PASSWORD_HASH,
                is_active=True,
            )
            db.add(rest)
            new_restaurants.append(r["code"])

        db.flush()  # получаем id для новых записей
        print(f"\nДобавлено ресторанов: {len(new_restaurants)}: {sorted(new_restaurants)}")

        # ── 5. Привязываем все пресеты к новым ресторанам ─────────────────
        new_rest_objs = db.query(Restaurant).filter(
            Restaurant.code.in_(new_restaurants)
        ).all()

        for rest in new_rest_objs:
            for preset in all_presets:
                db.execute(
                    insert(restaurant_presets)
                    .values(restaurant_id=rest.id, preset_id=preset.id)
                    .prefix_with("OR IGNORE")  # на случай дублей
                )
        print(f"Пресеты привязаны.")

        db.commit()

        # ── 6. Загружаем нормы из group_rate_restaurant.xlsx ──────────────
        print(f"\nЧитаем {RATES_XLSX}...")
        df_rates = pd.read_excel(RATES_XLSX)
        # Колонки: Department, Group, Rate
        print(f"Строк в файле норм: {len(df_rates)}")

        # Маппинг Department → код
        dept_to_code = build_dept_to_code_map(restaurant_data)

        # Получаем группы из БД: name → id
        group_map = {g.name.strip(): g.id for g in db.query(ProductGroup).all()}

        # Все рестораны из БД: code → id
        rest_map = {r.code: r.id for r in db.query(Restaurant).all()}

        added_rates = 0
        skipped_rates = 0
        unknown_dept = set()
        unknown_group = set()

        for _, row in df_rates.iterrows():
            dept = str(row["Department"]).strip()
            group_name = str(row["Group"]).strip()
            rate_raw = row["Rate"]

            try:
                rate_pct = float(str(rate_raw).replace(",", ".").replace("%", "").strip())
                # Если значение как 0.07 (7%) — умножаем
                if rate_pct <= 1.0:
                    rate_pct = rate_pct * 100
            except (ValueError, TypeError):
                continue

            code = dept_to_code.get(dept)
            if not code:
                unknown_dept.add(dept)
                continue

            rest_id = rest_map.get(code)
            if not rest_id:
                unknown_dept.add(f"{dept} (нет в БД: {code})")
                continue

            group_id = group_map.get(group_name)
            if not group_id:
                unknown_group.add(group_name)
                continue

            # Проверяем — уже есть?
            exists = db.query(WasteRate).filter(
                WasteRate.restaurant_id == rest_id,
                WasteRate.group_id == group_id,
            ).first()

            if exists:
                # Обновляем норму
                exists.rate_pct = rate_pct
                skipped_rates += 1
            else:
                db.add(WasteRate(
                    restaurant_id=rest_id,
                    group_id=group_id,
                    rate_pct=rate_pct,
                ))
                added_rates += 1

        db.commit()
        print(f"Норм добавлено: {added_rates}, обновлено: {skipped_rates}")

        if unknown_dept:
            print(f"\nНеизвестные департаменты (нет маппинга):")
            for d in sorted(unknown_dept):
                print(f"  - {d}")

        if unknown_group:
            print(f"\nНеизвестные группы (нет в product_groups):")
            for g in sorted(unknown_group):
                print(f"  - {g}")

        print("\n✓ Готово!")

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    main()
