import re

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)


class AllMusic(ServiceClient):
    def get_playlists_details(self, playlists):
        logger.info(f"{playlists}")

        if playlists[0] == "genres":
            endpoint = f"https://www.allmusic.com/{playlists[0]}"
            genre_block_re = re.compile(r"^genre\s(left|middle|right)$")
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib").find("div", id="cmn_wrap")
            genres = soup.find_all("div", attrs={"class": genre_block_re})

            return [
                {
                    "name": genre.h2.text,
                    "id": f"listoflists-genre-{genre.a['href']}",
                }
                for genre in genres
            ]

        elif re.match(r"^genre\-(?P<genreURL>.+)$", playlists[0]):
            endpoint = playlists[0][6:]
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")

            return [
                {
                    "name": "Artists",
                    "id": f"artists-{endpoint}/artists",
                },
                {
                    "name": "Albums",
                    "id": f"albums-{endpoint}/albums",
                },
                {
                    "name": "Songs",
                    "id": f"songs-{endpoint}/songs",
                },
            ] + sorted(
                [
                    {
                        "name": link["title"],
                        "id": f'listoflists-genre-https://www.allmusic.com{link["href"]}',
                    }
                    for link in soup.find(
                        "div", class_="desktop-only"
                    ).find_all("a", class_="genre-links")
                ],
                key=lambda k: k["name"],
            )

    def get_playlist_tracks(self, playlist):

        page_albums_filter = []

        # deal with featured new releases pages
        match_FNR = re.match(r"^FNR\-(?P<FNRdate>.+)$", playlist)
        if match_FNR:
            logger.debug(f'matched "featured new release" {playlist}')
            playlist = match_FNR["FNRdate"]
            endpoint = f"https://www.allmusic.com/newreleases/{playlist}"
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            page_albums_filter = soup.find_all("div", class_="new-release")

        # deal with genre and style album pages
        match_albums = re.match(r"^albums\-(?P<albumsURL>.+)$", playlist)
        if match_albums:
            logger.debug(f'matched "genre albums page" {playlist}')
            endpoint = match_albums["albumsURL"]
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            page_albums_filter = soup.find(
                "section", class_="album-highlights"
            ).find_all("div", class_="album-highlight")
            # html = page_albums_filter[0].prettify("utf-8")
            # with open("/tmp/output1.html", "wb") as file:
            #     file.write(html)

        if page_albums_filter:
            albums = [
                (
                    page_album.find("div", class_="artist")
                    .text.strip()
                    .split(" / "),
                    page_album.find("div", class_="title").text.strip(),
                )
                for page_album in page_albums_filter
            ]

            albums_to_return = search_and_get_best_albums(
                [album for album in albums if album[1]], self.ytmusic
            )

            return list(flatten(albums_to_return))

        # deal with genre and style songs pages
        match_songs = re.match(r"^songs\-(?P<songsURL>.+)$", playlist)
        if match_songs:
            logger.debug(f'matched "genre songs page" {playlist}')
            endpoint = match_songs["songsURL"]
            data = self.session.get(endpoint)
            soup = bs(data.text, "html5lib")
            page_tracks_filter = (
                soup.find("section", class_="song-highlights")
                .find("tbody")
                .find_all("tr")
            )

            tracks = [
                {
                    "song_name": track.find("td", class_="title").a.text,
                    "song_artists": [
                        performer.text
                        for performer in track.find(
                            "td", class_="performer"
                        ).find_all("a")
                    ],
                    "song_duration": 0,
                    "isrc": None,
                }
                for track in page_tracks_filter
            ]
            logger.debug(f"total tracks for {playlist}: {len(tracks)}")
            return search_and_get_best_match(tracks, self.ytmusic)

    def get_service_homepage(self):

        endpoint = r"https://www.allmusic.com/newreleases"
        data = self.session.get(endpoint)
        soup = bs(data.text, "html5lib")

        week_filter = soup.find("select", {"name": "week-filter"})
        weeks = week_filter.find_all("option")

        return [
            {
                "name": f"Featured New Releases, {week.text.strip()}",
                "id": f"FNR-{week['value']}",
            }
            for week in weeks
        ] + [{"name": "Genres", "id": "listoflists-genres"}]
