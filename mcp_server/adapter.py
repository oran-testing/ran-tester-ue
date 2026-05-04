import requests
import logging
import os
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class ControllerAdapter:
    """HTTP client for the RAN Tester UE Controller API"""

    def __init__(self, url: str, token: str, configs_dir: str = "/host/configs"):
        self.base_url = url.rstrip('/')
        self.token = token
        self.configs_dir = configs_dir
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        self.session.verify = False

    def list_components(self) -> Tuple[bool, Dict[str, Any]]:
        try:
            response = self.session.get(f"{self.base_url}/list")
            if response.status_code == 200:
                return True, response.json()
            return False, {"error": response.text}
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}

    def start_component(self, config: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        try:
            response = self.session.post(
                f"{self.base_url}/start_from_json",
                json=config
            )
            if response.status_code == 200:
                return True, response.json()

            try:
                error_data = response.json()
            except:
                error_data = {"error": response.text}

            return False, error_data
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}

    def stop_component(self, component_id: str) -> Tuple[bool, Dict[str, Any]]:
        try:
            response = self.session.post(
                f"{self.base_url}/stop",
                json={"id": component_id}
            )
            if response.status_code == 200:
                return True, response.json()
            return False, {"error": response.text}
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}

    def get_logs(self, component_id: str, component_type: str) -> Tuple[bool, Dict[str, Any]]:
        try:
            response = self.session.post(
                f"{self.base_url}/logs",
                json={"id": component_id, "type": component_type}
            )
            if response.status_code == 200:
                return True, response.json()
            return False, {"error": response.text}
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}

    def get_health(self, component_id: str) -> Tuple[bool, Dict[str, Any]]:
        try:
            response = self.session.post(
                f"{self.base_url}/health",
                json={"id": component_id}
            )
            if response.status_code == 200:
                return True, response.json()
            return False, {"error": response.text}
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}

    def get_schema(self, component_type: str) -> Tuple[bool, Dict[str, Any]]:
        try:
            response = self.session.get(
                f"{self.base_url}/schemas/{component_type}"
            )
            if response.status_code == 200:
                return True, response.json()
            return False, {"error": response.text}
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}

    def list_available_configs(self) -> Tuple[bool, list]:
        try:
            configs = []
            for root, dirs, files in os.walk(self.configs_dir):
                for file in files:
                    if file.endswith(('.yaml', '.yml', '.toml', '.conf')):
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, self.configs_dir)
                        configs.append({
                            "name": rel_path,
                            "path": full_path
                        })
            return True, configs
        except Exception as e:
            return False, [{"error": str(e)}]

    def get_config_template(self, config_name: str) -> Tuple[bool, str]:
        try:
            full_path = os.path.join(self.configs_dir, config_name)
            if not os.path.exists(full_path):
                return False, f"Config not found: {config_name}"

            with open(full_path, 'r') as f:
                return True, f.read()
        except Exception as e:
            return False, str(e)
