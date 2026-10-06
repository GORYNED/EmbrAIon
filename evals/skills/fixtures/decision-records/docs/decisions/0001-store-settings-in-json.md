# 0001: Store settings in a JSON file

- Status: Accepted
- Date: 2026-01-12
- Supersedes: None
- Superseded by: None

## Context

The service has about twenty settings, edited by hand during support sessions.

## Decision

Settings are stored as JSON in `settings.json` next to the executable, read at start and written on change.

## Consequences

Support staff can edit settings with any text editor. Concurrent writers are not handled.

## Alternatives considered

- SQLite: more robust, but settings could not be edited by hand.
- Environment variables: no place to persist changes made in the app.
