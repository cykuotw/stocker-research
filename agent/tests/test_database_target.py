"""The renamed research database remains the only Agent connection target."""

import pytest
from pydantic import ValidationError

from stocker_agent.config.app import AppSettings


def test_research_database_default():
    assert AppSettings().db_name == "stocker_research"


@pytest.mark.parametrize(
    "database", ["stocker_agent_runtime", "stocker_knowledge", "expense_tracker"]
)
def test_other_database_targets_are_rejected(database):
    with pytest.raises(
        ValidationError, match="Runtime may connect only to stocker_research"
    ):
        AppSettings(db_name=database)
    with pytest.raises(
        ValidationError, match="Runtime may connect only to stocker_research"
    ):
        AppSettings(database_uri=f"postgresql://localhost/{database}")
