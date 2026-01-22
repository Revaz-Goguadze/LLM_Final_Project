import json
from typing import Optional, List, TYPE_CHECKING

from .agent_state import AgentState
from .models import BugIssue, FixFormat
from .config import MAX_FIX_RETRIES

if TYPE_CHECKING:
    from .agent import ReActAgent


class FixLoopRunner:
    """Orchestrates the fix loop using a ReActAgent instance."""

    def __init__(self, agent: "ReActAgent"):
        self.agent = agent

    def run(self, issue: BugIssue, diff_text: Optional[str] = None) -> bool:
        agent = self.agent
        print(f"\n[Agent] Starting to fix: {issue.description}")
        print(f"[Agent] File: {issue.location.file}, Line: {issue.location.line}")

        state = AgentState.VALIDATE_ISSUE
        run_dir = agent._init_run_dir()
        agent._write_run_file(
            run_dir, "issue.json", issue.model_dump_json(indent=2)
        )

        is_valid, reason = agent._validate_issue(issue)
        if not is_valid:
            print(f"[Agent] Issue is not actionable: {reason}")
            agent._write_run_file(run_dir, "final_state.txt", state.value)
            return False

        last_error: Optional[str] = None
        last_fix: Optional[str] = None
        error_history: List[str] = []
        issue_key = agent._issue_key(issue)
        preferred_format = agent.fix_strategy_selector.recommend_format(
            issue, diff_text
        )
        enforce_format = False
        if issue.start_line and issue.end_line:
            preferred_format = FixFormat.REPLACE
            enforce_format = True

        for attempt in range(1, MAX_FIX_RETRIES + 1):
            state = AgentState.BUILD_CONTEXT
            print(f"\n[Agent] Attempt {attempt}/{MAX_FIX_RETRIES}")
            print("[Agent] Generating fix...")
            retry_strategy = None
            retry_instructions = ""
            context_multiplier = 1.0

            if last_error:
                retry_strategy = agent.fix_strategy_selector.adapt_retry_strategy(
                    last_error, attempt, preferred_format
                )
                context_multiplier = retry_strategy.context_multiplier
                if retry_strategy.change_format:
                    preferred_format = (
                        FixFormat.PATCH
                        if preferred_format == FixFormat.REPLACE
                        else FixFormat.REPLACE
                    )
                    enforce_format = True

                category = agent.error_classifier.classify_error(last_error)
                remedy = agent.error_classifier.suggest_remedy(category)
                retry_instructions = "\n".join(
                    part
                    for part in [
                        retry_strategy.additional_instructions if retry_strategy else "",
                        agent.error_classifier.get_retry_instructions(remedy),
                    ]
                    if part
                )

            fix_context = agent.fix_context_builder.build_context(
                issue,
                diff_text=diff_text,
                attempt=attempt,
                previous_error=last_error,
                context_multiplier=context_multiplier,
            )
            context_text = agent._format_fix_context(fix_context)
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
            if attempt == 1:
                agent._write_run_file(run_dir, "context.txt", context_text)
            agent._write_run_file(
                run_dir, f"attempt_{attempt}_context.txt", context_text
            )

            state = AgentState.GENERATE_FIX
            prompt, raw_fix = agent._generate_fix(
                issue,
                fix_context.file_context,
                last_error,
                context_text,
            )
            agent._write_run_file(run_dir, f"attempt_{attempt}_prompt.txt", prompt)
            agent._write_run_file(run_dir, f"attempt_{attempt}_raw_llm.txt", raw_fix)
            if not raw_fix:
                print("[Agent] Failed to generate fix")
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

            # For replace format, empty replacement is valid for line removal
            # For patch format, empty patch is invalid
            if not current_fix and is_patch:
                print("[Agent] Empty fix output, retrying")
                last_error = "Empty fix output"
                error_history.append(last_error)
                continue
            # For replace format, check if replacement key exists (empty is ok for deletion)
            if not is_patch and "replacement" not in normalized:
                print("[Agent] Missing replacement key, retrying")
                last_error = "Missing replacement key"
                error_history.append(last_error)
                continue

            if last_fix and current_fix == last_fix:
                print("[Agent] Fix repeated with no changes, stopping early")
                agent.fix_tracker.record_attempt(
                    issue_id=issue_key,
                    mode=preferred_format.value,
                    success=False,
                    attempts=attempt,
                    verification_method="skipped",
                    error_message="Repeated fix output",
                )
                return False

            start_line = normalized.get("start_line") if not is_patch else None
            end_line = normalized.get("end_line") if not is_patch else None

            if not is_patch and start_line:
                existing = agent._read_line_range(
                    issue.location.file, start_line, end_line or start_line
                )
                if existing.strip() == current_fix.strip():
                    print("[Agent] Proposed fix is a no-op")
                    last_error = "No-op fix"
                    error_history.append(last_error)
                    continue

            pre_content = "".join(agent._read_file_lines(issue.location.file))
            state = AgentState.APPLY_FIX
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

            state = AgentState.VERIFY
            verified, output = agent.fix_verifier.verify_with_fallback(
                issue.location.file, issue, diff_text=diff_text
            )
            verification_method = agent._extract_verification_method(output)
            agent._write_run_file(
                run_dir, f"attempt_{attempt}_verification.txt", output
            )
            if verified:
                print("[Agent] Fix applied and verified successfully!")
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

        print("[Agent] All fix attempts exhausted.")
        state = AgentState.FAIL
        agent._write_run_file(run_dir, "final_state.txt", state.value)
        agent.fix_tracker.record_attempt(
            issue_id=issue_key,
            mode=preferred_format.value,
            success=False,
            attempts=MAX_FIX_RETRIES,
            verification_method="failed",
            error_message=error_history[-1] if error_history else "",
        )
        return False
