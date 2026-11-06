import os
import tempfile

# Tests never use real keys or the real database.
_tmp = tempfile.mkdtemp(prefix="likhkedo-test-")
os.environ["DATA_DIR"] = _tmp
os.environ["GNANI_API_KEY"] = "test-key"
os.environ["EVON_BASE_URL"] = "http://evon.test/v1"
os.environ["EVON_API_KEY"] = "test-evon-key"
os.environ["DEMO_ONLY"] = "false"
os.environ["ADMIN_SECRET"] = "test-admin"

import pytest  # noqa: E402

from app import db  # noqa: E402
from app.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(autouse=True)
def fresh_db():
    db.init_db("sqlite://")
    yield
