# Appears to be offline as at 2024-12-20
import re

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)
from mopidy_youtube.comms import Client


class KEXP(ServiceClient):
    service_uri = "kexp"
    service_name = "KEXP 90.3FM"
    service_image = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/KEXP_logo_%28black_on_orange%29.svg/443px-KEXP_logo_%28black_on_orange%29.svg.png"
    service_endpoint = "http://www.kexplorer.com"
    service_schema = {
        "dj": {
            "container": {"name": "ul", "attrs": {"id": "chart-list"}},
            "item": {"name": "a", "attrs": {}},
        },
        "homepage": {
            "item": {"name": "div", "attrs": {"class": "listener-info"}}
        },
        "playlist": {
            "item": {"name": "div", "attrs": {"class": "home-playlist-song"}}
        },
    }

    def __init__(self, proxy, headers, ytm_client):
        # is this hack thing with headers necessary to get kexpeplorer to work consistently?
        Client.__init__(
            self,
            proxy,
            headers={
                "User-Agent": r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
            },
        )
        self.ytmusic = ytm_client

    def get_playlists_details(self, playlists):
        def job(playlist):
            # deal with DJ pages
            match_DJ = re.match(
                r"^DJ\-(?P<dj>.+)$",
                playlist,
            )
            if match_DJ:
                dj_stats_categories = self._get_items_soup(
                    f"/top/songs/of-all-time/{match_DJ['dj']}", "dj"
                )
                dj_results = []

                [
                    dj_results.append(
                        {
                            "name": f"Top Songs ({category.text})",
                            "id": category["href"],
                        }
                    )
                    for category in dj_stats_categories
                    if re.match(r"^\/top\/songs\/.+$", category["href"])
                ]

                [
                    dj_results.append(
                        {
                            "name": f"Top Albums ({category.text})",
                            "id": f"{category['href']}",
                        }
                    )
                    for category in dj_stats_categories
                    if re.match(r"^\/top\/albums\/.+$", category["href"])
                ]

                return dj_results

            else:
                # for other sorts of kexp playlists
                return

        # be careful before going multi-threaded
        results = [job(playlist) for playlist in playlists]

        return list(flatten(results))

    def get_playlist_tracks(self, playlist):
        stats_playlist_soup = self._get_items_soup(playlist, "playlist")
        if re.match(r"^\/top\/songs\/.+$", playlist):
            tracks = [
                {
                    "song_name": track.find(
                        "a", attrs={"href": re.compile(r"^\/song\/\d+$")}
                    ).text,
                    "song_artists": track.find(
                        "a", attrs={"href": re.compile(r"^\/artist\/\d+$")}
                    ).text.split(" feat. "),
                    "song_duration": 0,
                    "isrc": None,
                }
                for track in stats_playlist_soup
            ]
            logger.debug(f"total tracks for {playlist}: {len(tracks)}")
            return search_and_get_best_match(tracks, self.ytmusic)

        if re.match(r"^\/top\/albums\/.+$", playlist):
            albums = [
                (
                    album.find(
                        "a", attrs={"href": re.compile(r"^\/artist\/\d+$")}
                    ).text.split(" feat. "),
                    album.find("div", class_="info")
                    .find("a", attrs={"href": re.compile(r"^\/album\/\d+$")})
                    .text,
                )
                for album in stats_playlist_soup
            ]

            albums_to_return = search_and_get_best_albums(
                [album for album in albums if album[1]], self.ytmusic
            )

            return list(flatten(albums_to_return))

    def get_service_homepage(self):
        djs = [
            dj.a
            for djs in [
                self._get_items_soup(f"/djs/{n}", "homepage")
                for n in [1, 2, 3, 4]
            ]
            for dj in djs
        ]

        return [
            {
                "name": dj.text,
                "id": f"listoflists-DJ-{dj['href'].replace('/', '-')[1:]}",
            }
            for dj in djs
        ]
