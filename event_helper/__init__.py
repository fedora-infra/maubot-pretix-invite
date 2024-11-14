import hashlib
from itertools import chain
import hmac
import json
from json import JSONEncoder
from typing import List
from dataclasses import dataclass, field

import jinja2
from aiohttp.web import Response
from maubot import MessageEvent, Plugin
from maubot.handlers import command
from mautrix.client.api.events import EventMethods
from mautrix.client.api.rooms import RoomMethods
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper

from pathlib import Path

from .matrix_utils import MatrixUtils, UserInfo, validate_matrix_id
from .pretix import Pretix, AttendeeMatrixInformation
# ACCEPTED_TOPICS = ["issue.new", "git.receive", "pull-request.new"]

NL = "      \n"

class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper):
        helper.copy("pretix_instance_url")
        helper.copy("pretix_client_id")
        helper.copy("pretix_client_secret")
        helper.copy("pretix_redirect_url")
        helper.copy("allowlist")

@dataclass(frozen=True)
class FilterConditions:
    item: str = None
    variant: str = None

    @classmethod
    def from_json(cls, json_data: dict):
        return cls(json_data.get("item"), json_data.get("variant"))

    def __str__(self):
        text = []
        if self.item is not None:
            text.append(f"item={self.item}")
        
        if self.variant is not None:
            text.append(f"variant={self.variant}")

        return f"({', '.join(text)})"

@dataclass(frozen=True)
class Room:
    matrix_id: str
    condition: FilterConditions = FilterConditions()

    @classmethod
    def from_json(cls, json_data: dict):
        return cls(json_data["matrix_id"], FilterConditions.from_json(json_data["condition"]))


    @property
    def has_filter(self):
        return self.condition.item is not None or self.condition.variant is not None

    def matches(self, item, variant):
        if not self.has_filter:
            return True
        target_item = self.condition.item
        target_variant = self.condition.variant

        if target_item == item and target_variant is None:
            return True
        elif target_item == item and target_variant == variant:
            return True
        else:
            return False

class RoomEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, set):
            return list(o)
        
        return o.__dict__

def decode_hook(obj):
    if isinstance(obj, list):
        return set([Room.from_json(i) for i in obj])
        

@dataclass
class EventRooms:
    _mapping: dict = field(default_factory=lambda: {})
    persist_path:Path = field(default_factory=Path, kw_only=True, hash=False)
    persist_filename:str = field(default="event_rooms.json", kw_only=True, hash=False)

    def persist(self):
        persistfile = self.persist_path.joinpath(self.persist_filename)
        
        persistfile.write_text(json.dumps(self._mapping, cls=RoomEncoder), encoding="utf8")
    
    @classmethod
    def from_path(cls, persist_path=Path("."), persist_filename="event_rooms.json"):
        persistfile = persist_path.joinpath(persist_filename)
        if not persistfile.exists():
            print("persist file doesnt exist, creating fresh room map")
            return cls()
        data = persistfile.read_text(encoding="utf8")

        mapping = json.loads(data, object_hook=decode_hook)
            
        return cls(mapping, persist_filename=persist_filename, persist_path=persist_path)

    def rooms_by_event(self, organizer:str, event:str):
        if self._mapping.get(organizer) is None:
            return set()
        
        if self._mapping[organizer].get(event) is None:
            return set()
        
        return self._mapping[organizer].get(event)

    def rooms_by_ticket_variant(self, organizer:str, event:str, item_id:str, variant_id:str):
        item_id = str(item_id)
        variant_id = str(variant_id)
        
        event_rooms = self.rooms_by_event(organizer, event)

        rooms_matching_filter = filter(lambda r: r.matches(item_id, variant_id), event_rooms)

        return list(rooms_matching_filter)
    
    def add(self, organizer:str, event:str, room_id:str):
        self.add_object(organizer, event, Room(room_id))

    
    def add_object(self, organizer:str, event:str, room:Room):
        if self._mapping.get(organizer) is None:
            self._mapping[organizer] = {} 
        
        if self._mapping[organizer].get(event) is None:
            self._mapping[organizer][event] = set()
        
        self._mapping[organizer][event].add(room)
        self.persist()

    def remove(self, organizer:str, event:str, room_id:str):
        if room_id in self.rooms_by_event(organizer,event):
            self._mapping[organizer][event].remove(Room(room_id))
        self.persist()


    def room_is_mapped(self, room:str):
        return len(self.events_for_room(Room(room))) > 0

    def events_for_room(self, room_to_find:Room):
        """return a list of events that a room is mapped to in "organizer/event" format

        Args:
            room (str): the id of the room to return events for

        Returns:
            List[str]: the list of events the room is part of
        """
        events = []
        for organizer in self._mapping:
            for event in self._mapping[organizer]:
                for room in self._mapping[organizer][event]:
                    if room.matrix_id == room_to_find.matrix_id:
                        orgEventName = f"{organizer}/{event}"
                        if room.has_filter:
                            orgEventName += " "
                            orgEventName += str(room.condition)
                        events.append(orgEventName)
        return events
    
    def purge_room(self, room):
        """remove a room from all events it is mapped to
        """
        for organizer in self._mapping:
            for event in self._mapping[organizer]:
                if room in event:
                    self.remove(organizer, event, room.matrix_id)


