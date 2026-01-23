import json
import time
from typing import Optional, List, Set, TYPE_CHECKING

from .agent_state import AgentState
from .models import BugIssue, FixFormat
from .config import MAX_FIX_RETRIES, MAX_FIX_TIMEOUT

if TYPE_CHECKING:
    from .agent import ReActAgent


class FixLoopRunner:
    """Orchestrates the fix loop with timeout, error detection, and smart retries."""

    UNRECOVERABLE_ERRORS = {
        "file not found",
        "permission denied",
        "binary file",
        "encoding error",
    }

    FORMAT_SWITCH_ERRORS = {
        "patch application failed",
        "hunk failed",
        "context mismatch",
        "line numbers don't match",
    }

    def __init__(self, agent: "ReActAgent"):
        self.agent = agent
        self._context_cache: dict = {}
        self._failed_strategies: Set[str] = set()

    def _is_unrecoverable(self, error: str) -> bool:
        """Check if error is unrecoverable and should stop retries."""
        if not error:
            return False
        error_lower = error.lower()
        return any(pattern in error_lower for pattern in self.UNRECOVERABLE_ERRORS)

    def _should_switch_format(self, error: str) -> bool:
        """Check if error suggests we should switch fix format."""
        if not error:
            return False
        error_lower = error.lower()
        return any(pattern in error_lower for pattern in self.FORMAT_SWITCH_ERRORS)

    def _get_cached_context(
        self, issue: BugIssue, diff_text: Optional[str], multiplier: float
    ) -> Optional[str]:
        """Get cached context if available for same parameters."""
        cache_key = (issue.location.file, issue.location.line, multiplier)
        return self._context_cache.get(cache_key)

    def _cache_context(self, issue: BugIssue, multiplier: float, context: str) -> None:
        """Cache context for reuse."""
        cache_key = (issue.location.file, issue.location.line, multiplier)
        self._context_cache[cache_key] = context

    def run(self, issue: BugIssue, diff_text: Optional[str] = None) -> bool:
        agent = self.agent
        start_time = time.time()
        print(f"\n[Agent] Starting to fix: {issue.description}")
        print(f"[Agent] File: {issue.location.file}, Line: {issue.location.line}")

        state = AgentState.VALIDATE_ISSUE
        run_dir = agent._init_run_dir()
        agent._write_run_file(run_dir, "issue.json", issue.model_dump_json(indent=2))

        is_valid, reason = agent._validate_issue(issue)
        if not is_valid:
            print(f"[Agent] Issue is not actionable: {reason}")
            agent._write_run_file(run_dir, "final_state.txt", state.value)
            return False

        last_error: Optional[str] = None
        last_fix: Optional[str] = None
        error_history: List[str] = []
        fix_attempts: List[str] = []  # Track fix content to detect loops
        issue_key = agent._issue_key(issue)

        # Determine initial format preference
        preferred_format = agent.fix_strategy_selector.recommend_format(
            issue, diff_text
        )
        enforce_format = False
        if issue.start_line and issue.end_line:
            preferred_format = FixFormat.REPLACE
            enforce_format = True

        consecutive_same_error = 0
        last_error_type: Optional[str] = None

        for attempt in range(1, MAX_FIX_RETRIES + 1):
            state = AgentState.BUILD_CONTEXT
            elapsed = time.time() - start_time
            print(
                f"\n[Agent] Attempt {attempt}/{MAX_FIX_RETRIES} ({elapsed:.1f}s elapsed)"
            )

            if elapsed > MAX_FIX_TIMEOUT:
                print(f"[Agent] Timeout exceeded ({MAX_FIX_TIMEOUT}s), stopping")
                break

            if last_error and self._is_unrecoverable(last_error):
                print(f"[Agent] Unrecoverable error detected: {last_error}")
                break

            # Detect repeated errors (sign of systematic issue)
            current_error_type = last_error[:50] if last_error else None
            if current_error_type == last_error_type:
                consecutive_same_error += 1
                if consecutive_same_error >= 2:
                    print(
                        "[Agent] Same error repeated multiple times, trying different strategy"
                    )
                    # Force format switch
                    if not enforce_format:
                        preferred_format = (
                            FixFormat.PATCH
                            if preferred_format == FixFormat.REPLACE
                            else FixFormat.REPLACE
                        )
                        consecutive_same_error = 0
            else:
                consecutive_same_error = 0
            last_error_type = current_error_type

            # Determine retry strategy
            retry_strategy = None
            retry_instructions = ""
            context_multiplier = 1.0 + (attempt - 1) * 0.5  # Progressive expansion

            if last_error:
                retry_strategy = agent.fix_strategy_selector.adapt_retry_strategy(
                    last_error, attempt, preferred_format
                )
                context_multiplier = max(
                    context_multiplier, retry_strategy.context_multiplier
                )

                # Smart format switching
                if self._should_switch_format(last_error) and not enforce_format:
                    preferred_format = (
                        FixFormat.PATCH
                        if preferred_format == FixFormat.REPLACE
                        else FixFormat.REPLACE
                    )
                    print(
                        f"[Agent] Switching format to {preferred_format.value} due to error"
                    )
                elif retry_strategy.change_format and not enforce_format:
                    preferred_format = (
                        FixFormat.PATCH
                        if preferred_format == FixFormat.REPLACE
                        else FixFormat.REPLACE
                    )

                category = agent.error_classifier.classify_error(last_error)
                remedy = agent.error_classifier.suggest_remedy(category)
                retry_instructions = "\n".join(
                    part
                    for part in [
                        retry_strategy.additional_instructions
                        if retry_strategy
                        else "",
                        agent.error_classifier.get_retry_instructions(remedy),
                        f"PREVIOUS ERROR: {last_error[:200]}..."
                        if len(last_error) > 200
                        else f"PREVIOUS ERROR: {last_error}",
                    ]
                    if part
                )

            print("[Agent] Building context...")
            fix_context = agent.fix_context_builder.build_context(
                issue,
                diff_text=diff_text,
                attempt=attempt,
                previous_error=last_error,
                context_multiplier=context_multiplier,
            )
            context_text = agent._format_fix_context(fix_context)

            # Add target line info for precision
            if issue.start_line and issue.end_line:
                target_lines = f"{issue.start_line}-{issue.end_line}"
                target_text = issue.line_text or ""
                context_text = "\n\n".join(
                    part
                    for part in [
                        f"TARGET_LINE_RANGE: {target_lines}",
                        f"TARGET_LINE_TEXT: {target_text}" if target_text else "",
                        context_text,
                    ]
                    if part
                )

            if preferred_format:
                context_text = "\n\n".join(
                    part
                    for part in [
                        f"PREFERRED_FORMAT: {preferred_format.value}",
                        context_text,
                        f"RETRY_INSTRUCTIONS:\n{retry_instructions}"
                        if retry_instructions
                        else "",
                    ]
                    if part
                )

            # Cache context for first attempt
            if attempt == 1:
                agent._write_run_file(run_dir, "context.txt", context_text)
                self._cache_context(issue, context_multiplier, context_text)
            agent._write_run_file(
                run_dir, f"attempt_{attempt}_context.txt", context_text
            )

            state = AgentState.GENERATE_FIX
            print("[Agent] Generating fix...")
            prompt, raw_fix = agent._generate_fix(
                issue,
                fix_context.file_context,
                last_error,
                context_text,
            )
            agent._write_run_file(run_dir, f"attempt_{attempt}_prompt.txt", prompt)
            agent._write_run_file(run_dir, f"attempt_{attempt}_raw_llm.txt", raw_fix)

            if not raw_fix:
                print("[Agent] Failed to generate fix (empty response)")
                last_error = "Empty LLM response"
                error_history.append(last_error)
                agent._write_run_file(
                    run_dir,
                    f"attempt_{attempt}_payload.json",
                    '{"error": "Empty LLM response"}',
                )
                continue

            payload = agent._parse_fix_payload(raw_fix)
            state = AgentState.VALIDATE_FIX
            is_valid, reason, normalized = agent._validate_fix_payload(
                issue,
                payload,
                diff_text=diff_text,
                expected_format=preferred_format if enforce_format else None,
            )
            if not is_valid:
                last_error = reason
                error_history.append(reason)
                print(f"[Agent] Invalid fix payload: {reason}")
                agent._write_run_file(
                    run_dir,
                    f"attempt_{attempt}_payload.json",
                    json.dumps({"error": reason, "raw": payload}, indent=2),
                )
                continue

            agent._write_run_file(
                run_dir,
                f"attempt_{attempt}_payload.json",
                json.dumps(normalized, indent=2),
            )

            fix_format = normalized.get("format")
            is_patch = fix_format == "patch"
            if is_patch:
                current_fix = normalized.get("patch", "")
            else:
                current_fix = normalized.get("replacement", "")

            # Validate fix content
            if not current_fix and is_patch:
                print("[Agent] Empty patch output, retrying")
                last_error = "Empty patch output"
                error_history.append(last_error)
                continue
            if not is_patch and "replacement" not in normalized:
                print("[Agent] Missing replacement key, retrying")
                last_error = "Missing replacement key"
                error_history.append(last_error)
                continue

            # Detect fix loops (same fix repeated)
            fix_hash = hash(current_fix)
            if fix_hash in [hash(f) for f in fix_attempts[-3:]]:
                print("[Agent] Fix repeated - LLM is looping, stopping early")
                agent.fix_tracker.record_attempt(
                    issue_id=issue_key,
                    mode=preferred_format.value,
                    success=False,
                    attempts=attempt,
                    verification_method="skipped",
                    error_message="Repeated fix output (loop detected)",
                )
                return False
            fix_attempts.append(current_fix)

            # Check for no-op fix
            start_line = normalized.get("start_line") if not is_patch else None
            end_line = normalized.get("end_line") if not is_patch else None

            if not is_patch and start_line:
                existing = agent._read_line_range(
                    issue.location.file, start_line, end_line or start_line
                )
                if existing.strip() == current_fix.strip():
                    print("[Agent] Proposed fix is identical to existing code (no-op)")
                    last_error = "No-op fix - code unchanged"
                    error_history.append(last_error)
                    continue

            # Apply fix
            pre_content = "".join(agent._read_file_lines(issue.location.file))
            state = AgentState.APPLY_FIX
            print("[Agent] Applying fix...")
            success, touched_files = agent.fixer.apply_fix_with_transaction(
                issue,
                current_fix,
                start_line=start_line,
                end_line=end_line,
                is_patch=is_patch,
            )
            if not success:
                last_error = agent.fixer.get_last_error()
                error_history.append(last_error)
                print(f"[Agent] Could not apply fix: {last_error}")
                continue

            post_content = "".join(agent._read_file_lines(issue.location.file))
            if pre_content == post_content:
                last_error = "Fix applied but file did not change"
                error_history.append(last_error)
                print(f"[Agent] {last_error}")
                state = AgentState.ROLLBACK
                agent.fixer.rollback_files(touched_files)
                continue

            # Save applied fix artifact
            agent._write_run_file(
                run_dir, f"attempt_{attempt}_applied_fix.txt", current_fix
            )

            # Verify fix
            state = AgentState.VERIFY
            print("[Agent] Verifying fix...")
            verified, output = agent.fix_verifier.verify_with_fallback(
                issue.location.file, issue, diff_text=diff_text
            )
            verification_method = agent._extract_verification_method(output)
            agent._write_run_file(
                run_dir, f"attempt_{attempt}_verification.txt", output
            )

            if verified:
                elapsed = time.time() - start_time
                print(
                    f"[Agent] ✓ Fix applied and verified successfully! ({elapsed:.1f}s)"
                )
                state = AgentState.SUCCESS
                agent._write_run_file(run_dir, "final_state.txt", state.value)
                agent.fix_tracker.record_attempt(
                    issue_id=issue_key,
                    mode=preferred_format.value,
                    success=True,
                    attempts=attempt,
                    verification_method=verification_method,
                )
                return True

            last_error = output
            error_history.append(output)
            last_fix = current_fix
            state = AgentState.ROLLBACK
            agent.fixer.rollback_files(touched_files)
            print("[Agent] Fix failed verification, rolling back...")

        elapsed = time.time() - start_time
        print(f"[Agent] All fix attempts exhausted. ({elapsed:.1f}s)")
        state = AgentState.FAIL
        agent._write_run_file(run_dir, "final_state.txt", state.value)

        # Write summary of all errors for debugging
        agent._write_run_file(
            run_dir,
            "error_history.json",
            json.dumps(
                {"errors": error_history, "attempts": MAX_FIX_RETRIES}, indent=2
            ),
        )

        agent.fix_tracker.record_attempt(
            issue_id=issue_key,
            mode=preferred_format.value,
            success=False,
            attempts=MAX_FIX_RETRIES,
            verification_method="failed",
            error_message=error_history[-1] if error_history else "",
        )
        return False
