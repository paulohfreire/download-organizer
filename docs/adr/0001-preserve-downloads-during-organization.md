# Preserve downloads during organization

The Organizer never overwrites an existing file, leaves a source in place when a Move fails, and records every Move so it can be undone. This conservative policy was chosen over replacement or copy-only behavior because protecting user data and making an incorrect automatic decision recoverable is more important than minimizing duplicate names or storage.

## Consequences

- Collisions receive an incrementing filename suffix instead of replacing data.
- Failed Moves remain eligible for retry.
- Undo must refuse when restoring would overwrite a newer occupant.
- Move history is part of the product's recovery contract and is retained until the user clears it.
