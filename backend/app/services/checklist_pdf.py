"""
Генератор PDF для чек-листа менеджера смены.
Формат: A4, портрет, похож на бумажный оригинал.
"""
import io
from datetime import datetime, timezone, timedelta
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer,
    HRFlowable, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus.flowables import HRFlowable

# ── Цвета ─────────────────────────────────────────────────────────────────────
C_HEADER     = colors.HexColor("#1a1a2e")
C_YELLOW     = colors.HexColor("#f5a623")
C_SECTION_BG = colors.HexColor("#f0f4f8")
C_DONE       = colors.HexColor("#16a34a")
C_UNDONE     = colors.HexColor("#dc2626")
C_GRAY       = colors.HexColor("#6b7280")
C_LIGHT_GRAY = colors.HexColor("#e5e7eb")
C_WHITE      = colors.white
C_BLACK      = colors.black
C_TABLE_HEAD = colors.HexColor("#1e3a5f")
C_ROW_ALT   = colors.HexColor("#f8fafc")

ALMATY_TZ = timezone(timedelta(hours=5))

SECTION_LABELS = {
    "before_shift":  "ПОДГОТОВКА К СМЕНЕ",
    "during_people": "ЛЮДИ",
    "during_obs":    "НАБЛЮДЕНИЕ ЗА ОПАСНЫМИ ЗНАКАМИ",
    "during_equip":  "ОБОРУДОВАНИЕ",
    "evening_proc":  "ВЕЧЕРНИЕ ПРОЦЕДУРЫ",
    "after_shift":   "ПОСЛЕ СМЕНЫ",
}

SHIFT_LABELS = {"morning": "Утренняя", "evening": "Вечерняя", "night": "Ночная"}


def _styles():
    ss = getSampleStyleSheet()

    def s(name, **kwargs):
        return ParagraphStyle(name, parent=ss["Normal"], **kwargs)

    return {
        "title":       s("title",        fontSize=16, fontName="Helvetica-Bold",  textColor=C_WHITE,      alignment=TA_LEFT),
        "subtitle":    s("subtitle",     fontSize=9,  fontName="Helvetica",       textColor=C_WHITE,      alignment=TA_LEFT),
        "section":     s("section",      fontSize=9,  fontName="Helvetica-Bold",  textColor=C_TABLE_HEAD, spaceAfter=2),
        "task_done":   s("task_done",    fontSize=8,  fontName="Helvetica",       textColor=C_GRAY,       leading=11),
        "task_undone": s("task_undone",  fontSize=8,  fontName="Helvetica",       textColor=C_BLACK,      leading=11),
        "task_skip":   s("task_skip",    fontSize=8,  fontName="Helvetica",       textColor=C_GRAY,       leading=11),
        "normal":      s("normal",       fontSize=8,  fontName="Helvetica",       textColor=C_BLACK,      leading=12),
        "bold":        s("bold",         fontSize=8,  fontName="Helvetica-Bold",  textColor=C_BLACK),
        "small":       s("small",        fontSize=7,  fontName="Helvetica",       textColor=C_GRAY),
        "kpi_label":   s("kpi_label",    fontSize=7.5, fontName="Helvetica-Bold", textColor=C_BLACK),
        "priority":    s("priority",     fontSize=8,  fontName="Helvetica",       textColor=C_BLACK,      leading=12, leftIndent=4),
        "footer":      s("footer",       fontSize=7,  fontName="Helvetica",       textColor=C_GRAY,       alignment=TA_CENTER),
    }


def _checkbox(done: Optional[bool]) -> str:
    if done is True:   return "✓"
    if done is False:  return "✗"
    return "○"


def _fmt_num(v, decimals=0) -> str:
    if v is None: return "—"
    try:
        n = float(v)
        if decimals == 0: return f"{int(round(n)):,}".replace(",", " ")
        return f"{n:,.{decimals}f}".replace(",", " ")
    except Exception:
        return str(v)


