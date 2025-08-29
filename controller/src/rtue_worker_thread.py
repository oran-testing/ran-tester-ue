from worker_thread import WorkerThread

# UE process manager class:
# Handles all process and data management for one UE
# Collects data from UE then sends them to the webui
#

class rtue(WorkerThread):
    def start(self, process_config):
        self.config.image_name = "ghcr.io/oran-testing/rtue"
        self.cleanup_old_containers()
        self.setup_env()
        self.setup_networks()
        self.setup_volumes()

        self.start_container()



