"""Consumer code passes semantic task classes to EmbrAIon."""

from embraion.runtime import resolve_task_route


def effective_route(task_class: str, project):
    return resolve_task_route(task_class, project=project)
