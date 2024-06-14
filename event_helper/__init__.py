import hashlib
import hmac

import jinja2
from aiohttp.web import Response
from maubot import MessageEvent, Plugin
from maubot.handlers import command
from mautrix.client.api.events import EventMethods
from mautrix.client.api.rooms import RoomMethods
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper

from collections import Counter
import string
import validators
from urllib.parse import urlparse
from typing import List
from dataclasses import dataclass, field

from .matrix_utils import MatrixUtils, UserInfo, validate_matrix_id
from .pretix import Pretix, AttendeeMatrixInformation
# ACCEPTED_TOPICS = ["issue.new", "git.receive", "pull-request.new"]


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper):
        helper.copy("pretix_instance_url")
        helper.copy("pretix_client_id")
        helper.copy("pretix_client_secret")
        helper.copy("pretix_redirect_url")
        helper.copy("allowlist")

@dataclass
class EventRooms:
    _mapping: dict = field(default_factory=lambda: {})

    def rooms_by_event(self, organizer:str, event:str):
        if self.room_mapping.get(organizer) is None:
            return set()
        
        if self.room_mapping[organizer].get(event) is None:
            return set()
        
        return self.room_mapping[organizer].get(event)
    
    def add(self, organizer:str, event:str, room_id:str):
        if self._mapping.get(organizer) is None:
            self._mapping[organizer] = {} 
        
        if self._mapping[organizer].get(event) is None:
            self._mapping[organizer][event] = set()
        
        self._mapping[organizer][event].add(room_id)

    def remove(self, organizer:str, event:str, room_id:str):
        if room_id in self.rooms_by_event(organizer,event):
            self._mapping[organizer][event].remove(room_id)


    def room_is_mapped(self, room:str):
        for organizer in self._mapping:
            for event in self._mapping[organizer]:
                if room in event:
                    return True
        return False

    def events_for_room(self, room:str):
        """return a list of events that a room is mapped to in "organizer/event" format

        Args:
            room (str): the id of the room to return events for

        Returns:
            List[str]: the list of events the room is part of
        """
        events = []
        for organizer in self._mapping:
            for event in self._mapping[organizer]:
                if room in self._mapping[organizer][event]:
                    events.append(f"{organizer}/{event}")
        return events
    
    def purge_room(self, room):
        """remove a room from all events it is mapped to
        """
        for organizer in self._mapping:
            for event in self._mapping[organizer]:
                if room in event:
                    self._mapping[organizer][event].remove(room)


