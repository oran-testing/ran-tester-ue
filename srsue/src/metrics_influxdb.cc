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
  cout << "Initialized influxdb!\n";
}

metrics_influxdb::~metrics_influxdb()
{
  stop();
}

void metrics_influxdb::stop() {}

void metrics_influxdb::set_metrics(const ue_metrics_t& metrics, const uint32_t period_usec)
{
  cout << "DEBUG MCS: " << metrics.phy.dl[0].mcs << "\n";

  std::string response_text;
  int         result = influxdb_cpp::builder()
                   .meas("ue_info")
                   .tag("rnti", "test")
                   .field("mcs", float_to_string(metrics.phy.dl[0].mcs, 4))
                   .timestamp(get_timestamp())
                   .post_http(influx_server_info, &response_text);
  cout << "RESP: " << result << "\n";
  cout << "RESP TEXT: " << response_text << "\n";
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
