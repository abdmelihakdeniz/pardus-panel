from importlib import resources


def read_text_resource(category: str, name: str) -> str:
    return (
        resources.files("pardus_panel")
        .joinpath("data", category, name)
        .read_text(encoding="utf-8")
    )
