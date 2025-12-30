Final Project: Multi-LLM Collaborative Debate System
Assignment Overview
Build a debate system where three LLMs solve problems independently, then cross-evaluate each other's solutions through structured critique. After mutual refinement based on peer feedback, a fourth LLM judges all final solutions and returns the best answer. This system combats hallucination through diverse perspectives and adversarial review.

Phase 1: Problem Dataset Construction
Construct a dataset of 25 challenging problems 
Suggested Problem Categories: 
1.Mathematical/Logical Reasoning
    • Complex combinatorics, probability puzzles, number theory proofs
    • Problems where LLMs commonly make calculation errors or logical leaps
    • Example: "In how many ways can you tile a 3×8 rectangle with 2×1 dominoes?"
2. Physics & Scientific Reasoning
    • Multi-step physics problems requiring formula application and unit analysis
    • Counterintuitive scenarios (Monty Hall-style physics problems)
    • Example: "A ladder leans against a frictionless wall. Derive the minimum coefficient of friction needed with the ground to prevent slipping."
3. Logic Puzzles & Constraint Satisfaction
    • Multi-agent reasoning problems (knights and knaves, truth-tellers)
    • Constraint satisfaction with interdependent rules
    • Example: "Five people of different nationalities live in five colored houses. Given 15 clues about their pets, drinks, and cigarette brands, who owns the fish?"
4. Strategic Game Theory
    • Optimal strategy derivation in games with incomplete information
    • Backward induction problems, Nash equilibria calculations
    • Example: "In a two-player auction where bids are sealed and highest bidder pays the second-highest bid, what's the optimal bidding strategy?"
Requirements:
    • Each problem must have a verifiable correct answer
    • Problems should be challenging enough that single LLM attempts often fail

Phase 2: System Implementation
The Four Roles
Three Equal Solvers and 1 Final Judge
    1. Solver 1: Independent solution with reasoning
    2. Solver 2: Independent solution with reasoning
    3. Solver 3: Independent solution with reasoning
    4. Final Judge: Evaluates all refined solutions and picks the best
Workflow
Stage 0: Role Assignment
Give each LLM the original question and ask them which role they think will be best for them for this question.
Each of the 4 LLMs (GPT-4, Claude, Gemini, Grok) self-assesses:
{
  "role_preferences": ["Solver”,"Judge"],
  "confidence_by_role": {
    "Solver_1": 0.85,
    "Judge": 0.75
  },
  "reasoning": "I should be Solver because I'm strong at mathematical reasoning..."
} or any other format that you think will help you to better assign roles.
Stage 0.5: Algorithmic Role Assignment
After receiving results use deterministic algorithm to choose final role distribution.
Stage 1: Independent Solution Generation 
All three Solvers independently generate complete solutions with step by step reasoning.
No communication between Solvers at this stage.
Stage 2: Peer Review Round (15 points)
Each Solver evaluates the other two solutions using structured feedback:
{
  "solution_id": "solver_2",
  "evaluation": {
    "strengths": ["Clear step 1-3", "Correct formula application"],
    "weaknesses": ["Step 5 makes unjustified leap", "Didn't consider edge case X"],
    "errors": [
      {
        "location": "Step 5",
        "error_type": "logical_error",
        "description": "Claims X implies Y but this is false when Z...",
        "severity": "critical"
      }
    ],
    "suggested_changes": [
      "Reconsider step 5 with counterexample...",
      "Add verification for case when n=0"
    ]
  },
  "overall_assessment": "promising_but_flawed"
} or your chosen structure that in your opinion will work better.
Each Solver produces 2 reviews (one for each peer's solution).
Stage 3: Refinement Based on Feedback
Each Solver receives 2 reviews from their peers and must:
    • Address each critique explicitly
    • Defend their reasoning if critiques are wrong
    • Revise their solution incorporating valid feedback
    • Produce refined final solution
Solvers must output:
{
  "changes_made": [
    {"critique": "Step 5 was wrong", "response": "Fixed by...", "accepted": true},
    {"critique": "Missing edge case", "response": "This case doesn't apply because...", "accepted": false}
  ],
  "refined_solution": "...",
  "refined_answer": "...",
  "confidence": 0.90
} or your chosen structure that in your opinion will work better.
Stage 4: Final Judgment
Judge receives:
    • All three original solutions
    • All peer reviews 
    • All three refined solutions
Judge must produce:
{
  "winner": "solver_1",
  "confidence": 0.85,
  "reasoning": "Solver 1's solution is strongest because...",
} or your chosen structure that in your opinion will work better.

And depending on winner you will copy answer and return it to the user.

Phase 3: Evaluation and Analysis
Quantitative Metrics
System-Level Performance:
    • Overall Accuracy: % of problems solved correctly by final answer
    • Improvement Rate: % of problems where refinement improved initial answers
    • Consensus Rate: % of problems where all 3 Solvers reached same answer
    • Judge Accuracy: When Solvers disagree, does Judge pick the correct one?
Comparison to Baseline:
    • Single-LLM Baseline: Accuracy of "just ask GPT-4/Claude/Gemini/Grok once"
    • Simple Voting Baseline: 3 independent solutions, pick majority answer
    • Your System: Full debate with refinement

Deliverables
As Close as possible to production ready system project, code decomposition and structure is up to you.
Generated plots of evaluation results are MUST!

Submission Format
    • Group Projects: A GitHub repository link is mandatory. The repository must contain the notebooks, a README, and instructions on how to run the code. Do not write code offline and upload with 1 commit, I want to see that more or less everybody contributed equally.
    • Individual Projects: A GitHub link is suggested, but a ZIP file upload containing the notebooks and model artifacts is accepted.

IMPORTANT INFORMATION!!!:

Most models don't have free versions, so you may need to pay for usage. You have two options:
    1. Use a free model for all four roles we discussed (making 4 different API calls to the same free model with different parameters/system prompts)
    2. Pay the minimum fee (usually $5) to access paid models
Either approach is acceptable. Points won't be deducted for using only free models, but they will be deducted if you don't complete the final task. API limits won't be accepted as an excuse for non-delivery.

Presentation:
Presentation date and other details will be provided soon as an LMS post.

Due Date
23 January 23:59