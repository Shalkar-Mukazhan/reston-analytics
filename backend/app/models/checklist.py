from sqlalchemy import (
    Boolean, Column, Integer, String, Text, Date, Numeric, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.sql import func
from app.core.database import Base


class ChecklistTaskTemplate(Base):
    __tablename__ = "checklist_task_templates"

    id = Column(Integer, primary_key=True)
    section = Column(String(50), nullable=False)
    # before_shift / during_people / during_obs / during_equip / evening_proc / after_shift
    shift_applicability = Column(String(20), nullable=False, default="all")
    # all / morning / evening / night
    sort_order = Column(Integer, nullable=False, default=0)
    task_text = Column(Text, nullable=False)
    deadline_time = Column(String(20), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)


class ChecklistSubmission(Base):
    __tablename__ = "checklist_submissions"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    manager_name = Column(String(100), nullable=True)
    date = Column(Date, nullable=False)
    shift_type = Column(String(10), nullable=False)  # morning / evening / night
    status = Column(String(10), nullable=False, default="draft")  # draft / submitted

    priority_1_text = Column(Text, nullable=True)
    priority_2_text = Column(Text, nullable=True)
    priority_3_text = Column(Text, nullable=True)

    priority_1_done = Column(Boolean, nullable=True)
    priority_1_result = Column(Text, nullable=True)
    priority_2_done = Column(Boolean, nullable=True)
    priority_2_result = Column(Text, nullable=True)
    priority_3_done = Column(Boolean, nullable=True)
    priority_3_result = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)


class ChecklistAnswer(Base):
    __tablename__ = "checklist_answers"

    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey("checklist_submissions.id", ondelete="CASCADE"), nullable=False)
    template_id = Column(Integer, ForeignKey("checklist_task_templates.id"), nullable=False)
    is_done = Column(Boolean, nullable=True)
    note = Column(Text, nullable=True)
    filled_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("submission_id", "template_id", name="uq_answer"),)


class ChecklistKPI(Base):
    __tablename__ = "checklist_kpi"

    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey("checklist_submissions.id", ondelete="CASCADE"), nullable=False, unique=True)

    sales_plan = Column(Numeric(14, 2), nullable=True)
    sales_fact_morning = Column(Numeric(14, 2), nullable=True)
    sales_fact_evening = Column(Numeric(14, 2), nullable=True)

    gc_plan = Column(Integer, nullable=True)
    gc_fact_morning = Column(Integer, nullable=True)
    gc_fact_evening = Column(Integer, nullable=True)

    av_check_plan = Column(Numeric(10, 2), nullable=True)
    av_check_fact_morning = Column(Numeric(10, 2), nullable=True)
    av_check_fact_evening = Column(Numeric(10, 2), nullable=True)

    pct_dt_plan = Column(Numeric(5, 2), nullable=True)
    pct_kiosk_plan = Column(Numeric(5, 2), nullable=True)
    pct_cafe_plan = Column(Numeric(5, 2), nullable=True)
    pct_dlv_plan = Column(Numeric(5, 2), nullable=True)

    pct_dt_fact_m = Column(Numeric(5, 2), nullable=True)
    pct_dt_fact_e = Column(Numeric(5, 2), nullable=True)
    pct_kiosk_fact_m = Column(Numeric(5, 2), nullable=True)
    pct_kiosk_fact_e = Column(Numeric(5, 2), nullable=True)
    pct_cafe_fact_m = Column(Numeric(5, 2), nullable=True)
    pct_cafe_fact_e = Column(Numeric(5, 2), nullable=True)
    pct_dlv_fact_m = Column(Numeric(5, 2), nullable=True)
    pct_dlv_fact_e = Column(Numeric(5, 2), nullable=True)

    rating_gm_voice_plan = Column(Numeric(5, 2), nullable=True)
    rating_gm_voice_fact_m = Column(Numeric(5, 2), nullable=True)
    rating_gm_voice_fact_e = Column(Numeric(5, 2), nullable=True)
    rating_1and2_plan = Column(Numeric(5, 2), nullable=True)
    rating_1and2_fact_m = Column(Numeric(5, 2), nullable=True)
    rating_1and2_fact_e = Column(Numeric(5, 2), nullable=True)

    oepe_plan = Column(Integer, nullable=True)
    oepe_fact_morning = Column(Integer, nullable=True)
    oepe_fact_evening = Column(Integer, nullable=True)

    gcpch_plan = Column(Numeric(5, 2), nullable=True)
    gcpch_fact_morning = Column(Numeric(5, 2), nullable=True)
    gcpch_fact_evening = Column(Numeric(5, 2), nullable=True)

    waste_state_plan = Column(Numeric(5, 2), nullable=True)
    waste_state_fact = Column(Numeric(5, 2), nullable=True)

    dlv_orders_plan = Column(Integer, nullable=True)
    dlv_orders_fact_m = Column(Integer, nullable=True)
    dlv_orders_fact_e = Column(Integer, nullable=True)
