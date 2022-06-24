import json

from bs4 import BeautifulSoup as bs
from mopidy_youtube.comms import Client
from mopidy_youtube.yt_matcher import search_and_get_best_match

from mopidy_tubeify import logger


class Spotify(Client):
    def get_spotify_headers(self, endpoint):
        # Getting the access token first to send it with the header to the api endpoint
        page = self.session.get(endpoint)
        soup = bs(page.text, "html.parser")
        logger.debug(f"get_spotify_headers base url: {endpoint}")
        access_token_tag = soup.find("script", {"id": "config"})
        json_obj = json.loads(access_token_tag.contents[0])
        access_token_text = json_obj["accessToken"]
        self.session.headers.update(
            {
                "authorization": f"Bearer {access_token_text}",
                "referer": endpoint,
                "accept": "application/json",
                "app-platform": "WebPlayer",
            }
        )
        return

    def get_user_details(self, user):
        endpoint = f"https://api.spotify.com/v1/users/{user}"
        self.get_spotify_headers(f"https://open.spotify.com/user/{user}")
        data = self.session.get(endpoint).json()
        return data

    def get_user_playlists(self, user):
        endpoint = f"https://api.spotify.com/v1/users/{user}/playlists"
        self.get_spotify_headers(f"https://open.spotify.com/user/{user}")
        data = self.session.get(endpoint).json()
        playlists = data["items"]
        return [
            {"name": playlist["name"], "id": playlist["id"]}
            for playlist in playlists
        ]

    def get_playlist_details(self, playlists):
        self.get_spotify_headers(
            f"https://open.spotify.com/playlist/{playlists[0]}"
        )

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
        self.get_spotify_headers(
            f"https://open.spotify.com/playlist/{playlist}"
        )
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
        ]

        return search_and_get_best_match(tracks)

    def get_service_homepage(self):
        return []
