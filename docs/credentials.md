## API Keys

### Twitter

TODO

### Telegram

TODO

### ImgFlip

TODO

### Slack

- Go to https://api.slack.com/apps and create a new App ("from Scratch")

#### Bot Token

- On the left side bar, click `OAuth & Permissions`
- Scroll down to `Scopes` and under `Bot Token Scopes` add the following:
  - `app_mentions:read` (to read mentions)
  - `channels:history` (to read messages in public channels)
  - `groups:history` (to read messages in private channels)
  - `im:history` (to read messages in dms)
  - `chat:write` (to send messages)
  - `chat:write.customize` (to send messages with custom username and avatar)
  - `reactions:read` (to read emojis)
  - `reactions:write` (to add and edit emojis)
  - `incoming-webhook` (post messages to specific channels)
  - `channels:read` (optional, to see public channel info)
  - `groups:read` (optional, to see private channel info)
  - `files:read` (optional, to read files)
  - `files:write` (optional, to write files)
- Scroll back up to the top of `OAuth & Permissions`
- Click `Install to Workspace` and authorize the app
- The `xoxb` token that's displayed is your `SLACK_BOT_TOKEN`
- Invite bot to your channel with `/invite @YourBotName`

#### App Token

- Under app settings find `Socket Mode` and toggle `Enable Socket Mode` to On, and create an App-Level Token
- Add the token name, make sure scope `connections:write` is selected, and click `Generate`
- The `xapp-` token that's generated is the `SLACK_APP_TOKEN`
