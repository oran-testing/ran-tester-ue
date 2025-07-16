"""
Configuration Validator for RF Attack Systems

This module provides comprehensive validation and processing of YAML/TOML/CONF configurations
for RF-based attack systems (sniffer/jammer). It handles:
- Scientific notation conversion
- Multi-format configuration parsing
- Endpoint-specific validation
- Configuration compilation to JSON
"""

import yaml
import tomllib
import configparser
import os
import re

class ResponseValidator:
    """Validates and processes configuration responses for RF attack systems.
    
    Attributes:
        response (str): Raw configuration response text
        validated_data (dict): Processed and validated configuration
        errors (list): Accumulated validation error messages
    """

    def __init__(self, response: str):
        """Initialize validator with raw response text.
        
        Args:
            response: Raw configuration string containing YAML/TOML/CONF data
        """
        self.response = response
        self.validated_data = {}
        self.errors = []

    def _convert_scientific_notation(self, value):
        """Convert scientific notation strings to numeric values.
        
        Handles:
        - Quoted/unquoted scientific notation (e.g., "9.15e8" or 9.15e8)
        - Regular numeric strings
        - Existing numeric types
        
        Args:
            value: Input value to convert
            
        Returns:
            Converted numeric value or original value if conversion not applicable
        """
        if isinstance(value, str):
            value = value.strip('"\'')

            # Scientific notation pattern matching
            sci_pattern = r'^[-+]?(\d+\.?\d*|\.\d+)[eE][-+]?\d+$'
            if re.match(sci_pattern, value):
                try:
                    return float(value)
                except ValueError:
                    pass
            
            # Fallback to regular number conversion
            try:
                return float(value) if '.' in value else int(value)
            except ValueError:
                pass
        
        return value

    def _normalize_config_values(self, config):
        """Recursively normalize configuration values.
        
        Applies scientific notation conversion throughout nested structures.
        
        Args:
            config: Configuration dictionary/list to normalize
            
        Returns:
            Normalized configuration with proper numeric types
        """
        if isinstance(config, dict):
            return {key: self._normalize_config_values(value) 
                   for key, value in config.items()}
        elif isinstance(config, list):
            return [self._normalize_config_values(item) 
                   for item in config]
        return self._convert_scientific_notation(config)

    def extract_config(self) -> dict:
        """Extract configuration from response text.
        
        Supports multiple formats:
        - YAML (preferred)
        - TOML
        - CONF/INI
        
        Returns:
            Parsed configuration dictionary or None if extraction fails
        """
        # YAML parsing logic
        if "### YAML Output:" in self.response:    
            try:
                yaml_string = self.response.split("### YAML Output:")[-1].strip()
                if yaml_string.startswith("```yaml"):
                    yaml_string = yaml_string.split("```yaml\n", 1)[-1]
                    yaml_string = yaml_string.rsplit("```", 1)[0] if "```" in yaml_string else yaml_string
                
                config = yaml.safe_load(yaml_string)
                return self._normalize_config_values(config) if isinstance(config, dict) else None
            except (yaml.YAMLError, IndexError) as e:
                self.errors.append(
                    "YAML parsing failed. Ensure proper syntax:\n"
                    "```yaml\nkey: value\nfrequency: 9.15e8\n```")

        # TOML parsing logic
        if "### TOML Output:" in self.response:
            try:
                toml_string = self.response.split("### TOML Output:")[-1].strip()
                if toml_string.startswith("```toml"):
                    toml_string = toml_string.split("```toml\n", 1)[-1]
                    toml_string = toml_string.rsplit("```", 1)[0] if "```" in toml_string else toml_string

                config = tomllib.loads(toml_string)
                return self._normalize_config_values(config) if isinstance(config, dict) else None
            except (tomllib.TOMLDecodeError, IndexError) as e:
                self.errors.append(
                    "TOML parsing failed. Use format:\n"
                    "```toml\n[section]\nkey = \"value\"\n```")

        # CONF/INI parsing logic
        if "### CONF Output:" in self.response:
            try:
                conf_string = self.response.split("### CONF Output:")[-1].strip()
                if conf_string.startswith("```ini"):
                    conf_string = conf_string.split("```ini\n", 1)[-1]
                    conf_string = conf_string.rsplit("```", 1)[0] if "```" in conf_string else conf_string
                
                parser = configparser.ConfigParser()
                parser.read_string(conf_string)
                config = {section: dict(parser.items(section)) 
                         for section in parser.sections()}
                return self._normalize_config_values(config) if config else None
            except (configparser.Error, IndexError) as e:
                self.errors.append(
                    "CONF parsing failed. Use format:\n"
                    "```ini\n[section]\nkey = value\n```")
            
        return None

    def determine_endpoint(self, config: dict) -> str:
        """Determine endpoint type from configuration structure.
        
        Args:
            config: Parsed configuration dictionary
            
        Returns:
            Endpoint type ('jammer'/'sniffer') or None if undetermined
        """
        if not config:
            return None
            
        # Jammer identification criteria
        jammer_keys = {"center_frequency", "bandwidth", "tx_gain"}
        if jammer_keys.issubset(config.keys()):
            return "jammer"
        
        # Sniffer identification criteria
        if "sniffer" in config or "pdcch" in config:
            return "sniffer"
            
        return None

    def validate_config_jammer(self, config: dict) -> bool:
        """Validate jammer configuration parameters.
        
        Args:
            config: Parsed jammer configuration
            
        Returns:
            True if validation passes, False otherwise
        """
        required_keys = {
            "center_frequency": (int, float),
            "bandwidth": (int, float),
            "tx_gain": (int, float),
            "amplitude": (int, float),
            "amplitude_width": (int, float),
            "sampling_freq": (int, float),
            "num_samples": int
        }
        
        # Validate presence and type of required parameters
        for key, types in required_keys.items():
            if key not in config:
                self.errors.append(f"Missing required parameter: {key}")
                return False
            if not isinstance(config[key], types):
                self.errors.append(f"Invalid type for {key}. Expected {types}")
                return False
        
        # Validate parameter value ranges
        if config["center_frequency"] <= 0:
            self.errors.append("Center frequency must be > 0")
            return False
            
        if config["bandwidth"] <= 0:
            self.errors.append("Bandwidth must be > 0")
            return False
            
        if not (0 <= config["amplitude"] <= 1):
            self.errors.append("Amplitude must be 0-1")
            return False
            
        return True

    def validate_config_sniffer(self, config: dict) -> bool:
        """Validate sniffer configuration parameters.
        
        Args:
            config: Parsed sniffer configuration
            
        Returns:
            True if validation passes, False otherwise
        """
        if "sniffer" not in config:
            self.errors.append("Missing [sniffer] section")
            return False
            
        sniffer_config = config["sniffer"]
        
        required_sniffer_params = {
            "file_path": str,
            "sample_rate": int,
            "frequency": int,
            "nid_1": int,
            "ssb_numerology": int
        }
        
        # Validate sniffer section parameters
        for param, param_type in required_sniffer_params.items():
            if param not in sniffer_config:
                self.errors.append(f"Missing sniffer parameter: {param}")
                return False
            if not isinstance(sniffer_config[param], param_type):
                self.errors.append(f"Invalid type for sniffer.{param}")
                return False
        
        # Validate PDCCH configurations
        if "pdcch" not in config:
            self.errors.append("Missing [[pdcch]] section")
            return False
            
        pdcch_configs = config["pdcch"]
        if not isinstance(pdcch_configs, list) or not pdcch_configs:
            self.errors.append("PDCCH config must be non-empty list")
            return False
            
        return True

    def compile_to_json(self, config: dict, endpoint: str) -> dict:
        """Compile validated config to JSON request format.
        
        Args:
            config: Validated configuration
            endpoint: Target endpoint ('jammer'/'sniffer')
            
        Returns:
            Structured JSON request dictionary
            
        Raises:
            ValueError: For unknown endpoint types
        """
        if endpoint == "jammer":
            return {
                "endpoint": "jammer",
                "parameters": {
                    **config,
                    "initial_phase": config.get("initial_phase", 0),
                    "output_iq_file": config.get("output_iq_file", "output.fc32"),
                    "write_iq": config.get("write_iq", False)
                }
            }
        elif endpoint == "sniffer":
            return {
                "endpoint": "sniffer",
                "parameters": config
            }
        raise ValueError(f"Unknown endpoint: {endpoint}")

    def process_response(self) -> dict:
        """Execute full validation pipeline.
        
        Returns:
            Compiled JSON request
            
        Raises:
            ValueError: If any validation step fails
        """
        config = self.extract_config()
        if not config:
            raise ValueError("No valid configuration found")
            
        endpoint = self.determine_endpoint(config)
        if not endpoint:
            raise ValueError("Could not determine endpoint")
            
        if endpoint == "jammer":
            if not self.validate_config_jammer(config):
                raise ValueError("Jammer validation failed")
        elif endpoint == "sniffer":
            if not self.validate_config_sniffer(config):
                raise ValueError("Sniffer validation failed")
                
        self.validated_data = self.compile_to_json(config, endpoint)
        return self.validated_data


if __name__ == "__main__":
    test_response = """
    ### YAML Output:
    ```yaml
    amplitude: 0.9
    amplitude_width: 0.1
    center_frequency: "9.15e8"
    bandwidth: "1e7"
    tx_gain: 55
    sampling_freq: "2e7"
    num_samples: 20000
    ```
    """
    
    validator = ResponseValidator(test_response)
    try:
        result = validator.process_response()
        print("Validation successful:", result)
    except ValueError as e:
        print("Validation failed:", e)
        print("Details:", validator.errors)