import logging as log

from .beeperbot import bot
from .beeperbot.ui import Layout

SCRIPT_PY_VERSION = "0.1.0"

params = {
    "display_name": "BeeperBot",
    "is_tab": True
}


def load_file(fname: str) -> str:
    with open(fname, "r") as f:
        return f.read()


def ui(launch: bool = False):
    log.basicConfig(level=log.INFO)
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

    layout = Layout()

    layout.layout_ui(launch)


def custom_css() -> str:
    return """
        #refresh-characters, #channels-column-box {
            height: 100%;
        }
    """


def custom_js() -> str:
    return ""


if __name__ == '__main__':
    ui(launch=True)
