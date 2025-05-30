import re

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)


class AllMusic(ServiceClient):
    service_uri = "allmusic"
    service_name = "AllMusic"
    service_image = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/AllMusic_Logo.svg/187px-AllMusic_Logo.svg.png"
    service_endpoint = "https://www.allmusic.com"

    service_schema = {
        "albums": {
            "container": {
                "name": "div",
                "attrs": {"id": "descriptorAlbumHighlights"},
            },
            "item": {"name": "div", "attrs": {"class": "singleGenreAlbum"}},
        },
        "genre": {
            "container": {"name": "div", "attrs": {"class": "desktopOnly"}},
            "item": {"name": "a", "attrs": {"class": "genre-links"}},
        },
        "genres": {
            "container": {"name": "div", "attrs": {"id": "allGenresGrid"}},
            "item": {"name": "div", "attrs": {"class": "gridItem"}},
        },
        "editorschoice": {
            "container": {"name": "select", "attrs": {"name": "year-filter"}},
            "item": {"name": "option", "attrs": {}},
        },
        "EC-yyyy": {
            "container": {"name": "select", "attrs": {"name": "month-filter"}},
            "item": {"name": "option", "attrs": {}},
        },
        "ECMY": {
            "item": {"name": "div", "attrs": {"class": "editorsChoiceItem"}}
        },
        "FeaturedNewRelease": {
            "item": {"name": "article", "attrs": {"class": "newReleaseItem"}}
        },
        "newreleases": {
            "container": {"name": "select", "attrs": {"name": "week-filter"}},
            "item": {"name": "option", "attrs": {}},
        },
        "songs": {
            "container": {
                "name": "div",
                "attrs": {"id": "descriptorSongHighlights"},
            },
            "item": {"name": "div", "attrs": {"class": "songRow"}},
        },
    }

    def get_playlists_details(self, playlists):
        if playlists == []:
            return []

        if playlists[0] == "genres":
            genres = self._get_items_soup(f"/{playlists[0]}", playlists[0])
            genre_details = []
            for genre in genres:
                meta = genre.find("div", attrs={"class": "meta"})
                name = meta.a.text
                genre_id = f"listoflists-genre-{meta.a['href']}"
                genre_details.append({"name": name, "id": genre_id})
                image = genre.find("img").get(
                    "src", genre.find("img").get("data-src")
                )
                if image:
                    self.uri_images[genre_id] = (
                        f"{self.service_endpoint}{image}"
                    )
            return genre_details

        elif playlists[0] == "editorschoice":
            years = self._get_items_soup(
                f"/newreleases/{playlists[0]}", playlists[0]
            )
            return sorted(
                [
                    {
                        "name": f"Editors' Choices, {year.text.strip()}",
                        "id": f"listoflists-EC-{year['value']}",
                    }
                    for year in years
                ],
                key=lambda d: d["id"],
                reverse=True,
            )

        elif re.match(r"^EC\-(?P<year>\d{4})$", playlists[0]):
            year = re.match(r"^EC\-(?P<year>\d{4})$", playlists[0])["year"]
            months = self._get_items_soup(
                "/newreleases/editorschoice", "EC-yyyy"
            )
            return [
                {
                    "name": month.text.strip(),
                    "id": f"ECMY-/newreleases/editorschoice/{month.text.strip().lower()}-{year}",
                }
                for month in months
            ]

        elif re.match(r"^genre\-(?P<genreURL>.+)$", playlists[0]):
            endpoint = f"/{playlists[0][7:]}"
            subgenre_soup = self._get_items_soup(endpoint, "genre")
            if subgenre_soup:
                subgenres = sorted(
                    [
                        {
                            "name": link["title"],
                            "id": f'listoflists-genre-{link["href"]}',
                        }
                        for link in subgenre_soup
                    ],
                    key=lambda k: k["name"],
                )
            else:
                subgenres = []

            return [
                {
                    "name": name,
                    "id": f"{name.lower()}-{endpoint}/{name.lower()}",
                }
                for name in ["Artists", "Albums", "Songs"]
            ] + subgenres

    def get_playlist_tracks(self, playlist):
        page_albums_filter = []

        # deal with featured new releases pages
        match_FNR = re.match(r"^FNR\-(?P<FNRdate>.+)$", playlist)
        if match_FNR:

            logger.debug(f'matched "featured new release" {playlist}')
            page_albums_filter = self._get_items_soup(
                f"/newreleases/{match_FNR['FNRdate']}", "FeaturedNewRelease"
            )
        match_ECMY = re.match(r"^ECMY\-(?P<albumsURL>.+)$", playlist)
        if match_ECMY:
            logger.debug(f'matched "editors choice month-year" {playlist}')
            page_albums_filter = self._get_items_soup(
                match_ECMY["albumsURL"], "ECMY"
            )

        # deal with genre and style album pages
        match_albums = re.match(r"^albums\-(?P<albumsURL>.+)$", playlist)
        if match_albums:
            logger.debug(f'matched "genre albums page" {playlist}')
            page_albums_filter = self._get_items_soup(
                match_albums["albumsURL"], "albums"
            )
            # genre and style pages use spans and "descriptor" classes
            # convert to divs
            for page_album in page_albums_filter:
                artist_tag = page_album.find("span", class_="descriptorArtist")
                artist_tag.name = "div"
                artist_tag["class"] = "artist"
                title_tag = page_album.find("span", class_="descriptorTitle")
                title_tag.name = "div"
                title_tag["class"] = "title"

        if page_albums_filter:
            albums = [
                (
                    page_album.find(class_="artist")
                    .text.strip()
                    .split(" / "),
                    page_album.find(class_="title").text.strip(),
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
            page_tracks_filter = self._get_items_soup(
                match_songs["songsURL"], "songs"
            )
            tracks = [
                {
                    "song_name": track.find("span", class_="songTitle").a.text,
                    "song_artists": track.find("div", class_="songRight")
                    .text.strip()
                    .split(" / "),
                    "song_duration": 0,
                    "isrc": None,
                }
                for track in page_tracks_filter
            ]
            logger.debug(f"total tracks for {playlist}: {len(tracks)}")
            return search_and_get_best_match(tracks, self.ytmusic)

    def get_service_homepage(self):
        weeks = self._get_items_soup("/newreleases", "newreleases")
        return (
            [
                {
                    "name": f"Featured New Releases, {week.text.strip()}",
                    "id": f"FNR-{week['value']}",
                }
                for week in weeks
            ]
            + [{"name": "Genres", "id": "listoflists-genres"}]
            + [{"name": "Editors' Choice", "id": "listoflists-editorschoice"}]
        )
if __name__ == "__main__":
    headers = {
        "User-Agent": r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
    }
    from ytmusicapi import YTMusic

    scraper = AllMusic(None, headers, YTMusic())
    homepage = scraper.get_service_homepage()
    print(homepage)
    print([homepage[0]["id"]])
    gpd = scraper.get_playlist_tracks(homepage[0]["id"])
    print(gpd)
    # gpd = scraper.get_playlists_details([gpd[2]["id"][12:]])
    # print(gpd)
    # gpt = scraper.get_playlist_tracks(gpd[0]["id"])
    # print(gpt)