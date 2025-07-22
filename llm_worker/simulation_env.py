# simulation_environment.py (Updated for Robustness and Clarity)

# --- Define Target Parameters for Scoring ---
# These are the "ideal" values we want the LLM to generate.
TARGET_FREQ = 1.842e9
TARGET_BW = 80e6
TARGET_GAIN = 70.0
TARGET_AMPLITUDE = 0.7
TARGET_AMPLITUDE_WIDTH = 0.05
TARGET_SAMPLING_FREQ = 40e6
TARGET_NUM_SAMPLES = 20000
EXPECTED_DEVICE = "type=b200"

def mock_run_simulation_and_get_reward(config: dict) -> float:
    """
    Calculates a score for a given configuration dictionary. This function is
    written defensively to handle malformed or nonsensical input from the LLM.
    """
    # --- BLOCK 1: INITIAL VALIDATION AND PARSING ---
    
    # Handle cases where the parser failed to produce a dictionary at all.
    if not isinstance(config, dict):
        print("[SIM] FATAL ERROR: Input is not a valid dictionary. Reward: -1.0")
        return -1.0
        
    try:
        # Safely extract and cast all expected parameters.
        # Using .get() with a default of 0 prevents KeyErrors if a key is missing.
        center_freq = float(config.get("center_frequency", 0))
        bandwidth = float(config.get("bandwidth", 0))
        tx_gain = float(config.get("tx_gain", 0))
        amplitude = float(config.get("amplitude", 0))
        amplitude_width = float(config.get("amplitude_width", 0))
        sampling_freq = float(config.get("sampling_freq", 0))
        num_samples = int(config.get("num_samples", 0))
        device_args = config.get("device_args", "")

    # This 'except' block catches errors if the LLM provides a non-numeric value
    # (e.g., "high" instead of 60), leading to a TypeError or ValueError.
    except (TypeError, ValueError) as e:
        print(f"[SIM] FATAL ERROR: Type conversion failed ({e}). Reward: -1.0")
        return -1.0

    # --- BLOCK 2: LOGICAL VALIDATION ---
    # Check for values that are syntactically correct but don't make sense.
    validation_errors = []
    if device_args != EXPECTED_DEVICE:
        validation_errors.append(f"device_args was '{device_args}', expected '{EXPECTED_DEVICE}'")
    if bandwidth <= 0:
        validation_errors.append("bandwidth must be a positive number.")
    if not (0 <= amplitude <= 1):
        validation_errors.append("amplitude must be between 0 and 1.")

    if validation_errors:
        print(f"[SIM] LOGICAL ERROR: The following issues were found:")
        for error in validation_errors:
            print(f"  - {error}")
        print("  Reward: -0.5")
        return -0.5

    # --- BLOCK 3: SCORE CALCULATION ---
    
    # Each score component is calculated as 1.0 minus a normalized error.
    # The max(0, ...) ensures scores don't become negative from large errors.
    freq_score = max(0.0, 1.0 - (abs(center_freq - TARGET_FREQ) / 200e6))
    bw_score = max(0.0, 1.0 - (abs(bandwidth - TARGET_BW) / (TARGET_BW * 2)))
    gain_score = max(0.0, 1.0 - (abs(tx_gain - TARGET_GAIN) / 50.0))
    amplitude_score = max(0.0, 1.0 - (abs(amplitude - TARGET_AMPLITUDE) / 1.0))
    amp_width_score = max(0.0, 1.0 - (abs(amplitude_width - TARGET_AMPLITUDE_WIDTH) / 0.2))
    sampling_freq_score = max(0.0, 1.0 - (abs(sampling_freq - TARGET_SAMPLING_FREQ) / (TARGET_SAMPLING_FREQ * 2)))
    num_samples_score = max(0.0, 1.0 - (abs(num_samples - TARGET_NUM_SAMPLES) / (TARGET_NUM_SAMPLES * 2)))

    # The final reward is a weighted sum of the component scores.
    final_reward = (freq_score * 0.30) + (bw_score * 0.15) + (gain_score * 0.10) + \
                   (amplitude_score * 0.10) + (amp_width_score * 0.05) + \
                   (sampling_freq_score * 0.15) + (num_samples_score * 0.15)
    

    if final_reward > 0.98: 
        final_reward = 1.0

    # --- BLOCK 4: DEBUGGING AND RETURN ---
    print(f"[SIM] DEBUG: Scores -> Freq:{freq_score:.2f}, BW:{bw_score:.2f}, Gain:{gain_score:.2f}, Amp:{amplitude_score:.2f}")
    print(f"[SIM] RESULT: Final reward is {final_reward:.4f}")
    
    return final_reward