from enum import Enum


class FlagCategories(Enum):
    PERSON = 'person'
    EVENT = 'event'


class Gender(Enum):
    female = 'f'
    male = 'm'
    divers = 'd'
