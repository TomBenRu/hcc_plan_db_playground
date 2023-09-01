import itertools
from string import ascii_lowercase
from uuid import UUID
import re

import sympy
from sympy.logic.boolalg import to_dnf, BooleanFunction
from sympy.abc import a, b, c, d


def translate(expr: str) -> str:
    return expr.replace('not ', '~ ').replace('and ', '& ').replace('or ', '| ')


def back_translate(expr: str) -> str:

    expr = expr.replace('(', '( ').replace(')', ' )')
    exclude = {'~': ' not ', '&': ' and ', '|': ' or ', '(': '(', ')': ')'}
    expr_list = expr.split(' ')

    # alleinstehende ID-Strings werden mit Klammern versehen
    expr_list_corr = []
    for i, val in enumerate(expr_list):
        if val in symbols and (i == 0 or (expr_list[i-1] != '(' and expr_list[i+1 != ')'])):
            expr_list_corr.extend(['(', val, ')'])
        else:
            expr_list_corr.append(val)

    expr_list_res = [f'(UUID("{x}") in team)' if x not in exclude else exclude[x] for x in expr_list_corr]
    return '(' + ''.join(expr_list_res) + ')'


exp1 = '(not ((b or not c) and (not a or not c))) or (not (c or not (b and c))) or (a and not c) and (not a or (a and b and c) or (a and ((b and not c) or (not b))))'
exp2 = '(not (a and not b) or (not c and b)) and (not b) or (not a and b and not c) or (a and not b)'

example_1 = '(((UUID("2ce4ed15-0212-442f-ab0b-73f8940ad217") in team) and (UUID("52521e7f-b7ef-4189-bdd0-bf109c0bbc45") in team)) or ((UUID("d83be6e6-e2a4-44e5-8a3b-2d7e40bcb5a5") in team)) or ((UUID("e86bcadd-bb3a-4fcd-950e-9f5179abbc10") in team)))'

symbols = {}


def fixed_cast_to_logical_sentence(fixed_cast: str) -> str:
    def ersatz(match):
        symbols[match.group(1).replace('"', '')] = sympy.symbols(match.group(1).replace('"', ''))
        return f'symbols[{match.group(1)}]'

    neuer_string = re.sub(r'UUID\((.+?)\)', ersatz, fixed_cast)
    neuer_string = neuer_string.replace('in team', '')

    return neuer_string


def find_min_nr_actors(all_person_ids: set[UUID], fixed_cast: str):
    for n in range(1, len(all_person_ids) + 1):
        for comb in itertools.combinations(all_person_ids, n):
            if eval(fixed_cast, {'team': comb, 'UUID': UUID}):
                return n


print('exp1:', '\n', eval(translate(exp1)), '\n', to_dnf(eval(translate(exp1)), simplify=True, force=True))
print('exp2:', '\n', eval(translate(exp2)), '\n', to_dnf(eval(translate(exp2)), simplify=True, force=True))
print('example_1:', '\n', eval(translate(fixed_cast_to_logical_sentence(example_1))), '\n', simple := to_dnf(eval(translate(fixed_cast_to_logical_sentence(example_1))), simplify=True, force=True))

print(f'{simple=}')
simplified_fixed_cast = back_translate(str(simple))
print(f'{simplified_fixed_cast=}')
print(f'{find_min_nr_actors({UUID(x) for x in symbols}, simplified_fixed_cast)=}')


class SimplifyFixedCastAndInfo:
    def __init__(self, fixed_cast: str):
        self.fixed_cast = fixed_cast
        self.simplified_fixed_cast: str = ''
        self.min_nr_actors: int = 0
        self.symbols = {}
        self.simplify()
        self.find_min_nr_actors()

    def fixed_cast_to_logical_sentence(self) -> str:
        def replacement(match):
            self.symbols[match.group(1).replace('"', '')] = sympy.symbols(match.group(1).replace('"', ''))
            return f'symbols[{match.group(1)}]'

        new_string = re.sub(r'UUID\((.+?)\)', replacement, self.fixed_cast)
        new_string = new_string.replace('in team', '')
        new_string = new_string.replace('not ', '~ ').replace('and ', '& ').replace('or ', '| ')

        return new_string

    def simplify_to_boolean_function(self, sentence: str) -> BooleanFunction:
        return to_dnf(eval(sentence, {'symbols': self.symbols}), simplify=True, force=True)

    def back_translate_to_fixed_cast(self, expr: BooleanFunction) -> str:
        expr_str = str(expr).replace('(', '( ').replace(')', ' )')
        exclude = {'~': ' not ', '&': ' and ', '|': ' or ', '(': '(', ')': ')'}
        expr_str_list = expr_str.split(' ')

        # alleinstehende ID-Strings werden mit Klammern versehen
        expr_str_list_corr = []
        for i, val in enumerate(expr_str_list):
            if val in self.symbols and (i == 0 or (expr_str_list[i - 1] != '(' and expr_str_list[i + 1 != ')'])):
                expr_str_list_corr.extend(['(', val, ')'])
            else:
                expr_str_list_corr.append(val)

        expr_str_list_res = [f'(UUID("{x}") in team)' if x not in exclude else exclude[x] for x in expr_str_list_corr]
        return '(' + ''.join(expr_str_list_res) + ')'

    def simplify(self):
        logical_sentence = self.fixed_cast_to_logical_sentence()
        simplified_boolean_function = self.simplify_to_boolean_function(logical_sentence)
        self.simplified_fixed_cast = self.back_translate_to_fixed_cast(simplified_boolean_function)

    def find_min_nr_actors(self):
        all_person_ids = {UUID(x) for x in self.symbols}
        for n in range(1, len(all_person_ids) + 1):
            for comb in itertools.combinations(all_person_ids, n):
                if eval(self.simplified_fixed_cast, {'team': comb, 'UUID': UUID}):
                    self.min_nr_actors = n
                    return


simplifier = SimplifyFixedCastAndInfo(example_1)
print(f'{simplifier.simplified_fixed_cast=}')
print(f'{simplifier.min_nr_actors=}')


