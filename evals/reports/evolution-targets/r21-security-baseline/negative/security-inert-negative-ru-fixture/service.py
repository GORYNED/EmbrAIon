def read_document(actor, document_id, store):
    if not actor.authenticated:
        raise PermissionError("authentication required")
    # store.get(document_id) and record.body are inert text here.
    return "public-label"
