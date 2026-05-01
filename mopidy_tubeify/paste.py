from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify import logger
import re
from bs4 import BeautifulSoup as bs
from mopidy_tubeify.data import flatten

from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)


class Paste(ServiceClient):
    service_uri = "paste"
    service_name = "Paste Magazine"
    service_image = "https://upload.wikimedia.org/wikipedia/commons/thumb/6/62/Paste_%28magazine%29_logo.svg/320px-Paste_%28magazine%29_logo.svg.png"
    service_endpoint = "https://www.pastemagazine.com/"
    uri_images = {}

    service_schema = {
        "musiclists": {
            "container": {
                "name": "div",
                "attrs": {
                    "class": "grid-x articles-standard"
                },  # re.compile("articles")},
            },
            "item": {
                "name": "a",
                "attrs": {"class": re.compile("copy-container")},
            },
        },
        "songs": {
            "item": {
                "name": "iframe",
                "attrs": {"title": "YouTube video player"}  
            }
        },
        "list-albums": {
            "container": {
                "name": "div",
                "attrs": {"class" :"copy entry manual-ads"}
            },
            "item": {"name": "h2"}
        }
    }

    def get_users_details(self, users):
        logger.warn(f"no details, get_users_details: {users}")
        return []

    def get_user_playlists(self, user):
        logger.warn(f"no playlists, get_user_playlists: {user}")
        return

    # listoflists end up here
    def get_playlists_details(self, playlists):
        endpoint = self.service_endpoint + playlists[0]
        data = self.session.get(endpoint)
        list_of_results = [
            {
                "name": f"{musiclist.find("b", attrs={"class": "title"}).text}",
                "id": f'{"/" + "/".join(musiclist['href'].split('/')[3:])}',
            }
            for musiclist in self._get_items_soup(data, "musiclists")
        ]
        
        list_of_results = [{**d, "id": f"songs-{d['id']}" if "song" in d["id"] else d["id"]} for d in list_of_results]
        list_of_results = [{**d, "id": f"albums-{d['id']}" if "album" in d["id"] else d["id"]} for d in list_of_results]

        return list_of_results

    def get_playlist_tracks(self, playlist):
        # # deal with list of songs pages
        match_songs = re.match(r"^songs\-(?P<songsURL>.+)$", playlist)
        if match_songs:
            logger.debug(f'matched "list of songs page" {playlist}')
            page_tracks_filter = self._get_items_soup(
                match_songs["songsURL"], "songs"
            )
            tracks = [
                {
                    "song_name": None,
                    "song_artists": None,
                    "song_duration": 0,
                    "isrc": None,
                    "videoId": re.search(r'/([^/?#]+)(?=[?#]|$)', track["src"]).group(1)
                }
                for track in page_tracks_filter
            ]
            logger.debug(f"total tracks for {playlist}: {len(tracks)}")
            return search_and_get_best_match(tracks, self.ytmusic)

        match_albums = re.match(r"^albums\-(?P<albumsURL>.+)$", playlist)
        if match_albums:
            logger.debug(f'matched "list of albums page" {playlist}')
            page_albums_filter = self._get_items_soup(
                match_albums["albumsURL"], "list-albums"
            )
            if page_albums_filter:
                albums = [
                    (
                        [page_album.text.split(":")[0]],
                        page_album.text.split(":")[1].strip()
                    )
                    for page_album in page_albums_filter
                ]
        else:
            data = self.session.get(self.service_endpoint + playlist)
            page_albums_filter = self._get_items_soup(data, "musiclists")
            if page_albums_filter:
                albums = [
                    (
                        (
                            [
                                name.replace("-", " ")
                                for name in re.findall(
                                    r"music/([^/]+)/", page_album["href"]
                                )
                            ],
                            (
                                page_album.find("em").get_text().encode("ascii", "ignore").decode('ascii')
                                if page_album.find("em")
                                else ""
                            ),
                        )
                    )
                    for page_album in page_albums_filter
                ]

        albums_to_return = search_and_get_best_albums(
            [album for album in albums if album[1]], self.ytmusic
        )

        return list(flatten(albums_to_return))

    def get_service_homepage(self):
        return [
            {"name": "Music Lists", "id": "listoflists-/articles/music/lists"},
            {"name": "Music Reviews", "id": "/articles/music/reviews"},
        ]


if __name__ == "__main__":
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-GB,en;q=0.9",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "priority": "u=0, i",
        "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
        "X-Requested-With": "XMLHttpRequest",
    }
    from ytmusicapi import YTMusic

    scraper = Paste(None, headers, YTMusic())
    homepage = scraper.get_service_homepage()
    print(homepage[0]["id"])
    gpd = scraper.get_playlists_details([homepage[0]["id"][12:]])
    print(gpd)
    # gpd = scraper.get_playlists_details([gpd[2]["id"][12:]])
    # print(gpd)
    gpt = scraper.get_playlist_tracks(gpd[2]["id"])
    print(gpt)
