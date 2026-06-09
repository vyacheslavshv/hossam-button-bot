# Button Post Bot

A small Telegram bot that builds a **channel/group post with one big button** and
publishes it for you. A pinned message that has a single inline button is shown by
Telegram as a large button on top of the channel — this bot makes those posts.

## What it does

1. Anyone who opens the bot can build a post.
2. The post can be **text, or a photo / video / file** (with a caption) — exactly
   like composing a normal channel post.
3. You add **one button**: its label, its link (any website / bot / channel), and
   its **color** (Default, Blue, Green or Red).
4. The bot shows a **preview**, then you pick which channel to publish to.
5. It publishes the post and **pins** it, so the button shows up big on top.

The bot can only publish to channels/groups where it was added as an **admin**
(with *Post messages* and *Pin messages*). It remembers those automatically; you
can also add one by forwarding a message from the channel or sending its
`@username`.

## Setup (local)

```bash
./setup.sh                 # creates .venv and installs deps
cp .env.example .env       # then put your BOT_TOKEN in .env
.venv/bin/python main.py
```

## Use

1. In your channel/group: add the bot as **admin** (enable *Post messages* and
   *Pin messages*).
2. Open the bot, press **Create post** (or send `/new`).
3. Send the content → button label → button link → pick a color.
4. Choose the channel from the list → done. The post is published and pinned.

Commands: `/new` start a post · `/cancel` cancel · `/start` menu.

## Deploy (Linux server, systemd)

```bash
git clone <repo> && cd hossam-button-bot
./setup.sh                 # picks Python 3.10-3.14, builds .venv, installs deps
cp .env.example .env       # then put the real BOT_TOKEN in .env
sudo ./deploy.sh           # installs + starts a systemd service
```

Manage it:

```bash
systemctl status hossam-button-bot
journalctl -u hossam-button-bot -f
sudo ./deploy.sh           # run again to update: git pull + restart
```

State: SQLite (the list of admin channels) lives in `data/`, logs in `logs/` —
both are created automatically on first run.
