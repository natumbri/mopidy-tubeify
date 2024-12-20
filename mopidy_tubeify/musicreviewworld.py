import re
from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_albums


class MusicReviewWorld(ServiceClient):
    service_uri = "musicreviewworld"
    service_name = "Music Review World"
    service_endpoint = "https://musicreviewworld.com"
    service_image = f"{service_endpoint}/wp-content/uploads/2022/05/Music-Review-World_Official-Logo.png"

    service_schema = {
        "albums": {
            "container": {
                "name": "div",
                "attrs": {"class": "td-main-content-wrap td-container-wrap"},
            },
            "item": {
                "name": "a",
                "attrs": {"title": re.compile(r".*\(?Album Review\)?")},
            },
        },
        "homepage_items": {
            "container": {
                "name": "li",
                "attrs": {"class": re.compile(r".*menu-item-713.*")},
            },
            "item": {
                "name": "li",
                "attrs": {"class": "menu-item-0"},
            },
        },
    }

    def get_playlists_details(self, playlists):
        logger.warn(f"no details, get_playlists_details: {playlists}")
        return []

    def get_playlist_tracks(self, playlist):
        # deal with album review pages
        match_ARP = re.match(r"^ARP\-(?P<reviewPage>.+)$", playlist)
        if match_ARP:
            albums = []
            for album in self._get_items_soup(f'/{match_ARP["reviewPage"]}', "albums"):
                album_details = re.split(
                    r"\:\s|\s\–\s|\s\-\s",
                    re.sub(r"\(?Album Review\)?.*", "", album["title"]),
                )
                album_artists = album_details[0].split(",")
                album_title = album_details[1]
                new_album = (album_artists, album_title.strip())
                if new_album not in albums:
                    albums.append(new_album)

            albums_to_return = search_and_get_best_albums(
                [album for album in albums if album[1]], self.ytmusic
            )

            return list(flatten(albums_to_return))

    def get_service_homepage(self):

        return [
            {
                "name": review_page.a.text,
                "id": f"ARP-{review_page.a['href'].split(self.service_endpoint)[1]}",
            }
            for review_page in self._get_items_soup('', "homepage_items")
        ]


if __name__ == "__main__":
    headers = {
        "User-Agent": r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
    }
    from ytmusicapi import YTMusic

    scraper = MusicReviewWorld(None, headers, YTMusic())
    homepage = scraper.get_service_homepage()

    print(homepage)
    gpt = scraper.get_playlist_tracks(homepage[0]["id"])
    print(gpt)
