#!/usr/bin/env python3

# Program Name: zoom-recording-downloader.py
# Description:  Zoom Recording Downloader is a cross-platform Python script
#               that uses Zoom's API (v2) to download and organize all
#               cloud recordings from a Zoom account onto local storage.
#               This Python script uses the OAuth method of accessing the Zoom API
# Created:      2020-04-26
# Author:       Ricardo Rodrigues
# Website:      https://github.com/ricardorodrigues-ca/zoom-recording-downloader
# Forked from:  https://gist.github.com/danaspiegel/c33004e52ffacb60c24215abf8301680

# system libraries
import base64
import datetime
import json
import os
import re as regex
import signal
import sys as system
import time

# installed libraries
import dateutil.parser as parser
import pathvalidate as path_validate
import requests
import tqdm as progress_bar
import argparse

CONF_PATH = "zoom-recording-downloader.conf"
with open(CONF_PATH, encoding="utf-8-sig") as json_file:
    CONF = json.loads(json_file.read())

ACCOUNT_ID = CONF["OAuth"]["account_id"]
CLIENT_ID = CONF["OAuth"]["client_id"]
CLIENT_SECRET = CONF["OAuth"]["client_secret"]

APP_VERSION = "3.0 (OAuth)"

API_ENDPOINT_USER_LIST = "https://api.zoom.us/v2/users"

RECORDING_START_YEAR = 2025
RECORDING_START_MONTH = 6
RECORDING_START_DAY = 1


RECORDING_END_YEAR = 2025
RECORDING_END_MONTH = 6
RECORDING_END_DAY = 30


#RECORDING_END_DATE = datetime.date.today()
DOWNLOAD_DIRECTORY = r'N:\legacy recordings'
COMPLETED_MEETING_IDS_LOG = 'completed-downloads.log'
COMPLETED_MEETING_IDS = set()


class Color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARK_CYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"




def parse_args():
    parser = argparse.ArgumentParser(description="Download Zoom recordings for specified user or all users.")
    parser.add_argument("-e", "--email", type=str, help="Email of the user to download recordings for.")
    return parser.parse_args()




def load_access_token():
    """OAuth function to load or refresh the access token."""
    global ACCESS_TOKEN, AUTHORIZATION_HEADER, token_expiry

    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ACCOUNT_ID}"
    client_cred = f"{CLIENT_ID}:{CLIENT_SECRET}"
    client_cred_base64_string = base64.b64encode(client_cred.encode("utf-8")).decode("utf-8")

    headers = {
        "Authorization": f"Basic {client_cred_base64_string}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url, headers=headers).json()

    try:
        # Save token and expiration time
        ACCESS_TOKEN = response["access_token"]
        expires_in = response.get("expires_in", 3600)  # Default to 1 hour if not provided
        token_expiry = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)

        AUTHORIZATION_HEADER = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        print(f"New token acquired. Expires at: {token_expiry}")

    except KeyError as e:
        print(f"{Color.RED}Error loading access token: {e}{Color.END}")
        raise

def check_token_validity():
    """Check if the token is valid; refresh it if expired."""
    global token_expiry
    print(f"Current time: {datetime.datetime.now()}, Token expiry time: {token_expiry}")
    if datetime.datetime.now() >= token_expiry:
        print(f"{Color.YELLOW}Token expired. Refreshing...{Color.END}")
        load_access_token()
    else:
        print(f"{Color.GREEN}Token is valid.{Color.END}")

def is_network_available():
    try:
        requests.get("https://zoom.us", timeout=5)
        return True
    except requests.ConnectionError:
        return False


def get_users():
    """ loop through pages and return all users
    """
    response = requests.get(url=API_ENDPOINT_USER_LIST, headers=AUTHORIZATION_HEADER)

    if not response.ok:
        print(response)
        print(
            f"{Color.RED}### Could not retrieve users. Please make sure that your access "
            f"token is still valid{Color.END}"
        )

        system.exit(1)

    page_data = response.json()
    total_pages = int(page_data["page_count"]) + 1

    all_users = []

    for page in range(1, total_pages):
        url = f"{API_ENDPOINT_USER_LIST}?page_number={str(page)}"
        user_data = requests.get(url=url, headers=AUTHORIZATION_HEADER).json()
        users = ([
            (
                user["email"],
                user["id"],
                user["first_name"],
                user["last_name"]
            )
            for user in user_data["users"]
        ])

        all_users.extend(users)
        page += 1

    return all_users


