"""Constants for the Dockmaster integration."""

from datetime import timedelta

DOMAIN = "dockmaster"

CONF_HOST = "host"
CONF_PORT = "port"
DEFAULT_PORT = 3000

UPDATE_INTERVAL = timedelta(seconds=30)
# /api/apps runs one SSH/docker call per app on the NAS, so allow a generous timeout.
REQUEST_TIMEOUT = 30

HOST_LABELS = {"nas": "NAS", "pi": "Pi"}
