from pony.orm import db_session, commit

from pony_models import db

provider = 'sqlite'
filename = 'database.sqlite'


db.bind(provider=provider, filename=filename, create_db=True)
db.generate_mapping(create_tables=True)


if __name__ == '__main__':
    from pony_models import Project, Team
    with db_session:
        p = Project(name='ClownsAreMedicine', active=True)
    with db_session:
        t = Team(name='Mainz', project=list(Project.select())[0])
    print(f'{t.excel_export_settings=}')
