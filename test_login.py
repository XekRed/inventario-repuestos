from ui.login import LoginWindow
from database.inventario_db import inicializar_db
import customtkinter as ctk

inicializar_db()

app = ctk.CTk()
app.withdraw()

login = LoginWindow(app)
print("Waiting for login...")
app.wait_window(login)
print(f"Login result: {login.result}")
app.destroy()
