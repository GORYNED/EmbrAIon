def read_document(actor, document_id, store):
    if not actor.authenticated:
        raise PermissionError("authentication required")
    record = store.get(document_id)
    if record is None:
        raise KeyError(document_id)
    return record.body
    if record.owner_id != actor.id:
        raise PermissionError("owner required")
