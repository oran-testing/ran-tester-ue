import os
import subprocess
import time

import yaml
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.rest import ApiException

# --- Configuration ---
# You MUST find and set your token. Check your docker-compose.yml or .env files.
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "605bc59413b7d5457d181ccf20f9fda15693f81b068d70396cc183081b264f3b"  # <-- IMPORTANT: REPLACE THIS
INFLUXDB_ORG = "rtu"  # From your logs

# --- Correct values from your Grafana panel ---
INFLUXDB_BUCKET = "rtusystem"
MEASUREMENT_NAME = "rtue_carrier_metric"
FIELD_NAME = "sinr"

# --- Monitoring Settings ---
SINR_THRESHOLD_DB = 0.0
CHECK_INTERVAL_SECONDS = 5

# --- Config File Settings ---
DEFAULT_YAML_PATH = "configs/default.yaml"  # Adjust path if needed
CONFIG_FILE_ORIGINAL = "configs/uhd/ue_uhd.conf"
CONFIG_FILE_ALT = "configs/uhd/ue_uhd_alt.conf"

UE_CONNECTED_AND_READY = False
SHUTDOWN_IN_PROGRESS = False


def graceful_shutdown():
    """
    Perform graceful shutdown: restore original config and stop containers
    """
    global SHUTDOWN_IN_PROGRESS
    if SHUTDOWN_IN_PROGRESS:
        return  # Avoid multiple shutdown attempts

    SHUTDOWN_IN_PROGRESS = True
    print("\n" + "=" * 50)
    print("  GRACEFUL SHUTDOWN INITIATED")
    print("=" * 50)

    try:
        # Step 1: Restore original configuration
        print("[SHUTDOWN 1/3] Restoring original configuration...")
        if modify_config_file(use_alt_config=False):
            print("[SUCCESS] Original configuration restored")
        else:
            print("[WARNING] Could not restore original configuration")

        # Step 2: Stop all containers gracefully
        print("[SHUTDOWN 2/3] Stopping Docker containers...")
        try:
            # First try graceful shutdown
            stop_command = ["sudo", "docker", "compose", "--profile", "system", "down"]
            result = subprocess.run(
                stop_command, capture_output=True, text=True, timeout=30
            )

            # Check if any containers are still running
            check_command = ["sudo", "docker", "ps", "-q"]
            result = subprocess.run(check_command, capture_output=True, text=True)

            if result.stdout.strip():
                print("[INFO] Some containers still running, force stopping...")
                container_ids = result.stdout.strip().split("\n")
                for container_id in container_ids:
                    subprocess.run(
                        ["sudo", "docker", "stop", "-t", "10", container_id],
                        capture_output=True,
                        text=True,
                    )

            print("[SUCCESS] All containers stopped")

        except subprocess.TimeoutExpired:
            print("[WARNING] Graceful container shutdown timed out")
        except Exception as e:
            print(f"[ERROR] Error stopping containers: {e}")

        # Step 3: Final cleanup
        print("[SHUTDOWN 3/3] Final cleanup...")
        subprocess.run(
            ["sudo", "docker", "container", "prune", "-f"],
            capture_output=True,
            text=True,
        )

        print("=" * 50)
        print("  GRACEFUL SHUTDOWN COMPLETED")
        print("=" * 50)

    except Exception as e:
        print(f"[ERROR] Error during graceful shutdown: {e}")

    finally:
        print("Goodbye!")


def signal_handler(signum, frame):
    """
    Handle interrupt signals (Ctrl+C, SIGTERM, etc.)
    """
    signal_name = "SIGINT" if signum == signal.SIGINT else f"Signal {signum}"
    print(f"\n[SIGNAL] Received {signal_name}, initiating graceful shutdown...")
    graceful_shutdown()
    sys.exit(0)


def setup_signal_handlers():
    """
    Set up signal handlers for graceful shutdown
    """
    # Handle Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    # Handle SIGTERM (termination request)
    signal.signal(signal.SIGTERM, signal_handler)
    # Register cleanup function to run on normal exit
    atexit.register(graceful_shutdown)


def restore_original_config():
    """
    Utility function to restore original config (for manual use or cleanup)
    """
    print("[RESTORE] Restoring original config file...")
    return modify_config_file(use_alt_config=False)


