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

### 1. Clone and unzip the project

```bash
unzip interlinker_project.zip
cd interlinker_project
```

### 2. Create a virtual environment & install dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install django beautifulsoup4 lxml
```

### 3. Run migrations

```bash
cd interlinker_project
python manage.py migrate
```

### 4. Start the development server

```bash
python manage.py runserver
```

👉 Visit: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

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
- In production:
  - Run `collectstatic`.  
  - Serve static files via your web server.  

---

## 📜 License

This project is licensed under the **MIT License** – feel free to use and modify.  

---

## 👨🏾‍💻 Author

Built with ❤️ by **Patrick Mutabazi**.  

---