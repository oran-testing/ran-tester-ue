# Knowledge Base for RF Jammer Configuration

This document contains the physical, logical, and hardware rules for generating a valid wideband RF jammer configuration.

### Signal Generation Principles

- **Nyquist Constraint**: `sampling_freq` ≥ `bandwidth` (minimum), recommended ≥ 1.25× `bandwidth`.
- **Center Frequency & Bandwidth**:
  - `center_frequency` must be within supported band of the hardware.
  - `bandwidth` defines the jamming range around `center_frequency`.
- **Amplitude**: Normalized 0.0–1.0; typical for effective jamming: 0.8–0.9.

### Hardware-Specific Parameters

- **Transmit Gain (`tx_gain`)**: Set between 60–90 dB, but never exceed hardware safe limit.
- **Device Arguments (USRP)**:
  - `device_args` must include device type (e.g., `type=b200`)
  - May include `master_clock_rate` to match `sampling_freq`

### Logical Configuration

- **File I/O Flags**: `write_iq` and `write_csv` booleans control waveform saving.  
  For live jamming, set both to `false` to maximize performance.

### Output Requirements

- Use snake_case for all keys.
- All booleans lowercase `true`/`false`.
- All frequency values in scientific notation.
- Ensure `sampling_freq` is realistic for the SDR model (e.g., ≤ 61.44e6 for B210).
