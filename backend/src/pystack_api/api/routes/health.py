from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", operation_id="getHealth")
def get_health() -> dict[str, str]:
    return {"status": "ok"}
