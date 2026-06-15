import json
from pathlib import Path

from pystack_api.main import app


def main() -> None:
    output_path = Path("openapi.json")
    output_path.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
