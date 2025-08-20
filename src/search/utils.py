from datetime import datetime
from typing import Tuple


def year_split(year: str, default_start: str = '1900') -> Tuple[str, str]:
    """
    Split a year string into two years, representing the start and end of the year.
    :param year: A year string.
    :param default_start: The default start year if the year string starts with a '-'.
    :return: A tuple of two strings representing the start and end of the year.
    """
    year = year.strip()
    if year.startswith('-'):
        start = default_start
        end = year[1:]
    elif year.endswith('-'):
        start = year[:-1]
        end = datetime.now().year
    elif '-' in year:
        start, end = year.split('-')
    else:
        start = end = year
    return start, end
