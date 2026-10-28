"""Create and seed the demo databases: ``python -m app.seed [--reset]``."""

from __future__ import annotations

import argparse
import logging

from app.core.database import router
from app.services.provisioning import provision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true", help="re-seed every user's data"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    created = provision(router, reset=args.reset)
    print(f"Done. New databases: {', '.join(created) or 'none'}")


if __name__ == "__main__":
    main()
