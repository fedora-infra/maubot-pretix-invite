# maubot-events
A maubot plugin that helps facilitate Fedora virtual events that are run through Matrix

The code for this bot was originally based on the [maubot-pagure-notifications](https://github.com/fedora-infra/maubot-pagure-notifications) codebase due its implementation of similar features (i.e. handling webhooks).


## History and project Origins

This project began with the use of pretix + Matrix combo from the F40 release party ([ticket](https://gitlab.com/fedora/commops/interns/-/issues/15)) and was [adapted to be more automatic](https://gitlab.com/fedora/commops/interns/-/issues/16) for the Fedora Week of Diversity 2024 ([ticket](https://gitlab.com/fedora/dei/week-of-diversity/-/issues/23))


## Development

This bot uses [matrix-bots](https://github.com/fedora-infra/matrix-bots) as its dev environment.

### Dependencies
Things the bot needs to run:
- python dependencies from requirements.txt
- a public facing web address with HTTPS enabled (not fully supported yet but planned) - this is for webhooks and callbacks from pretix
- 

### Configuration

#### Pretix Auth

The main thing this bot needs to work is credentials for the event ticketing platform Pretix. Either of these options will likely require elevated permissions on the Fedora pretix team, or someone willing to authenticate for you.


There are a couple paths for getting credentials:
1. [Generate a token at the team level](https://docs.pretix.eu/en/latest/api/tokenauth.html#obtaining-an-api-token) 
2. (the one this bot uses) - Get a token [via an oauth grant](https://docs.pretix.eu/en/latest/api/oauth.html) 

You will need to create a pretix account (can probably be unpriviliged - may need an invite from someone) and [register an Oauth application](https://docs.pretix.eu/en/latest/api/oauth.html#registering-an-application) to get a client ID and secret (the secret may not be fully necessary).
- for the redirect URL, if you dont know whether you are going to have access to a public facing, https-capable web address, simply enter `https://localhost:8000/`



### Hacking workflow

Once your environment/vagrant vms are set up...

**If working in a separate git dir**
1. add the shared folder for your bot (in this case _maubot-events) to your working git repo as a remote (yes you can do this with a local.relative path)
2. push your changes to a new branch on the remote, in this case `prod`: `git push vm main:prod` (this is because you cannot push to a checked out branch)
3. from the shared folder (either in the VM or not) merge the changes (should be a fast foward) while on `main` to update main: `git merge prod`

Now continue with the rest of the instructions below...

**If working in the shared folder directly**
1. open the VM using `vagrant ssh` from the `matrix-bots` folder
2. cd to the `_maubot-events` directory in the vm
3. run `mbc build -u` to update the bot and see if it builds

if you get a message saying that it uploaded successfully, your bot has been updated and you can test it in your matrix client

### Creating test users

You may want to add a bunch of additional users to the dev environment for testing, to do so, SSH into the VM per the above instructions and run these commands for each user that you want to add, replacing `NAME` with the name you want:
```bash
register_new_matrix_user -u NAME -p password -c /etc/synapse/homeserver.yaml --no-admin
mbc auth -c --homeserver matrixbots.tinystage.test --username NAME --password password

```

This will set up the account and assign it a dummy client that will automatically join any rooms it is invited to.

You can set the name to whatever you like. Here are some ideas:
- adam
- brodie
- charlie
- dave
- evelyn
- faith

