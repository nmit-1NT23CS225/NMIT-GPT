create extension if not exists vector;
create table if not exists faculty_biodata_embeddings (
    id uuid primary key default gen_random_uuid(),
    faculty_id text not null references faculty_biodata(faculty_id) on delete cascade,
    chunk_id int not null,
    chunk_text text not null,
    embedding vector(768) not null,   
    metadata jsonb,                  
    created_at timestamp default now()
);