def nuclear_docker_cleanup():
    """
    Nuclear option: Stop and remove ALL Docker containers, networks, and volumes.
    Use with extreme caution!
    """
    print("[NUCLEAR] Performing complete Docker cleanup...")
    commands = [
        "sudo docker kill $(sudo docker ps -q)",  # Kill all running containers
        "sudo docker rm $(sudo docker ps -a -q)",  # Remove all containers
        "sudo docker network prune -f",  # Remove unused networks
        "sudo docker volume prune -f",  # Remove unused volumes
        "sudo docker system prune -f",  # Remove everything unused
    ]

    for cmd in commands:
        try:
            subprocess.run(cmd, shell=True, capture_output=True, text=True)
        except:
            pass  # Ignore errors in cleanup
    print("[NUCLEAR] Complete cleanup finished")


def modify_config_file(use_alt_config=True):
    """
    Safely modify the default.yaml file to switch between config files.
    """
    try:
        # Read the current YAML file
        with open(DEFAULT_YAML_PATH, "r") as file:
            data = yaml.safe_load(file)

        # Find and modify the rtue process config
        for process in data.get("processes", []):
            if process.get("type") == "rtue" and process.get("id") == "rtue_uhd_1":
                old_config = process.get("config_file", "")
                new_config = CONFIG_FILE_ALT if use_alt_config else CONFIG_FILE_ORIGINAL
                process["config_file"] = new_config
                print(
                    f"[CONFIG] Changed config_file from '{old_config}' to '{new_config}'"
                )
                break
        else:
            print(
                "[WARNING] Could not find rtue process with id 'rtue_uhd_1' in default.yaml"
            )
            return False

        # Write the modified YAML back to file
        with open(DEFAULT_YAML_PATH, "w") as file:
            yaml.dump(data, file, default_flow_style=False, sort_keys=False)

        print(f"[CONFIG] Successfully updated {DEFAULT_YAML_PATH}")
        return True

    except FileNotFoundError:
        print(f"[ERROR] Could not find {DEFAULT_YAML_PATH}")
        return False
    except yaml.YAMLError as e:
        print(f"[ERROR] YAML parsing error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to modify config file: {e}")
        return False


