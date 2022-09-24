import json
import re

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_album


class Discogs(ServiceClient):
    def get_playlists_details(self, playlists):
        def job(playlist):

            # for what to listen to if you like lists
            match_WTLT = re.match(r"^WTLT\-(?P<wtltpage>.+)$", playlist)
            if match_WTLT:
                logger.debug(f'matched "what to listen to page:" {playlist}')
                playlist = match_WTLT["wtltpage"]
                endpoint = f"https://www.discogs.com/digs/music/{playlist}"
                data = self.session.get(endpoint)
                soup = bs(data.text, "html5lib")
                new_releases_filter = soup.find_all(
                    "div", class_=re.compile(r".*release-item.*")
                )

                albums_dicts = [
                    {
                        "artist": new_release.find(
                            "div", class_=re.compile(r".*release-artist.*")
                        ).text,
                        "album": new_release.find(
                            "div", class_=re.compile(r".*release-title.*")
                        ).text,
                    }
                    for new_release in new_releases_filter
                ]

                return [
                    {
                        "name": f"{album['artist']}, {album['album']}",
                        "id": f"{json.dumps(album)}",
                    }
                    for album in albums_dicts
                ]
            else:
                # for other sorts of allmusic playlists
                pass

        results = []

        # does allmusic uses a captcha? be careful before going multi-threaded
        [results.append(job(playlist)) for playlist in playlists]

        return list(flatten(results))

    def get_playlist_tracks(self, playlist):

        # deal with what to listen to pages
        if re.match(r"^WTLT\-(?P<albumId>.+)$", playlist):
            return self.get_playlists_details([playlist])

        artists_albumtitle = (
            [json.loads(playlist)["artist"]],
            json.loads(playlist)["album"],
        )

        print(artists_albumtitle)

        try:
            # experimental, using ytmusic album instead of track-by-track matching
            album_browseId_list = search_and_get_best_album(
                artists_albumtitle=artists_albumtitle, ytmusic=self.ytmusic
            )
            print(f"a bId: {album_browseId_list}")
            album_browseId = album_browseId_list[0]["browseId"]
            album = self.ytmusic.get_album(album_browseId)
            tracks = album["tracks"]

            fields = ["artists", "thumbnails"]
            [
                track.update({field: album[field]})
                for field in fields
                for track in tracks
                if track[field] is None
            ]

            [
                track.update(
                    {
                        "album": {
                            "name": album["title"],
                            "id": album_browseId,
                        }
                    }
                )
                for track in tracks
            ]
            return tracks

        except Exception as e:

            logger.warn(
                f"error {e} getting album {artists_albumtitle} from ytmusic"
            )

        return

    def get_service_homepage(self):

        endpoint = r"https://www.discogs.com/digs/music/"
        data = self.session.get(endpoint)
        soup = bs(data.text, "html5lib")
        if_you_like_divs = soup.find_all(
            "li", attrs={"class": re.compile(".*tag-if-you-like.*")}
        )

        if_you_like_dicts = [
            {"title": div.h3.a.text, "href": div.h3.a["href"]}
            for div in if_you_like_divs
        ]

        if_you_like_results = [
            {
                "name": f"{if_you_like_dict['title']}",
                "id": f"listoflists-WTLT-{if_you_like_dict['href'][31:]}",
            }
            for if_you_like_dict in if_you_like_dicts
        ]

        of_all_time_divs = soup.find_all(
            "li", attrs={"class": re.compile(".*category-music.*")}
        )
        of_all_time_divs[:] = [
            of_all_time_div
            for of_all_time_div in of_all_time_divs
            if re.match(".*of All Time$", of_all_time_div.text.strip())
        ]

        of_all_time_dicts = [
            {"title": div.text.strip(), "href": div.a["href"]}
            for div in of_all_time_divs
        ]

        of_all_time_results = [
            {
                "name": f"{of_all_time_dict['title']}",
                "id": f"listoflists-WTLT-{of_all_time_dict['href'][31:]}",
            }
            for of_all_time_dict in of_all_time_dicts
        ]

        return if_you_like_results + of_all_time_results
