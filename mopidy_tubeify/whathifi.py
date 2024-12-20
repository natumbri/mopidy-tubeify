import re
import unicodedata

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.spotify import Spotify
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)


class WhatHiFi(ServiceClient):
    service_uri = "whathifi"
    service_name = "WhatHiFi"
    service_image = (
        "https://i.scdn.co/image/ab6775700000ee855f28402be2a38675edabae2b"
    )
    service_endpoint = "https://www.whathifi.com"
    service_schema = {
        "spotify_album_links": {
            "item": {
                "name": "iframe",
                "attrs": {"data-lazy-src": Spotify.album_regex},
            }
        },
        "spotify_playlist_link": {
            "container": {
                "name": "a",
                "attrs": {"href": Spotify.playlist_regex},
            }
        },
        "testtracks": {
            "container": {"name": "div", "attrs": {"id": "article-body"}},
            "item": {"name": "li"},
        },
    }

    # listoflists end up here
    def get_playlists_details(self, playlists):
        if playlists == []:
            return []

        if playlists[0] == "testtracks":
            list_items = self._get_items_soup(
                "/features/best-test-tracks-to-trial-your-hi-fi-system",
                "testtracks",
            )
            return [
                {
                    "name": list_item.a.text,
                    "id": list_item.a["href"].replace(
                        self.service_endpoint, ""
                    ),
                }
                for list_item in list_items
            ]

    def get_playlist_tracks(self, playlist):
        soup = self._get_items_soup(playlist)
        spotify_playlist_link = self._get_items_soup(
            soup, "spotify_playlist_link"
        )
        if spotify_playlist_link:
            spotify_playlist = Spotify.playlist_regex.match(
                spotify_playlist_link["href"]
            )
            if spotify_playlist:
                return Spotify.get_playlist_tracks(self, spotify_playlist[1])

        spotify_album_links = self._get_items_soup(soup, "spotify_album_links")
        if spotify_album_links:
            spotify_albums = [
                Spotify.album_regex.match(spotify_album_link["data-lazy-src"])[
                    1
                ]
                for spotify_album_link in spotify_album_links
            ]
            albums = search_and_get_best_albums(
                [
                    (album["artists"], album["name"])
                    for album in Spotify.get_albums_details(
                        self, spotify_albums
                    )
                ],
                self.ytmusic,
            )
            return list(flatten(albums))

        spotify_track_links = soup.find_all(
            "iframe", attrs={"data-lazy-src": Spotify.track_regex}
        )
        if spotify_track_links:
            spotify_tracks = [
                Spotify.track_regex.match(spotify_track_link["data-lazy-src"])[
                    1
                ]
                for spotify_track_link in spotify_track_links
            ]

            tracks = search_and_get_best_match(
                [
                    {
                        "song_name": track["name"],
                        "song_artists": track["artists"],
                        "isrc": None,
                    }
                    for track in Spotify.get_tracks_details(
                        self, spotify_tracks
                    )
                ],
                self.ytmusic,
            )

            return tracks

        youtube_track_regex = re.compile(
            r"https\:\/\/www\.youtube\.com\/embed\/(.{11})"
        )
        youtube_links = soup.find_all(
            "iframe", attrs={"data-lazy-src": youtube_track_regex}
        )

        if youtube_links:
            tracks = []
            youtube_titles = self._split_headings(soup)

            if youtube_titles:
                for title in youtube_titles:
                    video_title = self._extract_title(title)

                    video_id = None
                    while not video_id:
                        title = title.find_next_sibling()
                        if not title:
                            break
                        if "youtube-video" in title.attrs.get("class"):
                            video_id = youtube_track_regex.match(
                                title.find(
                                    "iframe",
                                    attrs={
                                        "data-lazy-src": youtube_track_regex
                                    },
                                )["data-lazy-src"]
                            )[1]
                            tracks.append(
                                {"title": video_title, "videoId": video_id}
                            )
                return tracks

            youtube_videos = [
                youtube_track_regex.match(youtube_link["data-lazy-src"])
                for youtube_link in youtube_links
            ]
            tracks = [
                self.ytmusic.get_song(video[1]) for video in youtube_videos
            ]
            return tracks

        # lots of assumptions down here
        tracks = self._split_headings(soup)

        if tracks:
            tracklist = [
                {
                    "song_artists": self._extract_artists(track),
                    "song_name": self._extract_title(track),
                    "isrc": None,
                }
                for track in tracks
            ]

            return search_and_get_best_match(tracklist, self.ytmusic)

        # tidal is broken
        # tidal_playlist_link = soup.find("a", href=Tidal.playlist_regex)
        # if tidal_playlist_link:
        #     tidal_playlist = Tidal.playlist_regex.match(
        #         tidal_playlist_link["href"]
        #     )
        #     if tidal_playlist:
        #         return Tidal.get_playlist_tracks(self, tidal_playlist[1])

        logger.warn(f"no tracks, get_playlist_tracks: {playlist}")
        return

    def get_service_homepage(self):
        return [
            {
                "name": "The ultimate music tracks to test your hi-fi system",
                "id": "listoflists-testtracks",
            }
        ]

    def _extract_section(self, item, section):
        try:
            return (
                unicodedata.normalize("NFKD", item.text)
                .split("-")[section]
                .strip()
            )
        except Exception as e:
            logger.warn(f"error extracting section: {e}")
            return "[item loading]"

    def _extract_title(self, item):
        return self._extract_section(item, 1)

    def _extract_artists(self, item):
        return self._extract_section(item, 0)

    def _split_headings(self, soup):
        headings = soup.find("div", attrs={"id": "article-body"}).find_all("h2")
        [
            heading.string.replace_with(heading.text.replace("–", "-"))
            for heading in headings
        ]
        return headings
