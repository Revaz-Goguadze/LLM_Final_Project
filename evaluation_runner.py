import json
import os
import time
from codereview.grader import MultiLLMGrader
from codereview.config import MODEL_GRADER_SECURITY, MODEL_GRADER_LOGIC, MODEL_GRADER_PERF

def run_evaluation():
    with open("evaluation/ground_truth.json", "r") as f:
        ground_truth = json.load(f)
    
    grader = MultiLLMGrader()
    results = []
    
    tp = 0 # True Positives
    fp = 0 # False Positives
    fn = 0 # False Negatives
    
    print("🚀 Starting Evaluation Runner...")
    print("-" * 40)
    
    for relative_path, truth in ground_truth.items():
        file_path = os.path.join("evaluation", relative_path)
        print(f"Analyzing {relative_path}...")
        
        with open(file_path, "r") as f:
            code = f.read()
        
        # Run graders
        r1 = grader.grade_with_model("security", MODEL_GRADER_SECURITY, code)
        r2 = grader.grade_with_model("logic", MODEL_GRADER_LOGIC, code)
        r3 = grader.grade_with_model("performance", MODEL_GRADER_PERF, code)
        
        final_report = grader.judge([r1, r2, r3])
        found_bugs = len(final_report.consolidated_issues)
        expected_bugs = truth["expected_bugs"]
        
        # Basic metric calculation
        # In a real scenario we'd match exact lines/types, 
        # but for this demo we'll use count-based matching for simplicity
        
        current_tp = min(found_bugs, expected_bugs)
        current_fp = max(0, found_bugs - expected_bugs)
        current_fn = max(0, expected_bugs - found_bugs)
        
        tp += current_tp
        fp += current_fp
        fn += current_fn
        
        results.append({
            "file": relative_path,
            "expected": expected_bugs,
            "found": found_bugs,
            "tp": current_tp,
            "fp": current_fp,
            "fn": current_fn
        })
        
        print(f"   Done. Found {found_bugs}/{expected_bugs} bugs.")
        time.sleep(1) # Rate limit protection

    # Calculate final metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    summary = {
        "metrics": {
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "total_tp": tp,
            "total_fp": fp,
            "total_fn": fn
        },
        "details": results
    }
    
    with open("evaluation/results.json", "w") as f:
        json.dump(summary, f, indent=2)
        
    print("-" * 40)
    print("✅ Evaluation Complete!")
    print(f"Final Precision: {precision:.2f}")
    print(f"Final Recall: {recall:.2f}")
    print(f"Results saved to evaluation/results.json")

if __name__ == "__main__":
    run_evaluation()
