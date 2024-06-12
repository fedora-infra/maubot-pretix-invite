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


class EventManagement(Plugin):
    @classmethod
    def get_config_class(cls):
        return Config

    async def start(self):
        self.config.load_and_update()
        self.room_methods = RoomMethods(api=self.client.api)
        self.event_methods = EventMethods(api=self.client.api)
        self.matrix_utils = MatrixUtils(self.client.api, self.log)
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
        message_topic = json.get("topic")

        # first check if the topic of the message is one of the ones that the plugin handles
        # if message_topic not in ACCEPTED_TOPICS:
        #     return Response()

        # try:
        #     if message_topic == "git.receive":
        #         project_name = json["msg"]["project_fullname"]
        #     elif message_topic == "pull-request.new":
        #         project_name = json["msg"]["pullrequest"]["project"]["fullname"]
        #     else:
        #         project_name = json["msg"]["project"]["fullname"]
        # except KeyError as e:
        #     self.log.error(f"The response from pagure was not as expected: {e}.")
        #     return Response()

        # if project_name not in self.config["projects"]:
        #     self.log.error(
        #         f"project {project_name} is sending me a webhook, "
        #         f"but it is not defined in my config!"
        #     )
        #     return Response()

        # try:
        #     key = self.config["projects"][project_name]["key"]
        #     topics = self.config["projects"][project_name]["topics"]
        #     rooms = self.config["projects"][project_name]["topics"][message_topic]
        # except KeyError as e:
        #     self.log.error(f"Project configuation for the plugin is invalid: {e}.")
        #     return Response()

        # content = await request.read()
        # hashhex = hmac.new(key.encode(), msg=content, digestmod=hashlib.sha1).hexdigest()

        # if not hmac.compare_digest(hashhex, request.headers.get("X-Pagure-Signature")):
        #     self.log.error(
        #         f"message from project {project_name} did not validate correctly. ignoring"
        #     )
        #     return Response()

        # if message_topic not in topics:
        #     return Response()

        # template = self.loader.sync_read_file(f"pagure_notifications/{message_topic}.j2")
        # message = jinja2.Template(template.decode()).render({"json": json})

        # for room in rooms:
        #     if room[0] == "#":
        #         roomaliasinfo = await self.client.resolve_room_alias(room)
        #         room = roomaliasinfo.room_id
        #     try:
        #         await self.client.send_text(room, None, html=message)
        #     except Exception as e:
        #         self.log.error(f"Problem sending message to room {room}: {e}")

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

        all_users = {}

        for matrix_attendee in data:
            matrix_id = matrix_attendee.matrix_id
            order_id = matrix_attendee.order_code
            self.log.debug(f"received username `{matrix_id}` to invite from order {order_id}")
            # validate matrix id
            try:
                validated_id = validate_matrix_id(matrix_id)
            except ValueError as e:
                self.log.debug(f"matrix ID was invalid for the following reason: {e}")
            else:
                self.log.debug(f"matrix ID was valid")
                all_users[validated_id] = UserInfo()

        await self.matrix_utils.ensure_room_invitees(room_id, all_users)

        # Ensure users have correct power levels
        # await self.matrix_utils.ensure_room_power_levels(room_id, all_users)


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
