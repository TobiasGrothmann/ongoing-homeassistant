"""Constants for the Ongoing integration."""

from datetime import timedelta
import logging

DOMAIN = "ongoing"

LOGGER = logging.getLogger(__package__)

MANUFACTURER = "Ongoing"

CONF_GROUP_KEY = "group_key"

# The `groupNotes` HTTPS function in the app's Firebase project.
ENDPOINT_URL = "https://us-central1-ongoing-34fe1.cloudfunctions.net/groupNotes"

# Notes change a few times a day; phones learn about changes through push,
# Home Assistant polls. Every poll reads one Firestore document per note, so
# the interval sets the Firebase read budget: 3:30 keeps a few lists of a few
# dozen notes well inside the free quota.
DEFAULT_SCAN_INTERVAL = timedelta(minutes=3, seconds=30)
