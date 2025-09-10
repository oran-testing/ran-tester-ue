from worker_thread import WorkerThread

class sniffer(WorkerThread):
    def start(self, process_config):
        self.config.image_name = "ghcr.io/oran-testing/5g-sniffer"
        self.cleanup_old_containers()
        self.setup_env()
        self.setup_networks()
        self.config.container_volumes[self.config.config_file] = {"bind": "/sniffer.toml", "mode": "ro"}
        self.setup_volumes()