def format_filename(params):
    file_extension = params["file_extension"]
    recording = params["recording"]
    recording_id = params["recording_id"]
    recording_type = params["recording_type"]

    invalid_chars_pattern = r'[<>:"/\\|?*\x00-\x1F]'
    topic = regex.sub(invalid_chars_pattern, '', recording["topic"])
    rec_type = recording_type.replace("_", " ").title()
    meeting_time = parser.parse(recording["start_time"]).strftime("%Y.%m.%d - %I.%M %p UTC")

    return (
        f"{topic} - {meeting_time} - {rec_type} - {recording_id}.{file_extension.lower()}",
        f"{topic} - {meeting_time}"
    )


def get_downloads(recording):
    if not recording.get("recording_files"):
        raise Exception("No recording files found.")

    downloads = []
    for download in recording["recording_files"]:
        file_type = download.get("file_type", "")
        file_extension = download.get("file_extension", "")
        recording_id = download["id"]
        file_size = download.get("file_size", 0)  # Capture file size from API

        if file_type == "":
            recording_type = "incomplete"
        elif file_type != "TIMELINE":
            recording_type = download.get("recording_type", "unknown")
        else:
            recording_type = file_type

        download_url = f"{download['download_url']}?access_token={ACCESS_TOKEN}"
        downloads.append((file_type, file_extension, download_url, recording_type, recording_id, file_size))

    return downloads



def get_recordings(email, page_size, rec_start_date, rec_end_date):
    return {
        "userId": email,
        "page_size": page_size,
        "from": rec_start_date,
        "to": rec_end_date
    }


def per_delta(start, end, delta):
    """ Generator used to create deltas for recording start and end dates
    """
    curr = start
    while curr < end:
        yield curr, min(curr + delta, end)
        curr += delta


def list_recordings(email, title_filter=""):
    recordings = []

    for start, end in per_delta(
        datetime.date(RECORDING_START_YEAR, RECORDING_START_MONTH, RECORDING_START_DAY),
        datetime.date(RECORDING_END_YEAR, RECORDING_END_MONTH, RECORDING_END_DAY),
        datetime.timedelta(days=30)
    ):
        post_data = get_recordings(email, 300, start, end)
        response = requests.get(
            url=f"https://api.zoom.us/v2/users/{email}/recordings",
            headers=AUTHORIZATION_HEADER,
            params=post_data
        )
        recordings_data = response.json()

        if 'meetings' in recordings_data:
            if title_filter:
                filtered_meetings = [meeting for meeting in recordings_data['meetings'] if title_filter.lower() in meeting['topic'].lower()]
                recordings.extend(filtered_meetings)
            else:
                recordings.extend(recordings_data['meetings'])
        else:
            print(f"No meetings found for user {email} from {start} to {end}.")
            if 'message' in recordings_data:
                print(f"Error: {recordings_data['message']}")

    return recordings


