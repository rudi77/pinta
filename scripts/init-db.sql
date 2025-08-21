-- Database initialization script for PostgreSQL
-- This script is run when the Docker container starts

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Set timezone
SET timezone = 'Europe/Berlin';

-- Create database if running in development
-- (In production, database should already exist)
-- Uncomment for development setup:
-- CREATE DATABASE maler_kostenvoranschlag_dev;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialization completed successfully';
END $$;