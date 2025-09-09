import urllib3
import requests

class ApiInterface():
    """
    Basic class to simplify making requests to the RT controller:
    does not include code for specific endpoints, only a way to make requests
    """
    def __init__(self, control_ip, control_port, control_token):
        # TODO: get rid of this
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.control_url = f"https://{control_ip}:{control_port}"
        self.auth_header = f"Bearer {control_token}"
        self.headers = {}

    def make_request(self, target_endpoint, payload=None):
        if(payload):
            return self._post_endpoint(target_endpoint, payload)
        else:
            return self._get_endpoint(target_endpoint)

    def _post_endpoint(self, target_endpoint, json_payload):
        logging.debug(f"Sending POST to {target_endpoint} with JSON:\n {json_payload}")
        headers = {"Authorization": auth_header, "Accept": "application/json", "User-Agent": "llm_worker/1.0", "Content-Type": "application/json"}
        try:
            response = requests.post(url=f"{self.control_url}{target_endpoint}", headers=headers, json=json_payload, verify=False)
            if response.status_code == 200:
                return True, response.json()
            return False, {"error": response.text}
        except requests.exceptions.RequestException as e:
            return False, {"error":str(e)}

    def _get_endpoint(self, target_endpoint):
        logging.debug(f"Sending GET to {target_endpoint}")
        self.headers = {"Authorization": auth_header, "Accept": "application/json", "User-Agent": "llm_worker/1.0"}
        try:
            response = requests.get(url=f"{self.control_url}{current_endpoint}", headers=headers, verify=False)
            if response.status_code == 200:
                return True, response.json()
            return False, {"error": response.text}
        except requests.exceptions.RequestException as e:
            return False, {"error":str(e)}
