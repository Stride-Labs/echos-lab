## API Keys

### Twitter

- Go to https://developer.twitter.com/en/portal/dashboard and sign in
- Click `Create Project` (or select an existing project)
- Fill in the project details and use case
- Select the project type that best matches your needs. The Basic plan is recommended to avoid rate limit issues.
- Save your project and proceed to the `Keys and Tokens` section

#### API Keys and Bearer Token

- The Consumer and Bearer Tokens define the project level read credentials
- Under `Keys and Tokens`, locate the `Consumer Keys` section
- The "API Key" shown is your `TWITTER_CONSUMER_KEY`
- The "API Secret Key" is your `TWITTER_CONSUMER_SECRET`
- Scroll down to find "Bearer Token" - this is your `TWITTER_BEARER_TOKEN`

#### Access Tokens

- The access tokens allow the bot to post on behalf of the new twitter account
- In the "Authentication Tokens" section, click "Generate" under "Access Token and Secret"
- The "Access Token" shown is your `TWITTER_ACCESS_TOKEN`
- The "Access Token Secret" is your `TWITTER_ACCESS_TOKEN_SECRET`

### Anthropic

- Go to https://console.anthropic.com/ and sign in
- Once logged in, navigate to the API Keys section
- Click `Create Key` to generate a new API key
- The key starting with `sk-ant-` is your `ANTHROPIC_API_KEY`

### ImgFlip

- Go to https://imgflip.com/ and click Signup
- If you logged in through a third party (e.g. google), go to your account settings and click `Change Password`
- Include your username and password under the variables `IMGFLIP_USERNAME` and `IMGFLIP_PASSWORD`

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

### Telegram

- Open Telegram and search for [@BotFather](https://t.me/BotFather)
- Start a chat with BotFather and send `/newbot`
- Follow the prompts to:
  - Choose a name for your bot (this is the display name)
  - Choose a username for your bot (must end in 'bot')
- BotFather will generate a token like `123456789:ABCdefGHIjklmNOPQrstUVwxyz`
- This is your `TELEGRAM_TOKEN`
