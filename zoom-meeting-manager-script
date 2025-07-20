import csv
import requests
import logging
import json
import os
import signal
import sys
import datetime
import base64
import re
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
CONF_PATH = os.path.join(script_dir, "zoom-meeting-creator.conf")
# === Load config from external JSON ===1
with open(CONF_PATH, encoding="utf-8-sig") as json_file:
    CONF = json.load(json_file)

ACCOUNT_ID = CONF["OAuth"]["account_id"]
CLIENT_ID = CONF["OAuth"]["client_id"]
CLIENT_SECRET = CONF["OAuth"]["client_secret"]

# === Global variables for OAuth ===
ACCESS_TOKEN = None
AUTHORIZATION_HEADER = None
token_expiry = datetime.datetime.now()

# === Logging Setup ===
logging.basicConfig(
    filename='zoom_meeting_creation_errors.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.ERROR
)

# === Terminal Color Output ===
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

# === Load OAuth Access Token ===
def load_access_token():
    global ACCESS_TOKEN, AUTHORIZATION_HEADER, token_expiry

    print(f"{Color.BLUE}Requesting new access token...{Color.END}")
    url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ACCOUNT_ID}"
    client_creds = f"{CLIENT_ID}:{CLIENT_SECRET}"
    encoded_creds = base64.b64encode(client_creds.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded_creds}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    response = requests.post(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    ACCESS_TOKEN = data["access_token"]
    token_expiry = datetime.datetime.now() + datetime.timedelta(seconds=data.get("expires_in", 3600))

    AUTHORIZATION_HEADER = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    print(f"{Color.GREEN}New token acquired. Expires at {token_expiry}.{Color.END}")

# === Token Validity Check ===
def check_token_validity():
    if datetime.datetime.now() >= token_expiry:
        print(f"{Color.YELLOW}Token expired. Refreshing...{Color.END}")
        load_access_token()
    else:
        print(f"{Color.GREEN}Access token valid.{Color.END}")

# === Network Availability Check ===
def is_network_available():
    try:
        requests.get("https://zoom.us", timeout=5)
        return True
    except requests.ConnectionError:
        return False

# === Create Recurring Meeting ===
def create_meeting(user_email, topic):
    check_token_validity()
    url = f'https://api.zoom.us/v2/users/{user_email}/meetings'
    headers = AUTHORIZATION_HEADER
    body = {
        "topic": topic,
        "type": 3,
        "settings": {
            "join_before_host": True,
            "approval_type": 2,
            "registration_type": 1,
            "waiting_room": True,
            "enforce_login": True,
            "mute_upon_entry": True,
            "auto_recording": "cloud"
        }
    }
    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    return response.json()

# === Process Input CSV and Write Output ===
def process_create_csv(input_file, output_file):
    success_count = 0
    failure_count = 0

    with open(input_file, newline='') as infile, open(output_file, 'w', newline='') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = ['username', 'meeting_name', 'meeting_id', 'meeting_link']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in reader:
            username = row.get('username', '').strip()
            topic = row.get('meeting_name', '').strip()

            if not username or not topic:
                logging.error(f"Skipping row with missing data: {row}")
                failure_count += 1
                continue

            try:
                meeting = create_meeting(username, topic)
                writer.writerow({
                    'username': username,
                    'meeting_name': topic,
                    'meeting_id': meeting['id'],
                    'meeting_link': meeting['join_url']
                })
                success_count += 1
                print(f"{Color.GREEN}Created meeting for {username}: {meeting['join_url']}{Color.END}")
            except Exception as e:
                logging.error(f"Failed to create meeting for {username} - {topic}", exc_info=True)
                print(f"{Color.RED}Error creating meeting for {username}{Color.END}")
                failure_count += 1

    print(f"\n{Color.BOLD}{Color.GREEN}✅ {success_count} meetings created, {failure_count} failed.{Color.END}")
    print(f"{Color.DARK_CYAN}See 'zoom_meeting_creation_errors.log' for error details.{Color.END}")

# === Extract Meeting ID from Link ===
def extract_meeting_id(link):
    match = re.search(r'/j/(\d+)', link)
    return match.group(1) if match else None

# === Fetch Meeting Metadata ===
def fetch_meeting_metadata(meeting_id):
    check_token_validity()
    url = f"https://api.zoom.us/v2/meetings/{meeting_id}"
    headers = AUTHORIZATION_HEADER
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return {
                'username': data.get('host_email', ''),
                'meeting_name': data.get('topic', '')
            }
        else:
            logging.warning(f"Could not fetch metadata for meeting {meeting_id}: {response.text}")
            return {'username': '', 'meeting_name': ''}
    except Exception as e:
        logging.error(f"Exception fetching metadata for meeting {meeting_id}", exc_info=True)
        return {'username': '', 'meeting_name': ''}

# === Delete Meeting ===
def delete_meeting(meeting_id):
    check_token_validity()
    url = f"https://api.zoom.us/v2/meetings/{meeting_id}"
    headers = AUTHORIZATION_HEADER
    response = requests.delete(url, headers=headers)
    if response.status_code in [204, 404]:
        return True
    else:
        logging.error(f"Failed to delete meeting ID {meeting_id}: {response.text}")
        return False

# === Delete Meetings from Links with Metadata and Audit ===
def delete_meetings_from_links(links):
    total = len(links)
    deleted_rows = []
    failed_rows = []

    for link in links:
        meeting_id = extract_meeting_id(link)
        if not meeting_id:
            print(f"{Color.YELLOW}Invalid link format: {link}{Color.END}")
            failed_rows.append({
                'username': '',
                'meeting_name': '',
                'meeting_id': '',
                'meeting_link': link
            })
            continue

        metadata = fetch_meeting_metadata(meeting_id)

        if delete_meeting(meeting_id):
            print(f"{Color.GREEN}Deleted meeting {meeting_id}{Color.END}")
            deleted_rows.append({
                'username': metadata['username'],
                'meeting_name': metadata['meeting_name'],
                'meeting_id': meeting_id,
                'meeting_link': link
            })
        else:
            print(f"{Color.RED}Failed to delete meeting {meeting_id}{Color.END}")
            failed_rows.append({
                'username': metadata['username'],
                'meeting_name': metadata['meeting_name'],
                'meeting_id': meeting_id,
                'meeting_link': link
            })

    with open('deleted_meetings.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['username', 'meeting_name', 'meeting_id', 'meeting_link'])
        writer.writeheader()
        writer.writerows(deleted_rows)

    with open('failed_deletions.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['username', 'meeting_name', 'meeting_id', 'meeting_link'])
        writer.writeheader()
        writer.writerows(failed_rows)

    print(f"\n{Color.BOLD}{Color.GREEN}✅ Deleted {len(deleted_rows)}/{total} meetings.{Color.END}")
    print(f"{Color.DARK_CYAN}Use 'deleted_meetings.csv' to recreate meetings if needed.{Color.END}")

# === Option to Paste Links Manually ===
def get_links_from_input():
    print(f"\n{Color.CYAN}Paste Zoom meeting links below (one per line). When done, type 'END' and press Enter:{Color.END}")
    links = []
    while True:
        line = input().strip()
        if line.upper() == "END":
            break
        if line:
            links.append(line)
    return links

# === Option to Load from CSV ===
def get_links_from_csv(file_path='delete_input.csv'):
    links = []
    try:
        with open(file_path, newline='') as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                link = row.get('meeting_link', '').strip()
                if link:
                    links.append(link)
    except Exception as e:
        logging.error("Failed to read delete_input.csv", exc_info=True)
        print(f"{Color.RED}Failed to read CSV: {e}{Color.END}")
    return links

# === Graceful Shutdown Handler ===
def graceful_shutdown_handler(sig, frame):
    print(f"\n{Color.YELLOW}Interrupted. Exiting gracefully.{Color.END}")
    sys.exit(0)

# === Main Menu ===
def main_menu():
    print(f"\n{Color.BOLD}What would you like to do?{Color.END}")
    print("1. Create Meetings")
    print("2. Delete Meetings")
    choice = input("Enter choice (1/2): ").strip()

    if choice == "1":
        process_create_csv("input.csv", "output.csv")
    elif choice == "2":
        print("\nChoose deletion input method:")
        print("1. Paste meeting links directly")
        print("2. Load from delete_input.csv")
        method = input("Enter choice (1/2): ").strip()
        if method == "1":
            links = get_links_from_input()
        elif method == "2":
            links = get_links_from_csv()
        else:
            print(f"{Color.RED}Invalid input method selected.{Color.END}")
            return
        delete_meetings_from_links(links)
    else:
        print(f"{Color.RED}Invalid menu selection.{Color.END}")

# === Run ===
if __name__ == '__main__':
    signal.signal(signal.SIGINT, graceful_shutdown_handler)

    if not is_network_available():
        print(f"{Color.RED}No internet connection. Please check and try again.{Color.END}")
        sys.exit(1)

    try:
        load_access_token()
        main_menu()
    except Exception as e:
        logging.error("Fatal error in script execution", exc_info=True)
        print(f"{Color.RED}❌ Unexpected error occurred: {e}{Color.END}")
