# RSS → Discord (Free, No Server)

This repo posts RSS feed updates (like CS2 and LoL patch notes) to your Discord channels using **Discord webhooks** and a **free GitHub Actions** schedule.

## What you get

- 🆓 No server needed — runs on GitHub Actions every 15 minutes.
- ✅ Avoid duplicates via `state.json` (committed only when new items appear).
- 🔧 Easy to add more feeds (edit `feeds.json`).
- 🔐 Your webhook URLs stay secret via GitHub **Secrets**.

## Quick start (about 5 minutes)

1. **Create a new GitHub repo** (public or private).
2. Download this folder and upload it to your repo, or push via Git.
3. In your Discord server, go to each target channel → *Edit Channel* → **Integrations** → **Webhooks** → **New Webhook** → copy the webhook URL.
4. In your GitHub repo, go to **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `DISCORD_WEBHOOK_CS2` = *your CS2 channel webhook URL*
   - `DISCORD_WEBHOOK_LOL` = *your LoL channel webhook URL*
5. (Optional) Edit **feeds.json** to add or change feeds. Default has:
   - CS2: Steam News feed for app 730
   - LoL: Official Patch Notes RSS
6. Go to **Actions** tab → enable workflows if prompted → run **RSS to Discord** with *Run workflow*.
7. The workflow will also run **every 15 minutes**. New items get posted with a nice embed. `state.json` will update to avoid duplicates.

## Customising

- **Add more feeds**: append entries in `feeds.json` like:
  ```json
  {"name": "valorant", "feed_url": "https://playvalorant.com/en-us/news/tags/patch-notes/feed/", "webhook_secret": "DISCORD_WEBHOOK_VAL"}
  ```
  Then add a new GitHub Secret `DISCORD_WEBHOOK_VAL` with that channel’s webhook URL, and expose it in the workflow `env:` block.

- **Posting format**: edit `post_to_discord` in `main.py` to change the embed.

- **Frequency**: change the `cron` in `.github/workflows/rss_to_discord.yml`.

## Notes

- The workflow commits only when `state.json` changes (i.e., when new items were posted).
- If a feed returns HTML in the summary, the script strips tags lightly.
- Rate-limited politely with ~1.2s between posts.

---

Happy patch-noting! 🎮
