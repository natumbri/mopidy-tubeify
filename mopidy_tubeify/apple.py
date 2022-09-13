import json
import re
from urllib.parse import unquote

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import find_in_obj
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_match


class Apple(ServiceClient):
    def get_applemusic_headers(self, endpoint=r"https://music.apple.com"):
        # Getting the access token first to send it with the header to the api endpoint
        page = self.session.get(endpoint)
        soup = bs(page.text, "html.parser")
        logger.debug(f"get_applemusic_headers base url: {endpoint}")

        access_token_tag = soup.find(
            "meta", {"name": "desktop-music-app/config/environment"}
        )
        json_obj = json.loads(unquote(access_token_tag["content"]))
        access_token_text = json_obj["MEDIA_API"]["token"]
        self.session.headers.update(
            {
                "authorization": f"Bearer {access_token_text}",
                "referer": endpoint,
                "accept": "application/json",
                "app-platform": "WebPlayer",
                "origin": endpoint,
            }
        )

    def get_users_details(self, users):
        def job(user):
            endpoint = f"https://music.apple.com/us/curator/{user}"  # npr-music/1437679561
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            user_dict = {"id": user, "name": soup.find("title").text}
            return user_dict

        results = []

        [results.append(job(user)) for user in users]
        return results

    def get_user_playlists(self, user):
        self.get_applemusic_headers()
        userId_re = re.compile(r".+/(?P<userId>\d{10})$")
        userId = userId_re.match(user)["userId"]
        endpoint = f"https://amp-api.music.apple.com/v1/catalog/us/curators/{userId}/playlists?offset=0"

        playlists = []

        while True:
            data = self.session.get(endpoint).json()
            playlists.extend(data["data"])
            if "next" in data:
                endpoint = f"https://amp-api.music.apple.com/{data['next']}"
            else:
                break

        return [
            {"name": playlist["attributes"]["name"], "id": playlist["id"]}
            for playlist in playlists
        ]

    def get_playlists_details(self, playlists):
        def job(playlist):
            endpoint = f"https://music.apple.com/us/playlist/{playlist}"
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            playlist_name = soup.find("title").text
            return {"name": playlist_name, "id": playlist}

        results = []

        # does apple uses a captcha? be careful before going multi-threaded
        [results.append(job(playlist)) for playlist in playlists]

        return results

    def get_playlist_tracks(self, playlist):
        endpoint = f"https://music.apple.com/us/playlist/{playlist}"
        data = self.session.get(endpoint)
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
        logger.debug(f"total tracks for {playlist}: {len(tracks)}")
        return search_and_get_best_match(tracks, self.ytmusic)

    def get_service_homepage(self):

        content_re = re.compile(
            r"^.+platform\.web[^\[]+(?P<content>.+\])\}\"\}$"
        )
        playlistid_re = re.compile(r"^.+playlist/(?P<playlistid>.+$)")

        endpoint = r"https://music.apple.com/us/browse"
        data = self.session.get(endpoint)
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
