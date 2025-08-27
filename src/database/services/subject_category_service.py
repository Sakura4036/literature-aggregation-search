from typing import Optional
from sqlalchemy import select

from src.database.connection import DbSession
from src.database.models import SubjectCategory
from src.models.schemas import CategorySchema


class SubjectCategoryService:
    """Static methods for subject category lookup/creation."""

    @staticmethod
    async def get_or_create(cat: CategorySchema) -> int:
        if not isinstance(cat, CategorySchema):
            raise TypeError("get_or_create expects CategorySchema")
        async with DbSession() as session:
            if cat.category_name:
                q = select(SubjectCategory).where(SubjectCategory.category_name == cat.category_name)
                res = await session.execute(q)
                orm = res.scalar_one_or_none()
                if orm:
                    return orm.id
            orm = SubjectCategory(category_name=cat.category_name, category_code=cat.category_code, category_type=cat.category_type, description=None)
            session.add(orm)
            await session.flush()
            await session.commit()
            return orm.id
