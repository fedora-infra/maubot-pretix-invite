import requests
import csv
from typing import List, Dict, NewType
from functools import reduce
from oauthlib.oauth2 import BackendApplicationClient

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
    extra: dict = field(default_factory={})

    @classmethod
    def from_pretix_json(cls, json:dict, include_all_data=True):
        """Create an instance of AttendeeMatrixInformation from pretix JSON data

        Args:
            json (dict): a dict of the json data from pretix

        Returns:
            AttendeeMatrixInformation: an object wrapping the most important parts of the attendee data
        """
        # explicitly make a copy so mutations dont leak outside this function
        json = dict(json)
        order_code = json['Order code']
        matrix_id = json[question_id_to_header("matrix")]
        del json['Order code']
        del json[question_id_to_header("matrix")]

        return cls(order_code, matrix_id, json if include_all_data else {})

class Pretix:

    def __init__(self, instance_url, client_id, client_secret, redirect_uri):
        self._instance_url = instance_url
        self._client_secret = client_secret
        self._processed_rows = []
        self._client_id = client_id
        # most providers will ask you for extra credentials to be passed along
        # when refreshing tokens, usually for authentication purposes.
        # extra = {
        #     'client_id': client_id,
        #     'client_secret': r'potato',
        # }
        self.oauth = OAuth2Session(
            client_id,
            scope=["read"],
            redirect_uri=redirect_uri
        )
            # token=token,
            # auto_refresh_url=self.token_url,
            # token_updater=self._update_token)#auto_refresh_kwargs=extra,
    
    @staticmethod
    def parse_invite_url(url):
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
        r = self.oauth.get(self.test_url)
        r.raise_for_status()

    @property
    def is_authorized(self):
        return self.oauth.authorized
        
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

    def _update_token(self, token:dict):
        """in-memory token storage

        Args:
            token (json): the token to store
        """
        self._token = Token.from_json(token)

    def handle_incoming_webhook(self, json:dict) -> (bool, dict):
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
        notification_id = json.get("notification_id")
        organizer = json.get("organizer")
        event = json.get("event")
        code = json.get("code")
        action = json.get("action")

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
        data = self.pretix.extract_answers(data)
        # embed organizer and event data so the matrix bot can look up what to do
        data["organizer"] = organizer
        data["event"] = event

        return (True, data)


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
            token_updater=self._update_token)#auto_refresh_kwargs=extra,
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
        return self._instance_url + "/api/v1"

    def listen(self):
        """spin up a web server to listen on a particular IP and port for the redirect code
        """
        pass

    def fetch_data(self, organizer, event, order_code=None) -> dict:
        order_code = f"{order_code}/" if order_code is not none else ""
        url = self.base_url + f"/organizers/{organizer}/events/{event}/orders/" + order_code

        data = []

        while url:
            response = self.oauth.get(url)
            response.raise_for_status()
            json_response = response.json()
            data.extend(json_response.get('results', []))
            url = json_response.get('next')
        return data

    def extract_answers(self, schema: dict, filter_processed=False) -> CSVData:
        def reducer(entries: Dict[str, dict], result: dict) -> Dict[str, dict]:
            for position in result.get('positions', []):
                ticket_id = position['order']
                if not entries.get(ticket_id):
                    entries[ticket_id] = {
                        'Order code': ticket_id,
                        'Email': result.get('email', ''),
                        "Order datetime": result.get("datetime", ''),
                        "Pseudonymization ID": position.get("pseudonymization_id", ''),
                        "Fedora Account Services (FAS)": '',
                        "Matrix ID": '',
                        "Invoice address name": result.get('invoice_address', {}).get('name', ''),
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


    def write_to_csv(self, entries: CSVData, file_name: str, display: bool = False) -> None:  # noqa: E501
        fieldnames = entries[0].keys()
        with open(file_name, mode='w+', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            for entry in entries:
                writer.writerow(entry)

            if not display:
                return

            csv_file.flush()
            csv_file.seek(0)
            print(csv_file.read())

    def filter_dict(self, old_dict: dict, your_keys: list[str]) -> dict:
        """filters a dictionary so it only contains the specified keys
        accomplishes this by constructing a new dictionary
        """
        return { your_key: old_dict[your_key] for your_key in your_keys }

    
    def csv_to_data(self, csv_file:str) -> CSVData:
        """_summary_

        Args:
            csv_file (str): the input filename to process

        Returns:
            CSVData: the csv data in dict format for further processing
        """
        
        with open(csv_file) as csvfile:
            reader = csv.DictReader(csvfile)
            return list(reader)

    def filter_csv_columns(self, csv_data:CSVData, filter_keys=["Order code", "Email", "Order date", "Order time", "Pseudonymization ID", "Fedora Account Services (FAS)", "Matrix ID", "Invoice address name"]) -> CSVData:
        """Takes in a CSV data (dict-formatted) and returns dict-formatted data with unused columns removed

        Args:
            csv_data (CSVData): the input csv data to process

        Returns:
            CSVData: the data with unused columns removed
        """
        return [filter_dict(d, filter_keys) for d in csv_data]
    

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
