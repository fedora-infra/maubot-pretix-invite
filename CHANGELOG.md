# Changelog


## v0.3.2
- handle storing auth credentials in maubot environments other than docker (i.e. fedora dev env)
- fix !help command
- Fix a bug where the bot would crash when trying to authenticate with an expired token. auto-refreshing pretix tokens now works correctly 
- Loads of README updates and docs improvements


## v0.3.1
- dont crash when starting up if no pre-saved pretix token is present

## v0.3.0

- bug fixes and debugging improvements
- add token persistence between bot runs


## v0.2.0

Initial release
- basic pretix auth and fetching
- bulk-inviting of participants via a bot command
- status command