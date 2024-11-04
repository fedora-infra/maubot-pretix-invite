from pretix import Pretix

from auth import Token

import argparse
from dotenv import load_dotenv
from logging import Logger
import os 
log = Logger("pretix-scripts")


if __name__ == "__main_":


    load_dotenv()

    organizer = os.getenv('EVENT_ORGANIZER')
    event = os.getenv('EVENT_NAME')
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    client_redirect = os.getenv('CLIENT_REDIRECT_URL')
    client_apiurl = os.getenv('CLIENT_INSTANCE_URL', "https://pretix.eu")



    parser = argparse.ArgumentParser(description='Pretix helper scripts')
    # parser.add_argument('--csvfile', type=str, help='csv filename downloaded from pretix')
    args = parser.parse_args()

    pretix = Pretix(
        client_id,
        client_secret,
        client_redirect,
        log,
        instance_url=client_apiurl,
    )

    print(pretix.get_auth_url())


    # prompt for user input to return callback token

    # token = os.getenv('ACCESS_TOKEN')
