"""Keep tests independent of local developer credentials, including collection."""

from stocker_agent.config import base

# Applied before graph imports during collection; dotenv tests use temporary files.
base.ENV_FILE = None
