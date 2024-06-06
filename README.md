# maubot-events
A maubot plugin that helps facilitate Fedora virtual events that are run through Matrix

The code for this bot was originally based on the [maubot-pagure-notifications](https://github.com/fedora-infra/maubot-pagure-notifications) codebase due its implementation of similar features (i.e. handling webhooks).


### Hacking workflow

**If working in a separate git dir**
1. add the shared folder for your bot (in this case _maubot-events) to your working git repo as a remote (yes you can do this with a local.relative path)
2. push your changes to a new branch on the remote, in this case `prod`: `git push vm main:prod` (this is because you cannot push to a checked out branch)
3. from the shared folder (either in the VM or not) merge the changes (should be a fast foward) while on `main` to update main: `git merge prod`

now continue with the rest of the instructions below

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

