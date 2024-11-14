import requests
import csv
import json
from typing import List, Dict, NewType
from functools import reduce
from oauthlib.oauth2 import BackendApplicationClient
from mautrix.util.logging import TraceLogger
from pathlib import Path
from base64 import b64encode

from requests_oauthlib import OAuth2Session
from .auth import Token 

from urllib.parse import urlparse, parse_qs
from dataclasses import dataclass, field

CSVData = NewType('CSVData', list[Dict[str, dict]])


# TODO: make this stuff configurable.
def question_id_to_header(question_id:str):
    if question_id == "fas":
        return "Fedora Account Services (FAS)"
    elif question_id == "matrix":
        return "Matrix ID"
    
    return ""

@dataclass
class AttendeeMatrixInformation:
    order_code: str
    matrix_id: str
    extra: dict = field(default_factory=lambda: {}, hash=False, compare=False)

    @classmethod
    def from_pretix_json(cls, json_data:dict, include_all_data=True):
        """Create an instance of AttendeeMatrixInformation from our internal, simplified pretix JSON data format

        Args:
            json (dict): a dict of the json data from pretix

        Returns:
            AttendeeMatrixInformation: an object wrapping the most important parts of the attendee data
        """
        # explicitly make a copy so mutations dont leak outside this function
        json_data = json_data.copy()
        order_code = json_data['Order code']
        matrix_id = json_data[question_id_to_header("matrix")]
        del json_data['Order code']
        del json_data[question_id_to_header("matrix")]

        return cls(order_code, matrix_id, json_data if include_all_data else {})

