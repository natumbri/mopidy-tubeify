import re

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)


class MusicReviewWorld(ServiceClient):
    service_uri = "musicreviewworld"
    service_name = "Music Review World"
    service_endpoint = "https://musicreviewworld.com/"

    def get_playlists_details(self, playlists):
        logger.warn(f"no details, get_playlists_details: {playlists}")
        return []

    def get_playlist_tracks(self, playlist):
        # deal with album review pages
        match_ARP = re.match(r"^ARP\-(?P<reviewPage>.+)$", playlist)
        if match_ARP:
            logger.debug(f'matched "album review page" {playlist}')
            reviewPage = match_ARP["reviewPage"]
            endpoint = f"{self.service_endpoint}{reviewPage}"
            data = self.session.get(endpoint)
            soup = (
                bs(data.text, "html5lib")
                .find(
                    "div",
                    attrs={"class": "td-main-content-wrap td-container-wrap"},
                )
                .find_all(
                    "a", attrs={"title": re.compile(r".*\(?Album Review\)?")}
                )
            )
            albums = []
            for album in soup:
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
        endpoint = self.service_endpoint
        data = self.session.get(endpoint)
        soup = (
            bs(data.content.decode("utf-8"), "html5lib")
            .find("li", attrs={"class": re.compile(r".*menu-item-713.*")})
            .find_all("li", attrs={"class": "menu-item-0"})
        )

        return [
            {
                "name": review_page.a.text,
                "id": f"ARP-{review_page.a['href'].split(self.service_endpoint)[1]}",
            }
            for review_page in soup
        ]
