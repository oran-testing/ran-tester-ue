# validation_tester.py

import sys
from validator import LLMResponseValidator

# ==============================================================================

# ==============================================================================

TEST_CASES = [
    {
        "name": "Success: Good Jammer Response (Full)",
        "input": """
            id: jammer_gps_001
            ### YAML Output:
            center_frequency: 1.57542e9
            bandwidth: 10e6
            sampling_freq: 20e6
            tx_gain: 60
            num_samples: 40000
            device_args: "type=b200"
            amplitude: 0.9
            amplitude_width: 0.1
            initial_phase: 0
            output_iq_file: "output.fc32"
            write_iq: false
        """,
        "expected_success": True,
        "expected_errors_contain": []
    },
    {
        "name": "Success: Good Sniffer Response (Full)",
        "input": """
            id: sniffer_5g_001
            ### TOML Output:
            [sniffer]
            file_path = "/var/log/captures/5g.iq"
            frequency = 1.8e9
            sample_rate = 20e6
            nid_1 = 101
            ssb_numerology = 3
            
            [[pdcch]]
            coreset_id = 1
            num_prbs = 50
            dci_sizes_list = [41, 42]
        """,
        "expected_success": True,
        "expected_errors_contain": []
    },

    # --- FAILED VALIDATION RULES ---
    {
        "name": "Failure: Jammer sampling_freq < bandwidth",
        "input": """
            id: jammer_bad_001
            ### YAML Output:
            center_frequency: 1.5e9; bandwidth: 20e6; sampling_freq: 10e6; tx_gain: 50; num_samples: 1; device_args: 'a'; amplitude: 0.5; amplitude_width: 0.1; initial_phase: 0; output_iq_file: 'a'; write_iq: false
        """,
        "expected_success": False,
        "expected_errors_contain": ["sampling_freq", "must be >="]
    },
    {
        "name": "Failure: Jammer missing required key (device_args)",
        "input": """
            id: jammer_bad_002
            ### YAML Output:
            center_frequency: 1.5e9; bandwidth: 20e6; sampling_freq: 20e6; tx_gain: 60; num_samples: 40000; amplitude: 0.9; amplitude_width: 0.1; initial_phase: 0; output_iq_file: "output.fc32"; write_iq: false
        """,
        "expected_success": False,
        "expected_errors_contain": ["missing required field", "device_args"]
    },
    {
        "name": "Failure: Sniffer missing [[pdcch]] section",
        "input": """
            id: sniffer_bad_001
            ### TOML Output:
            [sniffer]
            file_path = "a"; sample_rate=1; frequency=1; nid_1=1; ssb_numerology=1
        """,
        "expected_success": False,
        "expected_errors_contain": ["must have at least one", "[[pdcch]]"]
    },
    {
        "name": "Failure: Sniffer pdcch is an empty list",
        "input": """
            id: sniffer_bad_002
            ### TOML Output:
            [sniffer]
            file_path = "a"; sample_rate=1; frequency=1; nid_1=1; ssb_numerology=1
            pdcch = []
        """,
        "expected_success": False,
        "expected_errors_contain": ["must have at least one", "[[pdcch]]"]
    },
    {
        "name": "Failure: Jammer amplitude out of range",
        "input": """
            id: jammer_bad_amplitude_001
            ### YAML Output:
            center_frequency: 1.5e9; bandwidth: 10e6; sampling_freq: 20e6; tx_gain: 60; num_samples: 40000; device_args: "type=b200"; amplitude: 1.1; amplitude_width: 0.1; initial_phase: 0; output_iq_file: "output.fc32"; write_iq: false
        """,
        "expected_success": False,
        "expected_errors_contain": ["amplitude", "must be between 0.0 and 1.0"]
    },
    {
        "name": "Failure: Sniffer ssb_numerology out of range",
        "input": """
            id: sniffer_bad_numerology_001
            ### TOML Output:
            [sniffer]
            file_path = "a"; sample_rate=1; frequency=1; nid_1=1; ssb_numerology=5
            [[pdcch]]
            coreset_id = 1; num_prbs = 50; dci_sizes_list = [41, 42]
        """,
        "expected_success": False,
        "expected_errors_contain": ["ssb_numerology", "must be between 0 and 4"]
    },
    {
        "name": "Failure: Sniffer PDCCH item missing a key",
        "input": """
            id: sniffer_bad_pdcch_001
            ### TOML Output:
            [sniffer]
            file_path = "a"; sample_rate=1; frequency=1; nid_1=1; ssb_numerology=1
            [[pdcch]]
            coreset_id = 1; dci_sizes_list = [41, 42]
        """,
        "expected_success": False,
        "expected_errors_contain": ["pdcch", "item #0", "missing required field", "num_prbs"]
    },

    # --- FAILED PARSING & EXTRACTION ---
    {
        "name": "Failure: No config marker found",
        "input": "id: some_id\nHere is some text but no config block.",
        "expected_success": False,
        "expected_errors_contain": ["Could not find or parse", "configuration block"]
    },
    {
        "name": "Failure: Malformed YAML content",
        "input": """
            id: broken_yaml_001
            ### YAML Output:
            key: value
              bad_indent: problem
        """,
        "expected_success": False,
        "expected_errors_contain": ["Failed to parse YAML"]
    },
    {
        "name": "Failure: No ID found in the text",
        "input": """
            ### YAML Output:
            center_frequency: 1.5e9
            bandwidth: 10e6
            sampling_freq: 10e6
            tx_gain: 50
        """,
        "expected_success": False,
        "expected_errors_contain": ["Could not find a process 'id'"]
    },
    {
        "name": "Failure: Could not infer type from keys",
        "input": """
            id: unknown_type_001
            ### YAML Output:
            some_key: 123
            another_key: "abc"
        """,
        "expected_success": False,
        "expected_errors_contain": ["Could not determine process type"]
    },
    {
        "name": "Failure: Ambiguous type with both jammer and sniffer keys",
        "input": """
            id: ambiguous_001
            ### YAML Output:
            center_frequency: 1.5e9; bandwidth: 10e6; tx_gain: 60; num_samples: 1; device_args: 'a'; amplitude: 0.5; amplitude_width: 0.1; initial_phase: 0; output_iq_file: 'a'; write_iq: false; sampling_freq: 20e6
            sniffer:
              frequency: 1.8e9
        """,
        "expected_success": False,
        "expected_errors_contain": ["Ambiguous configuration"]
    },
    {
        "name": "Failure: Jammer with wrong data type for tx_gain (string)",
        "input": """
            id: jammer_string_gain_001
            ### YAML Output:
            center_frequency: 1.5e9; bandwidth: 10e6; sampling_freq: 20e6; tx_gain: "60"; num_samples: 1; device_args: 'a'; amplitude: 0.5; amplitude_width: 0.1; initial_phase: 0; output_iq_file: 'a'; write_iq: false
        """,
        "expected_success": False,
        "expected_errors_contain": ["tx_gain", "wrong type"]
    },

    # --- EDGE CASE TESTS ---
    {
        "name": "Edge Case: Empty config block",
        "input": """
            id: empty_config_001
            ### YAML Output:
        """,
        "expected_success": False,
        "expected_errors_contain": ["Could not find or parse"]
    },
    {
        "name": "Edge Case: Jammer with duplicate key (tx_gain)",
        "input": """
            id: jammer_duplicate_key_001
            ### YAML Output:
            center_frequency: 1.5e9; bandwidth: 10e6; tx_gain: 50; sampling_freq: 20e6; tx_gain: 60; num_samples: 1; device_args: 'a'; amplitude: 0.5; amplitude_width: 0.1; initial_phase: 0; output_iq_file: 'a'; write_iq: false
        """,
        "expected_success": False,
        "expected_errors_contain": ["Duplicate key 'tx_gain' found"]
    },
    {
        "name": "Edge Case: Boundary success (sampling_freq == bandwidth)",
        "input": """
            id: jammer_boundary_001
            ### YAML Output:
            center_frequency: 1.57542e9; bandwidth: 20e6; sampling_freq: 20e6; tx_gain: 60; num_samples: 40000; device_args: "type=b200"; amplitude: 0.9; amplitude_width: 0.1; initial_phase: 0; output_iq_file: "output.fc32"; write_iq: false
        """,
        "expected_success": True,
        "expected_errors_contain": []
    },
    {
        "name": "Edge Case: Sniffer list with wrong data type",
        "input": """
            id: sniffer_bad_list_001
            ### TOML Output:
            [sniffer]
            file_path = "a"; sample_rate=1; frequency=1; nid_1=1; ssb_numerology=1
            [[pdcch]]
            coreset_id = 1; num_prbs = 50; dci_sizes_list = [41, "42-is-a-string", 55]
        """,
        "expected_success": False,
        "expected_errors_contain": ["dci_sizes_list", "must contain only integers"]
    },
    {
        "name": "Edge Case: Jammer with zero num_samples",
        "input": """
            id: jammer_zero_samples_001
            ### YAML Output:
            center_frequency: 1.5e9; bandwidth: 10e6; sampling_freq: 20e6; tx_gain: 60; num_samples: 0; device_args: "type=b200"; amplitude: 0.9; amplitude_width: 0.1; initial_phase: 0; output_iq_file: "output.fc32"; write_iq: false
        """,
        "expected_success": False,
        "expected_errors_contain": ["num_samples", "must be a positive integer"]
    },
    {
        "name": "Edge Case: Completely empty input string",
        "input": "",
        "expected_success": False,
        "expected_errors_contain": ["Empty response received"]
    }
]

