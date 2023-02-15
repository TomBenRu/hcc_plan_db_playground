from pony_models import db


provider = 'sqlite'
filename = 'database.sqlite'


db.bind(provider=provider, filename=filename, create_db=True)
db.generate_mapping(create_tables=True)
