#!/usr/bin/env python3
import json
import os
import time
from codereview.grader import MultiLLMGrader
from codereview.config import MODEL_GRADER_SECURITY

SAMPLES_DIR = "evaluation/samples"
GROUND_TRUTH_PATH = "evaluation/ground_truth.json"


def load_ground_truth():
    with open(GROUND_TRUTH_PATH, "r") as f:
        return json.load(f)


def read_sample(path: str) -> str:
    full_path = os.path.join("evaluation", path)
    with open(full_path, "r") as f:
        return f.read()


def run_single_llm_evaluation():
    ground_truth = load_ground_truth()
    grader = MultiLLMGrader()

    total_tp, total_fp, total_fn = 0, 0, 0

    print("\n=== SINGLE LLM EVALUATION (Security grader only) ===\n")

    for file_path, expected in ground_truth.items():
        code = read_sample(file_path)
        expected_bugs = expected["expected_bugs"]

        report = grader.grade_with_model("security", MODEL_GRADER_SECURITY, code)
        found = len(report.issues)

        tp = min(found, expected_bugs)
        fp = max(0, found - expected_bugs)
        fn = max(0, expected_bugs - found)

        total_tp += tp
        total_fp += fp
        total_fn += fn

        print(f"  {file_path}: expected={expected_bugs}, found={found}")
        time.sleep(1)

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    f1 = (
        2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    )

    return {"precision": precision, "recall": recall, "f1": f1}


def run_multi_llm_evaluation():
    ground_truth = load_ground_truth()
    grader = MultiLLMGrader()

    total_tp, total_fp, total_fn = 0, 0, 0

    print("\n=== MULTI-LLM EVALUATION (3 graders + judge) ===\n")

    for file_path, expected in ground_truth.items():
        code = read_sample(file_path)
        expected_bugs = expected["expected_bugs"]

        r1 = grader.grade_with_model("security", MODEL_GRADER_SECURITY, code)
        time.sleep(0.5)
        r2 = grader.grade_with_model("logic", MODEL_GRADER_SECURITY, code)
        time.sleep(0.5)
        r3 = grader.grade_with_model("performance", MODEL_GRADER_SECURITY, code)
        time.sleep(0.5)

        final = grader.judge([r1, r2, r3])
        found = len(final.consolidated_issues)

        tp = min(found, expected_bugs)
        fp = max(0, found - expected_bugs)
        fn = max(0, expected_bugs - found)

        total_tp += tp
        total_fp += fp
        total_fn += fn

        print(f"  {file_path}: expected={expected_bugs}, found={found}")
        time.sleep(1)

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    f1 = (
        2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    )

    return {"precision": precision, "recall": recall, "f1": f1}


def main():
    print("=" * 60)
    print("SINGLE-LLM vs MULTI-LLM COMPARISON")
    print("=" * 60)

    single_results = run_single_llm_evaluation()
    multi_results = run_multi_llm_evaluation()

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    print(f"\nSingle-LLM (1 grader):")
    print(f"  Precision: {single_results['precision']:.2f}")
    print(f"  Recall:    {single_results['recall']:.2f}")
    print(f"  F1 Score:  {single_results['f1']:.2f}")

    print(f"\nMulti-LLM (3 graders + judge):")
    print(f"  Precision: {multi_results['precision']:.2f}")
    print(f"  Recall:    {multi_results['recall']:.2f}")
    print(f"  F1 Score:  {multi_results['f1']:.2f}")

    if single_results["f1"] > 0:
        improvement = (
            (multi_results["f1"] - single_results["f1"]) / single_results["f1"] * 100
        )
    else:
        improvement = 100 if multi_results["f1"] > 0 else 0

    print(f"\nMulti-LLM Improvement: {improvement:+.1f}%")
    print(f"Target: >15% improvement")
    print(f"Status: {'✅ PASSED' if improvement > 15 else '❌ BELOW TARGET'}")

    results = {
        "single_llm": single_results,
        "multi_llm": multi_results,
        "improvement_percent": improvement,
    }

    with open("evaluation/comparison_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to evaluation/comparison_results.json")


if __name__ == "__main__":
    main()
