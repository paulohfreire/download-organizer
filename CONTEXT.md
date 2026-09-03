# Download Organizer

The Download Organizer safely places completed downloads into user-defined folders while preserving recovery and traceability.

## Files and organization

**Download**:
A regular file received in the configured Downloads folder and eligible for organization.
_Avoid_: Item, asset

**Organizer**:
The user-facing system that watches the Downloads folder and applies organization rules.
_Avoid_: Cleaner, sorter

**Rule**:
A user-defined condition and destination that determines where a matching Download belongs.
_Avoid_: Filter, mapping

**Destination**:
The fixed folder where the Organizer places a Download after a Rule matches.
_Avoid_: Target, output folder

**Unsorted**:
The fallback destination for a Download that matches no Rule.
_Avoid_: Misc, Other

## Safety and recovery

**Completion**:
The point at which a Download is stable enough to be organized rather than still being written.
_Avoid_: Ready, Finished state

**Move**:
A recorded relocation of a Download from its configured Downloads folder location to a Destination or Unsorted.
_Avoid_: Transfer, copy

**Collision**:
A situation where a Move would use a pathname already occupied by another file.
_Avoid_: Conflict, duplicate

**Move history**:
The lasting record of Moves and their outcomes that supports activity review and recovery.
_Avoid_: Audit log, journal

**Undo**:
A request to reverse a recorded Move, subject to preserving any file that now occupies the original location.
_Avoid_: Revert, rollback
