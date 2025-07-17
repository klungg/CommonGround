import os
import json
import logging

logger = logging.getLogger(__name__)

def load_native_mcp_config():
    """
    Loads native MCP server configurations from environment variables or a configuration file.
    
    Returns:
        dict: A dictionary of enabled MCP server configurations.
    """
    config_str = os.getenv("NATIVE_MCP_SERVERS_CONFIG")
    config_path = os.getenv("NATIVE_MCP_SERVERS_CONFIG_PATH", "mcp.json") # Add default value
    config = {}

    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.debug("native_mcp_config_loaded_from_file", extra={"config_path": config_path})
        except Exception as e:
            logger.error("native_mcp_config_file_load_failed", extra={"config_path": config_path, "error": str(e)})
    elif config_str:
        try:
            config = json.loads(config_str)
            logger.debug("native_mcp_config_loaded_from_env")
        except json.JSONDecodeError as e:
            logger.error("native_mcp_config_env_parse_failed", extra={"error": str(e)})

    # Return only enabled server configurations
    enabled_servers = {}
    if isinstance(config, dict) and "mcpServers" in config:
         for name, server_conf in config["mcpServers"].items():
             if isinstance(server_conf, dict) and server_conf.get("enabled", False):
                 # [MODIFIED] Only require the transport field to be present
                 if "transport" in server_conf:
                     enabled_servers[name] = server_conf
                 else:
                    logger.warning("native_mcp_server_config_incomplete", extra={"server_name": name, "missing_field": "transport"})
             else:
                 logger.debug("native_mcp_server_disabled_or_invalid", extra={"server_name": name})

    logger.info("native_mcp_servers_loaded", extra={"enabled_count": len(enabled_servers)})
    return enabled_servers

# Global configuration
NATIVE_MCP_SERVERS = load_native_mcp_config()
