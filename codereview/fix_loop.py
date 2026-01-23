import json
from typing import Optional, List, TYPE_CHECKING

from .agent_state import AgentState
from .models import BugIssue, FixFormat
from .config import MAX_FIX_RETRIES
from .path_utils import normalize_repo_path

if TYPE_CHECKING:
    from .agent import ReActAgent


class FixLoopRunner:
    """Orchestrates the fix loop using a ReActAgent instance."""

    def __init__(self, agent: "ReActAgent"):
        self.agent = agent
        self._chunk_windows = [40, 120, 300]
        self._single_line_window_radius = 20

    def _expand_issue_chunk(self, issue: BugIssue, window_size: int) -> bool:
        if not issue.location.file or not issue.location.line:
            return False
        lines = self.agent._read_file_lines(issue.location.file)
        if not lines:
            return False
        total = len(lines)
        center = issue.location.line
        issue.chunk_start_line = max(1, center - window_size)
        issue.chunk_end_line = min(total, center + window_size)
        return True

    def _get_edit_window(self, issue: BugIssue) -> Optional[tuple[int, int, str]]:
        if not issue.location.line:
            return None
        if issue.chunk_start_line and issue.chunk_end_line and issue.chunk_type == "function":
            return issue.chunk_start_line, issue.chunk_end_line, "function"
        if issue.location.function and not issue.chunk_start_line:
            bounds = self._find_function_bounds(issue)
            if bounds:
                return bounds[0], bounds[1], "function"
        start = max(1, issue.location.line - self._single_line_window_radius)
        end = issue.location.line + self._single_line_window_radius
        return start, end, "window"

    def _find_function_bounds(self, issue: BugIssue) -> Optional[tuple[int, int]]:
        lines = self.agent._read_file_lines(issue.location.file)
        if not lines:
            return None
        func_name = issue.location.function.split(".")[-1].strip("()")
        if not func_name:
            return None
        start_idx = None
        for idx, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith(f"def {func_name}") or stripped.startswith(f"class {func_name}"):
                start_idx = idx
                break
        if start_idx is None:
            return None
        end_idx = len(lines) - 1
        for idx in range(start_idx + 1, len(lines)):
            stripped = lines[idx].lstrip()
            if stripped.startswith("def ") or stripped.startswith("class "):
                end_idx = idx - 1
                break
        return start_idx + 1, end_idx + 1

    def _ensure_edit_window(
        self, issue: BugIssue, refresh: bool = False
    ) -> Optional[tuple[int, int, str]]:
        if issue.start_line and issue.end_line and issue.start_line != issue.end_line:
            return None
        if refresh and issue.chunk_type == "window":
            issue.chunk_start_line = None
            issue.chunk_end_line = None
            issue.chunk_type = None
        if refresh and issue.location.function:
            bounds = self._find_function_bounds(issue)
            if bounds:
                issue.chunk_start_line, issue.chunk_end_line = bounds
                issue.chunk_type = "function"
                return bounds[0], bounds[1], "function"
        window = self._get_edit_window(issue)
        if not window:
            return None
        start, end, source = window
        issue.chunk_start_line = start
        issue.chunk_end_line = end
        issue.chunk_type = source
        return start, end, source

    @staticmethod
    def _summarize_diff(before: str, after: str) -> str:
        import difflib

        before_lines = before.splitlines()
        after_lines = after.splitlines()
        diff = list(
            difflib.unified_diff(
                before_lines,
                after_lines,
                lineterm="",
            )
        )
        if not diff:
            return "No changes detected."
        summary_lines = diff[:200]
        return "\n".join(summary_lines)

    def _relocate_issue_by_context(self, issue: BugIssue) -> bool:
        lines = self.agent._read_file_lines(issue.location.file)
        if not lines:
            return False

        evidence_candidates = []
        if issue.evidence:
            evidence_candidates.append(issue.evidence.strip())
        if issue.line_text:
            evidence_candidates.append(issue.line_text.strip())
        evidence_candidates = [c for c in evidence_candidates if c]

        def _find_in_range(start_idx: int, end_idx: int) -> Optional[int]:
            for idx in range(start_idx, end_idx):
                line = lines[idx]
                for candidate in evidence_candidates:
                    if candidate and candidate in line:
                        return idx
            return None

        if issue.location.line:
            window = 5
            start = max(0, issue.location.line - window - 1)
            end = min(len(lines), issue.location.line + window)
            found = _find_in_range(start, end)
            if found is not None:
                issue.location.line = found + 1
                issue.line_text = lines[found].rstrip("\n")
                return True

        if issue.location.function:
            func_name = issue.location.function.split(".")[-1].strip("()")
            if func_name:
                for idx, line in enumerate(lines):
                    if line.lstrip().startswith(f"def {func_name}"):
                        search_end = min(len(lines), idx + 200)
                        found = _find_in_range(idx, search_end)
                        if found is not None:
                            issue.location.line = found + 1
                            issue.line_text = lines[found].rstrip("\n")
                            return True
                    if line.lstrip().startswith(f"class {func_name}"):
                        search_end = min(len(lines), idx + 200)
                        found = _find_in_range(idx, search_end)
                        if found is not None:
                            issue.location.line = found + 1
                            issue.line_text = lines[found].rstrip("\n")
                            return True

        return False

    def _classify_missing_evidence(self, issue: BugIssue) -> str:
        lines = self.agent._read_file_lines(issue.location.file)
        content = "".join(lines)
        evidence = (issue.evidence or "").strip()
        suggested_fix = (issue.suggested_fix or "").strip()

        if self._relocate_issue_by_context(issue):
            return "relocated"

        if evidence and evidence in content:
            return "relocated"

        if suggested_fix and suggested_fix in content:
            return "resolved"

        if "open(" in evidence and "with open(" in content:
            return "resolved"

        return "stale"

    @staticmethod
    def _is_format_error(reason: str) -> bool:
        lowered = reason.lower()
        return (
            "empty fix payload" in lowered
            or "unsupported fix format" in lowered
            or "fix format must be" in lowered
            or "missing replacement content" in lowered
            or "missing patch content" in lowered
            or "json" in lowered
        )

    @staticmethod
    def _is_chunk_range_error(reason: str) -> bool:
        return "replacement must stay within the target chunk range" in reason.lower()

    def run(self, issue: BugIssue, diff_text: Optional[str] = None) -> bool:
        agent = self.agent
        print(f"\n[Agent] Starting to fix: {issue.description}")
        print(f"[Agent] File: {issue.location.file}, Line: {issue.location.line}")

        state = AgentState.VALIDATE_ISSUE
        run_dir = agent._init_run_dir()
        agent._write_run_file(
            run_dir, "issue.json", issue.model_dump_json(indent=2)
        )

        if issue.location and issue.location.file:
            issue.location.file = normalize_repo_path(issue.location.file)

        window_info: Optional[tuple[int, int, str]] = None

        is_valid, reason = agent._validate_issue(issue)
        if not is_valid:
            if "Evidence string not found in file" in reason:
                status = self._classify_missing_evidence(issue)
                if status == "relocated":
                    print(
                        "[Agent] Evidence moved within file; continuing with updated location."
                    )
                    is_valid = True
                    reason = ""
                    window_info = self._ensure_edit_window(issue, refresh=True)
                    if window_info:
                        start, end, source = window_info
                        print(f"[Agent] Edit window: {start}-{end} ({source})")
                elif status == "resolved":
                    print(
                        "[Agent] Issue appears resolved by previous patch; skipping."
                    )
                    agent._write_run_file(
                        run_dir, "final_state.txt", "RESOLVED_BY_PREVIOUS_PATCH"
                    )
                    return True
                else:
                    print("[Agent] Issue location is stale; skipping.")
                    agent._write_run_file(
                        run_dir, "final_state.txt", "STALE_LOCATION"
                    )
                    return True
            else:
                print(f"[Agent] Issue is not actionable: {reason}")
            if not is_valid:
                agent._write_run_file(run_dir, "final_state.txt", state.value)
                return False

        last_error: Optional[str] = None
        last_fix: Optional[str] = None
        error_history: List[str] = []
        issue_key = agent._issue_key(issue)
        preferred_format = agent.fix_strategy_selector.recommend_format(issue, diff_text)
        enforce_format = False
        desc_lower = (issue.description or "").lower()
        force_patch = False
        if issue.chunk_type == "class" and any(
            token in desc_lower for token in ["missing", "not initialized", "unimplemented"]
        ):
            force_patch = True
        if "missing method" in desc_lower or "missing methods" in desc_lower:
            force_patch = True

        if force_patch:
            preferred_format = FixFormat.PATCH
            enforce_format = True
        elif issue.start_line == issue.end_line and issue.start_line:
            preferred_format = FixFormat.REPLACE
            enforce_format = True

        last_verification_output: Optional[str] = None
        last_verification_error: Optional[str] = None
        last_diff_summary: Optional[str] = None
        repeated_verification = 0
        chunk_window_idx = 0
        attempts_used = 0
        format_error_streak = 0

        while attempts_used < MAX_FIX_RETRIES:
            attempt = attempts_used + 1
            state = AgentState.BUILD_CONTEXT
            print(f"\n[Agent] Attempt {attempt}/{MAX_FIX_RETRIES}")
            print("[Agent] Generating fix...")
            window_info = self._ensure_edit_window(issue, refresh=True)
            if window_info:
                start, end, source = window_info
                print(f"[Agent] Edit window: {start}-{end} ({source})")
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
                if "DIFF_SUMMARY" in last_error or last_error == "Repeated fix output":
                    retry_instructions = "\n".join(
                        part
                        for part in [
                            retry_instructions,
                            "Use a different strategy than the previous attempt.",
                        ]
                        if part
                    )

            verification_context = ""
            if last_verification_error and last_diff_summary:
                verification_context = "\n".join(
                    [
                        f"Previous patch failed verification because: {last_verification_error}",
                        "Here is what you changed last time:",
                        last_diff_summary,
                        "Do NOT repeat the same patch; use a different strategy.",
                        "Constraints:",
                        "- Do NOT change function signature",
                        "- Preserve return type",
                        "- Preserve whether inputs are mutated",
                        "- Preserve behavior expected by existing tests",
                    ]
                )

            fix_context = agent.fix_context_builder.build_context(
                issue,
                diff_text=diff_text,
                attempt=attempt,
                previous_error=last_error,
                context_multiplier=context_multiplier,
            )
            context_text = agent._format_fix_context(fix_context)
            if verification_context:
                context_text = "\n\n".join([verification_context, context_text])
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
            if window_info:
                start, end, source = window_info
                context_text = "\n\n".join(
                    part
                    for part in [
                        f"EDIT_WINDOW: {start}-{end} ({source})",
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
            if issue.location.function == "sort_scores" or "sort_scores" in (
                issue.description or ""
            ):
                sort_constraints = "\n".join(
                    [
                        "CONSTRAINTS:",
                        "- Keep the function signature unchanged",
                        "- Keep behavior identical",
                        "- Prefer built-in sorted()/list.sort() where safe",
                    ]
                )
                context_text = "\n\n".join([sort_constraints, context_text])
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
            if not is_valid and self._is_chunk_range_error(reason):
                if chunk_window_idx < len(self._chunk_windows):
                    expanded = self._expand_issue_chunk(
                        issue, self._chunk_windows[chunk_window_idx]
                    )
                    chunk_window_idx += 1
                    if expanded:
                        is_valid, reason, normalized = agent._validate_fix_payload(
                            issue,
                            payload,
                            diff_text=diff_text,
                            expected_format=preferred_format if enforce_format else None,
                        )
                        window_info = self._ensure_edit_window(issue, refresh=True)
                        if window_info:
                            start, end, source = window_info
                            print(f"[Agent] Edit window: {start}-{end} ({source})")

            if not is_valid and self._is_format_error(reason):
                format_error_streak += 1
                repair_instructions = (
                    "FORMAT_REPAIR: Return ONLY a valid unified diff with + and - lines "
                    "and @@ hunks. No explanations."
                )
                repair_context = "\n\n".join(
                    part for part in [context_text, repair_instructions] if part
                )
                prompt, raw_fix = agent._generate_fix(
                    issue,
                    fix_context.file_context,
                    reason,
                    repair_context,
                )
                agent._write_run_file(
                    run_dir, f"attempt_{attempt}_repair_prompt.txt", prompt
                )
                agent._write_run_file(
                    run_dir, f"attempt_{attempt}_repair_raw_llm.txt", raw_fix
                )
                if raw_fix:
                    payload = agent._parse_fix_payload(raw_fix)
                    is_valid, reason, normalized = agent._validate_fix_payload(
                        issue,
                        payload,
                        diff_text=diff_text,
                        expected_format=FixFormat.PATCH,
                    )
            if not is_valid:
                last_error = reason
                error_history.append(reason)
                print(f"[Agent] Invalid fix payload: {reason}")
                if window_info and (
                    "window" in reason.lower() or "chunk range" in reason.lower()
                ):
                    start, end, source = window_info
                    print(f"[Agent] Rejected outside edit window {start}-{end} ({source})")
                if self._is_format_error(reason) and format_error_streak < 2:
                    print("[Agent] Format error; retrying without consuming an attempt.")
                    continue
                attempts_used += 1
                lowered = reason.lower()
                if (
                    "patch check failed" in lowered
                    or "corrupt patch" in lowered
                    or "patch does not apply" in lowered
                ):
                    if force_patch:
                        preferred_format = FixFormat.PATCH
                        enforce_format = True
                    else:
                        preferred_format = FixFormat.REPLACE
                        enforce_format = True
                elif "fix format must be 'patch'" in lowered:
                    preferred_format = FixFormat.PATCH
                    enforce_format = True
                elif "fix format must be 'replace'" in lowered:
                    preferred_format = FixFormat.REPLACE
                    enforce_format = True
                agent._write_run_file(
                    run_dir,
                    f"attempt_{attempt}_payload.json",
                    json.dumps({"error": reason, "raw": payload}, indent=2),
                )
                continue
            format_error_streak = 0
            attempts_used += 1

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

            if not current_fix:
                print("[Agent] Empty fix output, retrying")
                last_error = "Empty fix output"
                error_history.append(last_error)
                continue

            if last_fix and current_fix == last_fix:
                print("[Agent] Fix repeated twice; stopping early due to no progress.")
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
                if is_patch and last_error and "patch" in last_error.lower():
                    window_info = self._ensure_edit_window(issue, refresh=True)
                    if window_info:
                        start, end, source = window_info
                        window_text = agent._read_line_range(
                            issue.location.file, start, end
                        )
                        last_error = (
                            f"{last_error}\nCURRENT_WINDOW:\n{window_text}\n"
                            "Generate a patch that matches the current file content exactly."
                        )
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

            pre_lines = pre_content.count("\n") + 1
            post_lines = post_content.count("\n") + 1
            if post_lines > pre_lines * 1.5 and (post_lines - pre_lines) > 200:
                last_error = "Fix expanded file significantly; stopping to avoid runaway edits"
                error_history.append(last_error)
                print(f"[Agent] {last_error}")
                state = AgentState.ROLLBACK
                agent.fixer.rollback_files(touched_files)
                agent.fix_tracker.record_attempt(
                    issue_id=issue_key,
                    mode=preferred_format.value,
                    success=False,
                    attempts=attempt,
                    verification_method="skipped",
                    error_message=last_error,
                )
                return False

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

            diff_summary = self._summarize_diff(pre_content, post_content)
            last_verification_error = output
            last_diff_summary = diff_summary
            last_error = f"{output}\nDIFF_SUMMARY:\n{diff_summary}"
            error_history.append(output)
            last_fix = current_fix
            state = AgentState.ROLLBACK
            agent.fixer.rollback_files(touched_files)
            print("[Agent] Fix failed verification, rolling back...")
            if output == last_verification_output:
                repeated_verification += 1
            else:
                repeated_verification = 0
            last_verification_output = output
            if repeated_verification >= 1:
                print("[Agent] Verification repeated with no progress, stopping early")
                agent.fix_tracker.record_attempt(
                    issue_id=issue_key,
                    mode=preferred_format.value,
                    success=False,
                    attempts=attempt,
                    verification_method=verification_method,
                    error_message="Repeated verification output",
                )
                return False

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
