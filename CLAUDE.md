# hcc plan — Projektkonventionen

## Web-API: Design-System (Tailwind CSS)

### Dark-Mode-Strategie

Das Projekt nutzt **class-basiertes Dark-Mode** (`[data-theme="dark"]` auf `<html>`).
Tailwind's `dark:` Prefix ist aktiviert und muss bei **allen** Hintergrund-, Text- und Border-Farben gesetzt werden.

**Pflicht-Paare:**

| Light                  | Dark                          | Verwendung                     |
|------------------------|-------------------------------|-------------------------------|
| `bg-white`             | `dark:bg-slate-800`           | Karten, Panels                |
| `bg-slate-50`          | `dark:bg-slate-900`           | Seiten-Hintergrund            |
| `bg-slate-50/50`       | `dark:bg-slate-900/40`        | Subtile Zeilen-Hinterlegung   |
| `text-slate-800`       | `dark:text-slate-100`         | Primärer Text                 |
| `text-slate-600`       | `dark:text-slate-300`         | Sekundärer Text               |
| `text-slate-400`       | `dark:text-slate-500`         | Tertiärer / Meta-Text         |
| `border-slate-100`     | `dark:border-slate-700/50`    | Subtile Ränder                |
| `border-slate-200`     | `dark:border-slate-700`       | Standard-Ränder               |
| `hover:bg-slate-50`    | `dark:hover:bg-slate-700/50`  | Hover-Zustände                |
| `shadow-sm`            | (kein dark: nötig)            | Box-Shadows sind neutral      |

### Typografie

- **Headlines / Display**: `font-display` (Fraunces), `font-semibold` oder `font-light`
- **Fließtext / Labels**: `font-sans` (Inter)
- **Seiten-Titel** (Sidebar): `text-2xl font-semibold`, Farbe `text-white`
- **Abschnitt-Label** über Titel: `text-xs font-semibold tracking-widest uppercase`, Farbe je Kontext

### Sidebar-Layout (Standard-Pattern für Listenseiten)

```html
<div class="h-[calc(100vh-56px)] flex flex-col overflow-hidden">
  <div class="page-wrapper flex-1 grid overflow-hidden"
       style="grid-template-columns: 240px 1fr;">

    <aside class="bg-navy grid-bg flex flex-col p-6 border-r border-white/5
                  overflow-y-auto sidebar-scroll animate-fade-up">
      <!-- Brand-Header: roter Dot + Label + Fraunces-Titel -->
      <!-- Divider: border-t border-white/5 -->
      <!-- Filter-Buttons (sidebar-filters) -->
      <!-- flex-1 Spacer -->
      <!-- Back-Link: /dashboard -->
    </aside>

    <main class="flex-1 overflow-y-auto content-scroll
                 bg-slate-50 dark:bg-slate-900 px-6 py-8">
      <div class="max-w-2xl mx-auto"> ... </div>
    </main>

  </div>
</div>
```

**Responsive Collapse** (<1024px): Sidebar wird zur horizontalen Leiste, Filter klappbar.
Immer die CSS-Klassen aus dem Referenz-Template (`cancellations/index.html`) übernehmen.

### Sidebar-Filter-Buttons

```html
<a href="?filter=wert"
   class="filter-btn flex items-center gap-2.5 w-full px-3 py-2 rounded-lg border
          border-transparent text-sm font-sans text-slate-400
          {% if aktiv %}active{% endif %}">
    <span class="w-2 h-2 rounded-full flex-shrink-0 bg-amber-400"></span>
    Label
</a>
```

Farben der Status-Dots: Offen `bg-amber-400` · Zurückgezogen `bg-slate-400` · Gelöst `bg-green-400`

### Karten (Cards)

```html
<div class="bg-white dark:bg-slate-800 rounded-xl border
            border-slate-100 dark:border-slate-700/50 shadow-sm
            hover:shadow-md hover:border-slate-200 dark:hover:border-slate-600
            transition-all duration-200 overflow-hidden">
```

Linker Farb-Streifen je Status:
```html
<div class="w-1 flex-shrink-0" style="background-color: {{ status_color }};"></div>
```

### Badges / Status-Chips

```html
<span class="text-[10px] font-medium px-2 py-0.5 rounded-full ring-1
             bg-amber-50 text-amber-700 ring-amber-200">
    Offen
</span>
```

Dark-Mode für Badges: eigene `dark:` Varianten mitgeben, z. B. `dark:bg-amber-900/30 dark:text-amber-400 dark:ring-amber-700/50`.

### HTMX-Interaktionen

- **Gelesen-Markierung / DOM-Update nach Request**: immer `hx-on::after-request` statt `onclick` verwenden.  
  `onclick` + `this.remove()` verhindert den HTMX-Request, weil HTMX `document.contains(element)` prüft, bevor es den Request abschickt.
- **Fehler-Feedback**: bei Formular-Submits `hx-target` auf ein Ergebnis-Div setzen, nicht auf `body`.

### Farbpalette (CSS-Variablen)

| Variable      | Wert (Light)   | Bedeutung                  |
|---------------|----------------|---------------------------|
| `--navy`      | `#0F1B2D`      | Sidebar-Hintergrund       |
| `--brand`     | Primärfarbe    | Akzentfarbe (Dot, Links)  |

Im CSS erreichbar als `bg-navy`, `text-brand`, `bg-brand`.

### Animations-Pattern

```html
<div class="anim" style="animation-delay: 0.05s;">...</div>
```

`@keyframes fadeUp` mit `opacity 0→1` + `translateY(10px)→0` in `0.35s ease-out`.

---

## Web-API: Backend-Konventionen

### SQLAlchemy / SQLModel Session

- `session.exec(sa_select(...))` ist **falsch** — liefert Row-Tuples statt ORM-Instanzen.
- Korrekt: `session.execute(sa_select(...)).scalars().all()` bzw. `.scalars().first()`.
- `session.exec(sqlmodel_select(...))` ist korrekt für SQLModel's eigenes `select()`.

### FastAPI Dependencies

`LoggedInUser = Annotated[WebUser, Depends(require_login)]` — kein Default-Wert setzen:
```python
# Richtig:
def endpoint(user: LoggedInUser, session: Session = Depends(get_db_session)):
# Falsch (Default wird ignoriert, aber verwirrend):
def endpoint(user: LoggedInUser = LoggedInUser, ...):
```

### Logout / Redirects

HTMX-Requests folgen 3xx-Redirects nicht browserbreit.  
Logout: `RedirectResponse(url="/auth/login", status_code=303)` mit `response.delete_cookie(...)`.