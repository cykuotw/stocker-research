"""Access the Knowledge pool created during application startup."""

from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request

from knowledge.app.database.factory import DatabaseResources


def get_database(request: Request) -> DatabaseResources:
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(status_code=503, detail="database_unavailable")
    return cast(DatabaseResources, database)


Database = Annotated[DatabaseResources, Depends(get_database)]
