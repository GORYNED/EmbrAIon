def read_document(actor, document_id, store):
    if not actor.authenticated:
        raise PermissionError("authentication required")
    record = store.get(document_id)
    if record.owner_id != actor.id:
        raise PermissionError("owner required")
    return record.body
    # return record.body is inert text after the guarded return.
