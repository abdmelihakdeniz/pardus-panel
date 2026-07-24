import sys

from pardus_panel.i18n import configure


def main() -> int:
    configure()

    from pardus_panel.application.app import PardusPanelApplication

    return int(PardusPanelApplication().run(sys.argv))


if __name__ == "__main__":
    raise SystemExit(main())
