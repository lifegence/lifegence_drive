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

### Fixed

- The frontend still called the old `/api/method/drive.api.*` paths after the rename, so uploads,
  previews, settings, team lists and folder downloads failed in the browser. It now calls
  `lifegence_drive.api.*`.
- The share dialog called `files.share`, which upstream `develop` never defined. It now exists and
  accepts only `share` and `unshare`; people can always remove their own access.
- Uploads whose names have no ASCII characters before the extension (for example `提案書.docx`)
  failed, because the type was detected from a temporary name without the extension.
- Invitation links point to the new method path.
- Creating a folder failed on sites that don't use the flat disk layout: the path was built from the
  parent's file URL and became absolute.
- Uploaded Word and PowerPoint files couldn't be downloaded from the menu, because they share their
  type with Writer and Slides documents. Only the latter are excluded now.
- "Delete forever" failed: the confirm dialog sent the file list as a JSON string, which the typed
  API rejected. It sends a list now, and the API accepts both.
- The Move button was disabled exactly when a different folder was chosen.
- The "With you" tab on Shared never loaded: switching tabs didn't fetch the new list.
- "Document" no longer appears in the Create menu when the Writer app isn't installed, the same as
  "Presentation" without Slides.
- Opening a public link without logging in no longer calls the visit tracker, which needs a login.
- People a folder is shared with (without Frappe roles on File) could not rename, move, trash,
  restore or permanently delete in it, nor upload into it: saves went through File role
  permissions, and the quota check required team membership. Drive permissions are checked first,
  then the change is saved; the quota check no longer needs membership.
- Renaming, moving or permanently deleting a folder now reaches everything inside it for those
  people too (children were looked up with the caller's role filter and came back empty).
- On a non-flat disk, renaming or moving a folder stored its new location without the leading
  `/` that uploads use (`private/files/...`). Renaming that folder again after uploading into it
  failed. Locations are now always stored as `/private/files/...`.

### Compatibility

- Old `drive.api.*` method paths keep working and are mapped to `lifegence_drive.api.*`, so
  invitation emails, images embedded in documents and S3 file URLs created by the `drive` app
  still resolve (`lifegence_drive/legacy_routes.py`).

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
