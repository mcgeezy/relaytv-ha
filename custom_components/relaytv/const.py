"""Constants for the RelayTV Web UI panel integration."""

DOMAIN = "relaytv"

PLATFORMS: list[str] = ["media_player"]

CONF_BASE_URL = "base_url"
CONF_PANEL_TITLE = "panel_title"
CONF_PANEL_ICON = "panel_icon"
CONF_PANEL_PATH = "panel_path"

DEFAULT_PANEL_TITLE = "RelayTV"
DEFAULT_PANEL_ICON = "mdi:cast"
DEFAULT_PANEL_PATH = "relaytv"

# Services
SERVICE_SMART_URL = "smart_url"
SERVICE_PLAY_NOW = "play_now"
SERVICE_ANNOUNCE = "announce"

# Data keys
DATA_COORDINATOR = "coordinator"
DATA_API = "api"
