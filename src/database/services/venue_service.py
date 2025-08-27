from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Venue
from src.models.schemas import VenueSchema


class VenueService:
    @staticmethod
    async def get_or_create(venue: VenueSchema, session: AsyncSession) -> int:
        if not isinstance(venue, VenueSchema):
            raise TypeError("get_or_create expects VenueSchema")
        if venue.venue_name:
            q = select(Venue).where(Venue.venue_name == venue.venue_name)
            res = await session.execute(q)
            orm = res.scalar_one_or_none()
            if orm:
                return orm.id
        orm = Venue(venue_name=venue.venue_name, venue_type=venue.venue_type, iso_abbreviation=venue.iso_abbreviation, issn_print=venue.issn_print, issn_electronic=venue.issn_electronic, publisher=venue.publisher, country=venue.country)
        async with session.begin():
            session.add(orm)
            await session.flush()
        return orm.id
