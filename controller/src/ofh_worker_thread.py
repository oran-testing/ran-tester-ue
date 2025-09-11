from worker_thread import WorkerThread
import os

class ofh_attacker(WorkerThread):
    def start(self):
        self.config.image_name = "ghcr.io/oran-testing/ofh"
        self.cleanup_old_containers()
        self.setup_env()
        self.setup_networks()

        self.config.container_volumes[self.config.config_file] = {"bind": "/attack_env/ofh.toml", "mode": "ro"}
        self.config.container_env["CONFIG_TOML"] = "/attack_env/ofh.toml"
        host_base = os.path.dirname(os.path.abspath(self.config.config_file))
        self.config.container_volumes[os.path.join(host_base, "Traffic")] = {"bind": "/attack_env/Traffic", "mode": "ro"}
        self.config.container_volumes[os.path.join(host_base, "attack_results")] = {"bind": "/attack_env/attack_results", "mode": "rw"}
        self.config.container_env["ATTACKER_DIR"] = "/attack_env"
        self.config.container_env["HOST_UID"] = os.getenv("HOST_UID", "1000") # TODO: remove after influxdb update
        self.config.container_env["HOST_GID"] = os.getenv("HOST_GID", "1000") # TODO: remove after influxdb update
        self.config.host_network = True 

        self.setup_volumes()
        self.start_container()
