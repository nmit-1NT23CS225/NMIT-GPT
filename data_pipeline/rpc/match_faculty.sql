create or replace function match_faculty_chunks (
    query_embedding vector(768),
    match_count int default 5
)
returns table (
    faculty_id text,
    chunk_id int,
    chunk_text text,
    distance float,
    metadata jsonb
)
language plpgsql
as $$
begin
    return query
    select
        faculty_id,
        chunk_id,
        chunk_text,
        embedding <-> query_embedding as distance,
        metadata
    from faculty_biodata_embeddings
    order by embedding <-> query_embedding
    limit match_count;
end;
$$;
