-- Initialize database schema for Arbetsytan

CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR,
    classification VARCHAR NOT NULL DEFAULT 'normal',
    due_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add due_date, description, and tags columns if they don't exist (idempotent)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='projects' AND column_name='status') THEN
        ALTER TABLE projects ADD COLUMN status VARCHAR NOT NULL DEFAULT 'research';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='projects' AND column_name='due_date') THEN
        ALTER TABLE projects ADD COLUMN due_date TIMESTAMP WITH TIME ZONE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='projects' AND column_name='description') THEN
        ALTER TABLE projects ADD COLUMN description TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='projects' AND column_name='tags') THEN
        ALTER TABLE projects ADD COLUMN tags JSONB DEFAULT '[]'::jsonb;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS project_events (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    event_type VARCHAR NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    actor VARCHAR,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_project_events_project_id ON project_events(project_id);
CREATE INDEX IF NOT EXISTS idx_project_events_timestamp ON project_events(timestamp DESC);

-- Add new columns to documents table (idempotent)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='documents' AND column_name='sanitize_level') THEN
        ALTER TABLE documents ADD COLUMN sanitize_level VARCHAR DEFAULT 'normal';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='documents' AND column_name='usage_restrictions') THEN
        ALTER TABLE documents ADD COLUMN usage_restrictions JSONB DEFAULT '{"ai_allowed": true, "export_allowed": true}';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='documents' AND column_name='pii_gate_reasons') THEN
        ALTER TABLE documents ADD COLUMN pii_gate_reasons JSONB;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='documents' AND column_name='metadata') THEN
        ALTER TABLE documents ADD COLUMN metadata JSONB;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='documents' AND column_name='document_metadata') THEN
        ALTER TABLE documents ADD COLUMN document_metadata JSONB;
    END IF;
END $$;

-- Add url column to project_sources (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='project_sources' AND column_name='url') THEN
        ALTER TABLE project_sources ADD COLUMN url TEXT;
    END IF;
END $$;

-- Add usage_restrictions to project_notes (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='project_notes' AND column_name='usage_restrictions') THEN
        ALTER TABLE project_notes ADD COLUMN usage_restrictions JSONB DEFAULT '{"ai_allowed": true, "export_allowed": true}';
    END IF;
END $$;

