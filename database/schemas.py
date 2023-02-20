from uuid import UUID

from pydantic import BaseModel, EmailStr


class PersonCreate(BaseModel):
    f_name: str
    l_name: str
    email: EmailStr
    phone_nr: str | None
    username: str
    password: str
    project: 'Project'


class Person(PersonCreate):
    id: UUID


class PersonShow(Person):
    pass


class ProjectCreate(BaseModel):
    name: str
    active: bool


class Project(ProjectCreate):
    id: UUID
    pass


class ProjectShow(Project):
    pass


PersonCreate.update_forward_refs(**locals())
