"""Stage 8 — retrieval evaluation (metrics, eval set, comparison, figures)."""

from ala.retrieval.evaluation.evaluate import EvalResult, evaluate
from ala.retrieval.evaluation.evalset import EvalQuery, build_known_item_evalset
from ala.retrieval.evaluation import metrics

__all__ = ["metrics", "EvalQuery", "build_known_item_evalset", "EvalResult", "evaluate"]
