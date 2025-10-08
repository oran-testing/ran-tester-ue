#!/usr/bin/env python3
"""
Experiment Log Parser
Reads and analyzes experiment trial logs from the LLM worker.
"""

import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
from datetime import datetime
from tabulate import tabulate
import textwrap


class ExperimentLogParser:
    """Parser for experiment trial logs"""
    
    def __init__(self, results_dir: str):
        self.results_dir = Path(results_dir)
        self.trials_dir = self.results_dir / "trials"
        
        if not self.trials_dir.exists():
            raise ValueError(f"Trials directory not found: {self.trials_dir}")
    
    def get_trial_dirs(self, n: int = None) -> List[Path]:
        """Get the last N trial directories, sorted by creation time"""
        trial_dirs = [d for d in self.trials_dir.iterdir() if d.is_dir()]
        trial_dirs.sort(reverse=True)
        
        if n is not None:
            trial_dirs = trial_dirs[:n]
        
        return trial_dirs
    
    def read_meta(self, trial_dir: Path) -> Dict[str, Any]:
        """Read meta.json from a trial directory"""
        meta_path = trial_dir / "meta.json"
        if not meta_path.exists():
            return {}
        
        with open(meta_path, 'r') as f:
            return json.load(f)
    
    def read_jsonl(self, jsonl_path: Path) -> List[Dict[str, Any]]:
        """Read a JSONL file and return list of records"""
        if not jsonl_path.exists():
            return []
        
        records = []
        with open(jsonl_path, 'r') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records
    
    def analyze_planner_attempts(self, trial_dir: Path) -> Dict[str, Any]:
        """Analyze planner attempts from planner.jsonl"""
        planner_path = trial_dir / "planner.jsonl"
        records = self.read_jsonl(planner_path)
        
        if not records:
            return {
                "total_attempts": 0,
                "llm_failures": 0,
                "validation_failures": 0,
                "success": False
            }
        
        llm_failures = sum(1 for r in records if r.get("llm_success") is False)
        validation_failures = sum(1 for r in records if r.get("validator_ok") is False)
        success = any(r.get("validator_ok") is True for r in records)
        
        return {
            "total_attempts": len(records),
            "llm_failures": llm_failures,
            "validation_failures": validation_failures,
            "success": success,
            "final_errors": records[-1].get("validator_errors", []) if records else []
        }
    
    def analyze_executor_attempts(self, trial_dir: Path) -> Dict[str, Any]:
        """Analyze executor attempts from executor.jsonl"""
        executor_path = trial_dir / "executor.jsonl"
        records = self.read_jsonl(executor_path)
        
        if not records:
            return {
                "total_attempts": 0,
                "llm_failures": 0,
                "validation_failures": 0,
                "success": False
            }
        
        llm_failures = sum(1 for r in records if r.get("llm_success") is False)
        validation_failures = sum(1 for r in records if r.get("validator_ok") is False)
        success = any(r.get("validator_ok") is True for r in records)
        
        return {
            "total_attempts": len(records),
            "llm_failures": llm_failures,
            "validation_failures": validation_failures,
            "success": success,
            "from_planner": records[0].get("from_planner", "") if records else "",
            "final_errors": records[-1].get("validator_errors", []) if records else []
        }
    
    def parse_trials(self, n: int = None) -> pd.DataFrame:
        """Parse the last N trials and return a DataFrame"""
        trial_dirs = self.get_trial_dirs(n)
        
        data = []
        for idx, trial_dir in enumerate(reversed(trial_dirs), 1):
            meta = self.read_meta(trial_dir)
            planner_analysis = self.analyze_planner_attempts(trial_dir)
            executor_analysis = self.analyze_executor_attempts(trial_dir)
            
            row = {
                "run_no": idx,
                "created": meta.get("created_at_utc", ""),
                "prompt": meta.get("user_prompt", ""),
                "from_p": executor_analysis["from_planner"],
                
                # Planner metrics (shortened)
                "p_total": meta.get("planner_total_attempts", planner_analysis["total_attempts"]),
                "p_success": meta.get("planner_success_attempt"),
                "p_max": meta.get("planner_reached_max_retry", False),
                
                # Executor metrics (shortened)
                "e_total": meta.get("executor_total_attempts", executor_analysis["total_attempts"]),
                "e_success": meta.get("executor_success_attempt"),
                "e_max": meta.get("executor_reached_max_retry", False),
            }
            
            data.append(row)
        
        return pd.DataFrame(data)
    
    def get_detailed_attempts(self, trial_id: str) -> Dict[str, Any]:
        """Get detailed attempt-by-attempt breakdown for a specific trial"""
        trial_dir = self.trials_dir / trial_id
        
        if not trial_dir.exists():
            raise ValueError(f"Trial not found: {trial_id}")
        
        meta = self.read_meta(trial_dir)
        planner_records = self.read_jsonl(trial_dir / "planner.jsonl")
        executor_records = self.read_jsonl(trial_dir / "executor.jsonl")
        
        return {
            "meta": meta,
            "planner_attempts": planner_records,
            "executor_attempts": executor_records
        }


def pretty_print_csv(df: pd.DataFrame) -> None:
    """Pretty print a DataFrame using the tabulate library with text wrapping."""
    if df.empty:
        print("No data to display.")
        return

    df_display = df.copy()

    wrap_columns = ['user_prompt', 'from_planner']
    wrap_width = 45

    for col in wrap_columns:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(
                lambda x: textwrap.fill(str(x).strip(), width=wrap_width) if pd.notna(x) else ""
            )

    print(tabulate(df_display, headers='keys', tablefmt='grid', showindex=False))

    # total_runs = len(df)
    # successful_runs = df["overall_success"].sum()
    # success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0

    # print(f"\nTotal Runs: {total_runs}")
    # print(f"Successful: {successful_runs} ({success_rate:.1f}%)")
    # print(f"Failed: {total_runs - successful_runs} ({100.0 - success_rate:.1f}%)")
    # print()


def main():
    parser = argparse.ArgumentParser(
        description="Parse and analyze LLM experiment trial logs"
    )
    parser.add_argument(
        "results_dir",
        type=str,
        help="Path to results directory containing trials/"
    )
    parser.add_argument(
        "-n", "--num-trials",
        type=int,
        default=None,
        help="Number of recent trials to analyze (default: all)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output file path (default: print to stdout)"
    )
    parser.add_argument(
        "-d", "--detail",
        type=str,
        default=None,
        help="Show detailed breakdown for specific trial_id"
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Output format (default: csv)"
    )
    parser.add_argument(
        "--no-pretty",
        action="store_true",
        help="Disable pretty printing for CSV (raw CSV output)"
    )
    
    args = parser.parse_args()
    
    log_parser = ExperimentLogParser(args.results_dir)
    
    if args.detail:
        details = log_parser.get_detailed_attempts(args.detail)
        print(json.dumps(details, indent=2))
        return
    
    df = log_parser.parse_trials(args.num_trials)
    
    if df.empty:
        print("No trials found.")
        return
    
    if args.format == "json":
        output = df.to_json(orient="records", indent=2)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"Results saved to {args.output}")
        else:
            print(output)
    else:
        if args.output:
            df.to_csv(args.output, index=False)
            print(f"Results saved to {args.output}")
            if not args.no_pretty:
                print("\nPreview:")
                pretty_print_csv(df)
        else:
            if args.no_pretty:
                print(df.to_csv(index=False))
            else:
                pretty_print_csv(df)


if __name__ == "__main__":
    main()