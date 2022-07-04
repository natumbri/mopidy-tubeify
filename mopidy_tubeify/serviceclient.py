from mopidy_youtube.comms import Client

from mopidy_tubeify import logger


class ServiceClient(Client):
    def flatten(self, items):
        """Yield items from any nested list; see Reference."""
        for x in items:
            if isinstance(x, list) and not isinstance(x, (str, bytes)):
                for sub_x in self.flatten(x):
                    yield sub_x
            else:
                yield x

    def get_users_details(self, users):
        logger.warn(f"no details, get_users_details: {users}")
        return []

    def get_user_playlists(self, user):
        logger.warn(f"no playlists, get_user_playlists: {user}")
        return

    def get_playlists_details(self, playlists):
        logger.warn(f"no details, get_playlists_details: {playlists}")
        return []

    def get_playlist_tracks(self, playlist):
        logger.warn(f"no tracks, get_playlist_tracks: {playlist}")
        return

    def get_service_homepage(self):
        logger.warn("no service homepage, get_service_homepage")
        return
