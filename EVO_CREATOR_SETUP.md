# Evo Creator / Art Shop

The Creator Studio and Art Shop are registered on the existing AIOHTTP server in `TEAMZYRO/modules/blackmarket.py`, alongside the Chess Mini App. No second web server or Flask dependency is used.

## Configuration
- No `ART_SHOP_URL` or `WEBAPP_URL` is needed for the Art Shop buttons. They reuse the bot's existing Main Mini App deep-link flow, like Chess (`https://t.me/<bot>?startapp=...`). The bot's existing Main Mini App setup must remain configured as it is for Chess.
- Configure the Telegram Mini App domain in BotFather.
- Keep bot token and MongoDB credentials in environment variables.

## Commands
- `/customise` opens Creator Studio.
- `/shop` opens the custom-art-only Art Shop.
- `/custompending` is the admin-only review queue.
- Approval publishes the listing; rejection refunds held 5,000 Evo Points.

## Rules
- Successful guess reward: 10 Evo Points.
- Submission cost: 5,000 Evo Points.
- Locked rarity: `customise`.
- Price: 10,000–1,000,000 Coins.
- Multiple different users may buy each approved character; each buyer can buy a listing once.
- Creator receives 100% of each sale in bot Coins.
- Art Shop lists only approved custom art.

## Storage and deployment
Images use MongoDB GridFS. Purchase balance changes use MongoDB transactions, which require Atlas/replica-set or sharded-cluster MongoDB. Test the purchase/refund paths in staging before production.
