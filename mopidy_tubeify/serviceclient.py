from bs4 import BeautifulSoup as bs
from mopidy_youtube.comms import Client

from mopidy_tubeify import logger


class ServiceClient(Client):
    service_uri = None
    service_name = None
    service_image = None
    service_endpoint = None
    service_schema = {}
    uri_images = {}

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

    def _get_items_soup(self, endpoint, items_type="playlists"):
        if items_type:
            schema = self.service_schema[items_type]
        data = self.session.get(f"{self.service_endpoint}{endpoint}")
        soup = bs(data.content.decode('utf-8'), "html5lib")  # is .content.decode('utf-8') always going to work?
        if soup:
            if "container" in schema:
                soup = soup.find(
                    schema["container"]["tag"],
                    attrs=schema["container"]["attrs"],
                )
        if soup:
            if "item" in schema:
                soup = soup.find_all(
                    schema["item"]["tag"], attrs=schema["item"]["attrs"]
                )
            return soup
        return []