def download_recording(download_url, email, filename, folder_name, expected_size):
    dl_dir = DOWNLOAD_DIRECTORY
    sanitized_download_dir = path_validate.sanitize_filepath(dl_dir)
    sanitized_filename = path_validate.sanitize_filename(filename)
    full_filename = os.path.join(sanitized_download_dir, sanitized_filename)

    # Ensure directory exists
    os.makedirs(sanitized_download_dir, exist_ok=True)

    # Check if the file already exists
    if os.path.exists(full_filename):
        actual_size = os.path.getsize(full_filename)
        if actual_size == expected_size:
            print(f"{Color.GREEN}File already downloaded and verified: {filename}{Color.END}. Skipping to next file.")
            return True
        else:
            print(
                f"{Color.YELLOW}File exists but size mismatch (expected: {expected_size}, found: {actual_size}). Redownloading...{Color.END}")
            os.remove(full_filename)  # Delete the file if size mismatch before redownload
    else:
        print(f"{Color.BLUE}File not found, downloading: {filename}{Color.END}")

    def attempt_download():
        try:
            response = requests.get(download_url, stream=True, timeout=(5, 60))
            total_size = int(response.headers.get('content-length', 0))
            with open(full_filename, "wb") as fd, progress_bar.tqdm(
                    total=total_size, unit='iB', unit_scale=True
            ) as prog_bar:
                for chunk in response.iter_content(32 * 1024):
                    prog_bar.update(len(chunk))
                    fd.write(chunk)

            actual_size = os.path.getsize(full_filename)
            if actual_size == expected_size:
                print(f"{Color.GREEN}Download successful: {filename}{Color.END}")
                return True
            else:
                print(f"{Color.RED}Size mismatch (expected: {expected_size}, actual: {actual_size}).{Color.END}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"{Color.RED}Error during download: {e}{Color.END}")
            return False

    # Retry logic
    for attempt in range(3):
        if attempt_download():
            return True
        else:
            print(f"{Color.YELLOW}Retrying download ({attempt + 1}/3)...{Color.END}")
            time.sleep(5)  # Wait before retrying

    print(f"{Color.RED}Failed to download {filename} after 3 attempts.{Color.END}")
    return False


def log_download_issue(filename):
    with open('downloads_with_issues.txt', 'a') as log_file:
        log_file.write(f"Download size mismatch: {filename}\n")


def load_completed_meeting_ids():
    try:
        with open(COMPLETED_MEETING_IDS_LOG, 'r') as fd:
            [COMPLETED_MEETING_IDS.add(line.strip()) for line in fd]

    except FileNotFoundError:
        print(
            f"{Color.DARK_CYAN}Log file not found. Creating new log file: {Color.END}"
            f"{COMPLETED_MEETING_IDS_LOG}\n"
        )


def download_recordings_for_user(email, recordings):
    total_count = len(recordings)
    print(f"==> Found {total_count} recordings for {email}")

    for index, recording in enumerate(recordings):
        check_token_validity()
        success = False
        meeting_id = recording["uuid"]
        #if meeting_id in COMPLETED_MEETING_IDS:
        #    print(f"==> Skipping already downloaded meeting: {meeting_id}")
        #    continue

        try:
            downloads = get_downloads(recording)
        except Exception:
            print(f"{Color.RED}### Recording files missing for call with id {Color.END}'{recording['id']}'\n")
            continue

        for file_type, file_extension, download_url, recording_type, recording_id, file_size in downloads:
            if recording_type != 'incomplete':
                filename, folder_name = format_filename({
                    "file_type": file_type,
                    "recording": recording,
                    "file_extension": file_extension,
                    "recording_type": recording_type,
                    "recording_id": recording_id
                })
                truncated_url = download_url[0:64] + "..."
                print(f"==> Downloading ({index + 1} of {total_count}) as {filename}")
                success |= download_recording(download_url, email, filename, folder_name, file_size)
            else:
                print(f"{Color.RED}### Incomplete Recording ({index + 1} of {total_count}) for recording with id {Color.END}'{recording_id}'")
                success = False

        if success:
            with open(COMPLETED_MEETING_IDS_LOG, 'a') as log:
                COMPLETED_MEETING_IDS.add(meeting_id)
                log.write(meeting_id)
                log.write('\n')
                log.flush()




def handle_graceful_shutdown(signal_received, frame):
    print(f"\n{Color.DARK_CYAN}SIGINT or CTRL-C detected. system.exiting gracefully.{Color.END}")

    system.exit(0)


# ################################################################
# #                        MAIN                                  #
# ################################################################
def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    load_access_token()
    load_completed_meeting_ids()


    if not is_network_available():
        print(f"{Color.RED}No internet connection. Please check your network and try again.{Color.END}")
        system.exit(1)


    # Prompt for user email
    user_email = input("Please enter the email of the user to download recordings for (leave empty for all users): ")
    meeting_title_fragment = ""

    if user_email:
        # Prompt for part of the meeting title only if an email is provided
        meeting_title_fragment = input("Enter part of the meeting title to filter by (leave empty for all recordings): ")

    if user_email:
        print(f"{Color.BOLD}Getting recording list for {user_email} with title containing: '{meeting_title_fragment}'{Color.END}")
        recordings = list_recordings(user_email, meeting_title_fragment)
        download_recordings_for_user(user_email, recordings)
    else:
        # If no email is provided, process all users
        print(f"{Color.BOLD}Getting user accounts...{Color.END}")
        users = get_users()
        for email, user_id, first_name, last_name in users:
            userInfo = f"{first_name} {last_name} - {email}" if first_name and last_name else email
            print(f"\n{Color.BOLD}Getting recording list for {userInfo}{Color.END}")
            recordings = list_recordings(user_id)
            download_recordings_for_user(email, recordings)

    print(f"\n{Color.BOLD}{Color.GREEN}*** All done! ***{Color.END}")
    save_location = os.path.abspath(DOWNLOAD_DIRECTORY)
    print(
        f"\n{Color.BLUE}Recordings have been saved to: {Color.UNDERLINE}{save_location}{Color.END}\n"
    )


if __name__ == "__main__":
    # tell Python to shutdown gracefully when SIGINT is received
    signal.signal(signal.SIGINT, handle_graceful_shutdown)

    main()
