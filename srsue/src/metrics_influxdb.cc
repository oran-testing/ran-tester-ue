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

#include "srsue/hdr/metrics_influxdb.h"
#include "srsue/hdr/influxdb.hpp"

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
                                   std::string influxdb_bucket) :
  influx_server_info(influxdb_url, influxdb_port, influxdb_org, influxdb_token, influxdb_bucket)
{
  metrics_init_time_nsec = get_epoch_time_nsec();
}

metrics_influxdb::~metrics_influxdb()
{
  stop();
}

void metrics_influxdb::stop() {}

// metrics carrier:
// phy and phy_nr
// stack -> mac metrics_t
void metrics_influxdb::set_metrics(const ue_metrics_t& metrics, const uint32_t period_usec)
{
  metrics_init_time_nsec += period_usec * 1000;

  if (!post_metics_carrier_independent(metrics, (uint64_t)metrics_init_time_nsec)){
    cout << "Failed to post metrics carrier independent\n";
    return;
  }

}

bool metrics_influxdb::post_metics_carrier_independent(
    const ue_metrics_t& metrics,
    const uint64_t current_time_nsec){

  std::string response_text;
  influxdb_cpp::builder()
                   .meas("srsue_info")
                   .tag("rnti", "test")
                   .tag("testbed", "default")

                   .field("rf_o", (long long)metrics.rf.rf_o)
                   .field("rf_u", (long long)metrics.rf.rf_u)
                   .field("rf_l", (long long)metrics.rf.rf_l)

                   .field("proc_rmem", (long long)metrics.sys.process_realmem)
                   .field("proc_rmem_kB", (long long)metrics.sys.process_realmem_kB)
                   .field("proc_vmem_kB", (long long)metrics.sys.process_virtualmem_kB)
                   .field("sys_mem", (long long)metrics.sys.system_mem)
                   .field("system_load", (long long)metrics.sys.process_cpu_usage)

                   .timestamp(current_time_nsec)
                   .post_http(influx_server_info, &response_text);
  if(response_text.length() > 0){
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
}
