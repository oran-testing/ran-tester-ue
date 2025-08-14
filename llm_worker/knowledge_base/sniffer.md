# Knowledge Base for 5G Sniffer Configuration

This document contains the physical and logical rules for configuring a 5G NR sniffer.

### Fundamental RF & Sampling Rules

- **Nyquist-Shannon Theorem**: The `sample_rate` must be at least twice the bandwidth of the signal being observed.
- **Standard 5G Sample Rates**: For sniffing a 20 MHz channel, use ≥ 40e6; common defaults are 61.44e6 or 30.72e6.
- **Hardware Constraints**: USRP B210 maximum is 61.44e6. Any value above this must be rejected. Values in the gigasample range (e.g., 2.5e9) are physically impossible on such devices.
- **5G Frequency Bands**: `frequency` must be in:
  - FR1: 4.10e8–7.125e9 Hz
  - FR2: 2.425e10–5.26e10 Hz  
  Values outside these ranges (e.g., ~9.51 GHz) are invalid.

### 5G NR Specific Rules

- **CORESET Duration**: `pdcch_coreset_duration` must be 1, 2, or 3.
- **Numerology Consistency**: `ssb_numerology` and `pdcch_numerology` must be identical. Valid: 0 (15 kHz), 1 (30 kHz), 2 (60 kHz).
- **PDCCH Search Space**: `pdcch_num_prbs` must be ≥ 10 and ≤ max PRBs for the channel bandwidth.

### Logical Consistency Rules

- **Range Parameters**: For any `_start`/`_end` field, `_start` ≤ `_end` is mandatory.

### Output Requirements

- Use snake_case for all keys.
- All booleans must be lowercase `true`/`false`.
- All frequencies must be in scientific notation (e.g., `1.805e9`).
