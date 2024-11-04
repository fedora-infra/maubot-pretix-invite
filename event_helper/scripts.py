from pretix import Pretix

from auth import Token

import argparse
from dotenv import load_dotenv
from logging import Logger
import os 
import sys
log = Logger("pretix-scripts")


if __name__ == "__main__":


    load_dotenv()

    organizer = os.getenv('EVENT_ORGANIZER')
    event = os.getenv('EVENT_NAME')
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    client_redirect = os.getenv('CLIENT_REDIRECT_URL')
    client_apiurl = os.getenv('CLIENT_INSTANCE_URL', "https://pretix.eu")



    parser = argparse.ArgumentParser(description='Pretix helper scripts')
    parser.add_argument('--auth', type=str, help='the url returned from an auth call')

    args = parser.parse_args()

    pretix_ins = Pretix(
        client_id,
        client_secret,
        client_redirect,
        log,
        instance_url=client_apiurl,
    )
    if not pretix_ins.has_token:

        if args.auth :

            pretix_ins.set_token_from_auth_callback(args.auth)
        else:
            print(pretix_ins.get_auth_url())
            sys.exit()
            

    
    print(pretix_ins.fetch_data(organizer, event, order_code="T03JJ"))


    # prompt for user input to return callback token

    # token = os.getenv('ACCESS_TOKEN')
