import sys
import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pardus_panel.i18n import configure


def _version() -> str:
    try:
        return version("pardus-panel")
    except PackageNotFoundError:
        project = Path(__file__).resolve().parents[2] / "pyproject.toml"
        try:
            with project.open("rb") as source:
                return str(tomllib.load(source)["project"]["version"])
        except (OSError, KeyError, tomllib.TOMLDecodeError):
            return "unknown"


def main() -> int:
    if any(argument in {"-v", "--version"} for argument in sys.argv[1:]):
        print(f"pardus-panel {_version()}")
        return 0

    configure()

    from pardus_panel.application.app import PardusPanelApplication

    return int(PardusPanelApplication().run(sys.argv))


if __name__ == "__main__":
    raise SystemExit(main())
