# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `create_recipe_full` and `patch_recipe` accept a `notes` argument for Mealie's
  `{title, text}` notes. Mealie requires a title but accepts an empty one, so
  the title defaults to `""`. `patch_recipe` replaces all notes; an empty list
  clears them.
