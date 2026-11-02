OFH DoS attacker sweep
Total runs: 22
  Baselines: 2 (one per injection point)
  Sweep: 20
Topspeed values: [0, 1]
Pacing rates (Mbps): [100, 500, 1000, 5000, 10000]
Injection points: ['DU', 'RU']
Output: /home/charles/ran-tester-ue/output/ofh/sweep_0
Metrics: /home/charles/ran-tester-ue/output/ofh/sweep_0/metrics.csv

Transport layer:
  eCPRI frame loss %
  Switch buffer queue drops

Synchronization layer:
  IEEE 1588 PTP phase error (ns)
  Slave clock out-of-lock duration (s)

Radio / service layer:
  Baseband processing deadline miss rate (ru.log, gnb_emu.log)
  Over-the-air frame drop rate

Note: all metrics require instrumented logs (OFH attacker results,
ru.log, gnb_emu.log). Values recorded as None when unavailable.

Network setup:
  host network mode (network_mode: host)
  lo device for ru_emulator and attacker
