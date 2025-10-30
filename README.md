# 🕸️ Interlinker

**Interlinker** is a lightweight Django web application that improves SEO and user navigation by automatically inserting **internal links** into your blog posts or reviews.  

It works by parsing your website’s **sitemap.xml**, extracting URLs, and matching their slugs against keywords in your content.  
Up to **10 relevant keywords per post** are automatically interlinked.

---

## ✨ Features

- Upload or fetch a `sitemap.xml` (URL or file).
- Extract and store all internal links in a database.
- Normalize slugs (e.g., `cold-wallets` → `cold wallets`) for keyword matching.
- Paste your blog post/review (plain text or HTML).
- Automatically interlink up to **10 keywords** with matching URLs.
- Clean, minimal HTML & CSS frontend using Django templates.
- Admin interface to inspect stored links.

---

## 🚀 Getting Started

### Quick start (Docker + Make)

#### Linux / macOS

1. Install Docker Engine (Linux) or Docker Desktop (macOS) and ensure `make` is available (`brew install make` on macOS if needed).
2. Copy the sample environment file:

   ```bash
   cp .env.example .env
   ```

   Adjust values if you need a non-default port, secret key, or database.

3. Build and start the stack:

   ```bash
   make up
   ```

   On macOS or Linux systems where Docker runs rootless, disable sudo by appending `USE_SUDO=0` (for example `make up USE_SUDO=0`).

4. Open the app at [http://127.0.0.1:8000/](http://127.0.0.1:8000/) and upload a sitemap to begin.

#### Windows

1. Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) and either:
   - Use the bundled Git Bash shell (preferred), or
   - Enable WSL 2 and work from an Ubuntu/WSL prompt.
   If you stay on PowerShell or Command Prompt, install GNU Make (`choco install make`).
2. Copy the sample environment file:

   ```bash
   copy .env.example .env
   ```

   (Use `cp` instead when running inside Git Bash or WSL.)

3. Start the stack (Git Bash / WSL):

   ```bash
   make up USE_SUDO=0
   ```

   PowerShell alternative:

   ```powershell
   mingw32-make up USE_SUDO=0
   ```

4. Visit [http://127.0.0.1:8000/](http://127.0.0.1:8000/) to confirm the app is running.

Useful helpers (all platforms):

- `make logs` to tail container logs.
- `make migrate` to apply database migrations inside the running container.
- `make down` to stop the stack.

### Local development (without Docker)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

The repository also ships with `bin/devserver`, which loads `.env` or `.env.example`, applies migrations, and boots the Django dev server in one command:

```bash
./bin/devserver
```

Windows users should run the script from Git Bash or WSL; if you prefer PowerShell, execute `python manage.py migrate` followed by `python manage.py runserver` instead.

---

## 🧩 Usage

### Upload Sitemap
1. Navigate to **Upload Sitemap**.  
2. Provide a sitemap URL (`https://yoursite.com/sitemap.xml`) or upload a file.  
3. Links are parsed and stored in the database.  

### View Links
- Navigate to **Links** to browse stored links.  
- Search and filter by domain or keyword.  

### Interlink Content
1. Navigate to **Interlink**.  
2. Paste your review/blog post text (plain or HTML).  
3. Choose a domain.  
4. Set a maximum number of links (default = 10).  
5. The app returns:
   - A preview with clickable internal links.  
   - A textarea containing copyable HTML.  

---

## 🛠️ Project Structure

```
interlinker_project/
├── interlinker/                # Django app
│   ├── models.py               # Domain & Link models
│   ├── services.py             # Sitemap parsing & interlinking logic
│   ├── forms.py                # Forms for sitemap & interlinking
│   ├── views.py                # Views for UI
│   ├── templates/interlinker/  # HTML templates
│   └── static/css/style.css    # Basic CSS
├── interlinker_project/        # Project config
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py / asgi.py
└── manage.py
```

---

## ⚙️ Settings

In `settings.py`, ensure you have:

```python
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
```

---

## 🧪 Development Tips

- Debug sitemap fetch issues by checking **HTTP status codes** in `services.py`.
- Some sites block bots — try with your own site or use `https://docs.python.org` for testing.
- Use `make shell` or `docker exec -it interlinker_app /bin/sh` to inspect the running container.
- Run tests with `pytest` (default settings pick up `.env.example` so SQLite is used locally).

---

## ✅ Quality Checks

- Install dev tooling: `pip install -r requirements-dev.txt`
- Run linting: `ruff check`
- Execute tests: `DJANGO_SECRET_KEY=test-secret DJANGO_DEBUG=true pytest`

---

## 🏭 Production Deployment

1. Copy `.env.example` to `.env` and set `DJANGO_SECRET_KEY`, `DATABASE_URL`, and trusted hosts/origins.
2. Build the container: `docker build -t interlinker .`  
   Run locally with Postgres: `docker run --env-file .env -p 8000:8000 interlinker`.
3. The bundled `entrypoint.sh` runs migrations and `collectstatic` on startup; set `SKIP_COLLECTSTATIC=1` if static assets are baked at build time.
4. Deploy to Cloud Run or similar by pushing the image, setting environment variables, and pointing a managed Postgres instance at `DATABASE_URL`.

---

## 📜 License

This project is licensed under the **MIT License** – feel free to use and modify.  

---

## 👨🏾‍💻 Author

Built with ❤️ by **Patrick Mutabazi**.  

---
