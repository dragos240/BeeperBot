import logging as log

from .beeperbot.log import log
from .beeperbot.settings import Settings
from .beeperbot.ui.layout import Layout
from .beeperbot.ui.controller import Controller

SCRIPT_PY_VERSION = "0.1.0"

params = {
    "display_name": "BeeperBot",
    "is_tab": True
}


def load_file(fname: str) -> str:
    with open(fname, "r") as f:
        return f.read()


def ui(launch: bool = False):
    api_ext_loaded = True

    try:
        from modules import shared

        if shared.args \
                and shared.args.extensions \
                and "api" not in shared.args.extensions:
            api_ext_loaded = False
    except ImportError:
        api_ext_loaded = False

    if not launch and not api_ext_loaded:
        log.error("API extension not enabled, quitting...")
        return

    settings = Settings()
    layout = Layout(settings)
    Controller(layout)


def custom_css() -> str:
    return ""


def custom_js() -> str:
    return ""


if __name__ == '__main__':
    ui(launch=True)
