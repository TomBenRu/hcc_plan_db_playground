import tkinter as tk
from tkinter import ttk
from uuid import UUID

# Form: 1 and (2 or 3 or 4), (1 or 2) and (3 or 4), (1 and 2) or (3 and 4)

bes1, bes2, bes3 = [1, 2], [3, 4], [2, 3]
eval_str1 = '(1 and 2) or (3 and 4)'
eval_str2 = '(1 or 2) and (3 or 4)'
eval_str3 = '1 and (2 or 3 or 4)'
team = bes3


root = tk.Tk()
expr_str = ''
last_input_operator = True
last_teilbed_input_operator = True
teilbed = 0


def add2string(value: str, operator=False):
    global last_input_operator, last_teilbed_input_operator, teilbed
    if teilbed:
        if operator == last_teilbed_input_operator:
            return
        entry_loc = entry_tmp
    else:
        if operator == last_input_operator:
            return
        entry_loc = entry_main

    if not operator:
        entry_loc.insert('end', f'({value} in team) ')
        if teilbed:
            last_teilbed_input_operator = False
        else:
            last_input_operator = False
    else:
        entry_loc.insert('end', f'{value} ')
        if teilbed:
            last_teilbed_input_operator = True
        else:
            last_input_operator = True


def goto_teilbed():
    global teilbed, last_teilbed_input_operator, last_input_operator
    if teilbed == 0 and not last_input_operator:
        return
    teilbed = (teilbed + 1) % 2
    if teilbed == 0:
        bt_teilbed['text'] = 'Teilbedingung'
        entry_main.insert('end', f'({entry_tmp.get().strip()}) ')
        entry_main['bg'] = 'white'
        entry_tmp['bg'] = 'grey'
        entry_tmp.delete(0, 'end')
        last_teilbed_input_operator = True
        last_input_operator = False
    else:
        entry_main['bg'] = 'grey'
        entry_tmp['bg'] = 'white'
        bt_teilbed['text'] = 'Teilbed. einfügen'


def make_teilbed():
    global teilbed, last_teilbed_input_operator, last_input_operator
    if teilbed == 0:
        if last_input_operator:
            return
        expr = entry_main.get().strip()
        entry_main.delete(0, 'end')
        entry_main.insert(0, f'({expr}) ')
    if teilbed == 1:
        if last_teilbed_input_operator:
            return
        expr = entry_tmp.get().strip()
        entry_tmp.delete(0, 'end')
        entry_tmp.insert(0, f'({expr}) ')


def reset():
    global teilbed, last_teilbed_input_operator, last_input_operator
    teilbed = 0
    last_teilbed_input_operator = True
    last_input_operator = True
    entry_main.delete(0, 'end')


def evaluate():
    print(eval(entry_main.get()))


mainframe = ttk.Frame(root, padding='0 0 0 0')
mainframe.pack()
frame_vars = ttk.Frame(mainframe, padding='10 10 10 10')
frame_vars.grid(row=0, column=0)
frame_operators = ttk.Frame(mainframe, padding='10 10 10 10')
frame_operators.grid(row=0, column=1)
frame_buttons = ttk.Frame(root, padding='10 10 10 10')
frame_buttons.pack()
frame_entrys = ttk.Frame(root, padding='10 10 10 10')
frame_entrys.pack()

variables = '123456789'

for i, v in enumerate(list(variables)):
    button = tk.Button(frame_vars, text=v, command=lambda val=v: add2string(value=val))
    button.grid(row=i // 3, column=i % 3, padx=5, pady=5)

bt_and = tk.Button(frame_operators, text='and', command=lambda: add2string(value='and', operator=True))
bt_and.pack(padx=5, pady=5)
bt_or = tk.Button(frame_operators, text='or', command=lambda: add2string(value='or', operator=True))
bt_or.pack(padx=5, pady=5)
lb_entry_tmp = tk.Label(frame_entrys, text='Unterbedingung:')
lb_entry_tmp.pack(pady=(0, 5))
entry_tmp = tk.Entry(frame_entrys, width=100, bg='grey')
entry_tmp.pack()
lb_entry_main = tk.Label(frame_entrys, text='Bedingung:')
lb_entry_main.pack(pady=(0, 5))
entry_main = tk.Entry(frame_entrys, width=100)
entry_main.pack()
bt_make_teilbed = tk.Button(frame_buttons, text='make Teilbed.', command=lambda: make_teilbed())
bt_make_teilbed.grid(row=0, column=0)
bt_teilbed = tk.Button(frame_buttons, text='Teilbedingung', command=lambda: goto_teilbed())
bt_teilbed.grid(row=0, column=1)
bt_del = tk.Button(frame_buttons, text='delete', command=reset)
bt_del.grid(row=0, column=2)
bt_eval = tk.Button(root, text='evaluate', command=evaluate)
bt_eval.pack(pady=10)


def transf_to_form(raw_form: tuple):
    form = []
    for val in raw_form:
        if type(val) == int:
            form.append([val])
        elif type(val) == str:
            form.append(val)
        else:
            form.append(list(val))
    return form


def back_translate(eval_str: str):
    e_s = eval_str.replace('and', ',"and",')
    e_s = e_s.replace('or', ',"or",')
    e_s = e_s.replace('in team', '')
    e_s = eval(e_s)
    return transf_to_form(e_s)


eval_str = '((1 in team) and (5 in team)) or ((2 in team) and (4 in team))'
eval_str = '((UUID("635a8539-518f-4156-af6c-97adfec2b0dd") in team)) or ((UUID("635A8539518F4156AF6C97ADFEC2B0DD") in team) and (UUID("635A8539518F4156AF6C97ADFEC2B0DD") in team))'
eval_str = '((2 in team) and (3 in team)) or (6 in team) or ((5 in team) and (4 in team)) '
# e_s = eval_str.replace('and', ',"and",')
# e_s = e_s.replace('or', ',"or",')
# e_s = e_s.replace('in team', '')
# print(e_s)
# print(eval(e_s))

print(back_translate(eval_str))

root.mainloop()
