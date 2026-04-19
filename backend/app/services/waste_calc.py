"""
Расчёт норм списания — логика идентична оригинальному app.py.
Ставки в БД хранятся как проценты (7, 10, 100).
Внутри функций конвертируем: rate = rate_pct / 100.
"""
import math
import pandas as pd


def to_float(val) -> float:
    try:
        return float(str(val).replace(",", ".").strip())
    except (ValueError, TypeError):
        return 0.0


def normalize_unit(x: str) -> str:
    x = str(x).strip().lower().replace(".", "").replace(",", "")
    if x in ("шт", "штука", "штук", "pcs", "piece"):
        return "шт"
    if x in ("кг", "kg", "килограмм", "килограммы"):
        return "кг"
    if x in ("л", "литр", "литры", "ltr", "l"):
        return "л"
    return x


def round_by_unit(value: float, unit_type: str) -> float:
    """Округление в зависимости от единицы измерения — как в app.py."""
    value = max(to_float(value), 0.0)  # отрицательные → 0
    unit = normalize_unit(unit_type or "")
    if unit == "шт":
        return float(math.floor(value))
    return round(value, 3)


def agg_amount(df: pd.DataFrame, source_col: str, out_col: str) -> pd.DataFrame:
    """Агрегация количества/суммы по ProductNum."""
    if df.empty:
        return pd.DataFrame(columns=["ProductNum", out_col])
    if "Product.Num" not in df.columns or source_col not in df.columns:
        return pd.DataFrame(columns=["ProductNum", out_col])

    tmp = df.copy()
    tmp["ProductNum"] = tmp["Product.Num"].astype(str).str.strip()
    tmp[source_col] = tmp[source_col].apply(to_float)
    grouped = tmp.groupby("ProductNum", as_index=False)[source_col].sum()
    return grouped.rename(columns={source_col: out_col})


def calc_allowed_qty(row: pd.Series) -> float:
    """
    Максимально допустимое кол-во списания.
    Логика из app.py:
      - rate == 1 (100%) AND inventory < 0 → abs(inventory)
      - иначе → sales * rate  (клипуется к 0 через round_by_unit)
    rate_pct хранится как % (7, 100), конвертируем сами.
    """
    rate = to_float(row.get("Норма %", 0)) / 100.0   # 7 → 0.07, 100 → 1.0
    sales_qty = to_float(row.get("Реализация", 0))
    inventory_net = to_float(row.get("Инвентаризация", 0))
    unit_type = str(row.get("Ед. изм.", ""))

    if rate == 1.0 and inventory_net < 0:
        return round_by_unit(abs(inventory_net), unit_type)

    return round_by_unit(sales_qty * rate, unit_type)


def calc_to_writeoff(row: pd.Series) -> float:
    """
    Кол-во к списанию.
    Логика из app.py:
      - rate == 1 AND inventory < 0 → abs(inventory)
      - иначе → min(remaining_limit, inventory_minus)
    """
    rate = to_float(row.get("Норма %", 0)) / 100.0
    inventory_net = to_float(row.get("Инвентаризация", 0))
    unit_type = str(row.get("Ед. изм.", ""))
    inventory_minus = max(-inventory_net, 0.0)   # положительное если дефицит

    if rate == 1.0 and inventory_net < 0:
        return round_by_unit(inventory_minus, unit_type)

    remaining_limit = to_float(row.get("Допустимо", 0)) - to_float(row.get("Уже списано", 0))
    remaining_limit = max(remaining_limit, 0.0)

    return round_by_unit(min(remaining_limit, inventory_minus), unit_type)


def calc_written_off_percent(row: pd.Series) -> float:
    """% списания от реализации — как в app.py."""
    sales_qty = to_float(row.get("Реализация", 0))
    already = to_float(row.get("Уже списано", 0))
    if sales_qty <= 0:
        return 0.0
    return round((already / sales_qty) * 100, 2)


def build_comment(row: pd.Series) -> str:
    """Комментарий к строке — идентично app.py."""
    group = str(row.get("Группа", ""))
    rate_pct = to_float(row.get("Норма %", 0))
    rate = rate_pct / 100.0
    inventory_net = to_float(row.get("Инвентаризация", 0))
    already = to_float(row.get("Уже списано", 0))
    allowed = to_float(row.get("Допустимо", 0))
    to_writeoff = to_float(row.get("К списанию", 0))

    if group == "NO_CATEGORY":
        return "Товар отсутствует в mapping"
    if rate == 0:
        return "Для группы товара не задан процент"
    if inventory_net >= 0:
        return "Инвентаризация корректна, списание не требуется"
    if rate == 1.0 and inventory_net < 0:
        return "Для товара установлена ставка 100%, можно списать весь минус инвентаризации"
    if already >= allowed and inventory_net < 0:
        return "Достигнут максимальный допустимый процент списания"
    if to_writeoff > 0:
        return "Минус по инвентаризации можно закрыть списанием"
    return "Требуется проверка продукта"


def _row_status(row: pd.Series) -> str:
    rate_pct = to_float(row.get("Норма %", 0))
    already = to_float(row.get("Уже списано", 0))
    allowed = to_float(row.get("Допустимо", 0))
    sales = to_float(row.get("Реализация", 0))

    if rate_pct == 0:
        return "no_rate"
    if sales == 0 and already == 0:
        return "no_writeoff_needed"
    if already > allowed and allowed >= 0:
        return "over_limit"
    return "ok"


