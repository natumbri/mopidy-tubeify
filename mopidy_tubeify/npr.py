import re

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)


class NPR(ServiceClient):
    def get_playlists_details(self, playlists):

        # is this really a list of playlists, or is it a special case?
        if len(playlists) == 1:
            # did we get here from the homepage?
            if playlists[0] == "NPR100BSO2022":
                endpoint = r"https://www.npr.org/2022/12/15/1135802083/100-best-songs-2022-page-1"
                idPrefix = "BSOx"
                page1 = [
                    {"name": "100-81", "id": f"{idPrefix}-{endpoint[19:]}"}
                ]

            elif playlists[0] == "NPR50BAO2022":
                endpoint = r"https://www.npr.org/2022/12/12/1134898067/50-best-albums-2022-page-1"
                idPrefix = "BAOx"
                page1 = [{"name": "50-41", "id": f"{idPrefix}-{endpoint[19:]}"}]

            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")

            segments_filter = soup.find("div", class_="subtopics")

            return page1 + [
                {"name": atag.text, "id": f"{idPrefix}-{atag['href']}"}
                for atag in segments_filter.find_all("a")
            ]

        # ordinary case of list of playlists here
        logger.warn("NPR get_playlists_details not returning anything")
        return

    def get_playlist_tracks(self, playlist):

        # is this a segment from BAOx? (Albums)
        match_BAOx = re.match(r"^BAOx\-(?P<segment>.+)$", playlist)
        if match_BAOx:
            albums_json = self._get_NPR_json(match_BAOx["segment"])
            albums = [(album[0].split("&"), album[1]) for album in albums_json]

            ytalbums = list(
                flatten(search_and_get_best_albums(albums, self.ytmusic))
            )

            return ytalbums

        # is this a segment of BSOx? (Songs)
        match_BSOx = re.match(r"^BSOx\-(?P<segment>.+)$", playlist)
        if match_BSOx:
            tracks_json = self._get_NPR_json(match_BSOx["segment"])
            tracks = [
                {
                    "song_name": track[1],
                    "song_artists": track[0].split("&"),
                    "song_duration": 0,
                    "isrc": None,
                }
                for track in tracks_json
            ]
            return search_and_get_best_match(tracks, self.ytmusic)

    def get_service_homepage(self):

        # future: programatically generate album and song lists from
        # somewhere to include in the library.  The "id" would ideally
        # be something like f"listoflists-{url of first page of the list}"

        # now: hard code a few lists
        return [
            {
                "name": "NPR Music's 100 Best Songs of 2022",
                "id": "listoflists-NPR100BSO2022",
            },
            {
                "name": "NPR Music's 50 Best Albums of 2022",
                "id": "listoflists-NPR50BAO2022",
            },
        ]

    def _get_NPR_json(self, endpoint):
        data = self.session.get("https://npr.org" + endpoint)
        soup = bs(data.text, "html5lib")
        list_numbers = soup.find_all("h6", text=re.compile(r"\d{1,3}\."))
        items_dicts = []
        for list_number in list_numbers:
            html = []
            for tag in list_number.find_next_siblings(class_="edTag"):
                if tag.name == "h6":
                    break
                elif tag.name == "h3":
                    html.append(tag.text.replace('"', ""))
            items_dicts.append(html)
        return items_dicts
