from skiljo_core.simulation.contradictions import Citation, Contradiction, FinancialImpact, detect_contradictions
from skiljo_core.simulation.cross_document import (
    CrossDocumentCitation,
    CrossDocumentContradiction,
    PolicyDocument,
    detect_cross_document_contradictions,
)
from skiljo_core.simulation.engine import compute_report, simulate_batch
from skiljo_core.simulation.evaluator import (
    evaluate_condition,
    evaluate_condition_or_predicate,
    evaluate_predicate,
)
from skiljo_core.simulation.executor import LLMRecommendation, simulate_ticket
from skiljo_core.simulation.generator import DivergenceSpec, TicketFieldRanges, generate_ticket_batch

__all__ = [
    "compute_report",
    "simulate_batch",
    "evaluate_condition",
    "evaluate_condition_or_predicate",
    "evaluate_predicate",
    "LLMRecommendation",
    "simulate_ticket",
    "DivergenceSpec",
    "TicketFieldRanges",
    "generate_ticket_batch",
    "Citation",
    "Contradiction",
    "FinancialImpact",
    "detect_contradictions",
    "CrossDocumentCitation",
    "CrossDocumentContradiction",
    "PolicyDocument",
    "detect_cross_document_contradictions",
]
