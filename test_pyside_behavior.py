
from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt

app = QApplication([])

list_widget = QListWidget()

original_data = {"id": 1, "name": "Original"}
item = QListWidgetItem("Test Item")
item.setData(Qt.ItemDataRole.UserRole, original_data)
list_widget.addItem(item)

# Retrieve data
retrieved_data = item.data(Qt.ItemDataRole.UserRole)

print(f"Original ID: {id(original_data)}")
print(f"Retrieved ID: {id(retrieved_data)}")

# Modify retrieved
retrieved_data["name"] = "Modified"

# Check original
print(f"Original Name after modification: {original_data['name']}")

if original_data['name'] == "Modified":
    print("It is a REFERENCE (Updates work)")
else:
    print("It is a COPY (Updates FAIL)")
