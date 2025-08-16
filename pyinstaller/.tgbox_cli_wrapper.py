from pathlib import Path
from sys import path as sys_path

sys_path = [str(Path(__name__).parent.parent)]
from main import safe_tgbox_cli_startup

if __name__ == '__main__':
    safe_tgbox_cli_startup()
