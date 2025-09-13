import asyncio
import json
import websockets

# Shared global variable to store latest gold price
_latest_gold_price = 0  # fallback initial price

async def get_current_price() -> float:
    """Return the latest gold price."""
    return _latest_gold_price

async def _websocket_price_updater():
    global _latest_gold_price
    uri = "wss://api.goldvault.app/ws/live-prices"
    while True:
        try:
            async with websockets.connect(uri, open_timeout=10) as websocket:
                async for message in websocket:
                    data = json.loads(message)
                    gold = data.get("gold")
                    if gold and "price" in gold and "Bid" in gold["price"]:
                        _latest_gold_price = float(gold["price"]["Bid"])
                        # Optional: log or print updated price
                        # print(f"[PriceUpdater] Updated gold price: {_latest_gold_price}")
        except Exception as e:
            # print(f"[PriceUpdater] Connection error: {e}. Reconnecting in 5 seconds.")
            await asyncio.sleep(5)