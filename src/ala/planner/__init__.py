"""Stage 20 — Study Session Planner.

Given a goal, a deadline, available daily time and the learner's Student Model,
produces an **adaptive daily study plan** (read / watch / practice / quiz /
revision) ordered by prerequisite + weakness, time-budgeted per day, with spaced
revision — plus a visual timeline. Fully additive: reads the Student Model, concept
graph and catalog; changes none.
"""

from ala.planner.models import (PlannerConfig, StudyActivity, StudyDay, StudyGoal,
                                StudyPlan)
from ala.planner.scheduler import StudyPlanner
from ala.planner.service import StudyPlannerService

__all__ = ["StudyPlanner", "StudyPlannerService", "StudyGoal", "StudyPlan",
           "StudyDay", "StudyActivity", "PlannerConfig"]
