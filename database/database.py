from enum import Enum

from pony.orm import db_session, commit, set_sql_debug

from database.enum_converter import EnumConverter
from .models import db

provider = 'sqlite'
filename = 'database.sqlite'


db.bind(provider=provider, filename=filename, create_db=True)

# Register the type converter with the database
db.provider.converter_classes.append((Enum, EnumConverter))

db.generate_mapping(create_tables=True)
set_sql_debug(False, False)
