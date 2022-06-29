from mopidy_youtube.comms import Client

class ServiceClient(Client):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 6.1) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/80.0.3987.149 Safari/537.36"
            )
        }

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
        logger.warn(f"no details, get_playlists_details: {users}")
        return []
    
    def get_playlist_tracks(self, playlist):
        logger.warn(f"no tracks, get_playlist_tracks: {playlist}")
        return
    
    def get_service_homepage(self):
        logger.warn(f"no service homepage, get_service_homepage")
        return

