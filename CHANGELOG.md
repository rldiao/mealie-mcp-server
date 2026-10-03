# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `create_recipe_full` and `patch_recipe` accept a `nutrition` argument covering
  Mealie's full key set (calories, macros, cholesterol, sodium, sugars, and the
  fat breakdown). Numbers are converted to the strings Mealie stores. Mealie
  replaces the whole nutrition object on write, so `patch_recipe` clears any key
  not passed.
