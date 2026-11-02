"""Controller HTTP client (config mode backend).

Talks directly to the controller REST API (SystemControlHandler) at
/start_from_json and /stop, exactly like the MCP server does.
"""

from __future__ import annotations

import requests


class ControllerClient:
    def __init__(self, base_url: str = "http://localhost:1343", token: str = "default_changeme", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}", "User-Agent": "ran-tester-automation/1.0"})

    def _post(self, endpoint: str, payload: dict):
        return self.session.post(f"{self.base_url}/{endpoint}", json=payload, verify=False, timeout=self.timeout)

    def list_components(self) -> list:
        resp = self.session.get(f"{self.base_url}/list", verify=False, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("running", [])

    def start(self, component_type: str, config: dict, rf: dict, component_repo: str | None = None) -> dict:
        payload: dict = {
            "id": config["id"],
            "type": component_type,
            "config_json": config,
            "rf": rf,
        }
        if component_repo:
            payload["component"] = component_repo
        resp = self._post("start_from_json", payload)
        if resp.status_code >= 400:
            return {"ok": False, "error": resp.text, "status_code": resp.status_code}
        return {"ok": True, "data": resp.json()}

    def stop(self, run_id: str) -> dict:
        resp = self._post("stop", {"id": run_id})
        if resp.status_code >= 400:
            return {"ok": False, "error": resp.text, "status_code": resp.status_code}
        return {"ok": True, "data": resp.json()}

    def health(self, run_id: str) -> dict:
        resp = self._post("health", {"id": run_id})
        if resp.status_code >= 400:
            return {"ok": False, "error": resp.text, "status_code": resp.status_code}
        return {"ok": True, "data": resp.json()}

    def logs(self, run_id: str, component_type: str = "ssb_spoofer") -> dict:
        resp = self._post("logs", {"id": run_id, "type": component_type})
        if resp.status_code >= 400:
            return {"ok": False, "error": resp.text, "status_code": resp.status_code}
        return {"ok": True, "data": resp.json()}