/**
 * Copyright 2013-2023 Software Radio Systems Limited
 *
 * This file is part of srsRAN.
 *
 * srsRAN is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of
 * the License, or (at your option) any later version.
 *
 * srsRAN is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * A copy of the GNU Affero General Public License can be found in
 * the LICENSE file in the top-level directory of this distribution
 * and at http://www.gnu.org/licenses/.
 *
 */

#include "rtue/hdr/metrics_influxdb.h"
#include "rtue/hdr/influxdb.hpp"

#include <float.h>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <time.h>
#include <unistd.h>

using namespace std;

namespace srsue {

metrics_influxdb::metrics_influxdb(std::string influxdb_url,
                                   uint32_t    influxdb_port,
                                   std::string influxdb_org,
                                   std::string influxdb_token,
                                   std::string influxdb_bucket,
                                   std::string ue_data_identifier) :
  influx_server_info(influxdb_url, influxdb_port, influxdb_org, influxdb_token, influxdb_bucket),
  data_id(ue_data_identifier)
{
  init_success = influx_server_info.resp_ == 0;
}

metrics_influxdb::~metrics_influxdb()
{
  stop();
}

void metrics_influxdb::stop() {}

// NOTE: carrier metrics need a loop:
// phy and phy_nr
// stack -> mac metrics_t

// NOTE: RLC metrics need a loop
void metrics_influxdb::set_metrics(const ue_metrics_t& metrics, const uint32_t period_usec)
{
  if (!init_success)
    return;
  uint64_t current_time_nsec = (uint64_t)get_epoch_time_nsec();

  if (!post_singleton_metrics(metrics, current_time_nsec)) {
    cout << "Failed to post metrics carrier independent\n";
    return;
  }

  for (uint32_t r = 0; r < metrics.phy.nof_active_cc; r++) {
    post_carrier_metrics(
        metrics.rf, metrics.sys, metrics.phy, metrics.stack.mac, metrics.stack.rrc, r, r, current_time_nsec, "lte");
  }

  // Metrics for NR carrier
  for (uint32_t r = 0; r < metrics.phy_nr.nof_active_cc; r++) {
    post_carrier_metrics(metrics.rf,
                         metrics.sys,
                         metrics.phy_nr,
                         metrics.stack.mac_nr,
                         metrics.stack.rrc,
                         metrics.phy.nof_active_cc + r, // NR carrier offset
                         r,
                         current_time_nsec,
                         "nr");
  }
}

bool metrics_influxdb::post_singleton_metrics(const ue_metrics_t& metrics, const uint64_t current_time_nsec)
{
  // TODO: differentiate UEs somehow
  std::string response_text;
  influxdb_cpp::builder()
      .meas("rtue_singleton_metric")
      .tag("testbed", "default")
      .tag("rtue_data_id", data_id)

      .field("rf_o", (long long)metrics.rf.rf_o)
      .field("rf_u", (long long)metrics.rf.rf_u)
      .field("rf_l", (long long)metrics.rf.rf_l)

      .field("nof_active_cc", (int)SRSRAN_MAX(metrics.phy.nof_active_cc, metrics.phy_nr.nof_active_cc))

      .field("dl_tput_mbps", metrics.gw.dl_tput_mbps)
      .field("ul_tput_mbps", metrics.gw.ul_tput_mbps)

      .field("ul_dropped_sdus", (long)metrics.stack.ul_dropped_sdus)
      .field("nof_active_eps_bearer", (long)metrics.stack.nas.nof_active_eps_bearer)
      .field("emm_state", (int)metrics.stack.nas.state)

      .field("proc_rmem", (long long)metrics.sys.process_realmem)
      .field("proc_rmem_kB", (long long)metrics.sys.process_realmem_kB)
      .field("proc_vmem_kB", (long long)metrics.sys.process_virtualmem_kB)
      .field("sys_mem", (long long)metrics.sys.system_mem)
      .field("system_load", (long long)metrics.sys.process_cpu_usage)

      .timestamp(current_time_nsec)
      .post_http(influx_server_info, &response_text);
  if (response_text.length() > 0) {
    cout << "Recieved error from influxdb: " << response_text << "\n";
    return false;
  }
  return true;
}

bool metrics_influxdb::post_carrier_metrics(const srsran::rf_metrics_t&  rf,
                                            const srsran::sys_metrics_t& sys,
                                            const phy_metrics_t&         phy,
                                            const mac_metrics_t          mac[SRSRAN_MAX_CARRIERS],
                                            const rrc_metrics_t&         rrc,
                                            const uint32_t               cc,
                                            const uint32_t               r,
                                            const uint64_t               current_time_nsec,
                                            std::string                  carrier_type)
{
  // TODO: get metrics of neighboring cells

  std::string response_text;
  influxdb_cpp::builder()
      .meas("rtue_carrier_metric")
      .tag("testbed", "default")
      .tag("rtue_data_id", data_id)
      .tag("carrier_channel_index", std::to_string(cc))
      .tag("carrier_type", carrier_type)

      .field("dl_earfcn", (long long)phy.info[r].dl_earfcn)
      .field("pci", (int)phy.info[r].pci)

      .field("rsrp", phy.ch[r].rsrp)
      .field("rsrq", phy.ch[r].rsrq)
      .field("rssi", phy.ch[r].rssi)
      .field("ri", phy.ch[r].ri)
      .field("sync_err", phy.ch[r].sync_err)
      .field("pathloss", phy.ch[r].pathloss)
      .field("cfo", phy.sync[r].cfo)
      .field("sfo", (int)phy.sync[r].cfo)

      .field("ul_mcs", phy.ul[r].mcs)
      .field("ul_power", phy.ul[r].power)
      .field("dl_mcs", phy.dl[r].mcs)
      .field("dl_evm", phy.dl[r].evm)
      .field("sinr", std::isinf((float)phy.ch[r].sinr) ? 0.0f : (float)phy.ch[r].sinr)
      .field("fec_iters", phy.dl[r].fec_iters)
      .field("rx_brate", mac[r].rx_brate > 0 ? mac[r].rx_brate / mac[r].nof_tti * 1e-3 : 0)
      .field("tx_brate", mac[r].tx_brate > 0 ? mac[r].tx_brate / mac[r].nof_tti * 1e-3 : 0)

      .field("rx_pkts", mac[r].rx_pkts)
      .field("rx_errors", mac[r].rx_errors)
      .field("tx_pkts", mac[r].tx_pkts)
      .field("tx_errors", mac[r].tx_errors)

      .field("ta_us", phy.sync[r].ta_us)
      .field("distance_km", phy.sync[r].distance_km)
      .field("speed_kmph", phy.sync[r].speed_kmph)
      .field("ul_buffer", (float)mac[r].ul_buffer)

      .field("rrc_state", (int)rrc.state)

      .timestamp(current_time_nsec)
      .post_http(influx_server_info, &response_text);

  if (response_text.length() > 0) {
    cout << "Recieved error from influxdb: " << response_text << "\n";
    return false;
  }
  return true;
}

unsigned long long metrics_influxdb::get_epoch_time_nsec()
{
  struct timespec ts;
  clock_gettime(CLOCK_REALTIME, &ts);
  unsigned long long timestamp = (unsigned long long)ts.tv_sec * 1000000000 + ts.tv_nsec;
  return timestamp;
}
} // namespace srsue
