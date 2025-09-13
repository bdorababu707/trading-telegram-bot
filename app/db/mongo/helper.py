# --- app/db/mongo/helper.py ---
import time
from typing import Optional, List, Dict, Any
from app.db.mongo.mongodb import get_database

class MongoHelper:

    @staticmethod
    async def find_one(
        collection: str,
        query: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None
    ) -> Optional[Dict[str, Any]]:
        db = get_database()
        return await db[collection].find_one(query, projection)

    @staticmethod
    async def find_many(
        collection: str, 
        query: Dict[str, Any], 
        skip: int = 0, 
        limit: int = 100,
        sort: List[tuple] = None,
        projection: Optional[Dict[str, int]] = None
    ) -> List[Dict[str, Any]]:
        db = get_database()
        cursor = db[collection].find(query, projection).skip(skip).limit(limit)
        
        if sort:
            cursor = cursor.sort(sort)
            
        return await cursor.to_list(length=limit)

    @staticmethod
    async def insert_one(
        collection: str, 
        document: Dict[str, Any]
    ) -> str:
        db = get_database()
        result = await db[collection].insert_one(document)
        return str(result.inserted_id)

    @staticmethod
    async def update_one(
        collection: str, 
        query: Dict[str, Any], 
        update: Dict[str, Any],
        upsert: bool = False
    ) -> int:
        db = get_database()
        result = await db[collection].update_one(query, update, upsert=upsert)

        if result.modified_count > 0:
            await db[collection].update_one(query, {"$set": {"updated_at": int(time.time())}})
            
        return result.modified_count

    @staticmethod
    async def delete_one(
        collection: str, 
        query: Dict[str, Any]
    ) -> int:
        db = get_database()
        result = await db[collection].delete_one(query)
        return result.deleted_count

    @staticmethod
    async def aggregate(
        collection: str, 
        pipeline: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        db = get_database()
        return await db[collection].aggregate(pipeline).to_list(length=None)

    @staticmethod
    async def count_documents(collection: str, query: dict) -> int:
        db = get_database()
        return await db[collection].count_documents(query)