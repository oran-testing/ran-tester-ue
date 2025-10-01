import os
import shutil
import logging
from worker_thread import WorkerThread

class uu_agent(WorkerThread):
    def start(self):
        self.config.image_name = "ghcr.io/oran-testing/uu-agent"
        self.cleanup_old_containers()
        self.setup_env()
        self.setup_networks()

        self.config.container_volumes[self.config.config_file] = {"bind": "/uu-agent.conf", "mode": "ro"} #update the config file binding

        # Add IQ output volume
        iq_output_dir = f"{os.getenv('DOCKER_SYSTEM_DIRECTORY')}/.uuagent_results"
        self.config.container_volumes[iq_output_dir] = {"bind": "/output/", "mode": "rw"}
        
        self._cleanup_old_iq_files(iq_output_dir)
        
        self.setup_volumes()
        self.start_container()
    
    def _cleanup_old_iq_files(self, iq_output_dir):
        """Remove old IQ files to preserve disk space"""
        try:
            os.makedirs(iq_output_dir, exist_ok=True)
            
            removed_count = 0
            total_size_removed = 0
            
            for filename in os.listdir(iq_output_dir):
                if filename.endswith(('.fc32', '.bin', '.dat', '.iq')):
                    file_path = os.path.join(iq_output_dir, filename)
                    file_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    removed_count += 1
                    total_size_removed += file_size
                    logging.info(f"Removed old IQ file: {filename} ({file_size / (1024*1024):.1f} MB)")
            
            if removed_count > 0:
                logging.info(f"Cleanup completed: {removed_count} files removed, {total_size_removed / (1024*1024):.1f} MB freed")
            else:
                logging.info("No old IQ files found to cleanup")
                    
        except Exception as e:
            logging.warning(f"Failed to cleanup old IQ files: {e}")
