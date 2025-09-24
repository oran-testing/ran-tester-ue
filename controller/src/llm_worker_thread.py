from worker_thread import WorkerThread
import secrets
import os
from docker.types import DeviceRequest

class llm_worker(WorkerThread):
    def __init__(self, influxdb_client, docker_client, process_config):
        super().__init__(influxdb_client, docker_client, process_config)
        self.access_token = secrets.token_urlsafe(32)

    def start(self):
        results_dir = self.config.process_config.get("results_dir", None)
        if not results_dir:
            raise RuntimeError("Failed to start llm_worker: required field results_dir is missing")

        self.config.image_name = "ghcr.io/oran-testing/llm_worker"
        self.cleanup_old_containers()

        self.config.container_env = {
            "CONFIG": self.config.config_file,
            "CONTROL_IP": os.getenv("DOCKER_CONTROLLER_API_IP"),
            "CONTROL_PORT": os.getenv("DOCKER_CONTROLLER_API_PORT"),
            "CONTROL_TOKEN": self.access_token,
            "RESULTS_DIR": results_dir,
            "NVIDIA_VISIBLE_DEVICES": "all",
            "NVIDIA_DRIVER_CAPABILITIES": "all"
        }
        self.setup_env()
        self.setup_networks()
        self.config.container_networks.append(self.config.docker_client.networks.get("rt_control"))

        self.config.container_volumes[self.config.config_file] = {"bind": "/llm.yaml", "mode": "ro"}
        self.config.container_volumes[f"{os.getenv('DOCKER_SYSTEM_DIRECTORY')}/.llm_worker_cache"] = {"bind": "/app/huggingface_cache", "mode": "rw"}
        self.config.container_volumes["/tmp/.rt_results"] = {"bind": "/host/logs/", "mode": "rw"}
        self.setup_volumes()

        self.config.device_requests.append(
            DeviceRequest(
                count=-1,
                capabilities=[["gpu"]],
                driver="nvidia"
            )
        )

        self.start_container()

    def get_token(self):
        return self.access_token