def generate_checklist_pdf(
    submission: dict,
    answers: list,        # [{"template_id": int, "is_done": bool|None, ...}]
    templates: list,      # [{"id": int, "section": str, "task_text": str, ...}]
    kpi: dict,
    restaurant_name: str,
) -> bytes:
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.2*cm, bottomMargin=1.5*cm,
        title="Чек-лист менеджера смены",
    )

    st = _styles()
    story = []

    # ── Шапка ─────────────────────────────────────────────────────────────────
    shift_label  = SHIFT_LABELS.get(submission.get("shift_type", ""), "—")
    manager_name = submission.get("manager_name") or "—"
    date_str     = submission.get("date", "—")
    status       = submission.get("status", "draft")
    submitted_at = submission.get("submitted_at")
    if submitted_at:
        try:
            dt = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
            dt = dt.astimezone(ALMATY_TZ)
            submitted_at_str = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            submitted_at_str = submitted_at
    else:
        submitted_at_str = "—"

    # Шапка с фоном
    header_data = [[
        Paragraph(f"<b>ЧЕК-ЛИСТ МЕНЕДЖЕРА СМЕНЫ</b>", st["title"]),
        Paragraph(f"I'M Restaurant · {restaurant_name}", st["subtitle"]),
    ]]
    header_table = Table(header_data, colWidths=[12*cm, 5*cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), C_HEADER),
        ("TEXTCOLOR",   (0,0), (-1,-1), C_WHITE),
        ("ROWPADDINGS", (0,0), (-1,-1), 8),
        ("TOPPADDING",  (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING", (0,0), (-1,-1), 12),
        ("RIGHTPADDING",(0,0),(-1,-1), 12),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",       (1,0), (1,-1), "RIGHT"),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 3*mm))

    # Мета-строка
    meta_data = [[
        Paragraph(f"<b>Дата:</b> {date_str}", st["bold"]),
        Paragraph(f"<b>Смена:</b> {shift_label}", st["bold"]),
        Paragraph(f"<b>Менеджер:</b> {manager_name}", st["bold"]),
        Paragraph(f"<b>Статус:</b> {'✓ Сдан' if status == 'submitted' else '⏳ Черновик'}", st["bold"]),
    ]]
    meta_table = Table(meta_data, colWidths=[4*cm, 3.5*cm, 5.5*cm, 4*cm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), C_SECTION_BG),
        ("TOPPADDING",   (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("BOX",          (0,0), (-1,-1), 0.5, C_LIGHT_GRAY),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 4*mm))

    # ── Индекс ответов ────────────────────────────────────────────────────────
    ans_map = {a["template_id"]: a for a in answers}
    tmpl_map = {t["id"]: t for t in templates}

    # Группируем шаблоны по секциям
    from collections import defaultdict
    SECTION_ORDER = ["before_shift", "during_people", "during_obs", "during_equip", "evening_proc", "after_shift"]
    by_section = defaultdict(list)
    for t in sorted(templates, key=lambda x: x["sort_order"]):
        by_section[t["section"]].append(t)

    # Считаем прогресс
    done_count  = sum(1 for a in answers if a.get("is_done") is True)
    total_count = len(templates)
    pct         = round(done_count / total_count * 100) if total_count else 0

    # ── Прогресс-бар ──────────────────────────────────────────────────────────
    prog_data = [[
        Paragraph(f"<b>Выполнено задач: {done_count} из {total_count} ({pct}%)</b>", st["bold"]),
        Paragraph(f"Сдан: {submitted_at_str}", st["small"]),
    ]]
    prog_table = Table(prog_data, colWidths=[13*cm, 4*cm])
    prog_table.setStyle(TableStyle([
        ("ALIGN",        (1,0), (1,0), "RIGHT"),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
    ]))
    story.append(prog_table)
    story.append(Spacer(1, 2*mm))

    # Полоска прогресса (два столбца: заполненная часть + остаток)
    bar_full  = 17*cm
    bar_done  = bar_full * pct / 100
    bar_color = C_DONE if pct >= 80 else (C_YELLOW if pct >= 50 else C_UNDONE)
    if pct == 0:
        bar = Table([[""]], colWidths=[bar_full], rowHeights=[6])
        bar.setStyle(TableStyle([("BACKGROUND", (0,0), (0,0), C_LIGHT_GRAY)]))
    elif pct == 100:
        bar = Table([[""]], colWidths=[bar_full], rowHeights=[6])
        bar.setStyle(TableStyle([("BACKGROUND", (0,0), (0,0), bar_color)]))
    else:
        bar = Table([["", ""]], colWidths=[bar_done, bar_full - bar_done], rowHeights=[6])
        bar.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,0), bar_color),
            ("BACKGROUND", (1,0), (1,0), C_LIGHT_GRAY),
            ("TOPPADDING",    (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
            ("LEFTPADDING",   (0,0), (-1,-1), 0),
            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
        ]))
    story.append(bar)
    story.append(Spacer(1, 4*mm))

    # ── Секции чеклиста ───────────────────────────────────────────────────────
    def section_block(sec_key):
        tasks = by_section.get(sec_key, [])
        if not tasks:
            return []

        label = SECTION_LABELS.get(sec_key, sec_key)
        rows = [[
            Paragraph(f"<b>{label}</b>", st["section"]),
            Paragraph("<b>✓/✗</b>", st["section"]),
        ]]
        alt = False
        for t in tasks:
            ans = ans_map.get(t["id"])
            done = ans.get("is_done") if ans else None
            cb = _checkbox(done)
            style = st["task_done"] if done else st["task_undone"]
            task_text = t["task_text"]
            if t.get("deadline_time"):
                task_text += f" <font color='#f5a623' size='7'>({t['deadline_time']})</font>"
            row = [
                Paragraph(task_text, style),
                Paragraph(f"<b>{cb}</b>", st["bold"]),
            ]
            rows.append(row)
            alt = not alt

        t_style = [
            ("BACKGROUND",   (0,0), (-1,0),  C_TABLE_HEAD),
            ("TEXTCOLOR",    (0,0), (-1,0),  C_WHITE),
            ("TOPPADDING",   (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0), (-1,-1), 4),
            ("LEFTPADDING",  (0,0), (-1,-1), 6),
            ("RIGHTPADDING", (0,0), (-1,-1), 6),
            ("ALIGN",        (1,0), (1,-1),  "CENTER"),
            ("VALIGN",       (0,0), (-1,-1), "TOP"),
            ("BOX",          (0,0), (-1,-1), 0.5, C_LIGHT_GRAY),
            ("LINEBELOW",    (0,0), (-1,-2), 0.3, C_LIGHT_GRAY),
        ]
        # Alternate row colors
        for i in range(1, len(rows)):
            if i % 2 == 0:
                t_style.append(("BACKGROUND", (0,i), (-1,i), C_ROW_ALT))

        tbl = Table(rows, colWidths=[15.5*cm, 1.5*cm])
        tbl.setStyle(TableStyle(t_style))
        return [KeepTogether([tbl, Spacer(1, 3*mm)])]

    # Блок 1: Подготовка к смене
    story.append(Paragraph("1. ПОДГОТОВКА К СМЕНЕ", st["section"]))
    story.extend(section_block("before_shift"))

    # Блок 2: Цели дня (KPI)
    story.append(Paragraph("2. ЦЕЛИ НА ДЕНЬ / KPI", st["section"]))

    kpi_rows = [
        [Paragraph("<b>Показатель</b>",       st["kpi_label"]),
         Paragraph("<b>План</b>",              st["kpi_label"]),
         Paragraph("<b>Факт утро</b>",         st["kpi_label"]),
         Paragraph("<b>Факт вечер</b>",        st["kpi_label"])],
    ]
    KPI_DEFS = [
        ("SALES (₸)",       "sales_plan",          "sales_fact_morning",       "sales_fact_evening"),
        ("GC (чеков)",      "gc_plan",             "gc_fact_morning",          "gc_fact_evening"),
        ("Av.Check (₸)",    "av_check_plan",       "av_check_fact_morning",    "av_check_fact_evening"),
        ("% DT",            "pct_dt_plan",         "pct_dt_fact_m",            "pct_dt_fact_e"),
        ("% Киоск",         "pct_kiosk_plan",      "pct_kiosk_fact_m",         "pct_kiosk_fact_e"),
        ("% Cafe",          "pct_cafe_plan",       "pct_cafe_fact_m",          "pct_cafe_fact_e"),
        ("% DLV",           "pct_dlv_plan",        "pct_dlv_fact_m",           "pct_dlv_fact_e"),
        ("Рейтинг GM Voice","rating_gm_voice_plan","rating_gm_voice_fact_m",   "rating_gm_voice_fact_e"),
        ("Рейтинг 1&2",     "rating_1and2_plan",   "rating_1and2_fact_m",      "rating_1and2_fact_e"),
        ("OEPE (сек)",      "oepe_plan",           "oepe_fact_morning",        "oepe_fact_evening"),
        ("GCPCH",           "gcpch_plan",          "gcpch_fact_morning",       "gcpch_fact_evening"),
        ("Waste State (%)", "waste_state_plan",    "waste_state_fact",         None),
        ("DLV заказы",      "dlv_orders_plan",     "dlv_orders_fact_m",        "dlv_orders_fact_e"),
    ]
    for label, p_key, fm_key, fe_key in KPI_DEFS:
        pv = _fmt_num(kpi.get(p_key))
        fmv = _fmt_num(kpi.get(fm_key))
        fev = _fmt_num(kpi.get(fe_key)) if fe_key else "—"
        kpi_rows.append([
            Paragraph(label, st["normal"]),
            Paragraph(pv,    st["normal"]),
            Paragraph(fmv,   st["normal"]),
            Paragraph(fev,   st["normal"]),
        ])

    kpi_table = Table(kpi_rows, colWidths=[5.5*cm, 3.5*cm, 4*cm, 4*cm])
    kpi_style = [
        ("BACKGROUND",   (0,0), (-1,0),  C_TABLE_HEAD),
        ("TEXTCOLOR",    (0,0), (-1,0),  C_WHITE),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("LEFTPADDING",  (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("BOX",          (0,0), (-1,-1), 0.5, C_LIGHT_GRAY),
        ("LINEBELOW",    (0,0), (-1,-2), 0.3, C_LIGHT_GRAY),
        ("ALIGN",        (1,0), (-1,-1), "CENTER"),
    ]
    for i in range(1, len(kpi_rows)):
        if i % 2 == 0:
            kpi_style.append(("BACKGROUND", (0,i), (-1,i), C_ROW_ALT))
    kpi_table.setStyle(TableStyle(kpi_style))
    story.append(KeepTogether([kpi_table, Spacer(1, 4*mm)]))

    # Приоритеты дня
    story.append(Paragraph("Приоритеты дня:", st["bold"]))
    story.append(Spacer(1, 2*mm))
    for n in range(1, 4):
        text = submission.get(f"priority_{n}_text") or "—"
        story.append(Paragraph(f"<b>Приоритет {n}:</b> {text}", st["priority"]))
    story.append(Spacer(1, 4*mm))

    # Блок 3: В течение смены
    story.append(Paragraph("3. В ТЕЧЕНИЕ СМЕНЫ", st["section"]))
    for sec in ["during_people", "during_obs", "during_equip", "evening_proc"]:
        story.extend(section_block(sec))

    # Блок 4: После смены
    story.append(Paragraph("4. ПОСЛЕ СМЕНЫ", st["section"]))
    story.extend(section_block("after_shift"))

    # Блок 5: Итоги
    story.append(Paragraph("5. ИТОГИ ДНЯ", st["section"]))
    story.append(Spacer(1, 2*mm))

    for n in range(1, 4):
        text   = submission.get(f"priority_{n}_text")   or ""
        done   = submission.get(f"priority_{n}_done")
        result = submission.get(f"priority_{n}_result") or ""

        done_str   = "✓ Выполнен" if done is True else ("✗ Не выполнен" if done is False else "○ Не отмечен")
        done_color = "#16a34a" if done is True else ("#dc2626" if done is False else "#6b7280")

        rows = [
            [Paragraph(f"<b>Приоритет {n}</b>", st["kpi_label"]),
             Paragraph(f"<font color='{done_color}'><b>{done_str}</b></font>", st["kpi_label"])],
            [Paragraph(f"Цель: {text or '—'}", st["normal"]),
             Paragraph("", st["normal"])],
            [Paragraph(f"Результат: {result or '—'}", st["normal"]),
             Paragraph("", st["normal"])],
        ]
        tbl = Table(rows, colWidths=[11*cm, 6*cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,0),  C_SECTION_BG),
            ("TOPPADDING",   (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0), (-1,-1), 4),
            ("LEFTPADDING",  (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("BOX",          (0,0), (-1,-1), 0.5, C_LIGHT_GRAY),
            ("SPAN",         (0,1), (-1,1)),
            ("SPAN",         (0,2), (-1,2)),
        ]))
        story.append(KeepTogether([tbl, Spacer(1, 3*mm)]))

    # ── Подпись ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_LIGHT_GRAY))
    story.append(Spacer(1, 3*mm))

    sign_rows = [[
        Paragraph("Менеджер смены: ___________________", st["normal"]),
        Paragraph(f"Подпись: ___________", st["normal"]),
        Paragraph(f"Дата: {date_str}", st["normal"]),
    ]]
    sign_table = Table(sign_rows, colWidths=[7*cm, 5*cm, 5*cm])
    sign_table.setStyle(TableStyle([
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
    ]))
    story.append(sign_table)

    # ── Футер ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 3*mm))
    now_almaty = datetime.now(ALMATY_TZ).strftime("%d.%m.%Y %H:%M")
    story.append(Paragraph(
        f"Сформировано: {now_almaty} (Алматы) · WasteControl · I'M Restaurant",
        st["footer"]
    ))

    def _add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(C_GRAY)
        canvas.drawRightString(A4[0] - 1.5*cm, 0.8*cm, f"Страница {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    return buf.getvalue()
