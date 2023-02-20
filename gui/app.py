import tkinter as tk
import customtkinter as ctk

# create_project_and_team('SaniClowns', 'Stuttgart')

ctk.set_appearance_mode('dark')


class MyMenuButton(tk.Menubutton):
    def __init__(self, parent, text: str):
        super().__init__(master=parent, text=text)
        self.config(background=parent['background'], foreground='white',
                    activebackground='#404040', activeforeground='white')
        self.menu = tk.Menu(self, tearoff=False, background='#404040', foreground='white', activebackground='#333333')
        self['menu'] = self.menu


class MainMenu(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(master=parent)

        self.file = MyMenuButton(self, text='File')
        self.file.grid(row=0, column=0, sticky='w')
        self.file.menu.add_command(label='option 1', command=lambda: print('file 1'))
        self.file.menu.add_command(label='option 2', command=lambda: print('file 2'))

        self.edit = MyMenuButton(self, text='Edit')
        self.edit.grid(row=0, column=1, sticky='w')
        self.edit.menu.add_command(label='option 1', command=lambda: print('edit 1'))
        self.edit.menu.add_command(label='option 2', command=lambda: print('edit 2'))

        self.help = MyMenuButton(self, text='Help')
        self.help.grid(row=0, column=2, sticky='e')
        self.help.menu.add_command(label='About', command=lambda: print('About...'))


class ToplevelWindow(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geometry("400x300")
        self.focus_set()
        self.grab_set()

        self.label = ctk.CTkLabel(self, text="ToplevelWindow")
        self.label.pack(padx=20, pady=20)


class App(ctk.CTk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geometry("500x400")

        # self.menu = MainMenu(self)
        self.menu = MainMenu(self)
        self.menu.pack(side='top', fill='x')

        self.button_1 = ctk.CTkButton(self, text="open toplevel", command=self.open_toplevel)
        self.button_1.pack(side="top", padx=20, pady=20)

        self.toplevel_window = None

    def open_toplevel(self):
        if self.toplevel_window is None or not self.toplevel_window.winfo_exists():
            self.toplevel_window = ToplevelWindow(self)  # create window if its None or destroyed
        else:
            self.toplevel_window.focus()  # if window exists focus it


def show_gui():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    show_gui()
