import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData


@pytest.fixture(scope="session")
def test_person():
    """Fixture to create test person objects"""
    class TestPerson:
        def __init__(self, person_id: int, name: str):
            self.id = person_id
            self.name = name

        def __eq__(self, other):
            if isinstance(other, TestPerson):
                return self.id == other.id
            return False
    
    return TestPerson


@pytest.fixture(scope="session")
def app():
    """Create a QApplication instance once for the entire test session"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def combo_box(app, test_person):
    """Create a fresh QComboBox for each test"""
    combo = QComboBoxToFindData()
    combo.addItem('Person 1', test_person(1, 'John'))
    combo.addItem('Number', 42)
    combo.addItem('Person 2', test_person(2, 'Jane'))
    combo.addItem('Text', 'hello')
    return combo


def test_find_data_with_custom_object(combo_box, test_person):
    # Test finding a person by equality
    search_person = test_person(1, 'Different Name')  # Name different but same ID
    index = combo_box.findData(search_person)
    assert index == 0  # Should find at index 0

    # Test person not in combo box
    not_found_person = test_person(99, 'Not Found')
    index = combo_box.findData(not_found_person)
    assert index == -1


def test_find_data_with_primitive_types(combo_box):
    # Test finding number
    index = combo_box.findData(42)
    assert index == 1

    # Test finding string
    index = combo_box.findData('hello')
    assert index == 3

    # Test value not in combo box
    index = combo_box.findData('not found')
    assert index == -1


def test_find_data_with_different_role(combo_box, test_person):
    # Test with different role (should not find anything)
    index = combo_box.findData(test_person(1, 'John'), Qt.ItemDataRole.DisplayRole)
    assert index == -1


def test_find_data_in_empty_combo_box(app, test_person):
    empty_combo = QComboBoxToFindData()
    index = empty_combo.findData(test_person(1, 'John'))
    assert index == -1
