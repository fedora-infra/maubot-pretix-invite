import hashlib
import hmac

import jinja2
from aiohttp.web import Response
from maubot import Plugin
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper

ACCEPTED_TOPICS = ["issue.new", "issue.comment.added", "git.receive"]


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper):
        helper.copy("pagure_instance")
        helper.copy("projects")


class PagureNotifications(Plugin):
    @classmethod
    def get_config_class(cls):
        return Config

    async def start(self):
        self.config.load_and_update()
        self.webapp.add_route("POST", "/notify", self.handle_request)
        self.log.info(f"Webhook URL is: {self.webapp_url}notify")
        print(self.webapp_url)
        self.log.error(self.config["projects"])

    async def handle_request(self, request):
        json = await request.json()
        message_topic = json.get("topic")

        # first check if the topic of the message is one of the ones that the plugin handles
        if message_topic not in ACCEPTED_TOPICS:
            return Response()

        try:
            if message_topic == "git.receive":
                project_name = json["msg"]["project_fullname"]
            else:
                project_name = json["msg"]["project"]["fullname"]
        except KeyError as e:
            self.log.error(f"The response from pagure was not as expected: {e}.")
            return Response()

        if project_name not in self.config["projects"]:
            self.log.error(
                f"project {project_name} is sending me a webhook, "
                f"but it is not defined in my config!"
            )
            return Response()

        try:
            key = self.config["projects"][project_name]["key"]
            topics = self.config["projects"][project_name]["topics"]
            rooms = self.config["projects"][project_name]["topics"][message_topic]
        except KeyError as e:
            self.log.error(f"Project configuation for the plugin is invalid: {e}.")
            return Response()

        content = await request.read()
        hashhex = hmac.new(key.encode(), msg=content, digestmod=hashlib.sha1).hexdigest()

        if not hmac.compare_digest(hashhex, request.headers.get("X-Pagure-Signature")):
            self.log.error(
                f"message from project {project_name} did not validate correctly. ignoring"
            )
            return Response()

        if message_topic not in topics:
            return Response()

        template = self.loader.sync_read_file(f"pagure_notifications/{message_topic}.j2")
        message = jinja2.Template(template.decode()).render({"json": json})

        for room in rooms:
            if room[0] == "#":
                roomaliasinfo = await self.client.resolve_room_alias(room)
                room = roomaliasinfo.room_id
            try:
                await self.client.send_text(room, None, html=message)
            except Exception as e:
                self.log.error(f"Problem sending message to room {room}: {e}")

        return Response()
