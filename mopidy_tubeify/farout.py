import re

from mopidy_tubeify import logger
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.spotify import Spotify


class FarOut(ServiceClient):
    service_uri = "farout"
    service_name = "FarOut"
    service_image = "https://faroutmagazine.co.uk/wp-content/themes/far-out-magazine/logo/minimal-logo.svg"
    service_endpoint = "https://faroutmagazine.co.uk"
    service_schema = {
        "musicplaylists": {
            "container": {"tag": "div", "attrs": {"class": "content"}},
        },
        "embeded_spotify_playlist": Spotify.service_schema["embeded_playlist"],
    }

    # listoflists end up here
    def get_playlists_details(self, playlists, page=1):
        # is this really a list of playlists, or is it a special case?
        if len(playlists) == 1:
            match_farout_music_playlists = re.match(
                r"playlists(\d{1,2})?", playlists[0]
            )

            if match_farout_music_playlists:
                if match_farout_music_playlists.group(1):
                    page = match_farout_music_playlists.group(1)
                results = []
                soup = self._get_items_soup(
                    f"/articles/music/playlists/page/{page}/", "musicplaylists"
                )
                articles = soup.find_all("article", attrs={"class": "article"})
                for article in articles:
                    text = article.find("h2").a
                    article_id = text["href"].replace(self.service_endpoint, "")
                    results.append({"name": text.text, "id": article_id})
                    self.uri_images[article_id] = article.find("img")["src"]
                next_page = soup.find(
                    "a", attrs={"class": "next page-numbers"}
                )["href"].split("/")[-2]
                results.append(
                    {
                        "name": f"Page {next_page}",
                        "id": f"listoflists-playlists{next_page}",
                    }
                )
                return results

        logger.warn(f"no details, get_playlists_details: {playlists}")
        return []

    def get_playlist_tracks(self, playlist):
        # some FarOut pages have their playlists as spotify playlists
        # so, use those
        spotify_playlist = Spotify.playlist_regex.match(
            self._get_items_soup(playlist, "embeded_spotify_playlist")["src"]
        )[1]

        if spotify_playlist:
            # hopefully, this isn't a terrible idea...
            return Spotify.get_playlist_tracks(self, spotify_playlist)

        logger.warn(f"no tracks, get_playlist_tracks: {playlist}")
        return

    def get_service_homepage(self):
        return [
            {
                "name": "Playlists",
                "id": "listoflists-playlists",
            },
        ]
