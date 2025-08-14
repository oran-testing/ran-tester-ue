# Knowledge Base for RT-UE Configuration

This document contains the rules, constraints, and default values for generating a valid configuration for the srsRAN RT-UE component.

### RF Parameters

- **Gain Settings**: `rf_tx_gain` = 40–60 dB; `rf_rx_gain` = 30–50 dB.
- **Sample Rate (`rf_srate`)**: Must be one of:
  - 1.536e7 (10 MHz)
  - 2.304e7 (20 MHz)
  - 3.072e7 (20 MHz, 30 kHz SCS)  
  Default for 20 MHz: 2.304e7.
- **Hardware Device**: If `rf_device_name` = `"uhd"`, `rf_device_args` must:
  - Include `type=<usrp_model>` (e.g., `type=b200`)
  - Optionally specify `clock=internal|external`
  - Optionally specify `master_clock_rate` if needed.

### 5G NR Channel Parameters

- **PRB Count**: For 20 MHz (`rf_srate`=2.304e7), set `rat_nr_nof_prb` = `rat_nr_max_nof_prb` = 106.
- **E-UTRA (LTE)**: In 5G-only mode, set `rat_eutra_nof_carriers` = 0.  
  `rat_eutra_dl_earfcn` can be a placeholder (e.g., 2850).

### Fixed Default Configurations

- **USIM**: `usim_mode` = `"soft"`, `usim_algo` = `"milenage"`.  
  Test constants may be used for `usim_opc`, `usim_k`, `usim_imsi`, `usim_imei`.
- **Network & Logging**:
  - `gui_enable` = `false`
  - `general_metrics_influxdb_token` must be `"<set_in_env>"` (do not hardcode secrets)
  - `gw` and `general` fields use predefined constants for IP/ports

### Output Requirements

- Use snake_case for all keys.
- All booleans must be lowercase `true`/`false`.
- Frequencies in scientific notation where applicable.
