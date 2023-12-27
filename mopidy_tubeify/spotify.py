import json
import re

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import find_in_obj
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_match

# from oauthlib.oauth2 import BackendApplicationClient
# from requests_oauthlib import OAuth2Session


class Spotify(ServiceClient):
    service_uri = "spotify"
    service_name = "Spotify"
    service_image = "https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Spotify_App_Logo.svg/400px-Spotify_App_Logo.svg.png"
    service_endpoint = "https://api.spotify.com"

    playlist_regex = re.compile(
        r"https\:\/\/open\.spotify\.com\/.*\/?playlist\/(.{22})"
    )
    album_regex = re.compile(
        r"https\:\/\/open\.spotify\.com\/embed\/album\/(.{22})"
    )
    track_regex = re.compile(
        r"https\:\/\/open\.spotify\.com\/embed\/track\/(.{22})"
    )

    def get_spotify_headers(self, endpoint=r"https://open.spotify.com"):
        # # Getting the access token first to send it with the header to the api endpoint

        # use temporary token from website
        page = self.session.get(f"{endpoint}/__noul__")
        soup = bs(page.text, "html.parser")
        access_token_tag = soup.find("script", text=re.compile("accessToken"))
        json_obj = json.loads(access_token_tag.contents[0])
        token = {"access_token": json_obj["accessToken"]}

        # # use oauth2 to get token; doesn't allow access to spotify homepage
        # # at https://api.spotify.com/v1/views/desktop-home
        # logger.info("refreshing spotify credentials")
        # with open("/tmp/spotify_creds.json") as f:
        #     creds = json.load(f)
        # client = BackendApplicationClient(client_id=creds["client_id"])
        # oauth = OAuth2Session(client=client)
        # token = oauth.fetch_token(
        #     token_url=creds["token_url"],
        #     client_id=creds["client_id"],
        #     client_secret=creds["client_secret"],
        # )

        self.session.headers.update(
            {
                "authorization": f"Bearer {token['access_token']}",
                "referer": endpoint,
                "accept": "application/json",
                "app-platform": "WebPlayer",
            }
        )
        return

    def get_users_details(self, users):
        self.get_spotify_headers()

        def job(user):
            endpoint = f"{Spotify.service_endpoint}/v1/users/{user}"
            data = self.session.get(endpoint).json()
            data["name"] = data["display_name"]
            return data

        results = []

        [results.append(job(user)) for user in users]
        return results

    def get_user_playlists(self, user):
        endpoint = f"{Spotify.service_endpoint}/v1/users/{user}/playlists"
        self.get_spotify_headers()
        data = self.session.get(endpoint).json()
        playlists = data["items"]
        return [
            {"name": playlist["name"], "id": playlist["id"]}
            for playlist in playlists
        ]

    def _get_spotify_details(self, kind, tracklist):
        endpoint = f"{Spotify.service_endpoint}/v1/{kind}/{tracklist}"
        data = self.session.get(endpoint).json()
        return data

    def get_playlists_details(self, playlists):
        Spotify.get_spotify_headers(self)
        results = {
            playlist: Spotify._get_spotify_details(self, "playlists", playlist)
            for playlist in playlists
        }
        return [
            {"name": details["name"], "id": playlist_id}
            for playlist_id, details in results.items()
            if details
        ]

    def get_albums_details(self, albums):
        Spotify.get_spotify_headers(self)
        results = {
            album: Spotify._get_spotify_details(self, "albums", album)
            for album in albums
        }
        return [
            {
                "name": details["name"],
                "id": album_id,
                "artists": [artist["name"] for artist in details["artists"]],
            }
            for album_id, details in results.items()
            if details
        ]

    def get_tracks_details(self, tracks):
        Spotify.get_spotify_headers(self)
        results = {
            track: Spotify._get_spotify_details(self, "tracks", track)
            for track in tracks
        }
        return [
            {
                "name": details["name"],
                "id": track_id,
                "artists": [artist["name"] for artist in details["artists"]],
            }
            for track_id, details in results.items()
            if details
        ]

    def get_playlist_tracks(self, playlist):
        Spotify.get_spotify_headers(self)
        data = Spotify._get_spotify_details(self, "playlists", playlist)
        items = data["tracks"]["items"]
        tracks = [
            {
                "song_name": item["track"]["name"],
                "song_artists": [
                    artist["name"] for artist in item["track"]["artists"]
                ],
                "song_duration": item["track"]["duration_ms"] // 1000,
                "isrc": item["track"]["external_ids"].get("isrc"),
            }
            for item in items
            if item["track"]
        ]
        return search_and_get_best_match(tracks, self.ytmusic)

    def get_service_homepage(self):
        self.get_spotify_headers()
        endpoint = f"{Spotify.service_endpoint}/v1/views/desktop-home"

        data = self.session.get(endpoint).json()
        playlists = list(find_in_obj(data, "type", "playlist"))

        self.uri_images.update(
            {
                playlist["id"]: playlist["images"][0]["url"]
                for playlist in playlists
            }
        )
        return [
            {"name": playlist["name"], "id": playlist["id"]}
            for playlist in playlists
        ]
