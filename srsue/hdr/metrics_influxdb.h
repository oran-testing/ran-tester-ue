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

/******************************************************************************
 * File:        metrics_influxdb.h
 * Description: Metrics writing to influx database
 *****************************************************************************/

#ifndef SRSUE_METRICS_INFLUXDB_H
#define SRSUE_METRICS_INFLUXDB_H

#include <fstream>
#include <iostream>
#include <mutex>
#include <pthread.h>
#include <stdint.h>
#include <string>

#include "influxdb.hpp"
#include "srsran/common/metrics_hub.h"
#include "ue_metrics_interface.h"

namespace srsue {

class metrics_influxdb : public srsran::metrics_listener<ue_metrics_t>
{
public:
  metrics_influxdb(std::string influxdb_url,
                   uint32_t    influxdb_port,
                   std::string influxdb_org,
                   std::string influxdb_token,
                   std::string influxdb_bucket);
  ~metrics_influxdb();

  void set_metrics(const ue_metrics_t& m, const uint32_t period_usec);
  void stop();

private:
  std::string        float_to_string(float f, int digits);
  unsigned long long get_timestamp();

  influxdb_cpp::server_info influx_server_info;
  ue_metrics_interface*     ue               = nullptr;
  uint32_t                  n_reports        = 0;
  std::mutex                mutex            = {};
  uint32_t                  flush_period_sec = 0;
  uint32_t                  flush_time_ms    = 0;
  uint64_t                  time_ms          = 0;
};

} // namespace srsue

#endif // SRSUE_METRICS_INFLUXDB_H
