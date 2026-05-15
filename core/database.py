from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Text, Boolean, func, select, update, text
from datetime import datetime, date
from core.config import settings
import logging

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    is_premium = Column(Boolean, default=False)
    daily_requests = Column(Integer, default=0)
    last_request_date = Column(DateTime, nullable=True)
    last_symptom_analysis = Column(DateTime, nullable=True)
    referral_code = Column(String(50), unique=True, nullable=True)
    referred_by = Column(BigInteger, nullable=True)
    free_analyses = Column(Integer, default=0)
    lab_balance = Column(Integer, default=0)


class Consultation(Base):
    __tablename__ = "consultations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    symptoms = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    triage_level = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    amount = Column(Integer, nullable=False)
    package_size = Column(Integer, nullable=False)   # 1, 3, 10
    pay_id = Column(String(64), unique=True, nullable=False)
    status = Column(String(20), default="pending")   # pending | paid | cancelled
    created_at = Column(DateTime, server_default=func.now())
    paid_at = Column(DateTime, nullable=True)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Add lab_balance column if missing (SQLite migration)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("ALTER TABLE users ADD COLUMN lab_balance INTEGER DEFAULT 0"))
            await conn.commit()
    except Exception:
        pass  # Column already exists


async def check_usage_limit(telegram_id: int) -> tuple[bool, int]:
    """
    Проверяет лимиты пользователя.
    Возвращает (can_proceed, current_count).
    Лимит: 3 бесплатных запроса в день.
    """
    async with async_session() as session:
        result = await session.execute(select(User).filter(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        
        if not user:
            return True, 0
            
        today = date.today()
        last_date = user.last_request_date.date() if user.last_request_date else None
        
        # Если новый день — сбрасываем счетчик
        if last_date != today:
            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(daily_requests=0, last_request_date=func.now())
            )
            await session.commit()
            return True, 0
            
        # Проверяем лимит (3 запроса)
        if user.daily_requests >= 3:
            return False, user.daily_requests
            
        return True, user.daily_requests


async def increment_usage(telegram_id: int):
        """Увеличивает счетчик запросов."""
        async with async_session() as session:
            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(
                    daily_requests=User.daily_requests + 1,
                    last_request_date=func.now()
                )
            )
            await session.commit()


async def update_last_symptom_analysis(telegram_id: int):
    """Обновляет время последнего анализа симптомов."""
    async with async_session() as session:
        try:
            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(last_symptom_analysis=func.now())
            )
            await session.commit()
        except Exception as e:
            logger.error(f"Error updating last_symptom_analysis: {e}")
            # If column doesn't exist, we can't update it, but don't fail the whole flow