class Pretix:

    def __init__(self, client_id, client_secret, redirect_uri, log:TraceLogger, token_storage_path: Path = Path("."), token_storage_filename="pretix-token.json", instance_url="https://pretix.eu"):
        self._instance_url = instance_url
        self._client_secret = client_secret
        self._processed_rows = []
        self._client_id = client_id
        self.logger = log

        if token_storage_path is None:
            token_storage_path = Path(".")
        
        self.token_storage_file = token_storage_path.joinpath(token_storage_filename)

        # if token storage file exists, save it
        if self.token_storage_file.exists():
            data = self.token_storage_file.read_text()
            self._token = Token.from_json(json.loads(data))
            self.logger.debug("token loaded from file")
            # TODO: check this token to see if its still valid

        # most providers will ask you for extra credentials to be passed along
        # when refreshing tokens, usually for authentication purposes.
        # extra = {
        #     'client_id': client_id,
        #     'client_secret': r'potato',
        # }
        if hasattr(self, '_token') and self._token is not None:

            self.oauth = OAuth2Session(
                client_id,
                token=self._token.to_dict(),
                scope=["read"],
                redirect_uri=redirect_uri,
                auto_refresh_url=self.token_url,
                token_updater=self._update_token
            )
        else:
            self.oauth = OAuth2Session(
                client_id,
                scope=["read"],
                redirect_uri=redirect_uri
            )

    
    @staticmethod
    def parse_invite_url(pretix_url):
        # TODO: extract and validate domain
        try:
            pretix_url = urlparse(pretix_url)
        except:
            raise ValueError(f"The input provided is not a valid URL")
        
        pretix_path = pretix_url.path
        # remove trailing slash as it will mess with the upcoming logic
        if pretix_path.endswith("/"):
            pretix_path = pretix_path[:-1]

        organizer = pretix_path.split("/")[-2]
        event = pretix_path.split("/")[-1]
       
        if organizer == "" or event == "":
            raise ValueError("Invalid input - please enter the pretix invitation URL. It should look like https://pretix.ey/<organizer>/<event>")
        
        return (organizer, event)

    def test_auth(self):
        # test the auth
        if not self.has_token:
            return False, None
        r = self.oauth.get(self.test_url, client_id=self._client_id, client_secret=self._client_secret)
        if r.status_code >= 200 and r.status_code < 300:
            return True, None
        else:
            return False, r

    @property
    def has_token(self):
        return self.oauth.authorized
        # TODO: test auth with organizer and event
        
    @property
    def _has_token(self):
        return self._token is not None and self._token != ""

    @property
    def _has_refresh_token(self):
        return self._refresh_token is not None and self._refresh_token != ""

    @property
    def oauth_url(self):
        return self.get_oauth_url()

    @property
    def token_url(self):
        return self.base_url + "/oauth/token"

    @property
    def test_url(self):
        return self.base_url + "/me"

        # TODO: test auth with organizer and event

    def _update_token(self, token:dict):
        """in-memory token storage

        Args:
            token (json): the token to store
        """
        self._token = Token.from_json(token)
        self.token_storage_file.write_text(json.dumps(token), 'utf-8')

    def handle_incoming_webhook(self, jsondata:dict) -> (bool, dict):
        """ handle the minimal data returned by a pretix webhook and fetch additional data
        see: https://docs.pretix.eu/en/latest/api/webhooks.html#receiving-webhooks

        Args:
            json (dict): the decoded JSON data from the webhook

        Returns:
            a tuple of (bool, dict) indicating whether the handling was successful.
                the dict provides either an error message  (containing keys "error" for
                user-facing or general error message, and "debug" for a more detailed
                explaination of the issue) or the fetched and filtered pretix order data
        """
        # standard entries
        notification_id = jsondata.get("notification_id")
        organizer = jsondata.get("organizer")
        event = jsondata.get("event")
        code = jsondata.get("code")
        action = jsondata.get("action")

        # verify some things:
        # is this for a valid action
        if action != "pretix.event.order.paid":
            return (False, {"error": f"could not process webhook for notification {notification_id}", "debug": "action did not match the expected value"})
            
        # is this for the expected event and organizer
        # this info is not stored and cant be checked easily as currently implemented

        # have we processed this order already?
        if code in self._processed_rows:
            return (False, {"error": f"could not process webhook for notification {notification_id}", "debug": f"order {code} has already been processed"})

        # if not, fetch the full data and return it
       
        data = self.fetch_data(organizer, event, order_code=code)
        data = self.extract_answers(data)
        # embed organizer and event data so the matrix bot can look up what to do
        result = {}
        result["organizer"] = organizer
        result["event"] = event
        result["data"] = data

        return (True, result)


    def get_auth_url(self, write=False):
        authorization_url, state = self.oauth.authorization_url(
            self.base_url + "/oauth/authorize"
        )
        # client_id
        # response_type
        # scope
        # redirect_uri
        
        # TODO: figure out what is needed to get write access - this isnt needed right now though
        # read_write = "read" if not write else ""

        # return self.base_url + f"/oauth/authorize?client_id={self.client_id}&response_type=code&scope=read&redirect_uri={self.redirect_uri}"
        return authorization_url

    def set_token_from_auth_callback(self, authorization_response:str):
        """complete the auth process by using the response from the oauth process to fetch a token

        Args:
            authorization_response (str): the URL of the auth response - it should contain the code value
        """
        redirected_url = urlparse(authorization_response)
        querystring = parse_qs(redirected_url.query)

        # if not state:
            # something went wrong
        self.oauth = OAuth2Session(
            self._client_id,
            state=querystring.get("state")[0],
            # token=token,
            auto_refresh_url=self.token_url,
            token_updater=self._update_token
        )
        token = self.oauth.fetch_token(
            self.token_url,
            authorization_response=authorization_response,
            client_secret=self._client_secret
            )
        self._update_token(token)
        return


    def revoke_access_token(self):
        """attempt to revoke the access token if it is suspected to have bene compromized or is no longer needed
        """
        url = self.base_url + "/oauth/revoke_token"
        body = {
            "token": self._token.access_token
        }

        r = self.oauth.post(url)
        r.raise_for_status()
    
    @property
    def base_url(self):
        if self._instance_url.endswith("/"):
            return self._instance_url + "api/v1"
        return self._instance_url + "/api/v1"

    def listen(self):
        """spin up a web server to listen on a particular IP and port for the redirect code
        """
        pass

    def fetch_data(self, organizer, event, order_code=None) -> dict:
        order_code = f"{order_code}/" if order_code is not None else ""
        url = self.base_url + f"/organizers/{organizer}/events/{event}/orders/" + order_code

        data = []

        if order_code == "":
            # many orders are being requested.
            while url:
                response = self.oauth.get(url, client_id=self._client_id, client_secret=self._client_secret)
                response.raise_for_status()
                json_response = response.json()
                data.extend(json_response.get('results', []))
                url = json_response.get('next')
        else:
            # one order is requested
            response = self.oauth.get(url, client_id=self._client_id, client_secret=self._client_secret)
            response.raise_for_status()
            json_response = response.json()
            data.append(json_response)

        return data

    def extract_answers(self, schema: dict, filter_processed=False) -> List[AttendeeMatrixInformation]:
        def reducer(entries: Dict[str, dict], result: dict) -> Dict[str, dict]:
            for position in result.get('positions', []):
                ticket_id = position['order']
                # if we havent seen this order already when processing in this series of paginated api calls
                if not entries.get(ticket_id):
                    entries[ticket_id] = {
                        'Order code': ticket_id,
                        'Email': result.get('email', ''),
                        "Order datetime": result.get("datetime", ''),
                        "Pseudonymization ID": position.get("pseudonymization_id", ''),
                        "Fedora Account Services (FAS)": '',
                        "Matrix ID": '',
                        # "Invoice address name": result.get('invoice_address', {}).get('name', ''),
                    }
                for answer in position.get('answers', []):
                    if answer['question_identifier'] in {'matrix', 'fas'}:
                        entries[ticket_id][question_id_to_header(answer['question_identifier'])] = answer['answer']  # noqa: E501
            return entries

        reduced_results = reduce(reducer, schema, {})

        result = [AttendeeMatrixInformation.from_pretix_json(j) for j in reduced_results.values()]

        if not filter_processed:
            return result
        else:
            return self._filter_processed_data(result, self._processed_rows)


    def mark_as_processed(self, rows: List[AttendeeMatrixInformation], replace=False):
        """add some attendees to the processed dataset indicating they were successfully invited

        Args:
            rows (List[AttendeeMatrixInformation]): a List of attendee data to mark as processed
        """
        processed_order_ids = [d.order_code for d in rows]

        if replace:
            self._processed_rows = processed_order_ids
        else:
            self._processed_rows = list(set(self._processed_rows).union(set(processed_order_ids)))


    def filter_dict(self, old_dict: dict, your_keys: list[str]) -> dict:
        """filters a dictionary so it only contains the specified keys
        accomplishes this by constructing a new dictionary
        """
        return { your_key: old_dict[your_key] for your_key in your_keys }


    def _filter_processed_data(self, data:List[AttendeeMatrixInformation], processed_ids:List[str]) -> List[AttendeeMatrixInformation]:
        """filters attendee information to remove data thats already been processed


        Args:
            data (List[AttendeeMatrixInformation]): the input attendee data to process
            processed_ids (List[str]): the list of identifers of processed records to filter out
        
        Returns:
            List[AttendeeMatrixInformation]: the filtered version of the initial data with already-processed entries removed
        """
        # return a list of records from the full data as long as they are not in the list of processed records
        return list(filter(lambda d: d.order_code not in processed_ids, data))
