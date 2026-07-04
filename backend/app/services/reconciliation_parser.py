"""
Парсер актов сверки взаиморасчётов (xls/xlsx/pdf), присланных поставщиками.

Стандартный формат 1С-выгрузки: два зеркальных блока таблицы
(«По данным {Организация 1}» / «По данным {Организация 2}»), каждый с
колонками Дата | Документ | Дебет | Кредит, плюс строки
«Сальдо на начало» / «Обороты за период» / «Сальдо на конец».

Никакого OCR/LLM — детерминированный разбор текстового/табличного слоя.
"""
import io
import re

_LABELS = ("Дата", "Документ", "Дебет", "Кредит")
_STOP_MARKERS = ("Обороты за период", "Сальдо на конец")
_START_MARKER = "Сальдо на начало"

_BIN_RE = re.compile(r"БИН:\s*(\d{9,12})")
_PERIOD_RE = re.compile(
    r"период\s+с\s+(\d{2}\.\d{2}\.\d{4})\s+по\s+(\d{2}\.\d{2}\.\d{4})", re.IGNORECASE
)
# Нежадный до "По данным" следующего блока или ", KZT" — заголовки двух
# колонок часто сливаются в одну строку при извлечении текста из PDF.
_ORG_RE = re.compile(r"По данным\s+(.+?)(?:,\s*KZT|(?=По данным)|$)", re.IGNORECASE)
_DOC_NUMBER_RE = re.compile(r"(\d{3,})\s*от\s*\d{2}\.\d{2}\.\d{4}")
_DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{2,4}$")


