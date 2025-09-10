# Knowledge Base for RF Jammer Configuration

This document contains the physical, logical, and hardware rules for generating a valid wideband RF jammer configuration.

### Signal Generation Principles

- **Nyquist Constraint**: `sampling_freq` ≥ **2×** `bandwidth` (recommended ≥ **2.5×** `bandwidth`).
- **Center Frequency & Bandwidth**:
  - `center_frequency` must be within supported band of the hardware.
  - Must lie in **NR FR1 (410e6–7.125e9)** or **NR FR2 (24.25e9–52.6e9)**.
  - `bandwidth` defines the jamming range around `center_frequency`.
- **Amplitude**: Normalized 0.0–1.0; typical effective range **0.2–0.6** (avoid clipping).

### Hardware-Specific Parameters

- **Transmit Gain (`tx_gain`)**: Keep within device-safe range (e.g., **0–76 dB** typical; never exceed hardware limit).
- **Device Arguments (USRP)**:
  - `device_args` must include device type (e.g., `type=b200`)
  - May include `master_clock_rate` to match `sampling_freq`
  - **B200-family constraints**:
    - `center_frequency` ≤ **6e9** (FR2 not supported)
    - `sampling_freq` ≤ **61.44e6**
    - Practical analog front-end bandwidth ≤ **56e6**

### Device Capability Cheat Sheet (use these to choose sane ranges)

- **USRP B200/B210**
  - Tuning range: ~**70e6–6e9** (FR1 only)
  - Practical instantaneous bandwidth: **≤ 56e6**
  - Max complex `sampling_freq`: **≈ 61.44e6**
  - Typical `tx_gain`: **0–76 dB**
  - Use cases: FR1 bands such as **n78 (3.3–3.8 GHz)**, **n41 (~2.5–2.69 GHz)**, **n48/CBRS (3.55 GHz)**

- **USRP X310 (with UBX-160)**
  - Tuning range: ~**10e6–6e9** (FR1 only)
  - Instantaneous bandwidth: up to **160e6**
  - Max complex `sampling_freq`: **≤ 200e6** (per channel, host/I/O dependent)
  - Typical `tx_gain`: **0–31.5 dB** (daughterboard dependent)
  - Use when you need wider FR1 jamming than B200 allows (e.g., **100e6** BW)

- **USRP N310/N320/N321**
  - Tuning range: ~**10e6–6e9** (FR1 only)
  - Instantaneous bandwidth: **>100e6** (model/dboard dependent)
  - Max complex `sampling_freq`: **up to ~200e6** (I/O dependent)
  - Suited for **wide FR1** scenarios (e.g., multi-carrier jamming up to ~100e6 BW)

- **USRP X410**
  - Tuning range: ~**1eMHz–7.2e9** (FR1 only)
  - Instantaneous bandwidth: up to **~400e6**
  - Max complex `sampling_freq`: very high; host/I/O pipeline is the limiter
  - Choose for **very wide FR1** experiments; still **not FR2**

- **LimeSDR (USB/Mini)**
  - Tuning range: ~**100e3–3.8e9** (FR1 subset)
  - Instantaneous bandwidth: **≤ 20–30e6** typical (up to **~61.44e6** in best cases)
  - Max complex `sampling_freq`: **≈ 61.44e6**
  - Lighter-weight FR1 jamming (e.g., **5–20e6** BW)

- **ADALM-PLUTO (PlutoSDR)**
  - Tuning range: **325e6–3.8e9** (some extend to ~6e9 unofficially)
  - Instantaneous bandwidth: **≤ 20e6** typical (lab-dependent)
  - Max complex `sampling_freq`: **≈ 61.44e6** (practical lower)
  - Good for **narrow-to-moderate** FR1 jamming (e.g., **5–10e6** BW)

> **FR2 note**: None of the above low-cost SDRs directly support **FR2 (24.25e9–52.6e9)** without external upconverters. If `center_frequency` is in FR2, enforce a hardware profile that actually supports it or reject the config.

### Practical Parameter Ranges (pick based on device)

- **B200/B210 example (CBRS-like)**
  - `center_frequency`: **3.55e9**
  - `bandwidth`: **10e6–20e6** (max **≤ 56e6**)
  - `sampling_freq`: **30.72e6** or **61.44e6**
  - `tx_gain`: **30–55 dB**
  - `amplitude`: **0.2–0.5**

- **X310 (UBX-160) example (wide FR1)**
  - `center_frequency`: **3.5e9**
  - `bandwidth`: **40e6–120e6** (≤ **160e6**)
  - `sampling_freq`: **122.88e6–200e6**
  - `tx_gain`: **10–25 dB** (board dependent)
  - `amplitude`: **0.2–0.5**

- **LimeSDR example**
  - `center_frequency`: **2.6e9**
  - `bandwidth`: **5e6–20e6** (≤ **~30e6** practical)
  - `sampling_freq`: **10e6–30.72e6** (≤ **61.44e6**)
  - `tx_gain`: device-specific (start mid-range)
  - `amplitude`: **0.2–0.5**

### Logical Configuration

- **File I/O Flags**: `write_iq` and `write_csv` booleans control waveform saving.  
  For live jamming, set both to `false` to maximize performance.

### Output Requirements

- Use snake_case for all keys.
- All booleans lowercase `true`/`false`.
- All frequency values in scientific notation.
- Ensure `sampling_freq` and `bandwidth` stay within the device’s supported ranges above, and maintain `sampling_freq` ≥ **2×** `bandwidth` (prefer **2.5×**).

