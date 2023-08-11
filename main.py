import json

from database.db_services import create_project_and_team, get_projects
from gui.app import show_gui

show_gui()

# create_project_and_team('ClownsCanCare', 'Karlsruhe')
# projects = get_projects()
# print(projects)
# print([p.model_dump() for p in projects])
# print([json.loads(p.json()) for p in projects])
