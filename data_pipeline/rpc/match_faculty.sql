create function match_faculty_chunks (
    query_embedding vector(768),
    match_count int default 5
)
returns table (
    faculty_id text,
    chunk_type text,
    chunk_index int,
    chunk_text text,
    similarity float,
    metadata jsonb
)
language sql
as $$
    select
        source_id as faculty_id,
        chunk_type,
        chunk_index,
        raw_text as chunk_text,
        1 - (embedding <=> query_embedding) as similarity,
        metadata
    from unified_embeddings
    where source_type = 'faculty_biodata'
    order by embedding <=> query_embedding
    limit match_count;
$$;
