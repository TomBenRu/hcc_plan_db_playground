from uuid import UUID

from database import db_services


def backtranslate_eval_str(fixed_cast: str, str_for_team: str = 'team'):
    form = []
    eval_str = fixed_cast
    if not eval_str:
        return
    e_s = eval_str.replace('and', ',"and",').replace('or', ',"or",').replace(f'in {str_for_team}', '')
    e_s = eval(e_s)
    if type(e_s) != tuple:
        e_s = (e_s,)
    for element in e_s:
        if type(element) == tuple:
            break
    else:
        e_s = [e_s]
    for val in e_s:
        if type(val) in [int, UUID]:
            form.append([val])
        elif type(val) == str:
            form.append(val)
        else:
            form.append(list(val))
    return form


def generate_fixed_cast_clear_text(fixed_cast: str | None):
    replace_map = {'and': 'und', 'or': 'oder'}

    def generate_recursive(item_list: list):
        clear_list = []
        for item in item_list:
            if isinstance(item, str):
                clear_list.append(replace_map[item])
            elif isinstance(item, UUID):
                person = db_services.Person.get(item)
                clear_list.append(f'{person.f_name} {person.l_name}')
            else:
                clear_list.append(str(generate_recursive(item)))
        return clear_list[0] if len(clear_list) == 1 else '(' + ' '.join(clear_list) + ')'
    item = backtranslate_eval_str(fixed_cast)
    clear_text = generate_recursive(item or [])
    if clear_text.startswith('('):
        clear_text = clear_text[1:]
    if clear_text.endswith(')'):
        clear_text = clear_text[:-1]

    return clear_text
