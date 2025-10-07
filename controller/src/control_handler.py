import json
import http.server
from globals import Config, Globals
import logging
import os
import logging
from rtue_worker_thread import rtue
from jammer_worker_thread import jammer
from sniffer_worker_thread import sniffer
from decoder_worker_thread import decoder
from llm_worker_thread import llm_worker
from rach_worker_thread import rach_agent
from uu_agent_worker_thread import uu_agent

class SystemControlHandler(http.server.SimpleHTTPRequestHandler):
    def _get_permissions(self):
        is_valid_token = False
        permissions = []
        auth_header = self.headers.get("Authorization")
        if not auth_header.startswith("Bearer "):
            return False, []
        token = auth_header.removeprefix("Bearer").strip()
        for process_config in Globals.process_metadata:
            for existing_tok in process_config["token"].keys():
                is_valid_token = existing_tok == token
                if is_valid_token:
                    permissions = process_config["token"][token]
                    break
            if is_valid_token:
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
        Globals.process_metadata
        is_valid_token, perms = self._get_permissions()
        if not is_valid_token:
            self._send_unauthorized()
            return

        response_list = []
        for process_config in Globals.process_metadata:
            if process_config["type"] not in perms:
                continue
            response_list.append({
                "id": process_config["id"],
                "type": process_config["type"],
                "config_file": process_config["config"]["config_file"],
                "permissions": process_config["config"]["permissions"]
            })
        self._set_headers()
        self.wfile.write(json.dumps({"running": response_list}).encode("utf-8"))

    def get_component_logs(self):
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

        query_api = Config.influxdb_client.query_api()
        result = query_api.query(org=Config.influxdb_client.org, query=query)

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
        Globals.process_metadata
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
        logging.debug(f"{payload}")
        
        if not all(k in payload for k in ("id", "type", "config_str", "rf")):
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing required fields: id, type, config_str, rf"}).encode("utf-8"))
                return

        rf_type = payload.get("rf").get("type", None)
        if not rf_type:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing required fields for rf: type"}).encode("utf-8"))
                return

        rf_keys = ("images_dir", "type")
        if rf_type == "zmq":
            rf_keys = ("tcp_subnet", "gateway")

        if not all(k in payload["rf"] for k in rf_keys):
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing required fields for rf: type, images_dir"}).encode("utf-8"))
                return

        if any(p["id"] == payload["id"] for p in Globals.process_metadata):
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

        # NOTE: config path must be translated to the host path
        config_file = config_file.replace("/host", os.getenv("DOCKER_SYSTEM_DIRECTORY"))
        logging.debug(f"Starting component with filename on host {config_file}")

        process_class = None
        try:
            process_class = globals()[payload["type"]]
        except KeyError:
            self._set_headers(403)
            self.wfile.write(json.dumps({"error":f"Invalid process type {payload['type']}"}).encode("utf-8"))
            return

        new_process_config = {
            "config_file": config_file,
            "id": payload["id"],
            "type": payload["type"],
            "rf": payload["rf"],
            "permissions": [],
        }

        process_handle = process_class(Config.influxdb_client, Config.docker_client, new_process_config)


        Globals.process_metadata.append({
            'id': payload['id'],
            'type': payload['type'],
            'config': new_process_config,
            'handle': process_handle,
            'token': {None: []}
        })
        process_handle.start()

        self._set_headers()
        self.wfile.write(json.dumps({"msg":f"process started: {payload['id']}"}).encode("utf-8"))

    def stop_component(self):
        Globals.process_metadata
        is_valid_token, perms = self._get_permissions()
        if not is_valid_token:
            self._send_unauthorized()
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        payload = {}
        try:
            payload = json.loads(post_data)
            logging.info(f"Stop payload: {payload}")
        except json.JSONDecodeError:
            self._send_unauthorized()
            return

        if "id" not in payload.keys():
            self._set_headers(400)
            self.wfile.write(json.dumps({"error":"Missing required field id"}).encode("utf-8"))
            return

        for i, process_config in enumerate(Globals.process_metadata):
            if process_config["id"] == payload["id"]:
                if process_config["type"] not in perms:
                    continue
                process_config["handle"].stop()
                self._set_headers()
                self.wfile.write(json.dumps({"id":process_config["id"]}).encode("utf-8"))
                del Globals.process_metadata[i]
                return
        self._set_headers(404)
        self.wfile.write(json.dumps({"error":"Component with ID does not exist"}).encode("utf-8"))

    def check_component_health(self):
        Globals.process_metadata
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
            self._send_unauthorized()
            return

        if "id" not in payload.keys():
            self._set_headers(400)
            self.wfile.write(json.dumps({"error":"Missing required field id"}).encode("utf-8"))
            return

        for i, process_config in enumerate(Globals.process_metadata):
            if process_config["id"] == payload["id"]:
                if process_config["type"] not in perms:
                    continue
                self._set_headers()
                self.wfile.write(json.dumps(process_config["handle"].get_status()).encode("utf-8"))
                return
        self._set_headers(404)
        self.wfile.write(json.dumps({"error":"Component with ID does not exist"}).encode("utf-8"))


    def do_GET(self):
        if self.path.startswith("/list"):
            self.get_components()
        else:
            self._send_nonexistent()

    def do_POST(self):
        if self.path.startswith("/start"):
            self.start_component()
        elif self.path.startswith("/stop"):
            self.stop_component()
        elif self.path.startswith("/logs"):
            self.get_component_logs()
        elif self.path.startswith("/health"):
            self.check_component_health()
        else:
            self._send_nonexistent()

