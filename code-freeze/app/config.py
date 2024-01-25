import os

import version
import timestamp
import y
from default_config import cfg
from .event_bus import event_bus

CONFIG_DIR = '/config'
CONFIG_EXT = "yaml"


class Config:

    def __init__(self):
        # copy default configuration
        try:
            os.mkdir(CONFIG_DIR)
        except OSError:
            pass
        cf = os.listdir(CONFIG_DIR)
        for k, v in cfg.items():
            f = f"{CONFIG_DIR}/{k}.{CONFIG_EXT}"
            if not f in cf:
                with open(f, 'w') as stream:
                    stream.write(v)
        self.load_config()

    def load_config(self):
        self._dict = {}
        try:
            dir = os.getcwd()
            os.chdir(CONFIG_DIR)
            for file_name in os.listdir(CONFIG_DIR):
                with open(file_name) as stream:
                    section, _ = file_name.rsplit('.', 1)
                    self._dict[section] = y.load(stream, section)
            # constants
            app = self.get('app')
            if not app:
                app = self._dict['app']  = {}
            app['version'] = version.VERSION
            app['epoch_offset'] = timestamp.EPOCH_OFFSET

        finally:
            os.chdir(dir)       

    def reset(self):
        # recreate CONFIG_DIR from default_config
        for f in os.listdir(CONFIG_DIR):
            os.remove(f"{CONFIG_DIR}/{f}")
        for k, v in cfg.items():
            f = f"{CONFIG_DIR}/{k}.{CONFIG_EXT}"
            with open(f, 'w') as stream:
                stream.write(v)
        self.load_config()

    def get(self, path=None, default=None):
        """Get value."""
        if not path: return self._dict
        path = path.split('/')
        res = self._dict
        try:
            for p in path:
                res = res[p]
        except (KeyError, AttributeError):
            return default
        return res

    def __str__(self):
        return y.dumps(self._dict)


async def _handle_config_event(event):
    global config
    et = event.get('type')
    if et == 'get_config':
        await event_bus.post(type='get_config_', data=config.get(), dst=event.get('src', '*'))
    elif et == 'reset_config':
        config.reset()
    

# singleton
config = Config()

event_bus.subscribe(_handle_config_event)
