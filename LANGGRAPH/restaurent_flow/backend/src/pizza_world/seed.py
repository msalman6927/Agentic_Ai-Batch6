"""Create tables, seed menu_items from the PDF extract, seed admin + chef users.

Run: uv run python -m pizza_world.seed
"""

from __future__ import annotations

from sqlalchemy import select

from pizza_world.config import settings
from pizza_world.core.runner import run
from pizza_world.core.security import hash_password
from pizza_world.data.menu_seed import MENU_ROWS
from pizza_world.db.models import Base, MenuItem, User
from pizza_world.db.session import dispose_engine, get_engine, get_session_maker


async def seed() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with get_session_maker()() as session:
        existing = (await session.execute(select(MenuItem))).scalars().first()
        if existing is None:
            session.add_all(
                MenuItem(name=n, category=c, size=s, price=p, description=d)
                for (n, c, s, p, d) in MENU_ROWS
            )
            print(f"Seeded {len(MENU_ROWS)} menu items")
        else:
            print("Menu already seeded, skipping")

        for email, password, role, name in (
            (settings.admin_email, settings.admin_password, "admin", "Admin"),
            (settings.chef_email, settings.chef_password, "chef", "Chef"),
        ):
            found = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if found is None:
                session.add(
                    User(
                        name=name,
                        email=email,
                        password_hash=hash_password(password),
                        role=role,
                    )
                )
                print(f"Seeded {role} user: {email}")
            else:
                print(f"{role} user already exists: {email}")

        await session.commit()

    await dispose_engine()


def main() -> None:
    run(seed())


if __name__ == "__main__":
    main()
