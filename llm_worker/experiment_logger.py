# experiment_logger.py
import os
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Union


class ExperimentLogger:
    """
    Writes a directory per user prompt (a 'trial'), with:
      - meta.json
      - planner.jsonl   (one line per planner attempt)
      - executor.jsonl  (one line per executor attempt)
    Each JSONL line contains the LLM raw output, validator decision, and errors.
    """

    def __init__(self, results_dir: str):
        self.results_dir = results_dir
        self.trials_root = os.path.join(results_dir, "trials")
        os.makedirs(self.trials_root, exist_ok=True)

    def _now(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

    def trial_dir(self, trial_id: str) -> str:
        return os.path.join(self.trials_root, trial_id)

    def new_trial(self, user_prompt: str = "") -> str:
        trial_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
        trial_dir = self.trial_dir(trial_id)
        os.makedirs(trial_dir, exist_ok=True)
        meta = {
            "trial_id": trial_id,
            "created_at_utc": self._now(),
            "user_prompt": user_prompt or "",
        }
        with open(os.path.join(trial_dir, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)
        return trial_id

    def _append_jsonl(self, path: str, record: Dict[str, Any]) -> None:
        with open(path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ---------- Planner ----------
    def log_planner_attempt(
        self,
        trial_id: str,
        attempt: int,
        input_errors: Optional[List[str]],
        raw_output: str,
        is_successful: bool,
        is_valid: Optional[bool],
        validator_errors: Optional[Union[List[str], Dict[str, Any]]],
    ) -> None:
        rec = {
            "ts_utc": self._now(),
            "attempt": attempt,
            "phase": "planner",
            "input_errors": input_errors or [],
            "raw_output": raw_output,
            "llm_success": bool(is_successful),
            "validator_ok": (None if is_valid is None else bool(is_valid)),
            "validator_errors": validator_errors or [],
        }
        path = os.path.join(self.trial_dir(trial_id), "planner.jsonl")
        self._append_jsonl(path, rec)

    # ---------- Executor ----------
    def log_executor_attempt(
        self,
        trial_id: str,
        plan_item: Dict[str, Any],
        attempt: int,
        input_errors: Optional[List[str]],
        raw_output: str,
        is_successful: bool,
        is_valid: Optional[bool],
        validator_errors: Optional[Union[List[str], Dict[str, Any]]],
    ) -> None:
        rec = {
            "ts_utc": self._now(),
            "attempt": attempt,
            "phase": "executor",
            "plan_item": plan_item,
            "input_errors": input_errors or [],
            "raw_output": raw_output,
            "llm_success": bool(is_successful),
            "validator_ok": (None if is_valid is None else bool(is_valid)),
            "validator_errors": validator_errors or [],
        }
        path = os.path.join(self.trial_dir(trial_id), "executor.jsonl")
        self._append_jsonl(path, rec)

    def log_phase_final(
        self,
        trial_id: str,
        phase: str,  # "planner" or "executor"
        succeeded: bool,
        parsed_json: Optional[Union[Dict[str, Any], List[Any]]],
        note: str = "",
    ) -> None:
        rec = {
            "ts_utc": self._now(),
            "phase": phase,
            "final": True,
            "succeeded": bool(succeeded),
            "parsed_json": parsed_json,
            "note": note,
        }
        path = os.path.join(self.trial_dir(trial_id), f"{phase}.jsonl")
        self._append_jsonl(path, rec)
