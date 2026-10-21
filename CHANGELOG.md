# Changelog

Changes in this fork, on top of upstream `main` at `0bd11d8` (Frappe Drive v0.3.0).

## 0.3.1 (2026-10-21)

### Security

- `call_controller_method` now accepts only the controller methods the client uses (`rename`,
  `change_color`, `share`, `unshare`), and checks the caller's write or share access on the file
  first. Before this, a logged-in user could run other methods on files they had no access to.
  `rename`, `change_color` and `unshare` also check access themselves.
- Email OTPs expire after 10 minutes, work only once, and are compared in constant time.
- The IP geolocation lookup at `pro.ip-api.com` is off unless the site config sets
  `drive_enable_ip_geolocation`. Upstream sent the requester's IP address on every OTP request.

### Added

- Japanese translations (`drive/locale/ja.po`, 213 strings).
- Integration tests for the changes above (`drive/api/test_controller_method.py`,
  `drive/api/test_otp.py`).

### Removed

- Upstream's GitHub Actions workflows, which push images to Frappe's registry and open translation
  pull requests with Frappe's credentials. They are replaced by a test workflow.
