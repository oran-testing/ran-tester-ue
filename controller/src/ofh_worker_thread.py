from worker_thread import WorkerThread
import os

class ofh(WorkerThread):
    def start(self):
        self.config.image_name = "ghcr.io/oran-testing/ofh"
        self.cleanup_old_containers()
        self.setup_env()
        self.setup_networks()

        self.config.container_volumes[self.config.config_file] = {"bind": "/ofh.toml", "mode": "ro"}
        self.config.container_env["CONFIG_TOML"] = "/ofh.toml"

        host_base = os.path.dirname(os.path.abspath(self.config.config_file))
        self.config.container_volumes[os.path.join(host_base, "Traffic")] = {"bind": "/attack_env/Traffic", "mode": "ro"}
        self.config.container_volumes[os.path.join(host_base, "attack_results")] = {"bind": "/attack_env/attack_results", "mode": "rw"}
        self.config.container_env["ATTACKER_DIR"] = "/attack_env"
        self.config.host_network = True 

        self.setup_volumes()
        self.start_container()
