"""Add checklist tables

Revision ID: 0024
Revises: 0023
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade():
    # Шаблоны задач (статичные, засеиваются один раз)
    op.create_table(
        "checklist_task_templates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("section", sa.String(50), nullable=False),
        # before_shift / during_people / during_obs / during_equip / evening_proc / after_shift
        sa.Column("shift_applicability", sa.String(20), nullable=False, server_default="all"),
        # all / morning / evening / night
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("task_text", sa.Text, nullable=False),
        sa.Column("deadline_time", sa.String(20), nullable=True),   # напр. "до 12:00"
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )

    # Одна запись = одна смена одного менеджера
    op.create_table(
        "checklist_submissions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("manager_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("manager_name", sa.String(100), nullable=True),   # ФИО вручную
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("shift_type", sa.String(10), nullable=False),     # morning / evening / night
        sa.Column("status", sa.String(10), nullable=False, server_default="'draft'"),
        # draft / submitted
        # ── Приоритеты дня (заполняются в разделе "Цели") ──
        sa.Column("priority_1_text", sa.Text, nullable=True),
        sa.Column("priority_2_text", sa.Text, nullable=True),
        sa.Column("priority_3_text", sa.Text, nullable=True),
        # ── Итоги по приоритетам (заполняются после смены) ──
        sa.Column("priority_1_done", sa.Boolean, nullable=True),
        sa.Column("priority_1_result", sa.Text, nullable=True),
        sa.Column("priority_2_done", sa.Boolean, nullable=True),
        sa.Column("priority_2_result", sa.Text, nullable=True),
        sa.Column("priority_3_done", sa.Boolean, nullable=True),
        sa.Column("priority_3_result", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Ответы по задачам чеклиста
    op.create_table(
        "checklist_answers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("checklist_submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("checklist_task_templates.id"), nullable=False),
        sa.Column("is_done", sa.Boolean, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("submission_id", "template_id", name="uq_answer"),
    )

    # KPI данные смены (план из БД + ручной ввод факта)
    op.create_table(
        "checklist_kpi",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("submission_id", sa.Integer, sa.ForeignKey("checklist_submissions.id", ondelete="CASCADE"), nullable=False, unique=True),
        # ── Sales ──
        sa.Column("sales_plan", sa.Numeric(14, 2), nullable=True),
        sa.Column("sales_fact_morning", sa.Numeric(14, 2), nullable=True),
        sa.Column("sales_fact_evening", sa.Numeric(14, 2), nullable=True),
        # ── GC ──
        sa.Column("gc_plan", sa.Integer, nullable=True),
        sa.Column("gc_fact_morning", sa.Integer, nullable=True),
        sa.Column("gc_fact_evening", sa.Integer, nullable=True),
        # ── Av.Check ──
        sa.Column("av_check_plan", sa.Numeric(10, 2), nullable=True),
        sa.Column("av_check_fact_morning", sa.Numeric(10, 2), nullable=True),
        sa.Column("av_check_fact_evening", sa.Numeric(10, 2), nullable=True),
        # ── Каналы % (план) ──
        sa.Column("pct_dt_plan", sa.Numeric(5, 2), nullable=True),
        sa.Column("pct_kiosk_plan", sa.Numeric(5, 2), nullable=True),
        sa.Column("pct_cafe_plan", sa.Numeric(5, 2), nullable=True),
        sa.Column("pct_dlv_plan", sa.Numeric(5, 2), nullable=True),
        # ── Каналы % (факт утро/вечер) ──
        sa.Column("pct_dt_fact_m", sa.Numeric(5, 2), nullable=True),
        sa.Column("pct_dt_fact_e", sa.Numeric(5, 2), nullable=True),
        sa.Column("pct_kiosk_fact_m", sa.Numeric(5, 2), nullable=True),
        sa.Column("pct_kiosk_fact_e", sa.Numeric(5, 2), nullable=True),
        sa.Column("pct_cafe_fact_m", sa.Numeric(5, 2), nullable=True),
        sa.Column("pct_cafe_fact_e", sa.Numeric(5, 2), nullable=True),
        sa.Column("pct_dlv_fact_m", sa.Numeric(5, 2), nullable=True),
        sa.Column("pct_dlv_fact_e", sa.Numeric(5, 2), nullable=True),
        # ── Ручные поля (нет в IIKO) ──
        sa.Column("rating_gm_voice_plan", sa.Numeric(5, 2), nullable=True),
        sa.Column("rating_gm_voice_fact_m", sa.Numeric(5, 2), nullable=True),
        sa.Column("rating_gm_voice_fact_e", sa.Numeric(5, 2), nullable=True),
        sa.Column("rating_1and2_plan", sa.Numeric(5, 2), nullable=True),
        sa.Column("rating_1and2_fact_m", sa.Numeric(5, 2), nullable=True),
        sa.Column("rating_1and2_fact_e", sa.Numeric(5, 2), nullable=True),
        sa.Column("oepe_plan", sa.Integer, nullable=True),
        sa.Column("oepe_fact_morning", sa.Integer, nullable=True),
        sa.Column("oepe_fact_evening", sa.Integer, nullable=True),
        sa.Column("gcpch_plan", sa.Numeric(5, 2), nullable=True),
        sa.Column("gcpch_fact_morning", sa.Numeric(5, 2), nullable=True),
        sa.Column("gcpch_fact_evening", sa.Numeric(5, 2), nullable=True),
        sa.Column("waste_state_plan", sa.Numeric(5, 2), nullable=True),
        sa.Column("waste_state_fact", sa.Numeric(5, 2), nullable=True),
        sa.Column("dlv_orders_plan", sa.Integer, nullable=True),
        sa.Column("dlv_orders_fact_m", sa.Integer, nullable=True),
        sa.Column("dlv_orders_fact_e", sa.Integer, nullable=True),
    )


def downgrade():
    op.drop_table("checklist_kpi")
    op.drop_table("checklist_answers")
    op.drop_table("checklist_submissions")
    op.drop_table("checklist_task_templates")
