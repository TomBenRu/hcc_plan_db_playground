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

def create_project_and_team(proj_name: str, team_name: str):
    from .models import Project, Team
    with db_session:
        p = Project(name=proj_name, active=True)
    with db_session:
        t = Team(name=team_name, project=Project.get(lambda p: p.name == proj_name))
    print(f'{t.excel_export_settings=}')


if __name__ == '__main__':
    create_project_and_team('ClinicClownsChemnitz', 'Chemnitz')
