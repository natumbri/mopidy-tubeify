from mopidy_tubeify import logger
from mopidy_tubeify.serviceclient import ServiceClient


class AmazonMusic(ServiceClient):
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
