import os
import tempfile

# Tests never use real keys or the real database.
_tmp = tempfile.mkdtemp(prefix="likhkedo-test-")
os.environ["DATA_DIR"] = _tmp
os.environ["GNANI_API_KEY"] = "test-key"
os.environ["EVON_BASE_URL"] = "http://evon.test/v1"
os.environ["EVON_API_KEY"] = "test-evon-key"
# pin the Evon engine so a developer's .env (e.g. EVON_PROVIDER=llamacpp) doesn't change test behaviour
os.environ["EVON_PROVIDER"] = "vllm"
os.environ["EVON_MODEL"] = "gnani/gnani-evon-v3.3-30B-A3B"
os.environ["EVON_QUANT"] = ""
os.environ["EVON_LABEL"] = ""
os.environ["EVON_TIMEOUT"] = "90"
os.environ["DEMO_ONLY"] = "false"
os.environ["ADMIN_SECRET"] = "test-admin"

import pytest  # noqa: E402

from app import db  # noqa: E402
from app.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(autouse=True)
def fresh_db():
    from app import ratelimit
    ratelimit.reset()
    db.init_db("sqlite://")
    yield
