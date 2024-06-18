# maubot-pretix-invites

A maubot plugin that automatically invites event participants from pretix into a matrix room. This helps facilitate Fedora virtual events that are run on Matrix.

## History and project Origins

This project began with the use of pretix + Matrix combo from the F40 release party ([ticket](https://gitlab.com/fedora/commops/interns/-/issues/15)) and started a [community operations intern initiative](https://gitlab.com/fedora/commops/interns/-/issues/16) to adapt and automate the process for the Fedora Week of Diversity 2024 ([ticket](https://gitlab.com/fedora/dei/week-of-diversity/-/issues/23))

## Features
- Can auth with pretix and fetch event attendees
- Can bulk-invite attendees who havent yet been processed
- can handle incoming webhooks from pretix for paid-for events and auto-invite those people to the event room(s)
- can associate matrix rooms with events to (theoretically) invite users to multiple matrix rooms

## Basic Usage and commands

Once the bot is running and in a matrix room, you can interact with it using a few commands:

`!authorize` (no arguments) will give you an oauth url to give the bot read only access to a pretix team you are a member of.

`!authorize <callback url>` will complete the auth process in the event you dont have (or havent configured, or this bot doesnt yet support) a web server thats publicly-accessible and HTTPS-capable for receiving the callback URL to complete the authentication process. Simply use this command with the URL that you are redirected to after auth and it will do the rest.

`!batchinvite <pretix url>` this command, in combination with the pretix invitation url you probably distributed to your event participants (i.e. `https://pretix.eu/fedora/matrix-test/`) will allow the bot to query your event and grab participants matrix IDs and attempt to invite them to the room where the command was issued

`!status` check the bot's auth status and the status of the current room (is it mapped to an event)

`!setroom <pretix url>` this command, in combination with the pretix invitation url you probably distributed to your event participants (i.e. `https://pretix.eu/fedora/matrix-test/`) will associate this room with the event so the bot doesnt need the room ID to be specified when inviting people (such as through `!batchinvite` (TODO), or the webhook handler)

`!unsetroom` this command will remove this room from all events it is currently associated with

### Examples
**Authorization and batch invite**
![A screenshot of a matrix conversation showing the usage of the authorization and batch invite commands](./demo/matrix%20auth%20and%20batch%20invite.png)

**Association and status**
![A screenshot of a matrix conversation showing the usage of the association and status commands](./demo/room%20association%20and%20status.png)



## Dependencies
External things the bot needs to run well:
- python dependencies from requirements.txt
- a public facing web address (optionally with HTTPS, this is for webhook calls from pretix)
- credentials for pretix
- a pretix event to invite people to


## Configuration

To configure the bot, modify `base-config.yaml` to add your pretix tokens and the matrix IDs of some authorized users.


## Development

See [CONTRIBUTING.md](./CONTRIBUTING.md) for more details on the development workflow

### Pretix

#### Getting Credentials


The main thing this bot needs to work is credentials for the event ticketing platform Pretix. Either of these options will likely require elevated permissions on the Fedora pretix team, or someone willing to authenticate for you.


There are a couple paths for getting credentials:
1. [Generate a token at the team level](https://docs.pretix.eu/en/latest/api/tokenauth.html#obtaining-an-api-token) 
2. (the one this bot uses) - Get a token [via an oauth grant](https://docs.pretix.eu/en/latest/api/oauth.html) 

You will need to create a pretix account (can probably be unpriviliged - may need an invite from someone) and [register an Oauth application](https://docs.pretix.eu/en/latest/api/oauth.html#registering-an-application) to get a client ID and secret (the secret may not be fully necessary).
- for the redirect URL, if you dont know whether you are going to have access to a public facing, https-capable web address, simply enter `https://localhost:8000/`

#### Setting up an event

Once you are in a pretix team you can set up an event. The process is pretty much the same as setting up any event in pretix, however....

If this event is being set up for testing, be sure to uncheck the "list publicly" box on the main settings page so that the event doesnt show up in your orgs public list of events

![The "list publicly" checkbox on the main settings page of pretix that reads "Show in lists"](./demo/pretix%20public%20checkbox.png)


You will also need to configure a custom question to collect participant's Matrix ID. Pretix doesnt seem to have user facing documentation on this, so your best bet is probably to copy the settings from an existing event that had these questions already set up.

Here's what you would need to set the values to for the matrix id question (ignore the FAS one - you may need to do additional things to set up questions, im not sure):

![the questions menu in pretix showing a configured matrix ID question](./demo/pretix%20questions%20setup.png)

Currently this bot is hardcoded to look for an `internal identifier` value (its under advanced when editing the question) thats set to `matrix`. In the future this may be configurable

