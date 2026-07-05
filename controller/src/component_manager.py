import shutil
import requests 
import time
import sys
import docker
import os
import importlib.util
import tempfile
import inspect
import logging
import subprocess
import threading

from influxdb_client import InfluxDBClient, WriteApi
from globals import Globals


class ComponentManager:
    def __init__(self, external_influx=None, exit_from_component=False):

        if external_influx is None:
            self.influxdb_metadata = self.configure_influxdb_local()
        else:
            self.influxdb_metadata = self.configure_influxdb_external(external_influx)

        self.exit_from_component = exit_from_component

        self.docker_client = docker.from_env()

        self.process_metadata = []

        self.monitor_thread = threading.Thread(target=self.worker_thread_monitor, daemon=True)
        self.monitor_thread.start()

    def worker_thread_monitor(self):
        poll_interval = 0.2

        while True:
            for p in list(self.process_metadata):
                handle = p.get("handle")

                if handle is None:
                    continue

                exit_code = getattr(handle, "exit_code", None)
                if exit_code is None:
                    continue

                if not isinstance(exit_code, int):
                    logging.error(
                        f"Invalid exit code type for {p.get('id')}: {exit_code}"
                    )
                    continue

                component_id = handle.config.container_id

                if exit_code == 0:
                    logging.info(
                        f"Worker '{component_id}' exited cleanly (0), removing from monitor"
                    )
                    self.process_metadata.remove(p)
                    continue

                logging.error(
                    f"Worker '{component_id}' exited with code {exit_code}"
                )

                self.process_metadata.remove(p)

                if self.exit_from_component:
                    logging.critical(
                        f"Fatal component exit: {component_id} ({exit_code})"
                    )
                    os._exit(1)

            time.sleep(poll_interval)

    def configure_influxdb_external(self, external_influx):
        influxdb_host = external_influx.get("host", None)
        influxdb_port = external_influx.get("port", None)
        influxdb_org = external_influx.get("org", None)
        influxdb_token = external_influx.get("token", None)

        if not influxdb_host or not influxdb_port or not influxdb_org or not influxdb_token:
            logging.critical("external_influx configuration is not complete! Ensure host, port, org and token are supplied")
            sys.exit(1)

        self.influxdb_client = InfluxDBClient(
            f"http://{influxdb_host}:{influxdb_port}",
            org=influxdb_org,
            token=influxdb_token
        )

        return {
            "host": influxdb_host,
            "port": influxdb_port,
            "org": influxdb_org,
            "token": influxdb_token
        }

    def configure_influxdb_local(self):
        influxdb_host = os.getenv("DOCKER_INFLUXDB_INIT_HOST")
        influxdb_port = os.getenv("DOCKER_INFLUXDB_INIT_PORT")
        influxdb_org = os.getenv("DOCKER_INFLUXDB_INIT_ORG")
        influxdb_token = os.getenv("DOCKER_INFLUXDB_INIT_ADMIN_TOKEN")

        if not influxdb_host or not influxdb_port or not influxdb_org or not influxdb_token:
            logging.critical("Influxdb environment is not complete! Ensure .env is configured and passed properly")
            sys.exit(1)

        self.influxdb_client = InfluxDBClient(
            f"http://{influxdb_host}:{influxdb_port}",
            org=influxdb_org,
            token=influxdb_token
        )

        return {
            "host": influxdb_host,
            "port": influxdb_port,
            "org": influxdb_org,
            "token": influxdb_token
        }

    def build(self, component):
        component_path = component.get("component")
        if component_path is None:
            logging.critical(f"Error in component: component required in build_spec\n{component}")
            sys.exit(1)

        component_branch = component.get("branch", "main")

        worker_thread_url = component.get("worker_thread_url", f"https://raw.githubusercontent.com/{component_path}/{component_branch}/worker_thread.py")
        self._load_worker_thread_from_url(worker_thread_url, component_path)

        docker_image = component.get("docker_image", None)
        if docker_image is None:
            docker_image = f"ghcr.io/{component_path}"

        try:
            enable_pull = component.get("pull", True)
            if enable_pull:
                logging.info(f"Pulling Docker image: {docker_image}")
                self.docker_client.images.pull(docker_image)
            else:
                logging.info(f"Building Docker image: {docker_image}")
                repo_url = f"https://github.com/{component_path}"
                repo_name = component_path.split('/')[-1]
                clone_dir = f"/tmp/{repo_name}"
                dockerfile_spec = component.get('dockerfile', 'Dockerfile')
                dockerfile_path = f"/tmp/{repo_name}/{dockerfile_spec}"

                if os.path.exists(clone_dir):
                    shutil.rmtree(clone_dir)

                process = subprocess.Popen(
                    ["git", "clone", "-b", component_branch, repo_url, clone_dir],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                logging.info(f"Running git clone {repo_url}...")
                process.wait()
                if process.returncode != 0:
                    for line in process.stderr:
                        logging.critical(line.strip())
                    logging.critical(f"git clone failed with code {process.returncode}")


                if not os.path.exists(dockerfile_path):
                    host_dockerfile = f"/host/{dockerfile_spec}"
                    if os.path.exists(host_dockerfile):
                        target_path = f"/tmp/{repo_name}/Dockerfile"
                        logging.info(f"Copying local Dockerfile from {host_dockerfile} to {target_path}")
                        shutil.copy2(host_dockerfile, target_path)
                        dockerfile_path = target_path
                    else:
                        raise RuntimeError(f"Dockerfile {dockerfile_spec} not found at {dockerfile_path} or {host_dockerfile}")

                logging.info(f"Building Docker image from: {dockerfile_path}")
                build_context = os.path.dirname(dockerfile_path)

                self._run_buildx_build(docker_image, dockerfile_path, build_context)

        except Exception as e:
            raise RuntimeError(f"Error while building component {component['component']}: {str(e)}")

    def build_if_not_exists(self, component):
        component_path = component.get("component")
        if component_path is None:
            logging.critical(f"Error in component: component required in build_spec\n{component}")
            sys.exit(1)

        docker_image = component.get("docker_image", None)
        if docker_image is None:
            docker_image = f"ghcr.io/{component_path}"

        try:
            images = self.docker_client.images.list()
            image_tags = [tag for image in images if image.tags for tag in image.tags]
            image_exists = any(tag.startswith(docker_image) for tag in image_tags)
            if image_exists:
                logging.debug(f"Component {component['component']} already exists. Skipping build.")
                thread_url = component.get("worker_thread_url", f"https://raw.githubusercontent.com/{component_path}/{component.get('branch', 'main')}/worker_thread.py")
                self._load_worker_thread_from_url(thread_url, component_path)
            else:
                logging.debug(f"Component {component['component']} does not exist. Building now.")
                self.build(component)

        except Exception as e:
            raise RuntimeError(f"Error while checking/existing component {component_path}: {str(e)}")

    
    def start(self, process_config):
        if "name" not in process_config.keys():
            logging.critical("name field required for each process")
            return

        if "component" not in process_config.keys():
            logging.critical("component field required for each process")
            return

        # config_file is optional for some process types (e.g., oai_ue which uses CLI args only)
        if "config_file" in process_config.keys():
            process_config["config_file"] = os.path.join("/host",process_config["config_file"])
            if not os.path.exists(process_config["config_file"]):
                logging.warning(f"File {process_config['config_file']} not found searching root")
                config_basename = process_config["config_file"].split("/")[-1]
                found = False
                for root, _, files in os.walk("/host"):
                    if config_basename in files:
                        process_config["config_file"] = os.path.join(root, config_basename)
                        logging.info(f"Found config file {process_config['config_file']}")
                        found = True
                        break
                if not found:
                    logging.critical(f"config file {process_config['config_file']} not found")
                    return
            process_config["config_file"] = process_config["config_file"].replace("/host", os.getenv("DOCKER_SYSTEM_DIRECTORY"))
            logging.debug(f"Filename on host {process_config['config_file']}")
        else:
            logging.debug(f"Process {process_config['name']} does not require a config file")
            process_config["config_file"] = ""



        if "depends_on" in process_config.keys():
            depends_on_list = list(process_config["depends_on"])
            for dependency in depends_on_list:
                found_dep = False
                for process_data in self.process_metadata:
                    if process_data["name"] == dependency:
                        found_dep = True
                if not found_dep:
                    logging.critical(f"Did not find dependent process '{dependency}' for '{process_config['name']}'")
                    return

        if "sleep_ms" in process_config.keys():
            logging.warning(f"Sleeping for {process_config['sleep_ms']/1000.0} seconds")
            sleep_time = float(process_config["sleep_ms"])/1000.0
            time.sleep(sleep_time)


        process_class = None
        try:
            process_class = Globals.worker_thread_registry[process_config["component"]]
        except KeyError:
            logging.critical(f"No worker thread class found for: {process_config['component']}")
            return

        process_config["influxdb_metadata"] = self.influxdb_metadata
        process_handle = process_class(self.influxdb_client, self.docker_client, process_config)

        self.process_metadata.append({
            'id': process_config['name'],
            'type': process_config['component'],
            'config': process_config,
            'handle': process_handle,
        })

        process_handle.start()

    def start_external(self, process_config):
        if "name" not in process_config.keys():
            logging.critical("name field required for each process")
            return

        if "component" not in process_config.keys():
            logging.critical("component field required for each process")
            return

        has_config = False
        # config_file is optional for some process types (e.g., oai_ue which uses CLI args only)
        if "config_file" in process_config.keys():
            process_config["config_file"] = os.path.join("/host",process_config["config_file"])
            if not os.path.exists(process_config["config_file"]):
                logging.warning(f"File {process_config['config_file']} not found searching root")
                config_basename = process_config["config_file"].split("/")[-1]
                found = False
                for root, _, files in os.walk("/host"):
                    if config_basename in files:
                        process_config["config_file"] = os.path.join(root, config_basename)
                        logging.info(f"Found config file {process_config['config_file']}")
                        found = True
                        break
                if not found:
                    logging.critical(f"config file {process_config['config_file']} not found")
                    return

            has_config = True
        else:
            logging.debug(f"Process {process_config['name']} does not require a config file")
            process_config["config_file"] = ""



        if "depends_on" in process_config.keys():
            depends_on_list = list(process_config["depends_on"])
            for dependency in depends_on_list:
                found_dep = False
                for process_data in self.process_metadata:
                    if process_data["name"] == dependency:
                        found_dep = True
                if not found_dep:
                    raise RuntimeError(f"Did not find dependent process '{dependency}' for '{process_config['name']}'")

        if "sleep_ms" in process_config.keys():
            logging.warning(f"Sleeping for {process_config['sleep_ms']/1000.0} seconds")
            sleep_time = float(process_config["sleep_ms"])/1000.0
            time.sleep(sleep_time)


        external_target = Globals.target_managers.get(process_config.get("target"), None)
        if external_target is None:
            logging.critical(f"External target with name: {process_config.get('target')} not found")
            return

        config_str = ""
        if has_config:
            with open(process_config["config_file"], 'r') as f:
                config_str = f.read()

        response = external_target.make_request("start", payload={
            "id": process_config["name"],
            "type": process_config["component"],
            "config_str": config_str,
            "rf": process_config["rf"],
        })

        logging.debug(f"Got reponse from external target: {response}")

        self.process_metadata.append({
            'id': process_config['name'],
            'type': process_config['component'],
            'config': process_config,
            'target': process_config.get("target"),
        })

    def stop(self, process_config):
        process_handle = process_config.get("handle", None)
        if process_handle:
            process_handle.stop()
            return

        process_target = process_config.get("target")
        external_target = Globals.target_managers.get(process_config.get("target"), None)

        response = external_target.make_request("stop", payload={
            "id": process_config.get("id"),
        })

        logging.debug(f"Got reponse from external target: {response}")

    def _run_buildx_build(self, docker_image, dockerfile_path, build_context):
        buildx_command = [
            "docker", "buildx", "build",
            "--file", dockerfile_path,
            "--tag", docker_image,
            "--progress", "plain",
            build_context
        ]

        logging.info(f"Running command: {' '.join(buildx_command)}")

        try:
            process = subprocess.Popen(
                buildx_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in iter(process.stdout.readline, ""):
                logging.debug(line.rstrip())

            process.stdout.close()

            return_code = process.wait()
            if return_code != 0:
                raise RuntimeError(f"Buildx build failed with exit code {return_code}")

            logging.info("Buildx build completed successfully.")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Buildx build failed: {e.stderr}")

    def _load_worker_thread_from_url(self, url: str, component_path):
        logging.debug(f"Loading worker thread from {url}")
        response = requests.get(url)
        if response.status_code != 200:
            logging.critical(
                f"Worker thread for specified component not provided. "
                f"Check that the file at this URL exists: {url}"
            )
            sys.exit(1)

        code = response.text
        logging.debug(f"Got worker thread:\n {code}")

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tmp_file:
            tmp_file.write(code)
            tmp_path = tmp_file.name

        module_name = os.path.basename(tmp_path)[:-3]
        spec = importlib.util.spec_from_file_location(module_name, tmp_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__name__ in ["WorkerThread", "ComponentManager"]:
                continue
            logging.info(f"Loaded worker class {cls.__name__} from {url}")
            Globals.worker_thread_registry[component_path] = cls
            return cls

        raise RuntimeError(f"No class definitions found in worker file from {url}")

