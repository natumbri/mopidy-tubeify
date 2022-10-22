import json
import re
from html import unescape

from bs4 import BeautifulSoup as bs

# from mopidy_tubeify import logger
# from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (  # search_and_get_best_album,
    search_and_get_best_match,
)


class RollingStone500Songs(ServiceClient):
    def get_playlist_tracks(self, playlist):
        endpoint = r"https://www.rollingstone.com/music/music-lists/best-songs-of-all-time-1224767/"
        data = self.session.get(
            endpoint + playlist + "/", allow_redirects=False
        )
        soup = bs(data.text, "html5lib")
        json_script = soup.find("script", id="pmc-lists-front-js-extra")
        json_re = re.compile(r"var\ pmcGalleryExports\ \=\ (?P<json_var>.+);")
        tracks_json = json.loads(
            unescape(json_re.search(json_script.text)["json_var"])
            .replace("‘", "'")
            .replace("’", "'")
        )["gallery"]
        name_artists = re.compile(r"^(?P<artist>.+),\s'(?P<name>.+)'$")
        tracks = [
            {
                "song_name": name_artists.match(track["title"])["name"],
                "song_artists": name_artists.match(track["title"])[
                    "artist"
                ].split(","),
                "song_duration": 0,
                "isrc": None,
            }
            for track in tracks_json
        ]
        return search_and_get_best_match(tracks, self.ytmusic)

    def get_service_homepage(self):

        endpoint = r"https://www.rollingstone.com/music/music-lists/best-songs-of-all-time-1224767/"
        data = self.session.get(endpoint)
        soup = bs(data.text, "html5lib")
        json_script = soup.find("script", id="pmc-lists-front-js-extra")
        json_re = re.compile(r"var\ pmcGalleryExports\ \=\ (?P<json_var>.+);")
        segments_json = json.loads(
            json_re.search(json_script.text)["json_var"]
        )["listNavBar"]["generatedRanges"]["800"]
        segment_dicts = [
            {
                "name": f'{segment["positionDisplayStart"]} - {segment["positionDisplayEnd"]}',
                "id": re.match(f"^{endpoint}(?P<tail>.+)$", segment["link"])[
                    "tail"
                ],
            }
            for segment in segments_json
        ]

        return segment_dicts
