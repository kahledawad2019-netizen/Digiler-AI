"""Stage 19 — Learning Analytics Dashboard.

Turns the Student Model (Stage 18) + concept graph + catalog into learner
analytics: progress, knowledge mastery, a weak-concept heatmap, learning timeline,
estimated time-spent, completion rate, confidence evolution and a recommendation
engine. Exports presentation-quality figures **and** a self-contained interactive
HTML dashboard. Fully additive — it reads existing structures, changes none.
"""

from ala.dashboard.models import DashboardConfig, DashboardData, Recommendation
from ala.dashboard.recommend import RecommendationEngine
from ala.dashboard.service import DashboardService

__all__ = ["DashboardService", "RecommendationEngine", "DashboardData",
           "Recommendation", "DashboardConfig"]
