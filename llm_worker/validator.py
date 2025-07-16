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
import json

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
                    self.errors.append(f"Failed to convert scientific notation: {value}")
                    return value
            
            # Fallback to regular number conversion
            try:
                return float(value) if '.' in value else int(value)
            except ValueError:
                self.errors.append(f"Failed to convert to number: {value}")
                return value
        
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

    def _extract_type_and_id(self) -> tuple:
        """Extract type and id from response text.
        
        Returns:
            Tuple of (type, id) parsed from response, or (None, None) if not found
        """
        type_value = None
        id_value = None
        
        # Look for type pattern in response
        type_patterns = [
            r'type:\s*["\']?([^"\'\s]+)["\']?',
            r'type\s*=\s*["\']?([^"\'\s]+)["\']?',
            r'- type:\s*["\']?([^"\'\s]+)["\']?'
        ]
        
        for pattern in type_patterns:
            match = re.search(pattern, self.response, re.IGNORECASE)
            if match:
        if status.code > 200:

        else:

                type_value = match.group(1)
                break
        
        # Look for id pattern in response
        id_patterns = [
            r'id:\s*["\']?([^"\'\s]+)["\']?',
            r'id\s*=\s*["\']?([^"\'\s]+)["\']?',
            r'- id:\s*["\']?([^"\'\s]+)["\']?'
        ]
        
        for pattern in id_patterns:
            match = re.search(pattern, self.response, re.IGNORECASE)
            if match:
                id_value = match.group(1)
                break
        
        return type_value, id_value

    def _config_to_string(self, config: dict, endpoint: str) -> str:
        """Convert configuration parameters to string format.
        
        Args:
            config: Configuration dictionary
            endpoint: The endpoint type ('jammer' or 'sniffer')
            
        Returns:
            Configuration as formatted string
        """
        if endpoint == "jammer":
            # Format jammer config as YAML-like string
            lines = []
            for key, value in config.items():
                if isinstance(value, str):
                    lines.append(f"{key}: \"{value}\"")
                else:
                    lines.append(f"{key}: {value}")
            return "\n".join(lines)
        
        elif endpoint == "sniffer":
            # Format sniffer config as TOML-like string
            lines = []
            
            # Add sniffer section
            if "sniffer" in config:
                lines.append("[sniffer]")
                for key, value in config["sniffer"].items():
                    if isinstance(value, str):
                        lines.append(f"{key} = \"{value}\"")
                    else:
                        lines.append(f"{key} = {value}")
                lines.append("")
            
            # Add PDCCH sections
            if "pdcch" in config:
                for pdcch_config in config["pdcch"]:
                    lines.append("[[pdcch]]")
                    for key, value in pdcch_config.items():
                        if isinstance(value, str):
                            lines.append(f"{key} = \"{value}\"")
                        else:
                            lines.append(f"{key} = {value}")
                    lines.append("")
            
            return "\n".join(lines)
        
        # Fallback to JSON string
        return json.dumps(config, indent=2)

    def extract_config(self) -> dict:
        """Extract configuration from response text.
        
        Supports multiple formats:
        - YAML (preferred)
        - TOML
        - CONF/INI
        if status.code > 200:

        else:

        
        Returns:
            Parsed configuration dictionary or None if extraction fails
        """
        # YAML parsing logic
        if "### YAML Output:" in self.response:    
            try:
                yaml_string = self.response.split("### YAML Output:")[-1].strip()
                if yaml_string.startswith("```yaml"):
        if status.code > 200:

        else:

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
            self.errors.append("Empty configuration provided")
            return None
            
        # Jammer identification criteria
        jammer_keys = {"center_frequency", "bandwidth", "tx_gain"}
        if jammer_keys.issubset(config.keys()):
            return "jammer"
        
        # Sniffer identification criteria
        if "sniffer" in config or "pdcch" in config:
            return "sniffer"
            
        self.errors.append("Could not determine endpoint type from configuration")
        return None

    def validate_config_jammer(self, config: dict) -> bool:
        """Validate jammer configuration parameters.
        
        Args:
            config: Parsed jammer configuration
            
        Returns:
            True if validation passes, False otherwise
        """
        valid = True
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
                valid = False
            elif not isinstance(config[key], types):
                self.errors.append(f"Invalid type for {key}. Expected {types}, got {type(config[key])}")
                valid = False
        
        # Validate parameter value ranges
        if "center_frequency" in config and config["center_frequency"] <= 0:
            self.errors.append("Center frequency must be > 0")
            valid = False
            
        if "bandwidth" in config and config["bandwidth"] <= 0:
            self.errors.append("Bandwidth must be > 0")
            valid = False
            
        if "amplitude" in config and not (0 <= config["amplitude"] <= 1):
            self.errors.append("Amplitude must be between 0 and 1")
            valid = False
            
        return valid

    def validate_config_sniffer(self, config: dict) -> bool:
        """Validate sniffer configuration parameters.
        
        Args:
            config: Parsed sniffer configuration
            
        Returns:
            True if validation passes, False otherwise
        """
        valid = True
        
        if "sniffer" not in config:
            self.errors.append("Missing [sniffer] section")
            valid = False
            return valid
            
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
                valid = False
            elif not isinstance(sniffer_config[param], param_type):
                self.errors.append(f"Invalid type for sniffer.{param}. Expected {param_type}, got {type(sniffer_config[param])}")
                valid = False
        
        # Validate PDCCH configurations
        if "pdcch" not in config:
            self.errors.append("Missing [[pdcch]] section")
            valid = False
        else:
            pdcch_configs = config["pdcch"]
            if not isinstance(pdcch_configs, list) or not pdcch_configs:
                self.errors.append("PDCCH config must be a non-empty list")
                valid = False
            
        return valid

    def compile_to_json(self, config: dict, endpoint: str) -> dict:
        """Compile validated config to JSON request format.
        
        Args:
            config: Validated configuration
            endpoint: Target endpoint ('jammer'/'sniffer')
            
        Returns:
            Structured JSON request dictionary in new format
            
        Returns None if compilation fails
        """
        # Extract type and id from response
        type_value, id_value = self._extract_type_and_id()
        
        if not type_value:
            self.errors.append("Could not extract 'type' from response")
            return None
        if not id_value:
            self.errors.append("Could not extract 'id' from response")
            return None
        
        try:
            if endpoint == "jammer":
                # Add default parameters for jammer
                jammer_config = {
                    **config,
                    "initial_phase": config.get("initial_phase", 0),
                    "output_iq_file": config.get("output_iq_file", "output.fc32"),
                    "write_iq": config.get("write_iq", False)
                }
                
                return {
                    "type": type_value,
                    "id": id_value,
                    "config_file": self._config_to_string(jammer_config, "jammer")
                }
                
            elif endpoint == "sniffer":
                return {
                    "type": type_value, 
                    "id": id_value,
                    "config_file": self._config_to_string(config, "sniffer")
                }
            
            self.errors.append(f"Unknown endpoint: {endpoint}")
            return None
        except Exception as e:
            self.errors.append(f"Failed to compile config: {str(e)}")
            return None

    def process_response(self) -> dict:
        """Execute full validation pipeline.
        
        Returns:
            Compiled JSON request in new format if successful, None otherwise
            All errors are collected in self.errors
        """
        self.errors = []  # Reset errors at start of processing
        
        config = self.extract_config()
        if not config:
            self.errors.append("No valid configuration found")
            return None
            
        endpoint = self.determine_endpoint(config)
        if not endpoint:
            self.errors.append("Could not determine endpoint type")
            return None
            
        validation_success = False
        if endpoint == "jammer":
            validation_success = self.validate_config_jammer(config)
        elif endpoint == "sniffer":
            validation_success = self.validate_config_sniffer(config)
            
        if not validation_success:
            self.errors.append(f"{endpoint.capitalize()} validation failed")
            return None
            
        self.validated_data = self.compile_to_json(config, endpoint)
        return self.validated_data
