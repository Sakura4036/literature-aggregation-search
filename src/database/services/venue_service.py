from typing import Optional
from sqlalchemy import select

from src.database.connection import DbSession
from src.database.models import Venue
from src.models.schemas import VenueSchema


class VenueService:
    """Static methods for venue lookup and creation."""

    @staticmethod
    async def get_or_create(venue: VenueSchema) -> int:
        if not isinstance(venue, VenueSchema):
            raise TypeError("get_or_create expects VenueSchema")
        async with DbSession() as session:
            if venue.venue_name:
                q = select(Venue).where(Venue.venue_name == venue.venue_name)
                res = await session.execute(q)
                orm = res.scalar_one_or_none()
                if orm:
                    return orm.id
            orm = Venue(venue_name=venue.venue_name, venue_type=venue.venue_type, iso_abbreviation=venue.iso_abbreviation, issn_print=venue.issn_print, issn_electronic=venue.issn_electronic, publisher=venue.publisher, country=venue.country)
            session.add(orm)
            await session.flush()
            await session.commit()
            return orm.id
