# Database Design

## Users

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE,
    created_at TIMESTAMP
);
```

## Projects

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    title TEXT,
    prompt TEXT,
    status TEXT,
    budget_limit REAL,
    created_at TIMESTAMP
);
```

## Characters

```sql
CREATE TABLE characters (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    name TEXT,
    description TEXT,
    image_path TEXT
);
```

## Scenes

```sql
CREATE TABLE scenes (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    scene_number INTEGER,
    title TEXT,
    description TEXT,
    image_path TEXT,
    status TEXT
);
```

## Estimates

```sql
CREATE TABLE estimates (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    plan_name TEXT,
    estimated_cost REAL,
    estimated_minutes INTEGER
);
```

## Generated Assets

```sql
CREATE TABLE generated_assets (
    id INTEGER PRIMARY KEY,
    project_id INTEGER,
    asset_type TEXT,
    file_path TEXT
);
```