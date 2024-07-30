from enum import Enum


class FlagCategories(Enum):
    PERSON = 'person'
    EVENT = 'event'


class Gender(Enum):
    female = 'f'
    male = 'm'
    divers = 'd'


# Enum für plan-api-remote access:
class TimeOfDay(Enum):
    morning = 'v'
    afternoon = 'n'
    whole_day = 'g'
