from worker_thread import WorkerThread

class jammer(WorkerThread):
    def start(self):
        self.config.image_name = "ghcr.io/oran-testing/jammer"
        self.cleanup_old_containers()
        self.setup_env()
        self.setup_networks()
        self.config.container_volumes[self.config.config_file] = {"bind": "/jammer.yaml", "mode": "ro"}
        self.setup_volumes()

        self.start_container()
