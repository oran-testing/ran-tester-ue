# Knowledge Base for RF Jammer Configuration

This document provides rules for generating valid configurations for a wideband RF jammer.

### Signal Generation Principles

- **Nyquist Theorem for Generation**: The `sampling_freq` must be greater than or equal to the specified jamming `bandwidth`. It is recommended to have the sampling frequency be at least 1.25x the bandwidth to allow for filter transition bands.
- **Bandwidth and Center Frequency**: The `bandwidth` determines the frequency range that will be affected by the jammer. This range is centered around the `center_frequency`.
- **Amplitude**: The `amplitude` determines the power of the generated jamming signal. It's a normalized value, typically between 0.0 and 1.0. A higher value like 0.8 or 0.9 is needed for effective jamming.

### Hardware-Specific Parameters

- **Transmit Gain (`tx_gain`)**: The jammer's transmit gain should be set to a high value to be effective, typically between 60 and 90 dB. However, this must not exceed the SDR hardware's maximum safe output power.
- **Device Arguments for USRP**: When using a common SDR like a USRP B200-series, the `device_args` string must specify the device type, for example: `type=b200`. It may also be necessary to set the `master_clock_rate` to match the desired sampling frequency, e.g., `master_clock_rate=50e6`.

### Logical Configuration

- **File I/O**: The boolean flags `write_iq` and `write_csv` control whether the generated jamming waveform is saved to disk. It is common to set these to `false` during live jamming operations to maximize performance.
