import json
import re

from bs4 import BeautifulSoup as bs
from mopidy_youtube.comms import Client
from mopidy_youtube.yt_matcher import search_and_get_best_match

from mopidy_tubeify import logger


class Apple(Client):

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36"
    }

    def get_user_details(self, user):
        logger.warn(f"no Apple get_user_details, user: {user}")
        return

    def get_user_playlists(self, user):
        logger.warn(f"no Apple get_user_playlists, user: {user}")
        return

    def get_playlist_details(self, playlists):
        def job(playlist):
            endpoint = f"https://music.apple.com/us/playlist/{playlist}"
            data = self.session.get(endpoint, headers=self.headers)
            soup = bs(data.text, "html5lib")
            playlist_name = soup.find("title").text
            return {"name": playlist_name, "id": playlist}

        results = []

        # does apple uses a captcha? be careful before going multi-threaded
        [results.append(job(playlist)) for playlist in playlists]

        return results

    def get_playlist_tracks(self, playlist):
        endpoint = f"https://music.apple.com/us/playlist/{playlist}"
        data = self.session.get(endpoint, headers=self.headers)
        soup = bs(data.text, "html5lib")

        # this script seems to have a json record of all the tracks
        # in the playlist, with information including title, duration,
        # album, etc for each
        track_list = (
            soup.find("script", {"id": "shoebox-media-api-cache-amp-music"})
            .text.encode("ascii", "ignore")
            .decode("unicode_escape")
        )

        # alternative: regex for isrc
        # isrc_pattern = re.compile(r'"isrc"\:"(?P<isrc>.{12})"')
        # isrcs = [match["isrc"] for match in isrc_pattern.finditer(track_list)]

        track_dict = {}
        content_re = re.compile(
            r"^.+platform\.web[^\[]+(?P<content>.+\])\}\"\}$"
        )
        extracted_content = content_re.match(track_list)
        content_dict = json.loads(extracted_content["content"])
        content_tracks = content_dict[0]["relationships"]["tracks"]["data"]

        for index, track in enumerate(content_tracks):

            song_name = track["attributes"]["name"]
            song_artists = [track["attributes"]["artistName"]]
            song_duration = track["attributes"]["durationInMillis"] // 1000
            isrc = track["attributes"]["isrc"]

            track_dict[index] = {
                "song_name": song_name,
                "song_artists": song_artists,
                "song_duration": song_duration,
                "isrc": isrc,
            }

        tracks = list(track_dict.values())
        return search_and_get_best_match(tracks)

    def get_service_homepage(self):

        content_re = re.compile(
            r"^.+platform\.web[^\[]+(?P<content>.+\])\}\"\}$"
        )
        playlistid_re = re.compile(r"^.+playlist/(?P<playlistid>.+$)")

        def find_in_obj(obj, condition, kind):
            # In case this is a list
            if isinstance(obj, list):
                for index, value in enumerate(obj):
                    for result in find_in_obj(value, condition, kind):
                        yield result
            # In case this is a dictionary
            if isinstance(obj, dict):
                for key, value in obj.items():
                    for result in find_in_obj(value, condition, kind):
                        yield result
                    if condition == key and obj[key] == kind:
                        yield obj

        endpoint = r"https://music.apple.com/us/browse"
        data = self.session.get(endpoint, headers=self.headers)
        soup = bs(data.text, "html5lib")

        # this script seems to have a json record of all the tracks
        # in the playlist, with information including title, duration,
        # album, etc for each
        content_script = (
            soup.find("script", {"id": "shoebox-media-api-cache-amp-music"})
            .text.encode("ascii", "ignore")
            .decode("unicode_escape")
        )
        extracted_content = content_re.match(content_script)
        content = json.loads(extracted_content["content"])
        playlists = list(find_in_obj(content, "type", "playlists"))

        track_dicts = []

        for playlist in playlists:
            playlistid = playlistid_re.match(playlist["attributes"]["url"])
            track_dicts.append(
                {
                    "name": playlist["attributes"]["name"],
                    "id": playlistid["playlistid"],
                }
            )

        return track_dicts
