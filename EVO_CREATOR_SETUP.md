# Evo Creator / Art Shop

Branch-only implementation for Evo Creator and custom-art marketplace.

## Configuration
- Set ART_SHOP_URL to this service's public HTTPS origin.
- Set PORT through the host.
- Configure the Telegram Mini App domain in BotFather.
- Keep bot token and MongoDB credentials in environment variables.

## Commands
- /customise opens Creator Studio.
- /shop opens the custom-art-only Art Shop.
- /custompending is admin-only review queue.
- Approval publishes the listing; rejection refunds held 5,000 Evo Points.

## Rules
- Successful guess reward: 10 Evo Points.
- Submission cost: 5,000 Evo Points.
- Locked rarity: customise.
- Price: 10,000–1,000,000 Coins.
- Multiple buyers may buy each approved character.
- Creator receives 100% of each sale in bot Coins.
- Art Shop lists only approved custom art.

## Deployment
Flask uses MongoDB GridFS for image storage and MongoDB transactions for purchase consistency. Transactions require Atlas/replica-set or sharded-cluster MongoDB. Test staging before production.
