import re
import csv
import os
import glob
import json
import pandas as pd
import numpy as np



def find_latest_run(base_root):
    # absolute path to latest run dir
    if not os.path.isdir(base_root):
        return None
    candidates = []
    for name in os.listdir(base_root):
        p = os.path.join(base_root, name)
        if os.path.isdir(p) and name.startswith("run_"):
            candidates.append(p)
    if not candidates:
        return None
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


def clean_ansi_escape(line):
    """Remove ANSI escape sequences like \x1b[0m."""
    return re.sub(r'\x1b\[[0-9;]*m', '', line)

def get_csv_output_path(log_path, subfolder):
    """Generate output CSV path in specified subfolder."""
    base = os.path.basename(log_path)
    csv_name = base.replace(".log", ".csv") if base.endswith(".log") else base + ".csv"
    folder = os.path.join(os.getcwd(), subfolder)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, csv_name)

# === RU Log Parser ===
def parse_ru(log_file_path):
    output_csv_path = get_csv_output_path(log_file_path, subfolder="ru_csv")

    with open(log_file_path, 'r') as f:
        lines = f.readlines()

    clean_lines = [clean_ansi_escape(line).strip() for line in lines]

    headers = []
    data_rows = []
    header_line_pattern = None

    for line in clean_lines:
        if not line.startswith("|"):
            continue
        if "TIME" in line and "TX_TOTAL" in line:
            current_header = [h.strip() for h in line.strip("|").split("|")]
            if not headers:
                headers = current_header
                header_line_pattern = line.strip("|")
            continue
        if line.strip("|") == header_line_pattern:
            continue
        values = [v.strip() for v in line.strip("|").split("|")]
        if len(values) == len(headers):
            data_rows.append(values)

    with open(output_csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        writer.writerows(data_rows)

    # print(f"[RU] Saved: {output_csv_path}")

# === gNB Log Parser ===
def parse_gnb(log_file_path):
    output_csv_path = get_csv_output_path(log_file_path, subfolder="gnb_csv")

    with open(log_file_path, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    headers = []
    data_rows = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if line.startswith("|--------------------DL"):
            if i + 1 < len(lines):
                header_line = lines[i + 1]
                headers = [h.strip() for h in header_line.replace('|', ' ').split()]
                i += 2
                continue
        if headers and "|" in line and not line.startswith("|--") and not any(k in line for k in ["DL", "UL"]):
            values = [v.strip() for v in line.split("|")]
            row = []
            for v in values:
                row.extend(v.split())
            if len(row) == len(headers):
                data_rows.append(row)
        i += 1

    with open(output_csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        writer.writerows(data_rows)

    # print(f"[gNB] Saved: {output_csv_path}")

# === Batch Parser ===
def parse_batch(base_folder="attack_results"):
    subfolders = [f.path for f in os.scandir(base_folder) if f.is_dir()]

    n = 1
    for folder in subfolders:
        ru_logs = glob.glob(os.path.join(folder, "ru_*.log"))
        gnb_logs = glob.glob(os.path.join(folder, "gnb_*.log"))

        if ru_logs:
            # print(f"\n[>>] Parsing RU log: {ru_logs[0]}")
            parse_ru(ru_logs[0])
        else:
            print(f"[--]****No RU log found in**** {folder}")

        if gnb_logs:
            # print(f"[>>] Parsing gNB log: {gnb_logs[0]}")
            parse_gnb(gnb_logs[0])
        else:
            print(f"[--]****No gNB log found in**** {folder}\n")

        n +=1 

# ============ gets avg of before, during and after logs =============
def get_avg_ru():
    columns_of_interest = [
        "RX_TOTAL", "RX_LATE",
        "RX_LATE_C", "RX_LATE_C_U",
        "TX_TOTAL"
    ]

    ru_csv_dir = "ru_csv"
    results = []

    for filename in os.listdir(ru_csv_dir):
        if filename.endswith(".csv"):
            file_path = os.path.join(ru_csv_dir, filename)
            try:
                df = pd.read_csv(file_path)
                df[columns_of_interest] = df[columns_of_interest].apply(pd.to_numeric, errors='coerce')

                first_5 = df.iloc[:5][columns_of_interest].mean()
                next_10 = df.iloc[5:15][columns_of_interest].mean()

                if len(df) > 15:
                    final_rows = df.iloc[15:20]
                else:
                    final_rows = pd.DataFrame(columns=columns_of_interest)

                final_avg = final_rows[columns_of_interest].mean()
                count_final = len(final_rows)

                results.append({
                    "file": filename,
                    "before": first_5.to_dict(),
                    "during": next_10.to_dict(),
                    "after": final_avg.to_dict(),
                })

            except Exception as e:
                print(f"Failed to process {file_path}: {e}")

    with open("ru_summary.json", "w") as f:
        json.dump(results, f, indent=4)

    print("\nSummary saved to: ru_summary.json")


# ========= json to csv =====================
def to_csv():

    with open("ru_summary.json") as f:
        data = json.load(f)

    df = pd.json_normalize(data)
    df.columns = [col.replace('.', '_') for col in df.columns]
    df.to_csv("ru_summary.csv", index=False)
    
    print("CSV saved to ru_summary.csv")

import pandas as pd
import numpy as np

# ========= Compute Delta Stats =====================

def compute_delta_stats(df):
    """
    Scan delta‐percent columns for RX_LATE, RX_LATE_C, RX_LATE_C_U, RX_TOTAL, TX_TOTAL
    and compute 1Q and median for each phase (during, after).
    For the three late‐metrics, ignore any non‐positive deltas (i.e. improvements) when
    calculating their quartiles/medians.
    Returns a dict: stats[col_name] = {"q1":…, "median":…}
    """
    late_metrics = {"RX_LATE", "RX_LATE_C", "RX_LATE_C_U"}
    other_metrics = ["RX_TOTAL", "TX_TOTAL"]
    phases = ["during", "after"]

    stats = {}
    for metric in late_metrics.union(other_metrics):
        for phase in phases:
            col = f"delta_pct_{phase}_{metric}"
            if col not in df.columns:
                continue

            vals = df[col].dropna().astype(float)
            # For late‐metrics, ignore any zero or negative deltas
            if metric in late_metrics:
                vals = vals[vals > 0]

            if not vals.empty:
                stats[col] = {
                    "q1":     vals.quantile(0.25),
                    "median": vals.median()
                }
    return stats

# ========= Display Delta Thresholds =====================

def display_delta_thresholds(stats):
    """
    Print the 1st quartile (q1) and median thresholds for each delta_pct_* column.
    """
    print("\nDelta Thresholds (1Q and Median):")
    print(f"{'Metric':<35} | {'1Q':>10} | {'Median':>10}")
    print("-" * 55)
    for col, thr in sorted(stats.items()):
        print(f"{col:<35} | {thr['q1']:8.4f}% | {thr['median']:8.4f}%")

# ========= Classify RU Events =====================
def classify(row, stats):
    """
    row: a DataFrame row
    stats: output of compute_delta_stats(df)
    
    Returns one of:
      - "no impact"
      - "rx overloaded with recovery" / "rx overloaded no recovery"
      - "rx degradation with recovery" / "rx degradation no recovery"
      - "late with recovery" / "late with no recovery"
      - "other"
    """
    late_metrics = ["RX_LATE", "RX_LATE_C", "RX_LATE_C_U"]
    overload_thresh = 5.0  # 5% threshold for RX/TX overload

    # fetch the key delta values
    rx_d = row["delta_pct_during_RX_TOTAL"]
    rx_a = row["delta_pct_after_RX_TOTAL"]
    tx_d = row["delta_pct_during_TX_TOTAL"]

    # 1) NO IMPACT:
    #    • both |rx_d| < 5% and |tx_d| < 5%
    #    • AND every late‐metric during ≤ its 1Q
    if (
        abs(rx_d) < overload_thresh
        and abs(tx_d) < overload_thresh
        and all(
            row[f"delta_pct_during_{m}"] <= stats[f"delta_pct_during_{m}"]["q1"]
            for m in late_metrics
            if f"delta_pct_during_{m}" in stats
        )
    ):
        return "no impact"

    # 2) RX OVERLOAD (rx_d > +5%)
    if rx_d > overload_thresh:
        if rx_a < overload_thresh:
            return "rx overloaded with recovery"
        else:
            return "rx overloaded no recovery"

    # 3) RX DEGRADATION (rx_d < −5%)
    if rx_d < -overload_thresh:
        if rx_a > -overload_thresh:
            return "rx degradation with recovery"
        else:
            return "rx degradation no recovery"

    # 4) LATE-ONLY CASES (no overload/degradation)
    #    For each late metric:
    #      - if during > 1Q → late event
    #      - then classify by after < median (recovery) or ≥ median (no recovery)
    for m in late_metrics:
        dcol = f"delta_pct_during_{m}"
        acol = f"delta_pct_after_{m}"
        if dcol in stats and acol in stats:
            if row[dcol] > stats[dcol]["q1"]:
                # this metric saw a late-spike:
                if row[acol] < stats[acol]["median"]:
                    return "late with recovery"
                else:
                    return "late with no recovery"

    return "other"

# ========= processing ru files =============
def process_ru():

    # Load CSV
    df = pd.read_csv("ru_summary.csv")
    
    # Clean 'file' column
    df['file'] = df['file'].str.replace(r'^ru_', '', regex=True)
    df['file'] = df['file'].str.replace(r'\.csv$', '', regex=True)

    # Drop rows with NaNs
    nan_summary = df.isna().sum(axis=1)
    files_with_nans = df.loc[nan_summary > 0, 'file'].tolist()
    if files_with_nans:
        with open("crash_summary.txt", "w") as f:
            for filename in files_with_nans:
                f.write(f"{filename}\n")
        print(f"\n{len(files_with_nans)} files had NaN values. Names written to crash_summary.txt")
        df = df[~df['file'].isin(files_with_nans)]

    # === Percent Calculation ===
    rx_metrics = ["RX_LATE", "RX_LATE_C", "RX_LATE_C_U"]
    rx_baseline = "before_RX_TOTAL"
    for metric in rx_metrics:
        for phase in ["before", "during", "after"]:
            source_col = f"{phase}_{metric}"
            pct_col = f"pct_{phase}_{metric}"
            if source_col in df.columns and rx_baseline in df.columns:
                df[pct_col] = 100 * df[source_col] / df[rx_baseline]

    # TX_TOTAL: percent based on before_TX_TOTAL
    tx_baseline = "before_TX_TOTAL"
    for phase in ["before", "during", "after"]:
        col = f"{phase}_TX_TOTAL"
        pct_col = f"pct_{phase}_TX_TOTAL"
        if col in df.columns and tx_baseline in df.columns:
            df[pct_col] = 100 * df[col] / df[tx_baseline]

    # RX_TOTAL: percent based on itself
    for phase in ["before", "during", "after"]:
        col = f"{phase}_RX_TOTAL"
        pct_col = f"pct_{phase}_RX_TOTAL"
        if col in df.columns and rx_baseline in df.columns:
            df[pct_col] = 100 * df[col] / df[rx_baseline]

    # === Delta Percent Calculation ===
    delta_metrics = rx_metrics + ["TX_TOTAL", "RX_TOTAL"]
    for metric in delta_metrics:
        for phase in ["during", "after"]:
            pct_col = f"pct_{phase}_{metric}"
            pct_before = f"pct_before_{metric}"
            delta_col = f"delta_pct_{phase}_{metric}"
            if pct_before in df.columns and pct_col in df.columns:
                df[delta_col] = df[pct_col] - df[pct_before]


    # compute thresholds
    stats = compute_delta_stats(df)
    display_delta_thresholds(stats)

    # apply classification:
    def classify_row(r):
        return classify(r, stats)


    df["attack_outcome"] = df.apply(classify_row, axis=1)

    # === Classification Placeholder ===
    df = df.replace([np.inf, -np.inf], np.nan).fillna(0)
    # --- Part 3: Map attack_outcome to outcome_rank ---
    
    rank_map = {
        "rx overloaded no recovery":       1,
        "rx overloaded with recovery":     2,
        "rx degradation no recovery":      3,
        "rx degradation with recovery":    4,
        "late with no recovery":           5,
        "late with recovery":              6,
        "no impact":                       7,
        "other":                          99
    }

    df["outcome_rank"] = (
        df["attack_outcome"]
        .map(rank_map)            # map strings → ints
        .fillna(99)               # anything missing → 99
        .astype(int)              # ensure integer dtype
    )


    # Save final
    df.to_csv("ru_summary.csv", index=False)
    print("Final summary with percentage and delta columns saved to ru_summary.csv")
    return df


# ========= print ru results in terminal ===============
def display_ru(filter_label=None):
    import pandas as pd

    df = pd.read_csv("ru_summary.csv")

    ordered_metrics = [
        "RX_TOTAL", "RX_LATE", "RX_LATE_C", "RX_LATE_C_U", "TX_TOTAL"
    ]

    if filter_label:
        df = df[df["attack_outcome"].str.contains(filter_label, case=False, na=False)]
        if df.empty:
            print(f"No entries found for label: {filter_label}")
            return

    for _, row in df.iterrows():
        rank  = row["outcome_rank"]
        label = row["attack_outcome"]

        print(f"\n{row['file']} — Rank: {rank} | Label: {label}\n")
        print(f"{'Metric':<20} | {'Before':>10} | {'During':>10} | {'After':>10} | "
              f"{'%Before':>10} | {'%During':>10} | {'%After':>10} | "
              f"{'Δ%During':>10} | {'Δ%After':>10}")
        print("-" * 110)

        for metric in ordered_metrics:
            b_val = row.get(f"before_{metric}", float('nan'))
            d_val = row.get(f"during_{metric}", float('nan'))
            a_val = row.get(f"after_{metric}", float('nan'))

            pct_b = row.get(f"pct_before_{metric}", float('nan'))
            pct_d = row.get(f"pct_during_{metric}", float('nan'))
            pct_a = row.get(f"pct_after_{metric}", float('nan'))

            delta_d = row.get(f"delta_pct_during_{metric}", float('nan'))
            delta_a = row.get(f"delta_pct_after_{metric}", float('nan'))

            print(f"{metric:<20} | {b_val:>10.2f} | {d_val:>10.2f} | {a_val:>10.2f} | "
                  f"{pct_b:>9.2f}% | {pct_d:>9.2f}% | {pct_a:>9.2f}% | "
                  f"{delta_d:>9.2f}% | {delta_a:>9.2f}%")



# ==== displaying labels and ranks ========================
def display_labels():

    df = pd.read_csv("ru_summary.csv")

    if not {"file", "attack_outcome", "outcome_rank"}.issubset(df.columns):
        print("Required columns not found in ru_summary.csv.")
        return

    df_sorted = df.sort_values(by="file")

    print(f"\n{'File':<40} | {'Rank':<5} | {'Outcome Label'}")
    print("-" * 65)
    for _, row in df_sorted.iterrows():
        print(f"{row['file']:<40} | {int(row['outcome_rank']):<5} | {row['attack_outcome']}")

# ========= gNB CSV Processing =========================
def process_gnb(base_dir="gnb_csv", output_file="gnb_summary.csv"):
    # 1) find all csv files under base_dir, including subfolders
    pattern = os.path.join(base_dir, "**", "*.csv")
    all_files = glob.glob(pattern, recursive=True)

    df_list = []
    for file_path in all_files:
        df = pd.read_csv(file_path)

        # drop first 5 and last 5 rows
        if len(df) <= 10:
            continue
        df = df.iloc[5:-5].copy()

        # inject filename column
        filename = os.path.basename(file_path)
        df.insert(0, "filename", filename)

        df_list.append(df)

    if not df_list:
        print("No data frames to combine (all files too short?).")
        return

    # concatenate
    combined = pd.concat(df_list, ignore_index=True)
    combined.to_csv(output_file, index=False)
    print(f"Saved combined summary: {output_file}")

    # --- Now validate brate columns ---
    # DL plane should be "390M"
    bad_dl = combined.loc[combined["brate"] != "390M", "filename"].unique().tolist()
    # UL plane should be "100M"
    bad_ul = combined.loc[combined["brate.1"] != "100M", "filename"].unique().tolist()

    if not bad_dl and not bad_ul:
        print("No change in brate values in either plane")
    else:
        if bad_dl:
            print("Change in brate values in DL plane for file(s):")
            for fn in bad_dl:
                print("  -", fn)
        if bad_ul:
            print("Change in brate values in UL plane for file(s):")
            for fn in bad_ul:
                print("  -", fn)

# === Run Batch ===
if __name__ == "__main__":

    base_root = os.environ.get("RESULTS_DIR", "attack_results")
    latest = find_latest_run(base_root)
    if not latest:
        print(f"No run_* folder found under {base_root}. Nothing to parse.")
        raise SystemExit(1)

    print(f"Parsing latest run folder: {latest}")
    parse_batch(latest)
    print("ru_emulator logs saved in ru_csv")
    print("gNB logs saved in gnb_csv")

    process_gnb()

    get_avg_ru()
    to_csv()
    df = process_ru()

    display_ru("")
    display_labels()
