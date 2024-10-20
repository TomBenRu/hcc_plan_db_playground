import os.path
from enum import Enum

from pony.orm import db_session, commit, set_sql_debug

from configuration.project_paths import curr_user_path_handler
from database.enum_converter import EnumConverter
from database.models import db

provider = 'sqlite'
db_folder = curr_user_path_handler.get_config().db_file_path
db_path = os.path.join(db_folder, 'database.sqlite')
if not os.path.exists(db_folder):
    os.makedirs(db_folder)

db.bind(provider=provider, filename=db_path, create_db=True)

# Register the type converter with the database
db.provider.converter_classes.append((Enum, EnumConverter))

db.generate_mapping(create_tables=True)
set_sql_debug(False, False)
