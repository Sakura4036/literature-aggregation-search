# Database Setup and Management

This document provides instructions for setting up, deploying, and managing the PostgreSQL database used by the Literature Aggregation Search System.

## 1. Configuration

The database connection is configured through environment variables. The application uses a `.env` file to load these variables during development.

Create a `.env` file in the project root directory and add the following variables:

```env
# .env

# PostgreSQL Database URL
# Format: postgresql+asyncpg://<user>:<password>@<host>:<port>/<dbname>
DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/literature_db"

# Set to true to enable debug mode (e.g., echo SQL statements)
DEBUG=true
```

- **`DATABASE_URL`**: The connection string for your PostgreSQL database.
- **`DEBUG`**: Set to `true` to see detailed logs, including all executed SQL queries.

## 2. Deployment with Docker

For a consistent and isolated development environment, we recommend using Docker and Docker Compose to run the PostgreSQL database.

### `docker-compose.yml`

Here is an example `docker-compose.yml` file to set up a PostgreSQL service:

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres_db:
    image: postgres:15-alpine
    container_name: literature_postgres
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: literature_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
    driver: local
```

### Steps to Deploy:

1.  **Install Docker and Docker Compose**: Ensure you have both installed on your system.
2.  **Save the `docker-compose.yml`**: Place the content above into a `docker-compose.yml` file in the project root.
3.  **Start the container**: Run the following command in your terminal:
    ```bash
    docker-compose up -d
    ```
4.  **Verify**: Check if the container is running:
    ```bash
    docker-compose ps
    ```

The database will now be running and accessible at `localhost:5432`.

## 3. Database Initialization

### Automatic Initialization

The FastAPI application is configured to automatically initialize the database when it starts up. The `lifespan` event handler in `src/api/main.py` calls the `init_database()` function.

This function connects to the database and creates all the tables defined in `src/database/models.py` if they do not already exist.

**To initialize the database, simply run the application:**

```bash
uvicorn src.api.main:app --reload
```

The server will start, and you should see a log message indicating that the database tables were created successfully.

### Manual Initialization (Optional)

If you need to create or reset the database schema manually, you can use the provided command-line script.

1.  **Create the database (if not already done)**:
    You can use a tool like `psql` or any other database client to create the database specified in your `.env` file.

2.  **Run the initialization script**:
    *A script for this will be provided in `scripts/cli.py` in a future update.* For now, the automatic initialization is the recommended approach.

## 4. Database Migrations

For managing changes to the database schema over time, we recommend using a migration tool like **Alembic**.

While not yet integrated, setting up Alembic would involve:
1.  Initializing Alembic in the project.
2.  Configuring it to use the application's database models and connection settings.
3.  Generating migration scripts for schema changes.
4.  Applying migrations to update the database.

This will be added in a future update to the project.
