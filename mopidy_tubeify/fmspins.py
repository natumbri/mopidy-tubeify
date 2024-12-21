import re

from mopidy_tubeify import logger
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import (
    search_and_get_best_albums,
    search_and_get_best_match,
)


class FMSpins(ServiceClient):
    service_uri = "fmspins"
    service_name = "FMSpins"
    service_image = None
    service_endpoint = "https://fmspins.com/"
    service_schema = {
        "stations": {
            "container": {"name": "div", "attrs": {"class": "stations"}},
            "item": {
                "name": "div",
                "attrs": {"class": re.compile(r"station$")},
            },
        },
        "tracks": {
            "container": {"name": "div", "attrs": {"id": "current-spins"}},
            "item": {
                "name": "div",
                "attrs": {"class": "wrapper spin-media"},
            },
        },
        "charttracks": {
            "container": {"name": "div", "attrs": {"class": "track-list"}},
            "item": {
                "name": "div",
                "attrs": {"class": "media track"},
            },
        },
        "dates": {
            "container": {"name": "ul", "attrs": {"class": "time"}},
            "item": {
                "name": "li",
                "attrs": {"class": re.compile(r"^(year|days)$")},
            },
        },
        "djs": {
            "container": {"name": "div", "attrs": {"class": "dj-list"}},
            "item": {
                "name": "a",
                "attrs": {"class": "list-group-item"},
            },
        },
    }

    # listoflists end up here
    def get_playlists_details(self, playlists):
        match_station = re.match(r"^/?(?P<type>.*)(/|-)(?P<station>.{4})$", playlists[0])
        if match_station:
            station = match_station["station"]
            if match_station["type"] == "station":
                return [
                    {
                        "name": f"{station} Playlist",
                        "id": f'playlist-{station}'
                    },
                    {
                        "name": f"Trending on {station}",
                        "id": f'listoflists-trending-{station}'
                    },
                    {
                        "name": f"{station} DJs",
                        "id": f'listoflists-DJs-{station}'
                    },
                ]
            elif match_station["type"] == "trending":
                endpoint = self.service_endpoint.replace("//",f"//{station}.")+"-/filters/time"
                data = self.session.get(endpoint)
                return [
                    {
                        "name": f"{track.text}",
                        "id": f"{station}-/charts?date={track['data-date']}",

                    }
                    for track in self._get_items_soup(data, "dates")
                ]

            elif match_station["type"] == "DJs":
                endpoint = self.service_endpoint.replace("//",f"//{station}.")+"-/djs"
                data = self.session.get(endpoint)
                return [
                    {
                        "name": f'{dj.find("div", attrs={"class": "dj-name"}).text}',
                        "id": f"{station}-{dj['href']}",
                    }
                    for dj in self._get_items_soup(data, "djs")
                ]

        return []

    def get_playlist_tracks(self, playlist):
        match_playlist = re.match(r"^playlist-(?P<station>.{4})$", playlist)
        if match_playlist:
            data = self.session.get(self.service_endpoint.replace("//",f"//{match_playlist['station']}."))
            tracks = [
                {
                    "song_name": track.find("div", attrs={"class":"track"}).text,
                    "song_artists": [track.find("div", attrs={"class":"artist"}).text],
                    "isrc": None,
                }
                for track in self._get_items_soup(data, "tracks")
            ]
            return search_and_get_best_match(tracks, self.ytmusic)
        
        match_charts = re.match(r"^(?P<station>.{4})(?P<chart>-/charts\?date=\d{1,4})$", playlist)
        if match_charts:
            data = self.session.get(self.service_endpoint.replace("//",f"//{match_charts['station']}.")+match_charts['chart'])
            tracks = [
                {
                    "song_name": track.find("div", attrs={"class":"track-name"}).text,
                    "song_artists": [track.find("div", attrs={"class":"artist-name"}).text],
                    "isrc": None,
                }
                for track in self._get_items_soup(data, "charttracks")
            ]
            return search_and_get_best_match(tracks, self.ytmusic)

        match_djs = re.match(r"^(?P<station>.{4})-(?P<dj>/dj-\d{1,4})$", playlist)
        if match_djs:
            data = self.session.get(self.service_endpoint.replace("//",f"//{match_djs['station']}.")+match_djs['dj'])
            tracks = [
                {
                    "song_name": track.find("div", attrs={"class":"track-name"}).text,
                    "song_artists": [track.find("div", attrs={"class":"artist-name"}).text],
                    "isrc": None,
                }
                for track in self._get_items_soup(data, "charttracks")
            ]
            return search_and_get_best_match(tracks, self.ytmusic)

        return []        

    def get_service_homepage(self):
        return [
            {
                "name": station.a["href"].replace("/station/", "")
                + " "
                + station.text,
                "id": f'listoflists-{station.a["href"]}',
            }
            for station in self._get_items_soup("", "stations")
        ]


if __name__ == "__main__":
    headers = {
        "User-Agent": r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"
    }
    from ytmusicapi import YTMusic

    scraper = FMSpins(None, headers, YTMusic())
    homepage = scraper.get_service_homepage()
    print(homepage)
    gpd = scraper.get_playlists_details([homepage[0]["id"][12:]])
    print(gpd)
    gpd = scraper.get_playlists_details([gpd[2]["id"][12:]])
    print(gpd)
    gpt = scraper.get_playlist_tracks(gpd[0]["id"])
    print(gpt)