import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .grader import MultiLLMGrader
from .rag_builder import build_rag_query, build_context_block, build_analysis_input
from .retriever import HybridRetriever
from .config import (
    DOCS_DB_COLLECTION,
    DOCS_BM25_INDEX_PATH,
    MODEL_GRADER_SECURITY,
    MODEL_GRADER_LOGIC,
    MODEL_GRADER_PERF,
)


@dataclass
class EvaluationCase:
    case_id: str
    diff: str
    query: Optional[str]
    expected_issues: List[Dict[str, Any]]


def _load_cases(path: str) -> List[EvaluationCase]:
    cases: List[EvaluationCase] = []
    with open(path, "r", encoding="utf-8") as f:
        data = f.read().strip()
    if data.startswith("["):
        items = json.loads(data)
    else:
        items = [json.loads(line) for line in data.splitlines() if line.strip()]
    for item in items:
        cases.append(
            EvaluationCase(
                case_id=item.get("id", "case"),
                diff=item["diff"],
                query=item.get("query"),
                expected_issues=item.get("expected_issues", []),
            )
        )
    return cases


def _match_issue(pred: Dict[str, Any], exp: Dict[str, Any]) -> bool:
    if exp.get("type") and pred.get("type") != exp.get("type"):
        return False
    if exp.get("file") and pred.get("location", {}).get("file") != exp.get("file"):
        return False
    exp_line = exp.get("line")
    pred_line = pred.get("location", {}).get("line")
    if exp_line is not None and pred_line is not None:
        if abs(int(pred_line) - int(exp_line)) > 3:
            return False
    keyword = exp.get("keyword")
    if keyword:
        text = (pred.get("description", "") + " " + pred.get("evidence", "")).lower()
        if keyword.lower() not in text:
            return False
    return True


def _score_case(predicted: List[Dict[str, Any]], expected: List[Dict[str, Any]]) -> Tuple[int, int, int, float]:
    matched = set()
    tp = 0
    for pred in predicted:
        for i, exp in enumerate(expected):
            if i in matched:
                continue
            if _match_issue(pred, exp):
                matched.add(i)
                tp += 1
                break
    fp = max(0, len(predicted) - tp)
    fn = max(0, len(expected) - tp)

    matched_with_fix = 0
    for pred in predicted:
        for i, exp in enumerate(expected):
            if _match_issue(pred, exp):
                if pred.get("suggested_fix"):
                    matched_with_fix += 1
                break
    fix_rate = (matched_with_fix / tp) if tp > 0 else 0.0
    return tp, fp, fn, fix_rate


class EvaluationRunner:
    def __init__(
        self,
        use_rag: bool = True,
        top_k: int = 6,
        docs_top_k: int = 4,
        use_docs_rag: bool = True,
    ):
        self.use_rag = use_rag
        self.top_k = top_k
        self.docs_top_k = docs_top_k
        self.use_docs_rag = use_docs_rag
        self.grader = MultiLLMGrader()

    def _build_context(self, query: Optional[str], diff: str) -> Optional[str]:
        if not self.use_rag:
            return None
        rag_query = build_rag_query(query, diff)
        if not rag_query:
            return None
        code_retriever = HybridRetriever()
        code_results = code_retriever.search(rag_query, n_results=self.top_k)
        code_context = build_context_block(code_results)

        docs_context = ""
        if self.use_docs_rag:
            docs_retriever = HybridRetriever(
                collection=DOCS_DB_COLLECTION,
                bm25_index_path=DOCS_BM25_INDEX_PATH,
            )
            docs_results = docs_retriever.search(rag_query, n_results=self.docs_top_k)
            docs_context = build_context_block(docs_results) if docs_results else ""

        parts = []
        if code_context:
            parts.append("Codebase context:\n" + code_context)
        if docs_context:
            parts.append("Python docs/best practices:\n" + docs_context)
        return "\n\n".join(parts) if parts else None

    def run(self, dataset_path: str) -> Dict[str, Any]:
        cases = _load_cases(dataset_path)
        totals = {"tp": 0, "fp": 0, "fn": 0, "fix_rate_sum": 0.0, "cases": 0}
        per_case = []
        per_model = {
            "security": {"tp": 0, "fp": 0, "fn": 0, "fix_rate_sum": 0.0, "cases": 0},
            "logic": {"tp": 0, "fp": 0, "fn": 0, "fix_rate_sum": 0.0, "cases": 0},
            "performance": {"tp": 0, "fp": 0, "fn": 0, "fix_rate_sum": 0.0, "cases": 0},
        }

        for case in cases:
            rag_context = self._build_context(case.query, case.diff)
            analysis_input = build_analysis_input(case.query, case.diff, rag_context)
            r1 = self.grader.grade_with_model("security", MODEL_GRADER_SECURITY, analysis_input)
            r2 = self.grader.grade_with_model("logic", MODEL_GRADER_LOGIC, analysis_input)
            r3 = self.grader.grade_with_model("performance", MODEL_GRADER_PERF, analysis_input)
            final = self.grader.judge([r1, r2, r3])

            predicted = [i.model_dump() for i in final.consolidated_issues]
            tp, fp, fn, fix_rate = _score_case(predicted, case.expected_issues)
            totals["tp"] += tp
            totals["fp"] += fp
            totals["fn"] += fn
            totals["fix_rate_sum"] += fix_rate
            totals["cases"] += 1

            # Per-model scoring
            for key, report in (("security", r1), ("logic", r2), ("performance", r3)):
                preds = [i.model_dump() for i in report.issues]
                mtp, mfp, mfn, mfix = _score_case(preds, case.expected_issues)
                per_model[key]["tp"] += mtp
                per_model[key]["fp"] += mfp
                per_model[key]["fn"] += mfn
                per_model[key]["fix_rate_sum"] += mfix
                per_model[key]["cases"] += 1

            per_case.append(
                {
                    "id": case.case_id,
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "fix_rate": fix_rate,
                }
            )

        precision = totals["tp"] / (totals["tp"] + totals["fp"]) if (totals["tp"] + totals["fp"]) else 0.0
        recall = totals["tp"] / (totals["tp"] + totals["fn"]) if (totals["tp"] + totals["fn"]) else 0.0
        fix_rate = totals["fix_rate_sum"] / totals["cases"] if totals["cases"] else 0.0

        per_model_scores = {}
        for key, stats in per_model.items():
            p = stats["tp"] / (stats["tp"] + stats["fp"]) if (stats["tp"] + stats["fp"]) else 0.0
            r = stats["tp"] / (stats["tp"] + stats["fn"]) if (stats["tp"] + stats["fn"]) else 0.0
            f = stats["fix_rate_sum"] / stats["cases"] if stats["cases"] else 0.0
            per_model_scores[key] = {"precision": p, "recall": r, "fix_rate": f, "totals": stats}

        return {
            "precision": precision,
            "recall": recall,
            "fix_rate": fix_rate,
            "totals": totals,
            "per_case": per_case,
            "per_model": per_model_scores,
        }