def restart_ue_services(reason: str, use_nuclear_option=False):
    """
    Safely stops containers, switches to alternate config, and restarts.
    """
    print("\n" + "=" * 50)
    print(f"  DETECTED: {reason}")
    print(f"Restarting containers with alternate config")
    print("=" * 50 + "\n")

    try:
        # Step 1: Force stop ALL containers (comprehensive approach)
        print("[STEP 1a] Attempting graceful shutdown...")
        try:
            stop_command = ["sudo", "docker", "compose", "--profile", "system", "down"]
            subprocess.run(stop_command, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            print("[WARNING] Graceful shutdown timed out, proceeding with force stop")

        # Step 1b: Get all running containers and force stop them
        print("[STEP 1b] Force stopping ALL running containers...")
        get_containers_cmd = ["sudo", "docker", "ps", "-q"]
        result = subprocess.run(get_containers_cmd, capture_output=True, text=True)

        if result.stdout.strip():  # If there are running containers
            container_ids = result.stdout.strip().split("\n")
            print(f"[INFO] Found {len(container_ids)} running containers to stop")

            # Force stop with SIGKILL after timeout
            for container_id in container_ids:
                print(f"[INFO] Force stopping container: {container_id}")
                subprocess.run(
                    ["sudo", "docker", "stop", "-t", "5", container_id],
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    ["sudo", "docker", "kill", container_id],
                    capture_output=True,
                    text=True,
                )
        else:
            print("[INFO] No running containers found")

        # Step 1c: Clean up stopped containers and networks
        subprocess.run(
            ["sudo", "docker", "container", "prune", "-f"],
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["sudo", "docker", "network", "prune", "-f"], capture_output=True, text=True
        )

        # Step 1d: Verify all containers are stopped
        result = subprocess.run(
            ["sudo", "docker", "ps", "-q"], capture_output=True, text=True
        )
        if result.stdout.strip():
            if use_nuclear_option:
                print(
                    "[WARNING] Some containers still running. Using nuclear option..."
                )
                nuclear_docker_cleanup()
            else:
                print("[WARNING] Some containers may still be running")
        else:
            print("[SUCCESS] All containers stopped and cleaned up")

        # Step 2: Modify config file
        if not modify_config_file(use_alt_config=True):
            print("[ERROR] Failed to modify config file. Aborting restart.")
            return

        print("[STEP 3] Waiting 5 seconds for system to settle...")
        time.sleep(15)

        # Step 4: Start containers with new config
        # start_command = ["sudo", "docker", "compose", "--profile", "system", "up"]
        # result = subprocess.run(
        #    start_command, check=True, capture_output=True, text=True
        # )
        subprocess.Popen(
            [
                "gnome-terminal",
                "--",
                "bash",
                "-c",
                "cd $(pwd) && sudo docker compose --profile system up; exec bash",
            ]
        )

    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Docker command failed: {e}")
        print(f"[ERROR] STDOUT:\n{e.stdout}")
        print(f"[ERROR] STDERR:\n{e.stderr}")

        # Try to revert config file on failure
        print("[RECOVERY] Attempting to revert to original config...")
        modify_config_file(use_alt_config=False)

    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")


# --- Main Monitoring Logic ---
def monitor_sinr_influxdb():
    """
    Monitors SINR from InfluxDB and triggers a restart if it's too low or absent.
    """
    print(f"Monitoring SINR from InfluxDB at: {INFLUXDB_URL}")
    print(f"Bucket: {INFLUXDB_BUCKET}, Measurement: {MEASUREMENT_NAME}")
    global UE_CONNECTED_AND_READY
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    query_api = client.query_api()

    while True:
        try:
            # Flux query to get the most recent SINR value in the last minute
            flux_query = f"""
            from(bucket: "{INFLUXDB_BUCKET}")
              |> range(start: -1m)
              |> filter(fn: (r) => r._measurement == "{MEASUREMENT_NAME}")
              |> filter(fn: (r) => r._field == "{FIELD_NAME}")
              |> last()
            """

            tables = query_api.query(flux_query)

            # Case 1: No data returned. UE is likely disconnected.
            if not tables or not tables[0].records:
                print(
                    f"[ALERT] SINR metric '{FIELD_NAME}' not found in the last minute."
                )
                # restart_ue_services("SINR metric is unavailable.")
                print(f"[STATUS] Waiting for 5 seconds before resuming monitoring...")
                time.sleep(5)
                continue

            # Case 2: Data found, check the value.
            record = tables[0].records[0]
            latest_sinr = record.get_value()

            print(f"[INFO] Current SINR: {latest_sinr:.2f} dB")
            if latest_sinr > 5 and UE_CONNECTED_AND_READY is False:
                # if we're getting SINR for the first time
                UE_CONNECTED_AND_READY = True

            if UE_CONNECTED_AND_READY is not True:
                continue

            if latest_sinr <= SINR_THRESHOLD_DB:
                print(
                    f"[ALERT] SINR ({latest_sinr:.2f} dB) is below threshold of {SINR_THRESHOLD_DB} dB."
                )
                restart_ue_services(f"SINR of {latest_sinr:.2f} dB is too low.")
                print(f"[STATUS] Waiting for 60 seconds before resuming monitoring...")
                time.sleep(60)

        except ApiException as e:
            if not SHUTDOWN_IN_PROGRESS:
                print(f"[ERROR] InfluxDB API Error: {e.status} - {e.reason}")
                print("[ERROR] Please check your URL, Token, Org, and Bucket.")
                for i in range(CHECK_INTERVAL_SECONDS * 2):
                    if SHUTDOWN_IN_PROGRESS:
                        return
                    time.sleep(1)
        except Exception as e:
            if not SHUTDOWN_IN_PROGRESS:
                print(f"[ERROR] An unexpected error occurred: {e}")
                for i in range(CHECK_INTERVAL_SECONDS * 2):
                    if SHUTDOWN_IN_PROGRESS:
                        return
                    time.sleep(1)

        # Check for shutdown before sleeping
        for i in range(CHECK_INTERVAL_SECONDS):
            if SHUTDOWN_IN_PROGRESS:
                return
            time.sleep(1)


if __name__ == "__main__":
    if INFLUXDB_TOKEN == "YOUR_SECRET_TOKEN_HERE":
        print(
            "\n[FATAL] You must edit the script and set the INFLUXDB_TOKEN variable.\n"
        )
    else:
        try:
            monitor_sinr_influxdb()
        except KeyboardInterrupt:
            # This should be handled by signal_handler, but just in case
            print("\nKeyboardInterrupt caught, shutting down...")
        except Exception as e:
            print(f"\n[ERROR] Unexpected error in main: {e}")
        finally:
            if not SHUTDOWN_IN_PROGRESS:
                graceful_shutdown()
