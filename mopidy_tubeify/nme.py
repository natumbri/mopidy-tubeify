import json
import re

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_album


class NME(ServiceClient):
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

        # deal with featured new releases pages
        if re.match(r"^FNR\-(?P<albumId>.+)$", playlist):
            return self.get_playlists_details([playlist])

        artists_albumtitle = (
            [json.loads(playlist)["artist"]],
            json.loads(playlist)["album"],
        )

        print(artists_albumtitle)

        try:
            # experimental, using ytmusic album instead of track-by-track matching
            album_browseId_list = search_and_get_best_album(
                artists_albumtitle=artists_albumtitle, ytmusic=self.ytmusic
            )
            print(f"a bId: {album_browseId_list}")
            album_browseId = album_browseId_list[0]["browseId"]
            album = self.ytmusic.get_album(album_browseId)
            tracks = album["tracks"]

            fields = ["artists", "thumbnails"]
            [
                track.update({field: album[field]})
                for field in fields
                for track in tracks
                if track[field] is None
            ]

            [
                track.update(
                    {
                        "album": {
                            "name": album["title"],
                            "id": album_browseId,
                        }
                    }
                )
                for track in tracks
            ]
            return tracks

        except Exception as e:

            logger.warn(
                f"error {e} getting album {artists_albumtitle} from ytmusic"
            )

        return

    def get_service_homepage(self):

        endpoint = r"https://www.nme.com/reviews/album"
        data = self.session.get(endpoint)
        soup = bs(data.text, "html5lib")
        album_divs = soup.find_all(
            "div", class_="tdb_module_loop td_module_wrap td-animation-stack"
        )
        album_re = re.compile(
            r"^(?P<artist>.+)\ \–\ \‘(?P<album>.+)\’((?P<ep>\ EP))?\ review.+$"
        )

        albums = [album_re.search(album.a["title"]) for album in album_divs]

        albums_dicts = [
            {
                "artist": album["artist"],
                "album": f"{album['album']}{album['ep'] or ''}",
            }
            for album in albums
        ]

        return [
            {
                "name": f"{album['artist']}, {album['album']}",
                "id": f"{json.dumps(album)}",
            }
            for album in albums_dicts
        ]
