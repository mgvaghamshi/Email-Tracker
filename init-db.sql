-- EmailTracker Database Initialization Script
-- This script runs when the PostgreSQL container first starts

-- Create the main database (already created by POSTGRES_DB)
-- CREATE DATABASE email_tracker;

-- Connect to the email_tracker database
\c email_tracker;

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create indexes for better performance (tables will be created by SQLAlchemy)
-- These will be created after the app initializes the database

-- Set default timezone
SET timezone = 'UTC';

-- Create a function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Grant privileges to the postgres user (default setup)
GRANT ALL PRIVILEGES ON DATABASE email_tracker TO postgres;

-- Print initialization complete message
\echo 'EmailTracker database initialization completed successfully!'
