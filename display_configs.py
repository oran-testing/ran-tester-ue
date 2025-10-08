#!/usr/bin/env python3
"""
Display Configs - Pretty print experiment trial configurations
Shows plan.json and execution configs in human-readable format
"""

import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
import toml


class ConfigDisplayer:
    """Display experiment configurations in human-readable format"""
    
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
        """Read meta.json"""
        meta_path = trial_dir / "meta.json"
        if not meta_path.exists():
            return {}
        
        with open(meta_path, 'r') as f:
            return json.load(f)
    
    def read_jsonl(self, jsonl_path: Path) -> List[Dict[str, Any]]:
        """Read JSONL file"""
        if not jsonl_path.exists():
            return []
        
        records = []
        with open(jsonl_path, 'r') as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records
    
    def extract_plan_from_planner(self, trial_dir: Path) -> Dict[str, Any]:
        """Extract the final successful plan from planner.jsonl"""
        planner_records = self.read_jsonl(trial_dir / "planner.jsonl")
        
        # Find the last successful validation
        for record in reversed(planner_records):
            if record.get("validator_ok") is True:
                raw_output = record.get("raw_output", "")
                # Try to extract JSON from the raw output
                try:
                    # Look for JSON block
                    start_idx = raw_output.find("[")
                    end_idx = raw_output.rfind("]") + 1
                    if start_idx != -1 and end_idx > start_idx:
                        plan_json = raw_output[start_idx:end_idx]
                        return json.loads(plan_json)
                except:
                    pass
        
        return None
    
    def extract_config_from_executor(self, trial_dir: Path) -> Dict[str, Any]:
        """Extract the final successful config from executor.jsonl"""
        executor_records = self.read_jsonl(trial_dir / "executor.jsonl")
        
        # Find the last successful validation
        for record in reversed(executor_records):
            if record.get("validator_ok") is True:
                raw_output = record.get("raw_output", "")
                # Try to extract JSON from the raw output
                try:
                    # Look for JSON block
                    start_idx = raw_output.find("{")
                    end_idx = raw_output.rfind("}") + 1
                    if start_idx != -1 and end_idx > start_idx:
                        config_json = raw_output[start_idx:end_idx]
                        return json.loads(config_json)
                except:
                    pass
        
        return None
    
    def pretty_print_separator(self, title: str, width: int = 100):
        """Print a nice separator"""
        padding = (width - len(title) - 2) // 2
        print("\n" + "=" * width)
        print(" " * padding + title)
        print("=" * width + "\n")
    
    def pretty_print_subsection(self, title: str, width: int = 100):
        """Print a subsection separator"""
        print("\n" + "-" * width)
        print(f"  {title}")
        print("-" * width + "\n")
    
    def pretty_print_dict(self, data: Dict[str, Any], indent: int = 0):
        """Pretty print a dictionary with proper formatting"""
        if not data:
            print("  (empty)")
            return
        
        indent_str = "  " * indent
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{indent_str}{key}:")
                self.pretty_print_dict(value, indent + 1)
            elif isinstance(value, list):
                print(f"{indent_str}{key}: [")
                for item in value:
                    if isinstance(item, dict):
                        print(f"{indent_str}  {{")
                        for k, v in item.items():
                            print(f"{indent_str}    {k}: {v}")
                        print(f"{indent_str}  }}")
                    else:
                        print(f"{indent_str}  {item}")
                print(f"{indent_str}]")
            else:
                print(f"{indent_str}{key}: {value}")
    
    def display_trial(self, trial_dir: Path, trial_num: int):
        """Display all configs for a single trial"""
        meta = self.read_meta(trial_dir)
        trial_id = meta.get("trial_id", trial_dir.name)
        
        self.pretty_print_separator(f"TRIAL #{trial_num}: {trial_id}")
        
        # Meta information
        print("META INFORMATION")
        print(f"  Created: {meta.get('created_at_utc', 'N/A')}")
        print(f"  User Prompt: {meta.get('user_prompt', 'N/A')}")
        print(f"  Planner: {meta.get('planner_total_attempts', 0)} attempts -> " +
              f"{'SUCCESS' if meta.get('planner_final_status') == 'success' else 'FAILED'}")
        print(f"  Executor: {meta.get('executor_total_attempts', 0)} attempts -> " +
              f"{'SUCCESS' if meta.get('executor_final_status') == 'success' else 'FAILED'}")
        
        # Planner output (plan.json equivalent)
        self.pretty_print_subsection("PLANNER OUTPUT (Final Plan)")
        plan = self.extract_plan_from_planner(trial_dir)
        if plan:
            if isinstance(plan, list):
                for idx, item in enumerate(plan, 1):
                    print(f"\nStep {idx}:")
                    self.pretty_print_dict(item, indent=1)
            else:
                self.pretty_print_dict(plan)
        else:
            print("  (No successful plan found)")
        
        # Executor output (config)
        self.pretty_print_subsection("EXECUTOR OUTPUT (Component Configuration)")
        config = self.extract_config_from_executor(trial_dir)
        if config:
            component_type = config.get("type", "unknown")
            print(f"Component Type: {component_type}")
            print(f"Component ID: {config.get('id', 'N/A')}\n")
            
            # Display config
            self.pretty_print_dict(config)
        else:
            print("  (No successful executor config found)")
        
        # Show from_planner description
        executor_records = self.read_jsonl(trial_dir / "executor.jsonl")
        if executor_records:
            from_planner = executor_records[0].get("from_planner", "")
            if from_planner:
                self.pretty_print_subsection("DESCRIPTION FROM PLANNER")
                print(f"  {from_planner}")
        
        print("\n" + "=" * 100 + "\n")
    
    def display_trials(self, n: int = None):
        """Display configs for the last N trials"""
        trial_dirs = self.get_trial_dirs(n)
        
        if not trial_dirs:
            print("No trials found.")
            return
        
        print(f"\n{'='*100}")
        print(f"  DISPLAYING CONFIGURATIONS FOR {len(trial_dirs)} TRIAL(S)")
        print(f"{'='*100}\n")
        
        for idx, trial_dir in enumerate(reversed(trial_dirs), 1):
            self.display_trial(trial_dir, idx)


def main():
    parser = argparse.ArgumentParser(
        description="Display experiment trial configurations in human-readable format"
    )
    parser.add_argument(
        "results_dir",
        type=str,
        help="Path to results directory containing trials/"
    )
    parser.add_argument(
        "-n", "--num-trials",
        type=int,
        default=1,
        help="Number of recent trials to display (default: 1)"
    )
    parser.add_argument(
        "-t", "--trial-id",
        type=str,
        default=None,
        help="Display specific trial by ID"
    )
    
    args = parser.parse_args()
    
    displayer = ConfigDisplayer(args.results_dir)
    
    if args.trial_id:
        # Display specific trial
        trial_dir = displayer.trials_dir / args.trial_id
        if not trial_dir.exists():
            print(f"Error: Trial '{args.trial_id}' not found")
            return
        displayer.display_trial(trial_dir, 1)
    else:
        # Display last N trials
        displayer.display_trials(args.num_trials)


if __name__ == "__main__":
    main()