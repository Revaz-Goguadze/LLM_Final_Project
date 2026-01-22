from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

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


# Fix Loop Models

class FixContext(BaseModel):
    file_context: str = ""
    code_rag_results: List[Dict[str, Any]] = Field(default_factory=list)
    docs_rag_results: List[Dict[str, Any]] = Field(default_factory=list)
    diff_context: Optional[str] = None
    related_files: List[str] = Field(default_factory=list)
    attempt: int = 1
    previous_error: Optional[str] = None


class VerificationResult(BaseModel):
    success: bool
    method: str = Field(..., description="pytest, syntax, import, semantic")
    output: str = ""
    diagnostics: List[str] = Field(default_factory=list)


class ErrorCategory(str, Enum):
    SYNTAX_ERROR = "syntax_error"
    TEST_FAILURE = "test_failure"
    CONTEXT_MISMATCH = "context_mismatch"
    LOGIC_ERROR = "logic_error"
    VERIFICATION_ERROR = "verification_error"
    UNKNOWN = "unknown"


class Remedy(BaseModel):
    action: str = Field(..., description="expand_context, change_format, add_imports, etc.")
    description: str
    params: Dict[str, Any] = Field(default_factory=dict)


class RetryStrategy(BaseModel):
    expand_context: bool = True
    change_format: bool = False
    context_multiplier: float = 1.5
    additional_instructions: str = ""


class FixFormat(str, Enum):
    PATCH = "patch"
    REPLACE = "replace"
