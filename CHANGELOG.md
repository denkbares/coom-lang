# Changelog of the COOM language

This file records changes to the language itself, by language version. The Python package has its own version and
states in its metadata which language version it implements.

Versioning: `MAJOR.MINOR`. A minor version only adds constructs, every valid model of the previous minor version stays
valid and keeps its meaning. A major version may change or remove constructs. Editorial changes to the documentation
do not bump the version.

The format follows https://keepachangelog.com. Entries name the profile or module they touch.

## 1.1 (unreleased)

### Added

- TEST: `isAvailable` and `isBlocked` accept values of every type, not only options, and leave out the value for a
  path to a structure feature to check the creation of its instance. This makes refused inputs testable.
- TEST: the steps `isHidden p`, `isHidden p = o` and `isReadonly p` assert the effective visibility directive of a slot
  and hidden options.

## 1.0 (unreleased)

Initial version of the language, defining the required profile CORE, the profiles N-OUT, N-LIN, N-FULL, C-FIX, C-USER,
C-OPEN, D-BASE, D-COND and O, and the modules UI and TEST.
