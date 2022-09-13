import json

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

from mopidy_tubeify import logger
from mopidy_tubeify.data import find_in_obj
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_match


class Spotify(ServiceClient):
    def get_spotify_headers(self, endpoint=r"https://open.spotify.com/"):

        # # Getting the access token first to send it with the header to the api endpoint

        # use temporary token from website; now blocked by recaptcha it seems
        # page = self.session.get(endpoint)
        # soup = bs(page.text, "html.parser")
        # logger.debug(f"get_spotify_headers base url: {endpoint}")
        # access_token_tag = soup.find("script", {"id": "config"})
        # json_obj = json.loads(access_token_tag.contents[0])
        # access_token_text = json_obj["accessToken"]

        # use oauth2 to get token; doesn't allow access to spotify homepage
        # at https://api.spotify.com/v1/views/desktop-home
        logger.info("refreshing spotify credentials")
        with open("/tmp/spotify_creds.json") as f:
            creds = json.load(f)

        client = BackendApplicationClient(client_id=creds["client_id"])
        oauth = OAuth2Session(client=client)
        token = oauth.fetch_token(
            token_url=creds["token_url"],
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
        )

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
            endpoint = f"https://api.spotify.com/v1/users/{user}"
            data = self.session.get(endpoint).json()
            data["name"] = data["display_name"]
            return data

        results = []

        [results.append(job(user)) for user in users]
        return results

    def get_user_playlists(self, user):
        endpoint = f"https://api.spotify.com/v1/users/{user}/playlists"
        self.get_spotify_headers()
        data = self.session.get(endpoint).json()
        playlists = data["items"]
        return [
            {"name": playlist["name"], "id": playlist["id"]}
            for playlist in playlists
        ]

    def get_playlists_details(self, playlists):
        self.get_spotify_headers()

        def job(playlist):
            endpoint = f"https://api.spotify.com/v1/playlists/{playlist}"
            data = self.session.get(endpoint).json()
            playlist_name = data["name"]
            return {"name": playlist_name, "id": playlist}

        results = []
        [results.append(job(playlist)) for playlist in playlists]
        return results

    def get_playlist_tracks(self, playlist):
        endpoint = f"https://api.spotify.com/v1/playlists/{playlist}"
        self.get_spotify_headers()
        data = self.session.get(endpoint).json()
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
        endpoint = r"https://api.spotify.com/v1/views/desktop-home"
        self.get_spotify_headers()
        data = self.session.get(endpoint).json()
        playlists = list(find_in_obj(data, "type", "playlist"))

        return [
            {"name": playlist["name"], "id": playlist["id"]}
            for playlist in playlists
        ]
