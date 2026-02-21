from sqlalchemy.ext.asyncio import AsyncSession
from app.models.token_record import TokenRecord

# from sqlalchemy import select


class TokenRecordService:
    async def record_token_usage(
        self, db: AsyncSession, ip: str, token_count: int, model: str = None
    ):
        try:
            # stmt = select(TokenRecord).where(TokenRecord.ip == ip)
            # result = await db.execute(stmt)
            # record = result.scalars().first()
            # if record:
            #     record.token_count += token_count
            # else:
            record = TokenRecord(ip=ip, token_count=token_count, model=model)
            db.add(record)
            await db.commit()
        except Exception as e:
            print(f"Error recording token usage: {e}")
            await db.rollback()


# 导出一个模块级实例，方便在其他地方直接使用
token_record_service = TokenRecordService()
