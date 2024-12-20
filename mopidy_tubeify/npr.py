import re

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.spotify import Spotify
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)


class NPR(ServiceClient):
    service_uri = "npr"
    service_name = "NPR"
    service_image = "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/NPR_Music_logo.jpg/480px-NPR_Music_logo.jpg"
    service_endpoint = "https://www.npr.org"
    service_schema = {
        "bxox": {"container": {"name": "div", "attrs": {"class": "subtopics"}}},
        "embeded_spotify_playlist": Spotify.service_schema["embeded_playlist"],
        "nmf": {
            "container": {"name": "div", "attrs": {"id": "storytext"}},
            # "item": {"tag": "li", "attrs": {}},  # it seems that nmf pages are just text lists with numbers or dots; not html lists
        },
        "nprjson": {"item": {"name": "h6", "attrs": {}}},
        "nprpl": {
            "item": {
                "name": "article",
                "attrs": {"class": re.compile(r"item")},
            },
        },
        "plarchive": {
            "container": {"name": "nav", "attrs": {"class": "archive-nav"}},
            "item": {"name": "li", "attrs": {}},
        },
    }

    def get_playlists_details(self, playlists):
        # is this really a list of playlists, or is it a special case?
        if len(playlists) == 1:
            match_npr_music_playlists = re.match(r"NPRPL(.*)", playlists[0])
            if match_npr_music_playlists:
                articles = self._get_items_soup(
                    match_npr_music_playlists[1], "nprpl"
                )
                results = []
                for article in articles:
                    text = article.find("h2").a
                    article_id = text["href"].replace(self.service_endpoint, "")
                    results.append({"name": text.text, "id": article_id})
                    self.uri_images[article_id] = article.find("img")["src"]
                return results

            match_npr_music_playlists_archive = re.match(
                r"ARCHIVE(.*)", playlists[0]
            )
            if match_npr_music_playlists_archive:
                archives = self._get_items_soup(
                    match_npr_music_playlists_archive[1], "plarchive"
                )
                results = []
                for archive in archives:
                    results.append(
                        {
                            "name": archive.a.text,
                            "id": f'listoflists-NPRPL{archive.a["href"]}',
                        }
                    )
                return results

            # did we get here from the homepage?
            if playlists[0] == "NPR100BSO2022":
                endpoint = "/2022/12/15/1135802083/100-best-songs-2022-page-1"
                idPrefix = "BSOx"
                page1 = [{"name": "100-81", "id": f"{idPrefix}-{endpoint}"}]

            elif playlists[0] == "NPR50BAO2022":
                endpoint = "/2022/12/12/1134898067/50-best-albums-2022-page-1"
                idPrefix = "BAOx"
                page1 = [{"name": "50-41", "id": f"{idPrefix}-{endpoint}"}]

            segments_filter = self._get_items_soup(endpoint, "bxox")
            return page1 + [
                {"name": atag.text, "id": f"{idPrefix}-{atag['href']}"}
                for atag in segments_filter.find_all("a")
            ]

        # ordinary case of list of playlists here
        logger.warn("NPR get_playlists_details not returning anything")
        return

    def get_playlist_tracks(self, playlist):
        # is this a segment from BAOx? (Albums)
        match_BAOx = re.match(r"^BAOx\-(?P<segment>.+)$", playlist)
        if match_BAOx:
            albums_json = self._get_NPR_json(match_BAOx["segment"])
            albums = [(album[0].split("&"), album[1]) for album in albums_json]

            ytalbums = list(
                flatten(search_and_get_best_albums(albums, self.ytmusic))
            )

            return ytalbums

        # is this a segment of BSOx? (Songs)
        match_BSOx = re.match(r"^BSOx\-(?P<segment>.+)$", playlist)
        if match_BSOx:
            tracks_json = self._get_NPR_json(match_BSOx["segment"])
            tracks = [
                {
                    "song_name": track[1],
                    "song_artists": track[0].split("&"),
                    "song_duration": 0,
                    "isrc": None,
                }
                for track in tracks_json
            ]
            return search_and_get_best_match(tracks, self.ytmusic)

        matchNMF = re.match(
            # r"^https\:\/\/www\.npr\.org\/\d{4}\/\d{2}/\d{2}\/\d{10}\/new-music-friday.*$",
            r"^.*new-music-friday.*$",
            playlist,
        )
        print(matchNMF)
        if matchNMF:
            albums_list = []
            albums_soup = self._get_items_soup(
                playlist.replace(self.service_endpoint, ""), "nmf"
            )

            albums_list = re.findall(
                r"(?:\d\.|•) (?P<artist>[^<]+), <em>(?P<album>[^<]+)<",
                str(albums_soup),
            )

            # for album in albums_soup:
            #     try:
            #         album_name = album.em.extract().text.strip()
            #         album_artist = re.split("— |- |, ", album.text)[0].strip()
            #         albums_list.append((album_artist, album_name))
            #     except Exception as e:
            #         logger.debug(
            #             f"error {e} with NMF album {str(album)} on {playlist}"
            #         )

            albums_to_return = search_and_get_best_albums(
                albums_list, self.ytmusic
            )

            if albums_to_return:
                return list(flatten(albums_to_return))

        # some NPR pages have their playlists as spotify playlists (and Apple Music playlists)
        # so, use those.  But the new music friday playlist is a single playlist
        # that is updated each week - so you can't use it to see previous weeks

        # spotify_playlist = Spotify.playlist_regex.match(
        #     self._get_items_soup(playlist, "embeded_spotify_playlist")["src"]
        # )[1]

        # if spotify_playlist:
        #     # hopefully, this isn't a terrible idea...
        #     return Spotify.get_playlist_tracks(self, spotify_playlist)

        if embeded_spotify_playlist := self._get_items_soup(
            playlist, "embeded_spotify_playlist"
        ):
            return Spotify.get_playlist_tracks(
                self,
                Spotify.playlist_regex.match(embeded_spotify_playlist["src"])[
                    1
                ],
            )

    def get_service_homepage(self):
        # future: programatically generate album and song lists from
        # somewhere to include in the library.  The "id" would ideally
        # be something like f"listoflists-{url of first page of the list}"

        # now: hard code a few lists
        return [
            {
                "name": "NPR Music's 100 Best Songs of 2022",
                "id": "listoflists-NPR100BSO2022",
            },
            {
                "name": "NPR Music's 50 Best Albums of 2022",
                "id": "listoflists-NPR50BAO2022",
            },
            {
                "name": "NPR Playlists",
                "id": "listoflists-NPRPL/series/526652351/npr-music-playlists",
            },
            {
                "name": "NPR Playlists Archive",
                "id": "listoflists-ARCHIVE/series/526652351/npr-music-playlists/archive",
            },
            {
                "name": "NPR New Music Friday",
                "id": "listoflists-NPRPL/sections/allsongs/606254804/new-music-friday",
            },
        ]

    def _get_NPR_json(self, endpoint):
        list_numbers = [
            heading
            for heading in self._get_items_soup(endpoint, "nprjson")
            if re.match(r"\d{1,3}\.", heading.text)
        ]
        items_dicts = []
        for list_number in list_numbers:
            html = []
            for tag in list_number.find_next_siblings(class_="edTag"):
                if tag.name == "h6":
                    break
                elif tag.name == "h3":
                    html.append(tag.text.replace('"', ""))
            items_dicts.append(html)
        return items_dicts
