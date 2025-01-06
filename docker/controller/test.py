from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

class SrsRANInfluxDB:
    def __init__(self):
        # Initialize the InfluxDB client
        self.influxdb_client = InfluxDBClient(
            url="http://0.0.0.0:8086",
            org="srs",
            token="605bc59413b7d5457d181ccf20f9fda15693f81b068d70396cc183081b264f3b"
        )
        self.bucket = "srsran"
        self.org = "srs"

    def add_field(self, measurement, tags, fields, timestamp=None):
        """
        Add a field to the specified measurement in the InfluxDB bucket.
        Args:
            measurement (str): The name of the measurement.
            tags (dict): Tags to associate with the data point (key-value pairs).
            fields (dict): Fields to store in the measurement (key-value pairs).
            timestamp (datetime, optional): Timestamp for the data point.
        """
        # Start with the measurement
        point = Point(measurement)

        # Add tags one by one
        for key, value in tags.items():
            point = point.tag(key, value)

        # Add fields
        for key, value in fields.items():
            point = point.field(key, value)

        # Add timestamp if provided
        if timestamp:
            point = point.time(timestamp)

        # Write the point
        write_api = self.influxdb_client.write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=self.bucket, org=self.org, record=point)
        print(f"Added field(s) to measurement '{measurement}': {fields}")

    def get_fields(self, measurement, start="-1h", stop="now()", limit=10):
        """
        Retrieve fields from the specified measurement in the InfluxDB bucket.
        Args:
            measurement (str): The name of the measurement.
            start (str): The start time for the query range (default: last 1 hour).
            stop (str): The end time for the query range (default: now).
            limit (int): Maximum number of results to return.
        Returns:
            List[dict]: A list of field data.
        """
        query = f"""
        from(bucket: "{self.bucket}")
          |> range(start: {start}, stop: {stop})
          |> filter(fn: (r) => r._measurement == "{measurement}")
          |> limit(n: {limit})
        """
        query_api = self.influxdb_client.query_api()
        tables = query_api.query(query)

        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "time": record.get_time(),
                    "measurement": record.get_measurement(),
                    "field": record.get_field(),
                    "value": record.get_value(),
                    "tags": record.values
                })

        print(f"Retrieved {len(results)} field(s) from measurement '{measurement}'.")
        return results


# Example usage
if __name__ == "__main__":
    from datetime import datetime

    db = SrsRANInfluxDB()

    # Add a field
    db.add_field(
        measurement="ue_metrics",
        tags={"ue_id": "123", "location": "lab"},
        fields={"signal_strength": -70, "latency_ms": 25.3},
        timestamp=datetime.utcnow()
    )

    # Get fields
    fields = db.get_fields(
        measurement="ue_metrics",
        start="-1h",
        limit=5
    )
    for field in fields:
        print(field)
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

class SrsRANInfluxDB:
    def __init__(self):
        # Initialize the InfluxDB client
        self.influxdb_client = InfluxDBClient(
            url="http://influxdb:8086",
            org="srs",
            token="605bc59413b7d5457d181ccf20f9fda15693f81b068d70396cc183081b264f3b"
        )
        self.bucket = "srsran"
        self.org = "srs"

    def add_field(self, measurement, fields, timestamp=None):
        """
        Add a field to the specified measurement in the InfluxDB bucket.
        Args:
            measurement (str): The name of the measurement.
            tags (dict): Tags to associate with the data point (key-value pairs).
            fields (dict): Fields to store in the measurement (key-value pairs).
            timestamp (datetime, optional): Timestamp for the data point.
        """
        point = Point(measurement).field(**fields)
        if timestamp:
            point = point.time(timestamp)

        write_api = self.influxdb_client.write_api(write_options=SYNCHRONOUS)
        write_api.write(bucket=self.bucket, org=self.org, record=point)
        print(f"Added field(s) to measurement '{measurement}': {fields}")

    def get_fields(self, measurement, start="-1h", stop="now()", limit=10):
        """
        Retrieve fields from the specified measurement in the InfluxDB bucket.
        Args:
            measurement (str): The name of the measurement.
            start (str): The start time for the query range (default: last 1 hour).
            stop (str): The end time for the query range (default: now).
            limit (int): Maximum number of results to return.
        Returns:
            List[dict]: A list of field data.
        """
        query = f"""
        from(bucket: "{self.bucket}")
          |> range(start: {start}, stop: {stop})
          |> filter(fn: (r) => r._measurement == "{measurement}")
          |> limit(n: {limit})
        """
        query_api = self.influxdb_client.query_api()
        tables = query_api.query(query)

        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "time": record.get_time(),
                    "measurement": record.get_measurement(),
                    "field": record.get_field(),
                    "value": record.get_value(),
                    "tags": record.values
                })

        print(f"Retrieved {len(results)} field(s) from measurement '{measurement}'.")
        return results


# Example usage
if __name__ == "__main__":
    from datetime import datetime

    db = SrsRANInfluxDB()

    # Add a field
    db.add_field(
        measurement="ue_metrics",
        fields={"signal_strength": -70, "latency_ms": 25.3},
        timestamp=datetime.utcnow()
    )

    # Get fields
    fields = db.get_fields(
        measurement="ue_metrics",
        start="-1h",
        limit=5
    )
    for field in fields:
        print(field)