class EventManagement(Plugin):
    @classmethod
    def get_config_class(cls):
        return Config

    async def start(self):
        self.config.load_and_update()
        self.room_methods = RoomMethods(api=self.client.api)
        self.event_methods = EventMethods(api=self.client.api)
        self.matrix_utils = MatrixUtils(self.client.api, self.log)
        self.room_mapping = EventRooms.from_path()

        # if in container
        maubot_base_location = Path("/data")
        if not maubot_base_location.exists():
            # Fedora dev environment
            maubot_base_location = Path("/var/lib/maubot/")
        
        # if it still doesnt exist
        if not maubot_base_location.exists():
            # fall back to the default supplied by pretix class (current directory)
            maubot_base_location = None



        self.pretix = Pretix(
            self.config["pretix_client_id"],
            self.config["pretix_client_secret"],
            self.config["pretix_redirect_url"],
            self.log,
            token_storage_path=maubot_base_location,
            instance_url=self.config["pretix_instance_url"],
        )

        self.webapp.add_route("POST", "/notify", self.handle_request)
        self.log.info(f"Webhook URL is: {self.webapp_url}/notify")
        print(self.webapp_url)

    def _get_handler_commands(self):
        for cmd, _ignore in chain(*self.client.event_handlers.values()):
            if not isinstance(cmd, command.CommandHandler):
                continue
            func_mod = cmd.__mb_func__.__module__
            if func_mod != __name__ and not func_mod.startswith(f"{__name__}."):
                continue  # pragma: no cover
            yield cmd

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
        attendees = result_dict.get("data")
        # order may already be processed (because im messing with it), so this may be empty
        order_id = attendees[0].order_code
        matrix_id = attendees[0].matrix_id
        order = self.pretix.fetch_orders(organizer, event, order_code=order_id)
        position = order[0].get("positions")[0]
        item_id = position.get("item")
        variant_id = position.get("variation")

        room_ids = [r.matrix_id for r in self.room_mapping.rooms_by_ticket_variant(organizer, event, item_id, variant_id)]
        
        if len(room_ids) == 0:
            self.log.debug(f"found no configured rooms for event {event} from organizer {organizer}."
            f"Unable to add attendee from registration {order_id} received via webhook")
        else:
            self.log.debug(f"webhook found {len(room_ids)} rooms for event {event} from organizer {organizer}")


        for room in room_ids:
            if room[0] == "#":
                roomaliasinfo = await self.client.resolve_room_alias(room)
                room_id = roomaliasinfo.room_id
            else:
                room_id = room
        
            self.log.debug(f"sending invite from webhook to {room_id}")
            failed_invites = await self.invite_attendees(room_id, attendees)

            # this assumes we are only really processing one new attendee at a time
            if len(failed_invites) == 0:
                self.pretix.mark_as_processed(attendees)
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


    async def invite_attendees(self, room_id:str, attendees:List[AttendeeMatrixInformation]):
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
                validated_id = validate_matrix_id(matrix_id, fix_at_sign=True)
            except ValueError as e:
                self.log.debug(f"matrix ID was invalid for the following reason: {e}")
                invalid_users.append(matrix_attendee)
                continue
            else:
                self.log.debug(f"matrix ID was valid")
                valid_users[validated_id] = UserInfo()

        if len(valid_users) > 0:
            await self.matrix_utils.ensure_room_invitees(room_id, valid_users)
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

        if not self.pretix.has_token:
            await evt.reply(f"Error when testing authentication. This is may be due to a lack of authorization to access the configured pretix instance to query event registrations. Please run the `!authorize` command to authorize access")
            return
        
        # TODO: allow this url to be optional if a room is mapped
        try:
            organizer, event = Pretix.parse_invite_url(pretix_url)
        except ValueError as e:
            await evt.reply(e)
            # await evt.reply(f"Invalid input - please enter")

        self.log.debug(f"organizer: {organizer}")
        self.log.debug(f"event: {event}")

        data = self.pretix.fetch_data(organizer, event)
        data = self.pretix.extract_answers(data, filter_processed=True)

        failed_invites = await self.invite_attendees(room_id, data)
        # TODO: mark successful ones as processed
        
        # Ensure users have correct power levels
        # await self.matrix_utils.ensure_room_power_levels(room_id, all_users)

    @command.new(name="setroom", help="associate the current matrix room with a specified pretix event")
    @command.argument("pretix_url", pass_raw=False, required=True)
    @command.argument("item_id", pass_raw=False, required=False)
    @command.argument("variant_id", pass_raw=False, required=False)
    async def setroom(self, evt: MessageEvent, pretix_url: str, item_id:str, variant_id:str) -> None:
        # permission check
        if evt.sender not in self.config["allowlist"]:
            await evt.reply(f"{evt.sender} is not allowed to execute this command")
            return


        # TODO: check domain
        try:
            organizer, event = Pretix.parse_invite_url(pretix_url)
        except ValueError as e:
            await evt.reply(e)
        
        # store the association
        room_id = evt.room_id

        rm = Room(room_id, condition=FilterConditions(item_id, variant_id))
        #TODO: add room from object
        self.room_mapping.add_object(organizer, event, rm)
        await evt.reply("room associated successfully")

    
    @command.new(name="unsetroom", help="de-associate the current matrix room with a specified pretix event or remove this room from all events")
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


    @command.new(name="authorize", help="authorize access to your pretix")
    @command.argument("auth_url", pass_raw=True, required=False)
    async def authorize(self, evt: MessageEvent, auth_url: str) -> None:
        # permission check
        if evt.sender not in self.config["allowlist"]:
            await evt.reply(f"{evt.sender} is not allowed to execute this command")
            return

        if auth_url is not None and auth_url != "":
            self.pretix.set_token_from_auth_callback(auth_url)
        
        if not self.pretix.test_auth()[0]:
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
        test_result, details = self.pretix.test_auth()
        pretix_auth_status = "authorized" if test_result else "not authorized"
        room_associated = "is" if self.room_mapping.room_is_mapped(room_id) else "is not"

        statustext = [
            f"Pretix status: {pretix_auth_status}",
            f"Room Status: the current room {room_associated} assigned to an event",
            f"Events: {','.join(self.room_mapping.events_for_room(Room(room_id)))}"
        ]
        await evt.reply(NL.join(statustext))
        
