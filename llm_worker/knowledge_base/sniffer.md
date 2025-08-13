# Knowledge Base for 5G Sniffer Configuration

This document contains the physical and logical rules for configuring a 5G NR sniffer.

### Fundamental RF & Sampling Rules

- **Nyquist-Shannon Theorem**: The `sample_rate` must be at least twice the bandwidth of the signal being observed. For sniffing a 20MHz 5G channel, the minimum sample rate is 40e6, but a standard rate like 61.44e6 is often used.
- **Hardware Constraints**: Common SDR hardware like a USRP B210 has a maximum sample rate of 61.44e6 (61.44 Msps). A value like 2.5e9 is physically impossible for such devices and should be rejected.
- **5G Frequency Bands**: The sniffer's center `frequency` must correspond to a valid cellular band. 5G NR Frequency Range 1 (FR1) is from 410 MHz to 7.125 GHz. Frequency Range 2 (FR2) is mmWave, from 24.25 GHz to 52.6 GHz. A frequency of 9.51 GHz is invalid as it falls outside of these ranges.

### 5G NR Specific Rules

- **CORESET Duration**: The `pdcch_coreset_duration` specifies the number of OFDM symbols for the Control Resource Set. This value MUST be an integer of 1, 2, or 3. Any other value is invalid.
- **Numerology**: The `ssb_numerology` and `pdcch_numerology` are typically related. Common values are 0 (15kHz SCS), 1 (30kHz SCS), or 2 (60kHz SCS). They dictate the subcarrier spacing and symbol duration.
- **PDCCH Search Space**: The `pdcch_num_prbs` defines the bandwidth of the search space for the control channel. This should be a reasonable integer, typically between 10 and the maximum number of PRBs for the channel.

### Logical Consistency Rules

- **Range Parameters**: For any parameter that defines a range, such as `pdcch_scrambling_id` or `pdcch_rnti`, the `_start` value must always be less than or equal to the `_end` value.
