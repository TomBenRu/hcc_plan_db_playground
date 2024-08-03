from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QApplication, QVBoxLayout, QPushButton, QWidget
from PySide6.QtCore import Qt


class MyTreeWidget(QTreeWidget):
    def dropEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item and isinstance(item.data(0, Qt.UserRole), Person):
            event.ignore()
        else:
            super().dropEvent(event)
            
            # Erweitert alle Elemente im Baum
            self.expandAll()

            # Passt die Breite der Spalten an
            self.resizeColumnToContents(0)
            self.resizeColumnToContents(1)


class Group:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f'{self.__class__.__name__}, {self.name}'


class Person:
    def __init__(self, name: str, age: int):
        self.name = name
        self.age = age

    def __repr__(self):
        return f'{self.__class__.__name__}, {self.name}'


def expand_tree():
    # Erweitert alle Elemente im Baum
    tree.expandAll()

    # Passt die Breite der Spalten an
    tree.resizeColumnToContents(0)
    tree.resizeColumnToContents(1)


app = QApplication()

tree = MyTreeWidget()
tree.setColumnCount(2)
tree.setHeaderLabels(["Name", "Age"])
tree.setDragDropMode(QTreeWidget.InternalMove)

# Fügt dem Baum einige Objekte
group_1 = Group('group_01')
group_2 = Group('group_02')

person_1 = Person("Thomas", 61)
person_2 = Person('Giuliano', 16)
person_3 = Person('Fred', 56)
person_4 = Person('Bernd', 33)

parent = QTreeWidgetItem(tree, [group_1.name])
parent.setData(0, Qt.UserRole, group_1)

item = QTreeWidgetItem(parent, [person_1.name, str(person_1.age)])
item.setData(0, Qt.UserRole, person_1)

item = QTreeWidgetItem(parent, [person_2.name, str(person_2.age)])
item.setData(0, Qt.UserRole, person_2)

parent = QTreeWidgetItem(tree, [group_2.name])
parent.setData(0, Qt.UserRole, group_2)

item = QTreeWidgetItem(parent, [person_3.name, str(person_3.age)])
item.setData(0, Qt.UserRole, person_3)

item = QTreeWidgetItem(parent, [person_4.name, str(person_4.age)])
item.setData(0, Qt.UserRole, person_4)

expand_tree()

# Verbindet das itemClicked-Signal mit einer Funktion
def on_item_clicked(item):
    my_object = item.data(0, Qt.UserRole)
    print(f"Clicked on {my_object}")

tree.itemClicked.connect(on_item_clicked)

# Erstellt einen Button zum Hinzufügen eines neuen Elements
button_add = QPushButton("Add Group")
button_add.clicked.connect(lambda: add_group(tree))
button_tree_to_dict = QPushButton('to dict')
button_tree_to_dict.clicked.connect(lambda: tree_to_dict(tree))
button_remove_selected_item = QPushButton('Remove Item')
button_remove_selected_item.clicked.connect(lambda: remove_selected_item(tree))

def add_group(tree):
    group_names = [item.data(0, Qt.UserRole).name for item in get_groups(tree)]
    indexes = [int(name.split('_')[-1]) for name in group_names]
    new_index = max(indexes) + 1 if indexes else 1
    new_name = f'group_{new_index:02}'

    new_group = Group(new_name)
    new_item = QTreeWidgetItem(tree.invisibleRootItem(), [new_group.name])
    new_item.setData(0, Qt.UserRole, new_group)

    expand_tree()


def remove_selected_item(tree):
    selected_items = tree.selectedItems()
    if not selected_items:
        return
    selected_item = selected_items[0]
    if selected_item.childCount() == 0:
        parent = selected_item.parent()
        if parent:
            parent.removeChild(selected_item)
        else:
            index = tree.indexOfTopLevelItem(selected_item)
            tree.takeTopLevelItem(index)


def tree_to_dict(tree):
    def add_children(item):
        children = []
        for i in range(item.childCount()):
            child = item.child(i)
            children.append({
                "object": child.data(0, Qt.UserRole),
                "children": add_children(child)
            })
        return children

    root = tree.invisibleRootItem()
    data = []
    for i in range(root.childCount()):
        item = root.child(i)
        data.append({
            "object": item.data(0, Qt.UserRole),
            "children": add_children(item)
        })
    print(data)

    dict_to_tree(tree, data)
    expand_tree()

    return data


def dict_to_tree(tree, data):
    #data = [{'object': group_1, 'children': [{'object': person_1, 'children': []}, {'object': person_2, 'children': []}, {'object': group_2, 'children': [{'object': person_3, 'children': []}, {'object': person_4, 'children': []}]}]}]
    def add_children(parent, children):
        for child in children:
            item = QTreeWidgetItem(parent, [child["object"].name, str(getattr(child["object"], "age", ""))])
            item.setData(0, Qt.UserRole, child["object"])
            add_children(item, child["children"])

    tree.clear()
    for item in data:
        parent = QTreeWidgetItem(tree, [item["object"].name])
        parent.setData(0, Qt.UserRole, item["object"])
        add_children(parent, item["children"])


def get_groups(tree):
    groups = []
    def traverse(item):
        if isinstance(item.data(0, Qt.UserRole), Group):
            groups.append(item)
        for i in range(item.childCount()):
            traverse(item.child(i))
    root = tree.invisibleRootItem()
    for i in range(root.childCount()):
        traverse(root.child(i))
    return groups



window = QWidget()
layout = QVBoxLayout(window)
layout.addWidget(tree)
layout.addWidget(button_add)
layout.addWidget(button_tree_to_dict)
layout.addWidget(button_remove_selected_item)
window.show()

app.exec()