def _parse_money(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_row_date(s: str) -> str | None:
    s = (s or "").strip()
    if not _DATE_RE.match(s):
        return None
    d, m, y = s.split(".")
    if len(y) == 2:
        y = "20" + y
    try:
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    except ValueError:
        return None


def _parse_full_date(s: str) -> str | None:
    s = (s or "").strip()
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", s)
    if not m:
        return None
    d, mo, y = m.groups()
    return f"{y}-{mo}-{d}"


def _extract_meta(full_text: str) -> dict:
    bins = _BIN_RE.findall(full_text)
    orgs = _ORG_RE.findall(full_text)
    period_m = _PERIOD_RE.search(full_text)
    return {
        "left_org": {
            "name": (orgs[0].strip() if len(orgs) > 0 else None),
            "bin": (bins[0] if len(bins) > 0 else None),
        },
        "right_org": {
            "name": (orgs[1].strip() if len(orgs) > 1 else None),
            "bin": (bins[1] if len(bins) > 1 else None),
        },
        "period": {
            "from": _parse_full_date(period_m.group(1)) if period_m else None,
            "to": _parse_full_date(period_m.group(2)) if period_m else None,
        },
    }


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _find_header_columns(grid: list[list]) -> tuple[int, dict[str, int], dict[str, int]]:
    """Ищет строку-заголовок (Дата/Документ/Дебет/Кредит x2) и определяет колонки left/right блоков."""
    for row_idx, row in enumerate(grid):
        cells = [_norm(c) for c in row]
        positions: dict[str, list[int]] = {label: [] for label in _LABELS}
        for col_idx, cell in enumerate(cells):
            if cell in positions:
                positions[cell].append(col_idx)
        if all(len(positions[label]) >= 2 for label in _LABELS):
            left = {label: positions[label][0] for label in _LABELS}
            right = {label: positions[label][1] for label in _LABELS}
            return row_idx, left, right
    raise ValueError(
        "Не найдена строка заголовка таблицы (Дата/Документ/Дебет/Кредит) — "
        "неизвестный формат акта сверки"
    )


def _parse_grid(grid: list[list], full_text: str) -> dict:
    header_idx, left_cols, right_cols = _find_header_columns(grid)
    meta = _extract_meta(full_text)

    rows: list[dict] = []
    opening: dict | None = None
    closing: dict | None = None
    warnings: list[str] = []

    def _cell(row, col_map, label):
        idx = col_map[label]
        return row[idx] if idx < len(row) else None

    for row in grid[header_idx + 1:]:
        row_text = _norm(" ".join(str(c) for c in row if c))
        if not row_text:
            continue

        if _START_MARKER in row_text:
            opening = {
                "left_debit": _parse_money(_cell(row, left_cols, "Дебет")),
                "left_credit": _parse_money(_cell(row, left_cols, "Кредит")),
                "right_debit": _parse_money(_cell(row, right_cols, "Дебет")),
                "right_credit": _parse_money(_cell(row, right_cols, "Кредит")),
            }
            continue

        if any(marker in row_text for marker in _STOP_MARKERS):
            closing = {
                "left_debit": _parse_money(_cell(row, left_cols, "Дебет")),
                "left_credit": _parse_money(_cell(row, left_cols, "Кредит")),
                "right_debit": _parse_money(_cell(row, right_cols, "Дебет")),
                "right_credit": _parse_money(_cell(row, right_cols, "Кредит")),
            }
            continue

        date_raw = _cell(row, left_cols, "Дата") or _cell(row, right_cols, "Дата")
        description = _norm(_cell(row, left_cols, "Документ") or _cell(row, right_cols, "Документ"))
        left_debit = _parse_money(_cell(row, left_cols, "Дебет"))
        left_credit = _parse_money(_cell(row, left_cols, "Кредит"))
        right_debit = _parse_money(_cell(row, right_cols, "Дебет"))
        right_credit = _parse_money(_cell(row, right_cols, "Кредит"))

        if not description and left_debit is None and left_credit is None and right_debit is None and right_credit is None:
            continue

        doc_m = _DOC_NUMBER_RE.search(description)
        rows.append({
            "date": _parse_row_date(date_raw),
            "description": description,
            "document_number": doc_m.group(1) if doc_m else None,
            "left_debit": left_debit,
            "left_credit": left_credit,
            "right_debit": right_debit,
            "right_credit": right_credit,
        })

    if not rows:
        warnings.append("В файле не найдено ни одной строки с операциями за период")

    return {
        "left_org": meta["left_org"],
        "right_org": meta["right_org"],
        "period": meta["period"],
        "rows": rows,
        "opening_balance": opening,
        "closing_balance": closing,
        "warnings": warnings,
    }


def _xls_to_grid(file_bytes: bytes) -> tuple[list[list], str]:
    import xlrd

    wb = xlrd.open_workbook(file_contents=file_bytes)
    sheet = wb.sheet_by_index(0)
    grid = [
        [sheet.cell_value(r, c) for c in range(sheet.ncols)]
        for r in range(sheet.nrows)
    ]
    full_text = "\n".join(_norm(c) for row in grid for c in row if c not in (None, ""))
    return grid, full_text


def _xlsx_to_grid(file_bytes: bytes) -> tuple[list[list], str]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    sheet = wb.worksheets[0]
    grid = [[cell for cell in row] for row in sheet.iter_rows(values_only=True)]
    full_text = "\n".join(_norm(c) for row in grid for c in row if c not in (None, ""))
    return grid, full_text


def _pdf_to_grid(file_bytes: bytes) -> tuple[list[list], str]:
    import pdfplumber

    grid: list[list] = []
    texts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            texts.append(page.extract_text() or "")
            for table in page.extract_tables():
                grid.extend(table)
    return grid, "\n".join(texts)


def parse_reconciliation_file(file_bytes: bytes, filename: str) -> dict:
    ext = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""

    if ext == ".xls":
        grid, full_text = _xls_to_grid(file_bytes)
    elif ext == ".xlsx":
        grid, full_text = _xlsx_to_grid(file_bytes)
    elif ext == ".pdf":
        grid, full_text = _pdf_to_grid(file_bytes)
    else:
        raise ValueError("Поддерживаются форматы: .xls, .xlsx, .pdf")

    return _parse_grid(grid, full_text)
