import re
import time
from operator import itemgetter

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_match


class KCRW(ServiceClient):
    service_uri = "kcrw"
    service_name = "KCRW 89.9FM"
    service_endpoint = "https://www.kcrw.com"
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
                endpoint = f"{self.service_endpoint}{match_PROGRAM['program']}"
                program_episodes_response = self.session.get(endpoint)
                program_episodes_soup = bs(
                    program_episodes_response.content.decode("utf-8"),
                    "html5lib",
                )
                program_episodes_list = program_episodes_soup.find(
                    "div", attrs={"id": "episodes"}
                ).find_all("div", attrs={"class": "single episode-Item"})
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
        endpoint = f"{self.service_endpoint}{playlist}"
        episode_playlist_response = self.session.get(endpoint)
        episode_playlist_soup = bs(
            episode_playlist_response.content.decode("utf-8"), "html5lib"
        )
        episode_playlist_url = episode_playlist_soup.find(
            "div",
            attrs={"class": "tracklist_container", "id": "playlist-entries"},
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
        endpoint = f"{self.service_endpoint}/shows"
        data = self.session.get(endpoint)
        soup = bs(data.content.decode("utf-8"), "html5lib")

        programs_soup = soup.find_all(
            "a",
            attrs={
                "class": "single",
                "data-filter-data": re.compile(
                    r".+\"categories\"\: \[\"Music\"\].+"
                ),
            },
        )

        programs = []
        for program_soup in programs_soup:
            program_id = f"listoflists-PROGRAM-{program_soup['href'][20:]}"
            programs.append({"name": program_soup["title"], "id": program_id})
            self.uri_images[program_id] = program_soup.find("img").get("src")
        return programs
