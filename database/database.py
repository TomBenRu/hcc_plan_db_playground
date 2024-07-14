import os.path
from enum import Enum

from pony.orm import db_session, commit, set_sql_debug

from database.enum_converter import EnumConverter
from database.models import db

provider = 'sqlite'
db_path = os.path.join(os.path.dirname(__file__), 'database.sqlite')

db.bind(provider=provider, filename=db_path, create_db=True)

# Register the type converter with the database
db.provider.converter_classes.append((Enum, EnumConverter))

db.generate_mapping(create_tables=True)
set_sql_debug(False, False)
