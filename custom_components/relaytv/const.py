"""Constants for the RelayTV Web UI panel integration."""

DOMAIN = "relaytv"

PLATFORMS: list[str] = ["media_player"]

CONF_BASE_URL = "base_url"
CONF_SERVER_NAME = "server_name"
CONF_PANEL_TITLE = "panel_title"
CONF_PANEL_ICON = "panel_icon"
CONF_PANEL_PATH = "panel_path"
CONF_PANEL_ENABLED = "panel_enabled"
CONF_PANEL_TARGET_ENTRY_ID = "panel_target_entry_id"

DEFAULT_PANEL_TITLE = "RelayTV"
DEFAULT_PANEL_ICON = "mdi:cast"
DEFAULT_PANEL_PATH = "relaytv"

# Services
SERVICE_SMART_URL = "smart_url"
SERVICE_PLAY_NOW = "play_now"
SERVICE_ANNOUNCE = "announce"
SERVICE_PLAY_TEMPORARY = "play_temporary"
SERVICE_OVERLAY = "overlay"
SERVICE_PLAY_SYNCED = "play_synced"
SERVICE_SNAPSHOT = "snapshot"
SERVICE_PLAY_WITH_RESUME = "play_with_resume"

CONF_SENSOR_STREAM_MAPPINGS = "sensor_stream_mappings"
CONF_RESUME_POSITIONS = "resume_positions"

# Data keys
DATA_COORDINATOR = "coordinator"
DATA_API = "api"
DATA_STORE = "store"
DATA_PANEL_SETTINGS = "panel_settings"
DATA_LAST_SNAPSHOT_URL = "last_snapshot_url"
