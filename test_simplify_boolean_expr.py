from string import ascii_lowercase
from uuid import UUID
import re

import sympy
from sympy.logic.boolalg import to_dnf
from sympy.abc import a, b, c, d


def translate(expr: str) -> str:
    return expr.replace('not ', '~ ').replace('and ', '& ').replace('or ', '| ')


def back_translate(expr: str) -> str:
    expr = expr.replace('(', '( ').replace(')', ' )')
    exclude = {'~': ' not ', '&': ' and ', '|': ' or ', '(': '(', ')': ')'}
    expr_list = expr.split(' ')
    expr_list = [f'(UUID("{x}") in team)' if x not in exclude else exclude[x] for x in expr_list]
    return '(' + ''.join(expr_list) + ')'


exp1 = '(not ((b or not c) and (not a or not c))) or (not (c or not (b and c))) or (a and not c) and (not a or (a and b and c) or (a and ((b and not c) or (not b))))'
exp2 = '(not (a and not b) or (not c and b)) and (not b) or (not a and b and not c) or (a and not b)'

example_1 = '(((UUID("2ce4ed15-0212-442f-ab0b-73f8940ad217") in team) and (UUID("52521e7f-b7ef-4189-bdd0-bf109c0bbc45") in team)) or ((UUID("2ce4ed15-0212-442f-ab0b-73f8940ad217") in team) and (UUID("d83be6e6-e2a4-44e5-8a3b-2d7e40bcb5a5") in team))) or (((UUID("2ce4ed15-0212-442f-ab0b-73f8940ad217") in team)) and ((UUID("52521e7f-b7ef-4189-bdd0-bf109c0bbc45") in team) or (UUID("d83be6e6-e2a4-44e5-8a3b-2d7e40bcb5a5") in team)))'


symbols = {}
def ersatz(match):
    symbols[match.group(1).replace('"', '')] = sympy.symbols(match.group(1).replace('"', ''))
    return f'symbols[{match.group(1)}]'

neuer_string = re.sub(r'UUID\((.+?)\)', ersatz, example_1)
neuer_string = neuer_string.replace('in team', '')


print('exp1:', '\n', eval(translate(exp1)), '\n', to_dnf(eval(translate(exp1)), simplify=True, force=True))
print('exp2:', '\n', eval(translate(exp2)), '\n', to_dnf(eval(translate(exp2)), simplify=True, force=True))
print('example_1:', '\n', eval(translate(neuer_string)), '\n', simple := to_dnf(eval(translate(neuer_string)), simplify=True, force=True))

print(f'{simple=}')
print(f'{back_translate(str(simple))=}')
