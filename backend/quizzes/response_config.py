import json
from pathlib import Path
from threading import Lock


_CONFIG_PATH = Path(__file__).resolve().parent / 'response_config.json'
_CACHE = {'data': None, 'mtime': None}
_LOCK = Lock()


def load_response_config():
    """
    Load the response configuration JSON file. The result is cached and reloaded
    whenever the file timestamp changes so edits take effect without a restart.
    """
    try:
        mtime = _CONFIG_PATH.stat().st_mtime
    except FileNotFoundError as exc:
        raise FileNotFoundError(f'Response config not found at {_CONFIG_PATH}') from exc
    with _LOCK:
        if _CACHE['data'] is None or _CACHE['mtime'] != mtime:
            with _CONFIG_PATH.open(encoding='utf-8') as config_file:
                _CACHE['data'] = json.load(config_file)
                _CACHE['mtime'] = mtime
        return _CACHE['data']
