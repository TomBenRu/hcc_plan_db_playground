from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Save(Command):
    def __init__(self, comb_locations, ):
        super().__init__()