# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-11

### Added

- Command line tool and library that turn a Google Maps directions link into a closed, smooth
  track-circuit outline.
- PNG and SVG output, with transparent backgrounds and configurable colors and line width.
- Optional waypoint markers.
- `--smoothing` (0 to 1) to round off kinks in the curve.
- Optional country borders (Natural Earth 1:50m), including the four UK nations.
- Waypoints from embedded coordinates, `lat,lon` or DMS segments, or named places geocoded with
  Nominatim.
