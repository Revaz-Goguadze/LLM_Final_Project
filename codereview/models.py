from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class CodeLocation(BaseModel):
    file: str
    line: Optional[int] = None
    function: Optional[str] = None

class BugIssue(BaseModel):
    severity: str = Field(..., description="critical, high, medium, low")
    type: str = Field(..., description="security, logic, performance, style")
    location: CodeLocation
    description: str
    evidence: str
    suggested_fix: str
    confidence: float

class BestPracticeViolation(BaseModel):
    rule: str
    description: str
    count: int

class GraderReport(BaseModel):
    grader_id: str
    issues: List[BugIssue]
    best_practices_violations: List[BestPracticeViolation]
    overall_score: float
    summary: str

class FinalReport(BaseModel):
    winner_assessment: Optional[str] = None
    consolidated_issues: List[BugIssue]
    overall_health_score: float
    summary: str

class GitDiff(BaseModel):
    staged: str
    unstaged: str
    last_commit: str
    changed_files: List[str]
