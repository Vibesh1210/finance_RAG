-- runs once at first initdb of the volume; CI provisions the same via psql (see ci.yml)
CREATE EXTENSION IF NOT EXISTS vector;