def run_tests():
    """Iterates through test cases and reports results."""
    passed_count = 0
    failed_count = 0
    
    # In some test cases, I've used semicolons to keep lines short. Let's replace them with newlines.
    for test in TEST_CASES:
        test['input'] = test['input'].replace(';', '\n')

    for i, test in enumerate(TEST_CASES):
        print(f"--- Running Test #{i+1}: {test['name']} ---")
        
        validator = LLMResponseValidator(test['input'])
        result = validator.process()
        
        has_errors = bool(result.get('errors'))
        test_passed = (not has_errors) == test['expected_success']
        
        # Additional check for failure cases: ensure the error message is as expected
        if not test_passed and not test['expected_success']:
            error_string = " ".join(result.get('errors', [])).lower()
            all_substrings_found = all(sub.lower() in error_string for sub in test['expected_errors_contain'])
            if all_substrings_found:
                test_passed = True
            else:
                 print(f"❌ FAILED: Expected error to contain {test['expected_errors_contain']} but got '{result.get('errors', [])}'")
                 failed_count += 1
                 continue

        if test_passed:
            print("✅ PASSED")
            passed_count += 1
        else:
            print(f"❌ FAILED: Expected success={test['expected_success']} but got success={not has_errors}")
            if has_errors:
                print("   Reported Errors:", result['errors'])
            failed_count += 1
    
    print("\n" + "="*40)
    print(f"Test Summary: {passed_count} PASSED, {failed_count} FAILED")
    print("="*40)

    if failed_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