def build_report_dataframe(
    sales: list,
    writeoffs: list,
    inventory: list,
    refs_goods: pd.DataFrame,
    group_rates_by_group: pd.DataFrame,
) -> pd.DataFrame:
    """
    Объединяет данные IIKO со справочниками.
    refs_goods:           ProductNum, product_catalog_id, Группа, Ед. изм.
    group_rates_by_group: Группа, Норма %   (Норма % — проценты: 7, 10, 100)
    """
    df_sales     = pd.DataFrame(sales)
    df_writeoff  = pd.DataFrame(writeoffs)
    df_inventory = pd.DataFrame(inventory)

    empty_qty = lambda col: pd.DataFrame(columns=["ProductNum", col])
    empty_sum = lambda col: pd.DataFrame(columns=["ProductNum", col])

    sales_agg     = agg_amount(df_sales,     "Amount",          "SalesQty")      if not df_sales.empty     else empty_qty("SalesQty")
    writeoff_agg  = agg_amount(df_writeoff,  "Amount",          "WriteOffQty")   if not df_writeoff.empty  else empty_qty("WriteOffQty")
    inventory_agg = agg_amount(df_inventory, "Amount",          "InventoryNet")  if not df_inventory.empty else empty_qty("InventoryNet")

    sales_sum_agg     = agg_amount(df_sales,     "Sum.ResignedSum", "SalesSum")      if not df_sales.empty     and "Sum.ResignedSum" in df_sales.columns     else empty_sum("SalesSum")
    writeoff_sum_agg  = agg_amount(df_writeoff,  "Sum.ResignedSum", "WriteOffSum")   if not df_writeoff.empty  and "Sum.ResignedSum" in df_writeoff.columns  else empty_sum("WriteOffSum")
    # Inventory TRANSACTIONS preset uses Amount as monetary value (no Sum.ResignedSum)
    if not df_inventory.empty:
        if "Sum.ResignedSum" in df_inventory.columns:
            inventory_sum_agg = agg_amount(df_inventory, "Sum.ResignedSum", "InventorySum")
        elif "Amount" in df_inventory.columns:
            inventory_sum_agg = agg_amount(df_inventory, "Amount", "InventorySum")
        else:
            inventory_sum_agg = empty_sum("InventorySum")
    else:
        inventory_sum_agg = empty_sum("InventorySum")

    # Мерж как в app.py: стартуем от IIKO данных (outer), потом left join refs_goods
    merged = sales_agg.merge(writeoff_agg,  on="ProductNum", how="outer")
    merged = merged.merge(inventory_agg,    on="ProductNum", how="outer")
    merged = merged.merge(sales_sum_agg,    on="ProductNum", how="outer")
    merged = merged.merge(writeoff_sum_agg, on="ProductNum", how="outer")
    merged = merged.merge(inventory_sum_agg,on="ProductNum", how="outer")
    merged = merged.fillna(0)

    # abs() как в app.py — IIKO отдаёт продажи/списания как отрицательные числа
    merged["SalesQty"]    = merged["SalesQty"].abs()
    merged["WriteOffQty"] = merged["WriteOffQty"].abs()
    merged["SalesSum"]    = merged["SalesSum"].abs()
    merged["WriteOffSum"] = merged["WriteOffSum"].abs()
    # InventoryNet НЕ abs() — отрицательное значение = дефицит, положительное = излишек

    # Left join к справочнику товаров
    refs = refs_goods.copy()
    refs["ProductNum"] = refs["ProductNum"].astype(str).str.strip()
    merged["ProductNum"] = merged["ProductNum"].astype(str).str.strip()
    merged = merged.merge(refs, on="ProductNum", how="left")

    merged["Группа"]   = merged["Группа"].fillna("NO_CATEGORY")
    merged["Ед. изм."] = merged["Ед. изм."].fillna("")

    # Переименовываем в русские колонки как в app.py
    df = merged.rename(columns={
        "SalesQty":     "Реализация",
        "WriteOffQty":  "Уже списано",
        "InventoryNet": "Инвентаризация",
        "SalesSum":     "Реализация сумма",
        "WriteOffSum":  "Уже списано сумма",
        "InventorySum": "Инвентаризация сумма",
    })

    qty_cols = ["Реализация", "Уже списано", "Инвентаризация"]
    sum_cols = ["Реализация сумма", "Уже списано сумма", "Инвентаризация сумма"]
    for col in qty_cols + sum_cols:
        df[col] = df[col].fillna(0.0).apply(to_float)

    # Нормы по группам
    df = df.merge(group_rates_by_group, on="Группа", how="left")
    df["Норма %"] = df["Норма %"].fillna(0.0)

    # Расчёт
    df["Допустимо"]               = df.apply(calc_allowed_qty, axis=1)
    df["К списанию"]              = df.apply(calc_to_writeoff, axis=1)
    df["Списано % от реализации"] = df.apply(calc_written_off_percent, axis=1)
    df["Сверх нормы"]             = ((df["Уже списано"] > df["Допустимо"]) & (df["Допустимо"] > 0)).astype(int)

    # Статус и комментарий добавляем после расчёта
    df["status"]      = df.apply(_row_status, axis=1)
    df["Комментарий"] = df.apply(build_comment, axis=1)

    # Сортировка как в app.py: |Инвентаризация| desc, К списанию desc
    df["_inv_abs"] = df["Инвентаризация"].abs()
    df = df.sort_values(by=["_inv_abs", "К списанию"], ascending=[False, False]).drop(columns=["_inv_abs"])

    return df
