from __future__ import annotations

import argparse
import os
import sys
import urllib.parse

from render_infra import DEFAULT_API_BASE_URL, POSTGRES_NAME, InfraError, RenderClient, render_api_key


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print the DBmate-compatible external URL for the Render Postgres database."
    )
    parser.add_argument("--database", default=POSTGRES_NAME, help="Render Postgres database name.")
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    return parser.parse_args()


def dbmate_url(connection_string: str) -> str:
    parts = urllib.parse.urlsplit(connection_string)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)

    if not any(key == "sslmode" for key, _ in query):
        query.append(("sslmode", "require"))

    # DBmate documents postgres:// URLs; Render's API currently returns
    # postgresql://, which libpq accepts but older tooling may not.
    return urllib.parse.urlunsplit(
        parts._replace(scheme="postgres", query=urllib.parse.urlencode(query))
    )


def main() -> int:
    if override := os.environ.get("DBMATE_PROD_DATABASE_URL"):
        print(dbmate_url(override))
        return 0

    args = parse_args()
    try:
        client = RenderClient(render_api_key(), args.api_base_url)
        postgres_id = client.get_postgres_id(args.database)
        info = client.request("GET", f"/postgres/{postgres_id}/connection-info")
    except InfraError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(dbmate_url(info["externalConnectionString"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
