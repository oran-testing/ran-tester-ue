# Knowledge Base for RT-UE Configuration

This document contains the rules, constraints, and default values for generating a valid configuration for the srsRAN RT-UE component.

### RF Parameters

- **Gain Settings**: The RT-UE transmit gain (`rf_tx_gain`) should be set within an optimal range of 40-60 dB. The receive gain (`rf_rx_gain`) is typically set between 30-50 dB.
- **Sample Rate (`rf_srate`)**: The sample rate must be a standard value compatible with 5G NR channel bandwidths. Valid options include 15.36e6 (for 10MHz), 23.04e6 (for 20MHz), and 30.72e6 (for 20MHz). A common default is 23.04e6.
- **Hardware Device**: The `rf_device_name` is typically 'uhd' for USRP radios. The corresponding `rf_device_args` for a standard setup is 'clock=internal'.

### 5G NR Channel Parameters

- **Physical Resource Blocks (PRBs)**: The number of PRBs is directly tied to the channel bandwidth. For a 20MHz channel bandwidth (which corresponds to a sample rate of 23.04e6), the `rat_nr_nof_prb` and `rat_nr_max_nof_prb` must both be set to 106.
- **E-UTRA (4G LTE)**: In a 5G-only test, E-UTRA is typically disabled by setting `rat_eutra_nof_carriers` to 0. A default `dl_earfcn` like 2850 (Band 7) can be used as a placeholder.

### Fixed Default Configurations

- **USIM Parameters**: For a test environment, the USIM configuration uses fixed, standard values to ensure compatibility. The mode must be 'soft' and the algorithm 'milenage'. The `usim_opc`, `usim_k`, `usim_imsi`, and `usim_imei` keys have specific, constant values that should always be used.
- **Network and Logging**: The GUI (`gui_enable`) must be disabled (`false`). The gateway (`gw`) and InfluxDB metrics (`general`) sections use predefined constant values for IP addresses, tokens, and filenames to integrate with the test environment.
