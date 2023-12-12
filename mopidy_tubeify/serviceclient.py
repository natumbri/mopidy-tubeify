from mopidy_youtube.comms import Client

from mopidy_tubeify import logger


class ServiceClient(Client):
    service_uri = None
    service_name = None
    service_endpoint = None

    def __init__(self, proxy, headers, ytm_client):
        super().__init__(proxy, headers)
        self.ytmusic = ytm_client

    def get_users_details(self, users):
        logger.warn(f"no details, get_users_details: {users}")
        return []

    def get_user_playlists(self, user):
        logger.warn(f"no playlists, get_user_playlists: {user}")
        return

    # listoflists end up here
    def get_playlists_details(self, playlists):
        logger.warn(f"no details, get_playlists_details: {playlists}")
        return []

    def get_playlist_tracks(self, playlist):
        logger.warn(f"no tracks, get_playlist_tracks: {playlist}")
        return

    def get_service_homepage(self):
        logger.warn("no service homepage, get_service_homepage")
        return
