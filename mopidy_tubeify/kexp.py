import re

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)


class KEXP(ServiceClient):
    service_uri = "kexp"
    service_name = "KEXP 90.3FM"

    def get_playlists_details(self, playlists):
        def job(playlist):
            # deal with DJ pages
            match_DJ = re.match(
                r"^DJ\-(?P<dj>.+)$",
                playlist,
            )
            if match_DJ:
                endpoint = f"http://www.kexplorer.com/top/songs/of-all-time/{match_DJ['dj']}"
                dj_stats_response = self.session.get(endpoint)
                dj_stats_soup = bs(
                    dj_stats_response.content.decode("utf-8"),
                    "html5lib",
                )
                dj_stats_categories = dj_stats_soup.find(
                    "ul", attrs={"id": "chart-list"}
                ).find_all("a")

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
        endpoint = f"http://www.kexplorer.com{playlist}"
        stats_playlist_response = self.session.get(endpoint)
        stats_playlist_soup = bs(
            stats_playlist_response.content.decode("utf-8"), "html5lib"
        ).find_all("div", attrs={"class": "home-playlist-song"})

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
        endpoint = r"http://www.kexplorer.com/djs/"
        djs = []
        for n in [1, 2, 3, 4]:
            data = self.session.get(f"{endpoint}{n}")
            soup = bs(data.content.decode("utf-8"), "html5lib")
            djs.extend(
                [
                    dj.a
                    for dj in soup.find_all(
                        "div", attrs={"class": "listener-info"}
                    )
                ]
            )

        return [
            {
                "name": dj.text,
                "id": f"listoflists-DJ-{dj['href'].replace('/', '-')[1:]}",
            }
            for dj in djs
        ]
