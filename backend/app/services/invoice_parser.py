"""
Парсинг Excel-выгрузки от поставщика ABL.
Формат файла:
  Лист HEADER: Дата получения, № накладной, № счета-фактуры, ...
  Лист DETAILS с колонками:
    № счета-фактуры | стол | WRIN код | ... | Наименование | ед.изм. | Кейсовость |
    [кол-во упаковок] | Цена за упаковку (с НДС) | Сумма без НДС | Ставка НДС |
    НДС | Сумма с НДС | ... | Subsys (ABL article)

Важно:
  "Цена за упаковку" = цена за кейс С НДС (не без!)
  unit_price (без НДС) = Сумма_без_НДС / кол_кейсов
  unit_price_vat       = "Цена за упаковку"
"""
import re
from datetime import datetime

import pandas as pd


def parse_abl_invoice(file_bytes: bytes) -> tuple[list[dict], dict]:
    """
    Парсит Excel байты накладной ABL.

    Возвращает:
      rows: list[dict] — строки DETAILS:
        invoice_num, abl_article, quantity, num_cases,
        unit_price (без НДС), unit_price_vat (с НДС),
        total_price (без НДС), total_price_vat (с НДС),
        vat_pct, vat_sum

      meta: dict — метаданные из HEADER:
        invoice_number, invoice_date (datetime | None), supplier_name
    """
    import io

    xls = pd.ExcelFile(io.BytesIO(file_bytes))

    # ── HEADER ────────────────────────────────────────────────────────────────
    meta: dict = {"invoice_number": None, "invoice_date": None, "supplier_name": "ABL"}

    if "HEADER" in xls.sheet_names:
        # Row 0 = column names, Row 1 = column numbers, Row 2+ = data
        hdr = pd.read_excel(xls, sheet_name="HEADER", header=0, skiprows=[1])
        hdr.columns = [str(c).strip().replace("\n", " ").strip() for c in hdr.columns]
        cols_l = [(c.lower(), c) for c in hdr.columns]

        def _hfind(*variants):
            for v in variants:
                for cl, c in cols_l:
                    if v in cl:
                        return c
            return None

        def _hval(col):
            if col is None or hdr.empty:
                return None
            vals = hdr[col].dropna()
            return vals.iloc[0] if not vals.empty else None

        # Дата накладной (приоритет) или Дата получения
        date_col = _hfind("дата накладной", "дата получения")
        raw_date = _hval(date_col)
        if raw_date is not None:
            if isinstance(raw_date, (datetime, pd.Timestamp)):
                meta["invoice_date"] = pd.Timestamp(raw_date).to_pydatetime().replace(tzinfo=None)
            else:
                for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                    try:
                        meta["invoice_date"] = datetime.strptime(str(raw_date).strip(), fmt)
                        break
                    except ValueError:
                        pass

        # Номер накладной
        num_col = _hfind("№ накладной", "номер накладной")
        raw_num = _hval(num_col)
        if raw_num is not None:
            meta["invoice_number"] = str(int(raw_num)) if isinstance(raw_num, (int, float)) else str(raw_num).strip()

    # ── DETAILS ───────────────────────────────────────────────────────────────
    if "DETAILS" not in xls.sheet_names:
        raise ValueError(f"В файле нет листа DETAILS. Листы: {xls.sheet_names}")

    df = pd.read_excel(xls, sheet_name="DETAILS")
    df.columns = [re.sub(r'\s+', ' ', str(c).replace("\n", " ")).strip() for c in df.columns]

    # Первая строка бывает числовым индексом — пропускаем
    if df.shape[0] > 0 and str(df.iloc[0, 0]).strip().lstrip("0").isdigit():
        df = df.iloc[1:].reset_index(drop=True)

    cols_lower = [(c.lower(), c) for c in df.columns]

    def _find(*variants, exclude=()):
        for variant in variants:
            for cl, c in cols_lower:
                if variant in cl and not any(e in cl for e in exclude):
                    return c
        raise ValueError(
            f"Не найдена колонка (искал: {list(variants)}) в {list(df.columns)}"
        )

    col_invoice  = _find("счета", "документ", "накладн")
    col_subsys   = _find("subsys")
    col_cases    = _find("кейсовость")

    # Кол-во упаковок — колонка сразу после 'Кейсовость'
    cases_pos  = list(df.columns).index(col_cases)
    col_qty    = df.columns[cases_pos + 1]

    col_price_case = _find("цена за упаковку")          # цена за кейс С НДС
    col_sum_no_vat = _find("сумма без ндс")             # итого без НДС
    col_sum_vat    = _find("сумма с ндс")               # итого с НДС
    col_vat_pct    = _find("ставка ндс")
    col_vat_sum    = _find("ндс", exclude=("сумма", "ставка", "код"))

    qty_cases  = pd.to_numeric(df[col_qty],       errors="coerce").fillna(1)
    qty_unit   = pd.to_numeric(df[col_cases],     errors="coerce").fillna(0)
    total_no   = pd.to_numeric(df[col_sum_no_vat],errors="coerce").fillna(0)
    total_vat  = pd.to_numeric(df[col_sum_vat],   errors="coerce").fillna(0)
    vat_sum    = pd.to_numeric(df[col_vat_sum],   errors="coerce").fillna(0)
    vat_pct    = pd.to_numeric(df[col_vat_pct],   errors="coerce").fillna(0)
    price_case_vat = pd.to_numeric(df[col_price_case], errors="coerce").fillna(0)

    # unit_price (без НДС) = Сумма_без_НДС / кол_кейсов
    unit_price = (total_no / qty_cases.replace(0, 1)).round(4)
    # unit_price_vat = Цена за упаковку (это уже с НДС)
    unit_price_vat = price_case_vat

    result_df = pd.DataFrame({
        "invoice_num":     df[col_invoice].astype(str).str.strip(),
        "abl_article":     df[col_subsys].astype(str).str.strip(),
        "quantity":        qty_unit * qty_cases,          # всего единиц
        "num_cases":       qty_cases,                     # кол-во кейсов
        "unit_price":      unit_price,                    # цена за кейс БЕЗ НДС
        "unit_price_vat":  unit_price_vat,                # цена за кейс С НДС
        "total_price":     total_no,                      # итого БЕЗ НДС
        "total_price_vat": total_vat,                     # итого С НДС
        "vat_pct":         vat_pct,
        "vat_sum":         vat_sum,
    })

    # Убираем строки без артикула
    result_df = result_df[result_df["abl_article"].notna()]
    result_df = result_df[result_df["abl_article"] != "nan"]
    result_df = result_df.reset_index(drop=True)

    return result_df.to_dict(orient="records"), meta
