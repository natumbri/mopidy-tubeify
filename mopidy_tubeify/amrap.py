import json
import re
import time
from operator import itemgetter

from bs4 import BeautifulSoup as bs

from mopidy_tubeify import logger
from mopidy_tubeify.data import flatten
from mopidy_tubeify.serviceclient import ServiceClient
from mopidy_tubeify.yt_matcher import search_and_get_best_match


def format_episode_date(date_str):
    return time.strftime("%-d %b %Y", time.strptime(date_str, "%Y-%m-%d"))


class Amrap(ServiceClient):
    def __init__(self, proxy, headers, ytm_client, stationId, stationName):
        super().__init__(proxy, headers, ytm_client)
        self.stationId = stationId
        self.service_uri = stationId
        self.service_name = stationName

    def get_amrap_headers(self, stationId, programId):
        position_url = f"https://airnet.org.au/program/position.js.php?url=https://{stationId}.radiopages.info/{programId}&referrer=https%3A//airnet.org.au"

        position_response = self.session.get(position_url)

        embed_url = re.search(
            r".+\[\{\surl\:\s+\"(?P<embed_url>[^\"]+)", position_response.text
        )["embed_url"]

        program_details_response = self.session.get(embed_url)
        program_details_soup = bs(
            program_details_response.content.decode("unicode-escape"),
            "html5lib",
        )
        program_details_script = program_details_soup.find(
            "div", class_="static"
        ).script.contents[0]
        program_details = {
            "owner": False,
            "csrfToken": re.search(
                r".+csrfToken\s=\s\'(?P<csrfToken>.+)'", program_details_script
            )["csrfToken"],
            "shareUrl": re.search(
                r".+phpShareUrl\s=\s\'(?P<phpShareUrl>.+)'",
                program_details_script,
            )["phpShareUrl"],
            "stationId": re.search(
                r".+stationId\s=\s(?P<stationId>.+);", program_details_script
            )["stationId"],
            "programId": re.search(
                r".+programId\s=\s(?P<programId>[^;]+)", program_details_script
            )["programId"],
            "programUrlComponent": re.search(
                r".+programUrlComponent\s=\s\'(?P<programUrlComponent>[^\']+)",
                program_details_script,
            )["programUrlComponent"],
            "programName": program_details_soup.find(
                "span", class_="programName-main"
            ).text,
            "programBroadcasters": program_details_soup.find(
                "span", class_="broadcasters-main"
            ).text,
            "stationName": re.search(
                r".+stationName\s=\s\'(?P<stationName>.+)'",
                program_details_script,
            )["stationName"],
        }

        return program_details

    def get_playlists_details(self, playlists):
        def job(playlist):
            # deal with program pages
            match_PROGRAM = re.match(
                r"^PROGRAM-(?P<playlist>(?P<stationId>[^\.]+)\.radiopages\.info\/(?P<programId>.+)$)",
                playlist,
            )
            if match_PROGRAM:
                logger.debug(f'matched "program" {playlist}')
                program_details = self.get_amrap_headers(
                    stationId=match_PROGRAM["stationId"],
                    programId=match_PROGRAM["programId"],
                )
                self.session.headers.update(
                    {"X-CSRF-Token": program_details["csrfToken"]}
                )
                endpoint = "https://airnet.org.au/program/ajax-server/getEpisodeArchive.php"

                episode_archive_page = self.session.get(
                    endpoint, params=program_details
                )
                episode_archive_soup = bs(
                    episode_archive_page.content.decode("utf-8"), "html5lib"
                )

                archive_json = json.loads(episode_archive_soup.text)

                episode_date_re = re.compile(
                    r"^.+/(?P<date>(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2}))-?.*$"
                )

                years = sorted(
                    [item for item in archive_json["archiveDetails"]],
                    reverse=True,
                )

                playlist_results = []
                for year in years:
                    program_details.update({"year": year})
                    episode_archive_page = self.session.get(
                        endpoint, params=program_details
                    )
                    episode_archive_soup = bs(
                        episode_archive_page.content.decode("utf-8"), "html5lib"
                    )
                    episode_archive_json = json.loads(
                        episode_archive_soup.text
                    )["episodes"]

                    [
                        playlist_results.append(
                            {
                                "name": (
                                    f'{program_details["programName"]}, '
                                    f'{format_episode_date(episode_date_re.search(episode["url"])["date"])}'
                                ),
                                "id": f'{match_PROGRAM["playlist"]};{episode["id"]}',
                                "date": time.strptime(
                                    episode_date_re.search(episode["url"])[
                                        "date"
                                    ],
                                    "%Y-%m-%d",
                                ),
                            }
                        )
                        for episode in episode_archive_json
                        if episode
                    ]

                return sorted(
                    playlist_results, key=itemgetter("date"), reverse=True
                )
            else:
                # for other sorts of amrap playlists
                return

        # does amrap uses a captcha? be careful before going multi-threaded
        results = [job(playlist) for playlist in playlists]

        return list(flatten(results))

    def get_playlist_tracks(self, playlist):
        match_EPISODE = re.match(
            r"^(?P<station>[^\.]+)\.radiopages\.info\/(?P<program>.+)\;(?P<episode>.+)$",
            playlist,
        )

        program_details = self.get_amrap_headers(
            stationId=match_EPISODE["station"],
            programId=match_EPISODE["program"],
        )
        program_details.update({"episode": match_EPISODE["episode"]})
        self.session.headers.update(
            {"X-CSRF-Token": program_details["csrfToken"]}
        )

        episode_url = "https://airnet.org.au/program/ajax-server/getEpisode.php"
        episode_response = self.session.post(episode_url, data=program_details)
        episode_response_soup = bs(
            episode_response.content.decode("unicode-escape"),
            "html5lib",  # "lxml"
        )
        track_table = episode_response_soup.find("table")
        track_class = re.compile(".*playlist-mainText.*")
        tracks = track_table.find_all("td", class_=track_class)
        track_list = [
            track.get_text(strip=True)
            .replace("\n", "")
            .replace("\t", "")
            .replace("<\\/td>", "")
            .replace(":", "")
            .strip()
            for track in tracks
        ]
        track_dicts = []
        for track in track_list:
            this_track = [
                item.strip().replace("\\/", "/").replace("</a>", "")
                for item in re.split(r'\.| -|- |\\\\n|\||"| \\\\/ ', track)
            ]

            this_track[:] = [
                item
                for item in this_track
                if "\\t" not in item
                and item.strip() != ""
                and len(item.strip()) >= 2
                and not item.strip().isdigit()
            ]

            # if the splitting didn't work, try something more agressive
            if len(this_track) == 1:
                this_track[:] = [item for item in re.split("/", this_track[0])]

            # if the split worked, assume artist first, then track name
            # and don't use any of the others.
            if len(this_track) >= 2:
                track_dicts.append(
                    {
                        "song_name": this_track[1],
                        "song_artists": [this_track[0]],
                        "song_duration": 0,
                        "isrc": None,
                    }
                )

        return search_and_get_best_match(track_dicts, self.ytmusic)

    def get_service_homepage(self):
        base_url = f"https://{self.stationId}.radiopages.info/"
        position_url = f"https://airnet.org.au/program/position.js.php?url={base_url}&referrer=https%3A//airnet.org.au"

        programs_response = self.session.get(position_url)
        programs_url = re.search(
            r".+\[\{\surl\:\s+\"(?P<programs_url>[^\"]+)",
            programs_response.text,
        )["programs_url"]

        programs_details_response = self.session.get(programs_url)
        programs_details_soup = bs(
            programs_details_response.content.decode("utf-8"), "html5lib"
        )
        programs_details_table = programs_details_soup.find(
            "div", attrs={"id": "programList"}
        ).table.tbody

        return [
            {
                "name": f"{program.text}",
                "id": f"listoflists-PROGRAM-{program['href'][8:]}",
            }
            for program in programs_details_table.find_all("a")
        ]
