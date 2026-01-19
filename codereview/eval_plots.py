from __future__ import annotations

import os
from typing import Dict, Any

import matplotlib.pyplot as plt


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def generate_plots(results: Dict[str, Any], output_dir: str) -> None:
    _ensure_dir(output_dir)

    # Overall metrics
    metrics = {
        "precision": results.get("precision", 0.0),
        "recall": results.get("recall", 0.0),
        "f1": results.get("f1", 0.0),
        "fix_rate": results.get("fix_rate", 0.0),
    }
    plt.figure(figsize=(6, 4))
    plt.bar(metrics.keys(), metrics.values(), color="#4C78A8")
    plt.ylim(0, 1)
    plt.title("Overall Metrics")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "precision_recall_f1.png"))
    plt.close()

    # Per-category metrics
    per_category = results.get("per_category", {})
    if per_category:
        labels = list(per_category.keys())
        f1_scores = [per_category[k].get("f1", 0.0) for k in labels]
        plt.figure(figsize=(8, 4))
        plt.bar(labels, f1_scores, color="#F58518")
        plt.ylim(0, 1)
        plt.title("F1 by Category")
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "performance_by_category.png"))
        plt.close()

    # Per-model metrics
    per_model = results.get("per_model", {})
    if per_model:
        labels = list(per_model.keys())
        precisions = [per_model[k].get("precision", 0.0) for k in labels]
        recalls = [per_model[k].get("recall", 0.0) for k in labels]
        f1_scores = [per_model[k].get("f1", 0.0) for k in labels]

        x = range(len(labels))
        plt.figure(figsize=(8, 4))
        plt.bar([i - 0.2 for i in x], precisions, width=0.2, label="precision")
        plt.bar([i for i in x], recalls, width=0.2, label="recall")
        plt.bar([i + 0.2 for i in x], f1_scores, width=0.2, label="f1")
        plt.xticks(list(x), labels)
        plt.ylim(0, 1)
        plt.title("Per-Model Metrics")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "per_model_comparison.png"))
        plt.close()