async def check_symptom_analysis_cooldown(telegram_id: int) -> tuple[bool, int]:
    """
    Проверяет, прошло ли 24 часа с последнего анализа симптомов.
    Возвращает (can_proceed, seconds_remaining).
    """
    async with async_session() as session:
        try:
            result = await session.execute(select(User).filter(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()
            
            if not user:
                return True, 0
                
            # Handle missing column gracefully (if DB hasn't been migrated)
            if not hasattr(user, 'last_symptom_analysis') or not user.last_symptom_analysis:
                return True, 0
                
            from datetime import datetime
            now = datetime.now()
            last_analysis = user.last_symptom_analysis
            
            # Если last_analysis naive (как в БД), сравниваем как есть
            time_passed = now - last_analysis
            seconds_passed = time_passed.total_seconds()
            cooldown_seconds = 24 * 60 * 60  # 24 часа
            
            if seconds_passed >= cooldown_seconds:
                return True, 0
            else:
                seconds_remaining = int(cooldown_seconds - seconds_passed)
                return False, seconds_remaining
                
        except Exception as e:
            logger.error(f"Error checking cooldown: {e}")
            # If there's an error (e.g., column doesn't exist), allow new analysis
            return True, 0


@asynccontextmanager
async def get_session():
    async with async_session() as session:
        yield session


# --- Referral System ---
async def generate_referral_code(telegram_id: int) -> str:
    """Generate a unique referral code for a user."""
    import uuid
    code = f"ref_{uuid.uuid4().hex[:12]}"
    async with async_session() as session:
        async with session.begin():
            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(referral_code=code)
            )
    return code


async def get_or_create_referral_code(telegram_id: int) -> str:
    """Генерирует или возвращает существующий реферальный код пользователя."""
    async with async_session() as session:
        result = await session.execute(select(User).filter(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            return ""
        if user.referral_code:
            return user.referral_code
        import uuid
        code = f"ref_{uuid.uuid4().hex[:12]}"
        await session.execute(
            update(User).where(User.telegram_id == telegram_id).values(referral_code=code)
        )
        await session.commit()
        return code


async def process_referral(new_user_id: int, referral_code: str):
    """
    Обрабатывает реферальный переход:
    - Находит пригласившего по referral_code
    - Даёт +1 бесплатный анализ новому пользователю
    - Даёт +1 бесплатный анализ пригласившему
    """
    async with async_session() as session:
        # Находим пригласившего
        result = await session.execute(
            select(User).filter(User.referral_code == referral_code)
        )
        referrer = result.scalar_one_or_none()
        if not referrer or referrer.telegram_id == new_user_id:
            return

        # Проверяем, что новый пользователь ещё не получал реферальный бонус
        new_user_result = await session.execute(
            select(User).filter(User.telegram_id == new_user_id)
        )
        new_user = new_user_result.scalar_one_or_none()
        if not new_user or new_user.referred_by is not None:
            return  # Уже получал бонус — пропускаем

        # Даём +1 новому
        await session.execute(
            update(User).where(User.telegram_id == new_user_id).values(
                referred_by=referrer.telegram_id,
                free_analyses=User.free_analyses + 1
            )
        )

        # Даём +1 пригласившему
        await session.execute(
            update(User).where(User.telegram_id == referrer.telegram_id).values(
                free_analyses=User.free_analyses + 1
            )
        )

        await session.commit()


async def get_free_analyses(telegram_id: int) -> int:
    """Возвращает количество бесплатных анализов пользователя."""
    async with async_session() as session:
        result = await session.execute(select(User).filter(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        return user.free_analyses if user else 0


async def use_free_analysis(telegram_id: int) -> bool:
    """Use one free analysis if available. Returns True if used, False if none available."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user or user.free_analyses <= 0:
            return False
        user.free_analyses -= 1
        await session.commit()
        return True


async def grant_bonus_analysis(telegram_id: int, amount: int = 1) -> None:
    """Grant bonus free analyses to user."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user:
            user.free_analyses += amount
            await session.commit()


# --- Payment / Lab Balance ---

async def create_payment_record(user_id: int, amount: int, package_size: int) -> Payment:
    """Create a new pending payment record."""
    import uuid
    pay_id = f"pay_{uuid.uuid4().hex[:16]}"
    async with async_session() as session:
        payment = Payment(
            user_id=user_id,
            amount=amount,
            package_size=package_size,
            pay_id=pay_id,
            status="pending",
        )
        session.add(payment)
        await session.commit()
        return payment


async def get_payment_by_pay_id(pay_id: str) -> Payment | None:
    """Get payment record by internal pay_id."""
    async with async_session() as session:
        result = await session.execute(
            select(Payment).filter(Payment.pay_id == pay_id)
        )
        return result.scalar_one_or_none()


async def confirm_payment(pay_id: str) -> bool:
    """Mark payment as paid and add package to user's lab_balance."""
    async with async_session() as session:
        result = await session.execute(
            select(Payment).filter(Payment.pay_id == pay_id)
        )
        payment = result.scalar_one_or_none()
        if not payment or payment.status == "paid":
            return False

        payment.status = "paid"
        payment.paid_at = func.now()

        # Add package to user's lab balance
        await session.execute(
            update(User).where(User.telegram_id == payment.user_id).values(
                lab_balance=User.lab_balance + payment.package_size
            )
        )
        await session.commit()
        return True


async def get_lab_balance(telegram_id: int) -> int:
    """Get user's lab analysis balance."""
    async with async_session() as session:
        result = await session.execute(select(User).filter(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        return user.lab_balance if user else 0


async def use_lab_balance(telegram_id: int) -> bool:
    """Use one lab analysis from balance. Returns True if used."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user or user.lab_balance <= 0:
            return False
        user.lab_balance -= 1
        await session.commit()
        return True


async def get_referral_stats(telegram_id: int) -> dict:
    """Возвращает реферальную статистику пользователя."""
    async with async_session() as session:
        result = await session.execute(
            select(func.count()).select_from(User).filter(User.referred_by == telegram_id)
        )
        total_referred = result.scalar() or 0
        return {
            "total_referred": total_referred,
}
