
![](media/logo.png)


# Desktop App
![](media/app_screenshot.png)

# Web Dashboard
![](media/web_dash.png)


# todo notes
- [ ] Make sure users get tied to clients and tags they create 

# 🚀 Getting Started

This project uses **Poetry** for dependency management and virtual environments, and **Django** as the web framework.

Follow the steps below to get up and running.

---

# 📦 Install Poetry

## Install Poetry (if not installed)

### macOS / Linux / WSL
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### Windows (PowerShell)
```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
```


---

# 🔌 Install Poetry Shell Plugin

Poetry 2+ does **not** include `poetry shell` by default.  
We use it to enter the virtual environment.

```bash
poetry self add poetry-plugin-shell
```


---

# 🐍 Install Project Dependencies

From the project root:

```bash
poetry install
```

This installs all dependencies from `pyproject.toml`.

---

# ⚡ Enter the Virtual Environment

We only use **poetry shell** to activate the environment.

```bash
poetry shell
```

Once inside, you can run Python and Django commands normally:

```bash
python
pip
python manage.py ...
```

To exit:

```bash
exit
```

---

# 🛠 Django Setup

## Run Database Migrations

```bash
python manage.py migrate
```

---

## Create New Migrations (after model changes)

```bash
python manage.py makemigrations
```

Then apply them:

```bash
python manage.py migrate
```

---

## Run Development Server

```bash
python manage.py runserver
```

Default server:

```
http://127.0.0.1:8000
```

---

## Create Superuser (Admin Login)

```bash
python manage.py createsuperuser
```

Admin panel:

```
http://127.0.0.1:8000/admin
```

---

# 📁 Typical First-Time Setup Flow

```bash
poetry install
poetry shell
python manage.py migrate
python manage.py runserver
```

---

# ✅ Environment Rules for This Project

- Always work inside `poetry shell`
- Never run Django outside the virtual environment
- Dependencies must be added through Poetry

Add a package:

```bash
poetry add package_name
```

Dev dependency:

```bash
poetry add -D package_name
```

---

---

# 🖥 Electron Desktop App (VISA Uploader)

This project includes a local **Electron desktop application** used for ingesting file paths into the Django API.

The Electron app is intentionally simple:

- Drag and drop files
- Create a batch
- Send file paths to Django
- Optionally add tags to the batch
- Reset batch session

No files are uploaded — only local file paths.

## 📁 Location

```bash
electron_app/
```

---

# ⚡ Run Electron App (Development)

Open a new terminal and run:

```bash
cd electron_app
npm install
npm start
```

This launches the VISA uploader window.

---

# 🔗 Electron ↔ Django Requirements

The Django server **must be running** before starting the Electron app.

```bash
python manage.py runserver
```

Default API endpoint:

```plaintext
http://127.0.0.1:8000
```

Electron communicates with Django via:

```plaintext
POST /api/batches/ensure/   → create/reset batch
POST /api/media_files/      → send file paths + tags
```

---

# 📦 Electron Dependencies

Electron dependencies are managed separately from Python dependencies.

Install or update:

```bash
cd electron_app
npm install
```

Electron packages are **not managed by Poetry**.

---

# 🧠 Development Notes

- Electron stores the current batch in memory
- Batch resets when the app reloads or reset button is pressed
- Django handles all persistence

