import json
import matplotlib.pyplot as plt
import numpy as np
import os

def generate_plots():
    if not os.path.exists("evaluation/results.json"):
        print("Error: Run evaluation_runner.py first.")
        return

    with open("evaluation/results.json", "r") as f:
        data = json.load(f)

    metrics = data["metrics"]
    
    # 1. Bar Chart: Precision vs Recall
    plt.figure(figsize=(10, 6))
    labels = ['Precision', 'Recall', 'F1 Score']
    values = [metrics['precision'], metrics['recall'], metrics['f1_score']]
    colors = ['#4CAF50', '#2196F3', '#FF9800']
    
    plt.bar(labels, values, color=colors)
    plt.ylim(0, 1.1)
    plt.title('CodeReview AI Detection Metrics', fontsize=14)
    plt.ylabel('Score (0.0 - 1.0)')
    
    # Add values on top of bars
    for i, v in enumerate(values):
        plt.text(i, v + 0.02, f"{v:.2f}", ha='center', fontsize=12)
    
    plt.tight_layout()
    plt.savefig('evaluation/metrics_summary.png')
    print("Saved evaluation/metrics_summary.png")

    # 2. Issues by category (using details)
    categories = ['Security', 'Logic', 'Performance', 'Clean']
    found = [0, 0, 0, 0]
    expected = [0, 0, 0, 0]
    
    for item in data["details"]:
        if "security" in item["file"]:
            found[0] += item["found"]
            expected[0] += item["expected"]
        elif "logic" in item["file"]:
            found[1] += item["found"]
            expected[1] += item["expected"]
        elif "performance" in item["file"]:
            found[2] += item["found"]
            expected[2] += item["expected"]
        elif "clean" in item["file"]:
            found[3] += item["found"]
            expected[3] += item["expected"]

    plt.figure(figsize=(10, 6))
    x = np.arange(len(categories))
    width = 0.35
    
    plt.bar(x - width/2, expected, width, label='Ground Truth (Expected)', color='#9E9E9E')
    plt.bar(x + width/2, found, width, label='LLM Detected', color='#E91E63')
    
    plt.xlabel('Category')
    plt.ylabel('Bug Count')
    plt.title('Detection Performance by Category')
    plt.xticks(x, categories)
    plt.legend()
    
    plt.tight_layout()
    plt.savefig('evaluation/category_performance.png')
    print("Saved evaluation/category_performance.png")

if __name__ == "__main__":
    generate_plots()
