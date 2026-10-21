<div align="center">
  <img src=".github/new_logo.svg" height="80" width="80" alt="Drive logo">
  <h2>Drive (Lifegence fork of Frappe Drive)</h2>

**File storage, sharing and collaboration for Frappe sites, with security fixes**

[日本語](#日本語) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md) · [Upstream README](README.upstream.md)

</div>

> [!Important]
> This is a community-maintained fork. It is not affiliated with or endorsed by Frappe Technologies.
> "Frappe" is a trademark of Frappe Technologies Pvt. Ltd.

## Why this fork

[Frappe Drive](https://github.com/frappe/drive) was archived on 2026-10-01 and its development moved
to [Frappe Suite](https://github.com/frappe/suite). Suite has no stable release yet, and it can't be
installed on a site that has Drive. Sites already running Drive on Frappe v15 or v16 therefore stay
on the last Drive release (v0.3.0), which no longer receives fixes.

This fork keeps that line usable:

- It starts from upstream `main` (v0.3.0, commit `0bd11d8`), the branch the upstream README tells
  people to install.
- It adds security fixes and Japanese translations. See [CHANGELOG.md](CHANGELOG.md).
- It keeps the app name, modules and DocTypes unchanged, so existing data works as is, and the
  upstream path to Suite still applies.

New features are out of scope. For those, wait for Frappe Suite.

## Branches

| Branch | Contents |
| --- | --- |
| `lifegence` (default) | Upstream `main` plus the changes in this fork. Install this one. |
| `main` | Unchanged copy of upstream `main`, kept for comparison. |

## Installation

Requirements: Frappe Framework v15 or v16. `ffmpeg` is optional. Video thumbnails use OpenCV, which ships its own codecs.

### Bench

```bash
bench get-app https://github.com/lifegence/drive --branch lifegence
bench --site yoursite install-app drive
```

### Frappe Cloud or a self-hosted Press

Add a new app from GitHub with the URL `https://github.com/lifegence/drive` and the branch
`lifegence`, deploy the bench, then install Drive on the site.

### Switching from upstream Drive

The app name and DocTypes are the same, so no data migration is needed. Take a backup, point the
app at this repository, and update:

```bash
bench --site yoursite backup --with-files
cd apps/drive
git remote add lifegence https://github.com/lifegence/drive
git fetch lifegence
git checkout -b lifegence lifegence/lifegence
cd ../..
bench build --app drive
bench --site yoursite migrate
```

On Frappe Cloud, replace the app source in the bench group with this repository and deploy.

### Moving to Frappe Suite later

Follow the [migration steps in the Suite README](https://github.com/frappe/suite#migrating-from-the-standalone-apps).
They apply to this fork in the same way as to upstream Drive.

## Configuration

| Site config key | Default | Effect |
| --- | --- | --- |
| `drive_app_roles` | not set | A role name or a list of them, for example `["System Manager"]`. Only users with one of these roles (and Administrator) see Drive on the apps screen. It hides the icon only; file permissions are unchanged. |
| `drive_enable_ip_geolocation` | off | When on, sign-up and OTP requests look up the requester's IP address at `pro.ip-api.com`, which is what upstream always did. |

## Running the tests

```bash
bench --site test-site set-config allow_tests 1
bench --site test-site run-tests --module drive.api.test_controller_method
bench --site test-site run-tests --module drive.api.test_otp
bench --site test-site run-tests --module drive.api.test_access_app
```

Upstream's Cypress UI tests are still in `cypress/`.

## Security

Please report vulnerabilities privately. See [SECURITY.md](SECURITY.md).

## License

GNU Affero General Public License v3.0, the same as upstream. See [LICENSE](LICENSE).

This is a modified version of Frappe Drive, © Frappe Technologies Pvt. Ltd. Lifegence Corporation
made the changes listed in [CHANGELOG.md](CHANGELOG.md), starting in October 2026. If you run a modified version for users over a
network, AGPL-3.0 section 13 requires you to offer them its source.

---

## 日本語

Frappe Drive は 2026-10-01 に上流でアーカイブされ、開発は Frappe Suite に移りました。Suite はまだ
正式版がなく、Drive が入っているサイトには入れられません。このフォークは、最後のリリース（v0.3.0）に
セキュリティ修正と日本語訳を加えて保守するものです。Frappe Technologies とは関係のない、
コミュニティによるフォークです。

- 対応：Frappe v15・v16
- インストール：`bench get-app https://github.com/lifegence/drive --branch lifegence`
- アプリ名と DocType は上流と同じなので、上流の Drive からはデータ移行なしで切り替えられます。
  Suite が正式版になったら、Suite の README の手順でそのまま移行できます
- 変更点：[CHANGELOG.md](CHANGELOG.md)
- 脆弱性の報告：[SECURITY.md](SECURITY.md)（公開の Issue には書かないでください）
- アプリ画面のアイコンを特定ロールだけに出すには、サイト設定 `drive_app_roles` を使います（例：`["System Manager"]`）
- 画面の文言の多くは翻訳の仕組みを通っていないため、日本語化は一部です

ライセンスは上流と同じ AGPL-3.0 です。
