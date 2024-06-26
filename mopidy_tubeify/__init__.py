import logging
import pathlib

import pkg_resources
from mopidy import config, ext

__version__ = pkg_resources.get_distribution("Mopidy-Tubeify").version

logger = logging.getLogger(__name__)


class Extension(ext.Extension):
    dist_name = "Mopidy-Tubeify"
    ext_name = "tubeify"
    version = __version__

    def get_default_config(self):
        return config.read(pathlib.Path(__file__).parent / "ext.conf")

    def get_config_schema(self):
        schema = super().get_config_schema()
        schema["applemusic_playlists"] = config.List()
        schema["applemusic_users"] = config.List()
        schema["lastfm_username"] = config.String()
        schema["lastfm_password"] = config.String()
        schema["lastfm_users"] = config.List()
        schema["spotify_users"] = config.List()
        schema["spotify_playlists"] = config.List()
        schema["tidal_playlists"] = config.List()

        return schema

    def setup(self, registry):
        from .backend import TubeifyBackend

        registry.add("backend", TubeifyBackend)
        registry.add(
            "http:app", {"name": self.ext_name, "factory": self.factory}
        )

    def factory(self, config, core):
        from .web import WebHandler

        return [(r"/", WebHandler, {"config": config, "core": core})]
