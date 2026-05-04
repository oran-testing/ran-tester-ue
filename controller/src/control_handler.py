import json
import http.server
from globals import Globals
import logging
import os
from config_converters import CONFIG_CONVERTERS

class SystemControlHandler(http.server.SimpleHTTPRequestHandler):
    def _get_permissions(self):
        is_valid_token = False
        permissions = []
        auth_header = self.headers.get("Authorization")
        if not auth_header.startswith("Bearer "):
            return False, []
        token = auth_header.removeprefix("Bearer").strip()
        for api in Globals.api_auth:
            if api.get("token", "") == token:
                if self.path[1:] in api.get("scopes", []):
                    is_valid_token = True
                    permissions = api.get("allowed_components", [])
                    break
        return is_valid_token, permissions

    def _set_headers(self, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def _send_unauthorized(self):
        self._set_headers(401)
        self.wfile.write(json.dumps({"error":"Unauthorized"}).encode("utf-8"))

    def _send_nonexistent(self):
        self._set_headers(404)
        self.wfile.write(json.dumps({"error":"Endpoint not found"}).encode("utf-8"))

    def get_components(self):
        is_valid_token, _ = self._get_permissions()
        if not is_valid_token:
            self._send_unauthorized()
            return

        response_list = []
        for process_config in Globals.thread_manager.process_metadata:
            response_list.append({
                "id": process_config["id"],
                "type": process_config["type"],
                "config_file": process_config["config"]["config_file"]
            })
        self._set_headers()
        self.wfile.write(json.dumps({"running": response_list}).encode("utf-8"))

    def get_component_logs(self):
        is_valid_token, _ = self._get_permissions()
        if not is_valid_token:
            self._send_unauthorized()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        payload = {}
        try:
            payload = json.loads(post_data)
        except json.JSONDecodeError:
            self._set_headers(403)
            self.wfile.write(json.dumps({"error":"malformed request"}).encode("utf-8"))
            return

        if not all(k in payload for k in ("id", "type")):
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing required fields: id, type"}).encode("utf-8"))
                return

        influx_bucket = "rtusystem"
        influx_id = payload["id"]

        query = f'''
            from(bucket: "{influx_bucket}")
            |> range(start: {Globals.controller_init_time})
            |> filter(fn: (r) => r._measurement == "component_log")
            |> filter(fn: (r) => r["id"] == "{influx_id}")
            |> sort(columns: ["_time"])
        '''

        query_api = Globals.thread_manager.influxdb_client.query_api()
        result = query_api.query(org=Globals.thread_manager.influxdb_client.org, query=query)

        logs = []
        for table in result:
            for record in table.records:
                logs.append({
                    "time": record.get_time().isoformat(),
                    "message": record.get_value()
                })

        self._set_headers()
        self.wfile.write(json.dumps({"logs":logs}).encode("utf-8"))


    def start_component(self):
        is_valid_token, perms = self._get_permissions()
        if not is_valid_token:
            self._send_unauthorized()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        payload = {}
        try:
            payload = json.loads(post_data)
        except json.JSONDecodeError:
            self._set_headers(403)
            self.wfile.write(json.dumps({"error":"malformed request"}).encode("utf-8"))
            return

        logging.debug(f"{payload.keys()}")
        if not all(k in payload for k in ("id", "type", "config_str", "rf")):
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing required fields: id, type, config_str, rf"}).encode("utf-8"))
                return

        rf_type = payload.get("rf").get("type", None)
        if not rf_type:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing required fields for rf: type"}).encode("utf-8"))
                return

        if payload.get("type") not in perms:
            self._set_headers(403)
            self.wfile.write(json.dumps({"error":"unauthorized to start that component"}).encode("utf-8"))
            return

        if any(p["id"] == payload["id"] for p in Globals.thread_manager.process_metadata):
                self._set_headers(409)
                self.wfile.write(json.dumps({"error": "ID conflict with existing component"}).encode("utf-8"))
                return

        if not os.path.isdir("/host/.generated/"):
            os.makedirs("/host/.generated", exist_ok=True)

        file_ext = {
            "rtue": "conf",
            "sniffer": "toml"
        }.get(payload["type"], "yaml")

        config_file = f"/host/.generated/{payload['id']}.{file_ext}"

        try:
            with open(config_file, "w") as f:
                f.write(payload["config_str"])
        except IOError as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error":f"Failed to write config to file {config_file}"}))
            return

        new_process_config = {
            "config_file": config_file,
            "name": payload["id"],
            "component": payload["type"],
            "rf": payload["rf"],
            "permissions": [],
        }

        Globals.thread_manager.start(new_process_config)

        self._set_headers()
        self.wfile.write(json.dumps({"msg":f"process started: {payload['id']}"}).encode("utf-8"))

    def stop_component(self):
        is_valid_token, _ = self._get_permissions()
        if not is_valid_token:
            self._send_unauthorized()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        payload = {}
        try:
            payload = json.loads(post_data)
        except json.JSONDecodeError:
            self._send_unauthorized()
            return

        if "id" not in payload.keys():
            self._set_headers(400)
            self.wfile.write(json.dumps({"error":"Missing required field id"}).encode("utf-8"))
            return

        for i, process_config in enumerate(Globals.thread_manager.process_metadata):
            if process_config["id"] == payload["id"]:
                self._set_headers()
                self.wfile.write(json.dumps({"id":process_config["id"]}).encode("utf-8"))
                process_config["handle"].stop()
                del Globals.thread_manager.process_metadata[i]
                return
        self._set_headers(404)
        self.wfile.write(json.dumps({"error":"Component with ID does not exist"}).encode("utf-8"))

    def check_component_health(self):
        is_valid_token, _ = self._get_permissions()
        if not is_valid_token:
            self._send_unauthorized()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        payload = {}
        try:
            payload = json.loads(post_data)
        except json.JSONDecodeError:
            self._send_unauthorized()
            return

        if "id" not in payload.keys():
            self._set_headers(400)
            self.wfile.write(json.dumps({"error":"Missing required field id"}).encode("utf-8"))
            return

        for i, process_config in enumerate(Globals.thread_manager.process_metadata):
            if process_config["id"] == payload["id"]:
                self._set_headers()
                self.wfile.write(json.dumps(process_config["handle"].get_status()).encode("utf-8"))
                return
        self._set_headers(404)
        self.wfile.write(json.dumps({"error":"Component with ID does not exist"}).encode("utf-8"))

    def start_component_from_json(self):
        is_valid_token, perms = self._get_permissions()
        if not is_valid_token:
            self._send_unauthorized()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        payload = {}
        try:
            payload = json.loads(post_data)
        except json.JSONDecodeError:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": "malformed JSON"}).encode("utf-8"))
            return

        required_fields = ("id", "type", "config_json", "rf")
        missing = [k for k in required_fields if k not in payload]
        if missing:
            self._set_headers(400)
            self.wfile.write(json.dumps({
                "error": "Missing required fields",
                "missing": missing,
                "required": list(required_fields)
            }).encode("utf-8"))
            return

        component_type = payload["type"]
        if component_type not in CONFIG_CONVERTERS:
            self._set_headers(400)
            self.wfile.write(json.dumps({
                "error": f"Unsupported component type: {component_type}",
                "supported_types": list(CONFIG_CONVERTERS.keys())
            }).encode("utf-8"))
            return

        converter = CONFIG_CONVERTERS[component_type]

        try:
            config_str = converter.from_json(payload["config_json"])
        except ValueError as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({
                "error": "Configuration validation failed",
                "details": str(e)
            }).encode("utf-8"))
            return
        except Exception as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({
                "error": "Configuration conversion failed",
                "details": str(e)
            }).encode("utf-8"))
            return

        if component_type not in perms:
            self._set_headers(403)
            self.wfile.write(json.dumps({"error":"unauthorized to start that component"}).encode("utf-8"))
            return

        if any(p["id"] == payload["id"] for p in Globals.thread_manager.process_metadata):
            self._set_headers(409)
            self.wfile.write(json.dumps({"error": "ID conflict with existing component"}).encode("utf-8"))
            return

        if not os.path.isdir("/host/.generated/"):
            os.makedirs("/host/.generated", exist_ok=True)

        file_ext = {
            "rtue": "conf",
            "sniffer": "toml"
        }.get(component_type, "yaml")

        config_file = f"/host/.generated/{payload['id']}.{file_ext}"

        try:
            with open(config_file, "w") as f:
                f.write(config_str)
        except IOError as e:
            self._set_headers(500)
            self.wfile.write(json.dumps({"error":f"Failed to write config to file {config_file}"}))
            return

        new_process_config = {
            "config_file": config_file,
            "name": payload["id"],
            "component": component_type,
            "rf": payload["rf"],
            "permissions": [],
        }

        Globals.thread_manager.start(new_process_config)

        self._set_headers()
        self.wfile.write(json.dumps({"msg":f"process started: {payload['id']}"}).encode("utf-8"))

    def get_component_schema(self):
        is_valid_token, _ = self._get_permissions()
        if not is_valid_token:
            self._send_unauthorized()
            return

        parts = self.path.split('/')
        if len(parts) < 3 or not parts[2]:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": "Missing component type"}).encode("utf-8"))
            return

        component_type = parts[2]

        if component_type not in CONFIG_CONVERTERS:
            self._set_headers(404)
            self.wfile.write(json.dumps({
                "error": f"Schema not found for component type: {component_type}",
                "available_types": list(CONFIG_CONVERTERS.keys())
            }).encode("utf-8"))
            return

        converter = CONFIG_CONVERTERS[component_type]

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": f"{component_type} Configuration",
            "type": "object",
            "required": converter.REQUIRED_KEYS,
            "properties": {}
        }

        if hasattr(converter, 'SCHEMA'):
            for key, type_hint in converter.SCHEMA.items():
                if isinstance(type_hint, tuple):
                    json_type = self._python_to_json_type(type_hint[0])
                else:
                    json_type = self._python_to_json_type(type_hint)
                schema["properties"][key] = {"type": json_type}

        self._set_headers()
        self.wfile.write(json.dumps(schema).encode("utf-8"))

    def _python_to_json_type(self, python_type):
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object"
        }
        return type_map.get(python_type, "string")


    def do_GET(self):
        if self.path.startswith("/list"):
            self.get_components()
        elif self.path.startswith("/schemas"):
            self.get_component_schema()
        else:
            self._send_nonexistent()

    def do_POST(self):
        if self.path.startswith("/start_from_json"):
            self.start_component_from_json()
        elif self.path.startswith("/start"):
            self.start_component()
        elif self.path.startswith("/stop"):
            self.stop_component()
        elif self.path.startswith("/logs"):
            self.get_component_logs()
        elif self.path.startswith("/health"):
            self.check_component_health()
        else:
            self._send_nonexistent()

