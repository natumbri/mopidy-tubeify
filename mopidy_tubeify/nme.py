# import json
import re

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_albums


class NME(ServiceClient):
    service_uri = "nme"
    service_name = "NME"

    def get_playlist_tracks(self, playlist):
        # album review pages
        match_ARP = re.match(r"^ARP\-(?P<reviewPage>.+)$", playlist)
        if match_ARP:
            logger.info(f'matched "album review page" {playlist}')
            reviewPage = match_ARP["reviewPage"]
            endpoint = f"https://www.nme.com/{reviewPage}"

            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            album_divs = soup.find_all(
                "div",
                class_="tdb_module_loop td_module_wrap td-animation-stack",
            )
            album_re = re.compile(
                r"^(?P<artist>.+)\ \–\ \‘(?P<album>.+)\’((?P<ep>\ EP))?\ review.+$"
            )

            albums = [album_re.search(album.a["title"]) for album in album_divs]
            artists_albumtitle = [
                (
                    [album["artist"]],
                    f"{album['album']}{album['ep'] or ''}",
                )
                for album in albums
                if album
            ]

            albums_to_return = search_and_get_best_albums(
                [album for album in artists_albumtitle if album[1]],
                self.ytmusic,
            )

            return list(flatten(albums_to_return))

    def get_service_homepage(self):
        track_dicts = []

        track_dicts.append(
            {
                "name": r"Recently Reviewed Albums",
                "id": r"ARP-reviews/album",
            }
        )

        track_dicts.append(
            {
                "name": r"Previously Reviewed Albums",
                "id": r"ARP-reviews/album/page/2",
            }
        )

        track_dicts.append(
            {
                "name": r"Albums reviewed a while ago",
                "id": r"ARP-reviews/album/page/3",
            }
        )

        return track_dicts