class EventManagement(Plugin):
    @classmethod
    def get_config_class(cls):
        return Config

    async def start(self):
        self.config.load_and_update()
        self.room_methods = RoomMethods(api=self.client.api)
        self.event_methods = EventMethods(api=self.client.api)
        self.matrix_utils = MatrixUtils(self.client.api, self.log)
        self.room_mapping = EventRooms()
        self.pretix = Pretix(
            self.config["pretix_instance_url"],
            self.config["pretix_client_id"],
            self.config["pretix_client_secret"],
            self.config["pretix_redirect_url"]
        )

        self.webapp.add_route("POST", "/notify", self.handle_request)
        self.log.info(f"Webhook URL is: {self.webapp_url}/notify")
        print(self.webapp_url)

    async def handle_request(self, request):
        json = await request.json()
        
        # this checks whether the webhook type is correct
        success, result_dict = self.pretix.handle_incoming_webhook(json)

        if not success:
            self.log.info(result_dict.get("error"))
            self.log.debug(result_dict.get("debug"))

        # this assumes we are only really processing one new attendee at a time
        organizer = result_dict.get("organizer")
        event = result_dict.get("event")
        self.log.debug(result_dict.get("data"))
        matrix_id = result_dict.get("data")[0].matrix_id

        try:
            room_ids = list(self.room_mapping.rooms_by_event(organizer, event))
        except (KeyError, TypeError) as e:
            # if project_name not in self.config["projects"]:
            self.log.error(
                f"event {event} from organizer {organizer} is sending me a webhook, "
                f"but I cant find a room to invite them to because no room has been specified!"
            )
            return Response()

        for room_id in room_ids:
        #   if room[0] == "#":
        #       roomaliasinfo = await self.client.resolve_room_alias(room)
        #       room = roomaliasinfo.room_id
            self.log.debug(f"sending invite from webhook to {room_id}")
            failed_invites = self.invite_attendees(room_id, data)

            # this assumes we are only really processing one new attendee at a time
            if len(failed_invites) == 0:
                self.oretix.mark_as_processed(result)
            else:
                self.log.error(f"unable to invite member {matrix_id}")

        # Pretix:  If you successfully received a webhook call, your endpoint
        # should return a HTTP status code between 200 and 299.
        # If any other status code is returned, we will assume you did not receive the call.
        return Response()


    @command.new(name="help", help="list commands")
    @command.argument("commandname", pass_raw=True, required=False)
    async def bothelp(self, evt: MessageEvent, commandname: str) -> None:
        """return help"""
        output = []

        if commandname:
            # return the full help (docstring) for the given command
            for cmd in self._get_handler_commands():
                if commandname != cmd.__mb_name__:
                    continue
                output.append(cmd.__mb_full_help__)
                break
            else:
                await evt.reply(f"`{commandname}` is not a valid command")
                return
        else:
            # list all the commands with the help arg from command.new
            for cmd in self._get_handler_commands():
                output.append(
                    f"* `{cmd.__mb_prefix__} {cmd.__mb_usage_args__}` - {cmd.__mb_help__}"
                )
        await evt.respond(NL.join(output))


    @command.new(help="return information about this bot")
    async def version(self, evt: MessageEvent) -> None:
        """
        Return the version of the plugin

        Takes no arguments
        """

        await evt.respond(f"maubot-events version {self.loader.meta.version}")


    def invite_attendees(self, room_id:str, attendees:List[AttendeeMatrixInformation]):
        """attempt to invite attendees

        Args:
            room_id (str): the ID of the room to invite users to
            attendees (List[AttendeeMatrixInformation]): the list of attendees to invite

        Returns:
            List[AttendeeMatrixInformation]: the list of users with invalid matrix IDs.
            If fully successful this will be an empty list
        """
        valid_users = {} #users in Dict[str,UserInfo] format for the matrix APIs
        invalid_users = [] # list of AttendeeMatrixInformation
        for matrix_attendee in attendees:
            matrix_id = matrix_attendee.matrix_id
            order_id = matrix_attendee.order_code
            self.log.debug(f"received username `{matrix_id}` to invite from order {order_id}")
            # validate matrix id
            try:
                validated_id = validate_matrix_id(matrix_id)
            except ValueError as e:
                self.log.debug(f"matrix ID was invalid for the following reason: {e}")
                invalid_users.append(matrix_attendee)
                continue
            else:
                self.log.debug(f"matrix ID was valid")
                valid_users[validated_id] = UserInfo()

        if len(valid_users) > 0:
            self.matrix_utils.ensure_room_invitees(room_id, valid_users)
        else:
            self.log.debug(f"no users with valid Matrix IDs to invite")

        return invalid_users


    @command.new(name="batchinvite", help="invite attendees from pretix")
    @command.argument("pretix_url", pass_raw=True, required=True)
    async def batchinvite(self, evt: MessageEvent, pretix_url: str) -> None:
        # permission check
        if evt.sender not in self.config["allowlist"]:
            await evt.reply(f"{evt.sender} is not allowed to execute this command")
            return

        room_id = evt.room_id

        if not self.pretix.is_authorized:
            await evt.reply(f"Error when testing authentication. This is may be due to a lack of authorization to access the configured pretix instance to query event registrations. Please run the `!authorize` command to authorize access")
            return
        
        try:
            organizer, event = Pretix.parse_invite_url(pretix_url)
        except ValueError as e:
            await evt.reply(e)
            # await evt.reply(f"Invalid input - please enter")

        self.log.debug(f"organizer: {organizer}")
        self.log.debug(f"event: {event}")

        data = self.pretix.fetch_data(organizer, event)
        data = self.pretix.extract_answers(data, filter_processed=True)

        failed_invites = self.invite_attendees(room_id, data)
        # Ensure users have correct power levels
        # await self.matrix_utils.ensure_room_power_levels(room_id, all_users)

    @command.new(name="setroom", help="associate the current matrix room with a specified pretix event")
    @command.argument("pretix_url", pass_raw=True, required=True)
    async def setroom(self, evt: MessageEvent, pretix_url: str) -> None:
        # permission check
        if evt.sender not in self.config["allowlist"]:
            await evt.reply(f"{evt.sender} is not allowed to execute this command")
            return

        try:
            organizer, event = Pretix.parse_invite_url(pretix_url)
        except ValueError as e:
            await evt.reply(e)
        
        # store the association
        room_id = evt.room_id
        self.room_mapping.add(organizer,event, room_id)
        await evt.reply("room associated successfully")

    
    @command.new(name="unsetroom", help="de-associate the current matrix room with a specified pretix event")
    @command.argument("pretix_url", pass_raw=True, required=False)
    async def unsetroom(self, evt: MessageEvent, pretix_url: str) -> None:
        # permission check
        if evt.sender not in self.config["allowlist"]:
            await evt.reply(f"{evt.sender} is not allowed to execute this command")
            return

        room_id = evt.room_id

        if pretix_url is not None and pretix_url != "":
            try:
                organizer, event = Pretix.parse_invite_url(pretix_url)
            except ValueError as e:
                await evt.reply(e)
            
            # remove the association
            if self.room_mapping.rooms_by_event(organizer, event) == set():
                await evt.reply("room was not part of the specified event")
                return
            self.room_mapping.remove(organizer, event, room_id)
            await evt.reply("room deassociated from event successfully")

        else:
            # TODO: fix me - this is surprising to users and may not be desired
            self.room_mapping.purge_room(room_id)
            await evt.reply("room deassociated from all events successfully")


    # @command.new(name="directauthorize", help="authorize access to your pretix")
    # @command.argument("token_str", pass_raw=True, required=True)
    # async def authorize_token(self, evt: MessageEvent, token_str: str) -> None:
    #     # permission check
    #     if evt.sender not in self.config["allowlist"]:
    #         await evt.reply(f"{evt.sender} is not allowed to execute this command")
    #         return

    #     self.pretix.set_token_manually(token_str)

    #     if self.pretix.is_authorized:
    #         await evt.reply(f"Authorization successful")
    #     else:
    #         await evt.reply(f"Smth happened")


    @command.new(name="authorize", help="authorize access to your pretix")
    @command.argument("auth_url", pass_raw=True, required=False)
    async def authorize(self, evt: MessageEvent, auth_url: str) -> None:
        # permission check
        if evt.sender not in self.config["allowlist"]:
            await evt.reply(f"{evt.sender} is not allowed to execute this command")
            return

        if auth_url is not None and auth_url != "":
            self.pretix.set_token_from_auth_callback(auth_url)
        
        if not self.pretix.is_authorized:
            auth_url = self.pretix.get_auth_url()
            # inform user to visit the url and run the !token command with the response
            await evt.reply(f"Please visit {auth_url} and re-run the `!authorize` command again with the URL you are redirected to in order to authorize.")
            return
        
        await evt.reply(f"Authorization successful")

    @command.new(name="status", help="check the status of the various configuration options for this bot")  
    async def status(self, evt: MessageEvent) -> None:
        # permission check
        if evt.sender not in self.config["allowlist"]:
            await evt.reply(f"{evt.sender} is not allowed to execute this command")
            return
        
        room_id = evt.room_id
        pretix_auth_status = "authorized" if self.pretix.is_authorized else "not authorized"
        room_associated = "is" if self.room_mapping.room_is_mapped(room_id) else "is not"

        await evt.reply(f"""
Pretix status: {pretix_auth_status}
Room Status: the current room {room_associated} assigned to an event
Events: {','.join(self.room_mapping.events_for_room(room_id))}
""")
        
