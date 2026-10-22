# Changelog

Changes made by Lifegence Corporation to Frappe Drive. Since 0.4.0 they are on top of upstream
`develop` at `f12393e` (the last commit before the repository was archived).

## 0.4.0 (unreleased)

### Changed

- Rebased on upstream `develop` (`f12393e`) instead of `main` (`0bd11d8`). This brings in about 250
  upstream commits that never reached `main`, including the database-stored, single-use tokens for
  the Office preview and stricter permission checks on Drive Disk Settings and sorting.
- The app is renamed from `drive` to `lifegence_drive`. DocType names, the `Drive` module, the
  `/drive` URLs and the stored data are unchanged. Sites that have `drive` installed move over with
  `bench --site <site> migrate-from-drive` (see the README).
- The app title and publisher now name Lifegence Corporation.

### Security

Carried over from 0.3.1:

- Email OTPs expire after 10 minutes, work only once, and are compared in constant time.
- The IP geolocation lookup at `pro.ip-api.com` is off unless the site config sets
  `drive_enable_ip_geolocation`.

The `call_controller_method` fix from 0.3.1 is no longer needed: upstream `develop` removed the
function.

### Added

- Carried over from 0.3.2: the site config key `drive_app_roles` limits who sees Drive on the apps
  screen.

### Removed

- Upstream's image build, translation sync and Crowdin configuration, which use Frappe's
  credentials. The test workflow from 0.3.1 replaces them.

## 0.3.2 (2026-10-21)

On upstream `main`. Added the site config key `drive_app_roles`.

## 0.3.1 (2026-10-21)

On upstream `main`. Security fixes for `call_controller_method`, email OTPs and the IP geolocation
lookup, Japanese translations, and tests for these.
