from typing import Annotated

from fastapi import Depends

from pystack_api.db.connection import DatabaseConnection, get_connection

ConnectionDependency = Annotated[DatabaseConnection, Depends(get_connection)]
