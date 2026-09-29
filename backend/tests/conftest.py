import logging
import os
import tempfile

logger = logging.getLogger("backend.tests.conftest")

# This MUST run at import time, not in a fixture: pytest imports this conftest
# before collecting test modules, and those modules import the local stores
# (services.local_store, utils.job_queue) which compute DATA_DIR at import time.
# Setting the env here guarantees the throwaway dir is used for the whole run.
os.environ["RANKFORGE_DATA_DIR"] = tempfile.mkdtemp(prefix="rankforge-tests-")
os.environ.setdefault("TESTING", "1")
