<div align="center">
  <img src=".github/new_logo.svg" height="80" width="80" alt="Drive logo">
  <h2>Lifegence Drive</h2>

**File storage, sharing and collaboration for Frappe sites, based on Frappe Drive**

[日本語](#日本語) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md) · [Upstream README](README.upstream.md)

</div>

> [!Important]
> Lifegence Drive is a modified version of Frappe Drive, maintained by Lifegence Corporation.
> It is not affiliated with or endorsed by Frappe Technologies. "Frappe" is a trademark of
> Frappe Technologies Pvt. Ltd.

## Background

[Frappe Drive](https://github.com/frappe/drive) was archived on 2026-10-01 and its development moved
to [Frappe Suite](https://github.com/frappe/suite). Lifegence Drive continues the Drive code base on
its own:

- It starts from upstream `develop` at `f12393e`, the last commit before the archive. `develop` has
  about 250 commits, including security fixes, that never reached the `main` branch.
- It adds security fixes and other changes. See [CHANGELOG.md](CHANGELOG.md).
- The app is called `lifegence_drive`, so it can't be confused with upstream Drive. DocTypes, the
  `Drive` module and the `/drive` URLs keep their upstream names, so existing data works as is.

Because of the new app name, the [Suite migration steps](https://github.com/frappe/suite#migrating-from-the-standalone-apps)
don't apply as written. A site would first have to be moved back to the app name `drive`.

## Installation

Requirements: Frappe Framework v15 or v16.

```bash
bench get-app https://github.com/lifegence/lifegence_drive --branch lifegence
bench --site yoursite install-app lifegence_drive
```

On Frappe Cloud or a self-hosted Press, add the app from GitHub with this repository's URL and
branch, deploy the bench, then install `lifegence_drive` on the site.

### Switching from upstream Drive or from the 0.3 line

Sites that have the app `drive` installed (upstream Drive, or this repository before 0.4.0) keep
their data. The app records are renamed, and `bench migrate` applies the upstream `develop` patches.

```bash
bench --site yoursite backup --with-files
# Replace apps/drive with this repository, as apps/lifegence_drive
bench get-app https://github.com/lifegence/lifegence_drive --branch lifegence
bench remove-app drive --no-backup --force   # removes the code only; the site still has the data
bench --site yoursite migrate-from-drive
bench --site yoursite migrate
bench build --app lifegence_drive
```

`remove-app` only takes the app out of the bench. Don't run `uninstall-app` on the site: that
deletes the Drive DocTypes and their data.

## Configuration

| Site config key | Default | Effect |
| --- | --- | --- |
| `drive_app_roles` | not set | A role name or a list of them, for example `["System Manager"]`. Only users with one of these roles (and Administrator) see Drive on the apps screen. It hides the icon only; file permissions are unchanged. |
| `drive_enable_ip_geolocation` | off | When on, sign-up and OTP requests look up the requester's IP address at `pro.ip-api.com`, which is what upstream always did. |

## Running the tests

```bash
bench --site test-site set-config allow_tests 1
bench --site test-site run-tests --module lifegence_drive.api.test_otp
bench --site test-site run-tests --module lifegence_drive.api.test_access_app
```

## Security

Please report vulnerabilities privately. See [SECURITY.md](SECURITY.md).

## License

GNU Affero General Public License v3.0, the same as upstream. See [LICENSE](LICENSE).

This is a modified version of Frappe Drive, © Frappe Technologies Pvt. Ltd. Lifegence Corporation
made the changes listed in [CHANGELOG.md](CHANGELOG.md), starting in October 2026. If you run a
modified version for users over a network, AGPL-3.0 section 13 requires you to offer them its source.

---

## 日本語

Lifegence Drive は、Frappe Drive をもとにライフジェンス株式会社が保守しているアプリです。
Frappe Technologies とは関係ありません。

- 上流の Frappe Drive は 2026-10-01 にアーカイブされました。Lifegence Drive は、アーカイブ直前の
  `develop`（`f12393e`）を起点にしています。`main` に入らなかった修正（セキュリティ修正を含む）も含みます
- アプリ名は `lifegence_drive` です。DocType 名、`Drive` モジュール、`/drive` の URL は上流と同じなので、
  データはそのまま使えます
- 上流の Drive（アプリ名 `drive`）からの切り替え手順は、上の「Switching from upstream Drive」を参照してください。
  サイトで `uninstall-app` を実行するとデータが消えるので、実行しないでください
- アプリ名を変えたため、Frappe Suite への移行手順はそのままでは使えません
- 変更点：[CHANGELOG.md](CHANGELOG.md)
- 脆弱性の報告：[SECURITY.md](SECURITY.md)（公開の Issue には書かないでください）

ライセンスは上流と同じ AGPL-3.0 です。
