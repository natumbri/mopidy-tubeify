import re
import time
from operator import itemgetter

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_match


class KCRW(ServiceClient):
    service_uri = "kcrw"
    service_name = "KCRW 89.9FM"
    service_endpoint = "https://www.kcrw.com"
    service_schema = {
        "episode_playlist": {
            "container": {
                "tag": "div",
                "attrs": {
                    "class": "tracklist_container",
                    "id": "playlist-entries",
                },
            },
        },
        "playlists": {
            "container": {"tag": "div", "attrs": {"id": "episodes"}},
            "item": {"tag": "div", "attrs": {"class": "single episode-Item"}},
        },
        "shows": {
            "item": {
                "tag": "a",
                "attrs": {
                    "class": "single",
                    "data-filter-data": re.compile(
                        r".+\"categories\"\: \[\"Music\"\].+"
                    ),
                },
            }
        },
    }
    service_image = f"{service_endpoint}/events/images/grand-opening-2017/logo-kcrw.png/image_preview"

    def get_playlists_details(self, playlists):
        def job(playlist):
            # deal with program pages
            match_PROGRAM = re.match(
                r"^PROGRAM\-(?P<program>.+)$",
                playlist,
            )
            if match_PROGRAM:
                logger.debug(f"matched program {match_PROGRAM['program']}")
                program_episodes_list = self._get_items_soup(
                    match_PROGRAM["program"], "playlists"
                )
                playlist_results = []

                [
                    playlist_results.append(
                        {
                            "name": episode.h3.text,
                            "id": episode.a["href"][20:],
                            "date": time.strptime(
                                episode.time["datetime"],
                                "%Y-%m-%dT%H:%M:%SZ",
                            ),
                        }
                    )
                    for episode in program_episodes_list
                    if episode
                ]

                return sorted(
                    playlist_results, key=itemgetter("date"), reverse=True
                )
            else:
                # for other sorts of kcrw playlists
                return

        # be careful before going multi-threaded
        results = [job(playlist) for playlist in playlists]

        return list(flatten(results))

    def get_playlist_tracks(self, playlist):
        episode_playlist_url = self._get_items_soup(
            playlist, "episode_playlist"
        )["data-tracklist-url"]
        json_data = self.session.get(episode_playlist_url).json()

        tracks = [
            {
                "song_name": track["title"],
                "song_artists": [track["artist"]],
                "song_duration": 0,
                "isrc": None,
            }
            for track in json_data
            if track["title"]
        ]
        logger.debug(f"total tracks for {playlist}: {len(tracks)}")
        return search_and_get_best_match(tracks, self.ytmusic)

    def get_service_homepage(self):
        programs_soup = self._get_items_soup("/shows", "shows")
        programs = []
        for program_soup in programs_soup:
            program_id = f"listoflists-PROGRAM-{program_soup['href'].replace(self.service_endpoint, '')}"
            programs.append({"name": program_soup["title"], "id": program_id})
            self.uri_images[program_id] = program_soup.find("img").get("src")
        return programs
