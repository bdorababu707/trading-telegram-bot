from app.db.mongo.helper import MongoHelper
from app.utils.config import settings

class PositionService:

    @staticmethod
    async def get_closed_positions_with_pnl(user_uuid: str):
        query = {"user_id": user_uuid, "status": "CLOSED"}
        projection = {
            "buy_at": 1, "buy_grams": 1, "buy_price": 1,
            "sell_at": 1, "sell_grams": 1, "sell_price": 1,
            "uuid": 1
        }
        closed_positions = []
        cursor = await MongoHelper.find_many(collection=settings.DB_TABLE.TRANSACTIONS, query=query, projection=projection)
        for txn in cursor:
            buy_amount = txn.get("buy_grams", 0) * txn.get("buy_price", 0)
            sell_amount = txn.get("sell_grams", 0) * txn.get("sell_price", 0)
            pnl = sell_amount - buy_amount

            closed_positions.append({
                "order_id": txn.get("uuid"),
                "buy_at": txn.get("buy_at"),
                "sell_at": txn.get("sell_at"),
                "buy_grams": txn.get("buy_grams"),
                "sell_grams": txn.get("sell_grams"),
                "buy_price": txn.get("buy_price"),
                "sell_price": txn.get("sell_price"),
                "pnl": pnl,
            })
        return closed_positions

    @staticmethod
    async def fetch_open_positions(user_uuid: str):
        query = {"user_id": user_uuid, "status": "OPEN"}
        projection = {
            "uuid": 1,
            "buy_at": 1, "buy_grams": 1, "buy_price": 1,
            "sell_at": 1, "sell_grams": 1, "sell_price": 1,
            "buy_price_type": 1,
            "sell_price_type": 1,
        }
        positions = await MongoHelper.find_many(
            collection=settings.DB_TABLE.TRANSACTIONS,
            query=query,
            projection=projection,
            limit=50,
        )
        return positions
    
    @staticmethod
    async def format_position_summary(pos, index):
        if pos.get("buy_price", 0) > 0 and pos.get("buy_grams", 0) > 0:
            return (f"{index}. BUY {pos['buy_grams']}g @ ${pos['buy_price']:.2f} (ID:{pos['uuid'][:5]})")
        if pos.get("sell_price", 0) > 0 and pos.get("sell_grams", 0) > 0:
            return (f"{index}. SELL {pos['sell_grams']}g @ ${pos['sell_price']:.2f} (ID:{pos['uuid'][:5]})")
        return f"{index}. Position ID {pos['uuid'][:8]} (Unknown Type)"