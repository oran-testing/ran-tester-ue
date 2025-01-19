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
}

metrics_influxdb::~metrics_influxdb()
{
  stop();
}

void metrics_influxdb::stop() {}

void metrics_influxdb::set_metrics(const ue_metrics_t& metrics, const uint32_t period_usec)
{


  float dl_rate_sum = 0.0, ul_rate_sum = 0.0;
  for (size_t i = 0; i < metrics.stack.rrc.ues.size(); i++) {
    dl_rate_sum += metrics.stack.mac.ues[i].tx_brate / (metrics.stack.mac.ues[i].nof_tti * 1e-3);
    ul_rate_sum += metrics.stack.mac.ues[i].rx_brate / (metrics.stack.mac.ues[i].nof_tti * 1e-3);
  }

  const srsran::sys_metrics_t& m = metrics.sys;

  // Make POST request to influxdb with all metrics
  std::string response_text;
  influxdb_cpp::builder()
                   .meas("ue_info")
                   .tag("pci", "test")
                   .tag("rnti", "test")
                   .tag("testbed", "default")

                   .field("nof_ue", metrics.stack.rrc.ues.size())
                   .field("dl_brate", SRSRAN_MAX(0.0f, (float)dl_rate_sum))
                   .field("ul_brate", SRSRAN_MAX(0.0f, (float)ul_rate_sum))
                   .field("proc_rmem", m.process_realmem)
                   .field("proc_rmem_kB", m.process_realmem_kB)
                   .field("proc_vmem", m.process_virtualmem)
                   .field("proc_vmem_kB", m.process_virtualmem_kB)
                   .field("sys_mem", m.system_mem)
                   .field("system_load", m.process_cpu_usage)

                   .timestamp(get_timestamp())
                   .post_http(influx_server_info, &response_text);
  if(response_text.length > 0){
    cout << "Recieved error from influxdb: " << response_text << "\n";
  }
}

std::string metrics_influxdb::float_to_string(float f, int digits)
{
  std::ostringstream os;
  const int          precision = (f == 0.0) ? digits - 1 : digits - log10f(fabs(f)) - 2 * DBL_EPSILON;
  os << std::fixed << std::setprecision(precision) << f;
  return os.str();
}

unsigned long long metrics_influxdb::get_timestamp()
{
  struct timespec ts;
  clock_gettime(CLOCK_REALTIME, &ts);
  unsigned long long timestamp = (unsigned long long)ts.tv_sec * 1000000000 + ts.tv_nsec;
  return timestamp;
}

} // namespace srsue
