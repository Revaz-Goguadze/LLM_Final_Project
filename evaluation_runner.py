import json
from pathlib import Path

from codereview.evaluator import EvaluationRunner
from codereview.eval_plots import generate_plots


def run_evaluation(dataset_path: str = "evaluation/eval_dataset.json") -> None:
    dataset = Path(dataset_path)
    if not dataset.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset}")

    print("🚀 Starting Evaluation Runner...")
    print("-" * 40)

    runner = EvaluationRunner()
    results = runner.run(str(dataset))

    output_dir = Path("evaluation")
    output_dir.mkdir(exist_ok=True)

    summary_path = output_dir / "results_summary.json"
    details_path = output_dir / "results_details.json"
    summary_path.write_text(
        json.dumps(
            {
                "precision": results["precision"],
                "recall": results["recall"],
                "f1": results["f1"],
                "fix_rate": results["fix_rate"],
                "totals": results["totals"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    details_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    generate_plots(results, str(output_dir / "plots"))

    print("-" * 40)
    print("✅ Evaluation Complete!")
    print(f"Final Precision: {results['precision']:.2f}")
    print(f"Final Recall: {results['recall']:.2f}")
    print(f"F1: {results['f1']:.2f}")
    print(f"Fix rate: {results['fix_rate']:.2f}")
    print(f"Results saved to {summary_path}")


if __name__ == "__main__":
    run_evaluation()
