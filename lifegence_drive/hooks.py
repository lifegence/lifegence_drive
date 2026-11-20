from . import __version__ as app_version

app_name = "lifegence_drive"
app_title = "Lifegence Drive"
app_publisher = "Lifegence Corporation (based on Frappe Drive by Frappe Technologies Pvt. Ltd.)"
app_description = "An easy to use, document sharing and management solution."
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "contact@lifegence.com"
app_license = "GNU Affero General Public License v3.0"

# WOPI endpoints for Collabora Online (only active when drive_collabora_url is set)
page_renderer = ["lifegence_drive.api.wopi.WOPIPage"]
auth_hooks = ["lifegence_drive.api.wopi.authenticate"]

website_route_rules = [
    {"from_route": "/drive/<path:app_path>", "to_route": "drive"},
]

add_to_apps_screen = [
    {
        "name": "lifegence_drive",
        "logo": "/assets/lifegence_drive/frontend/favicon-310x310.png",
        "title": "Drive",
        "route": "/drive",
        "has_permission": "lifegence_drive.api.product.access_app",
    }
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/lifegence_drive/css/drive.css"
app_include_js = "ff_integration.bundle.js"

# include js, css files in header of web template
# web_include_css = "/assets/lifegence_drive/css/drive.css"
# web_include_js = "/assets/lifegence_drive/js/drive.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "drive/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"doctype" : "public/js/file.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "drive"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "lifegence_drive.utils.jinja_methods",
# 	"filters": "lifegence_drive.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "lifegence_drive.install.before_install"
after_install = "lifegence_drive.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "lifegence_drive.uninstall.before_uninstall"
# after_uninstall = "lifegence_drive.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "drive.notifications.get_notification_config"
# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
    "Drive Team": "lifegence_drive.utils.overrides.filter_drive_team",
    "Drive Permission": "lifegence_drive.utils.overrides.filter_drive_permission",
    "Drive Favourite": "lifegence_drive.utils.overrides.filter_drive_favourite",
    "Drive Entity Log": "lifegence_drive.utils.overrides.filter_drive_recent",
    "Drive Notification": "lifegence_drive.utils.overrides.filter_drive_notif",
}

has_permission = {
    "File": "lifegence_drive.api.permissions.user_has_permission",
}

after_upload_file = "lifegence_drive.overrides.file.after_upload_file"

# Tools for the AI agent (ai_agent_app). Each provider returns dicts in ai_agent_app's ToolSpec
# fields; the agent applies its own policy, audit, caps and approval to them. Ignored when
# ai_agent_app is not installed or does not read this hook yet.
ai_agent_tools = ["lifegence_drive.ai.tools.get_tools"]
# write_file = 'lifegence_drive.overrides.file.write_file'
# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"File": "lifegence_drive.overrides.file.File"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Presentation": {
        "on_update": "lifegence_drive.api.integration.presentation",
        "on_trash": "lifegence_drive.api.integration.presentation",
    },
    "User": {
		"after_insert": "lifegence_drive.utils.users.assign_drive_role_and_create_settings",
	},
    "File": {"on_trash": "lifegence_drive.api.versions.on_file_trash"},
}


fixtures = [
    # Drive bolts its fields onto the framework File doctype; without this the
    # custom_field.json / role.json fixtures never sync to other sites.
    {"dt": "Custom Field", "filters": [["dt", "=", "File"]]},
    # Desk-form tweaks for the framework File form (Drive folder + file_url fields).
    {"dt": "Property Setter", "filters": [["doc_type", "=", "File"]]},
    {"dt": "Role", "filters": [["role_name", "like", "Drive %"]]},
]

# Scheduled Tasks
# ---------------

scheduler_events = {
    "daily": [
        "lifegence_drive.api.scripts.auto_delete_from_trash",
        "lifegence_drive.api.scripts.clear_deleted_files",
        "lifegence_drive.api.versions.prune_all",
    ],
}

after_request = "lifegence_drive.api.product.after_request"
# Testing
# -------

# before_tests = "lifegence_drive.install.before_tests"

# Overriding Methods
# ------------------------------
#
# Keep links and stored URLs that use the old drive.api.* paths working
from lifegence_drive.legacy_routes import override_whitelisted_methods  # noqa: E402, F401
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "drive.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"drive.auth.validate"
# ]


signup_form_template = "templates/signup.html"
ALLOWED_PATHS = [
    "/api/method/create-site-migration",
    "/api/method/find-my-sites",
    "/api/method/frappe.realtime.get_user_info",
    "/api/method/frappe.realtime.can_subscribe_doc",
    "/api/method/frappe.realtime.can_subscribe_doctype",
    "/api/method/frappe.realtime.has_permission",
    "/api/method/frappe.www.login.login_via_frappe",
    "/api/method/frappe.integrations.oauth2.authorize",
    "/api/method/frappe.integrations.oauth2.approve",
    "/api/method/frappe.integrations.oauth2.get_token",
    "/api/method/frappe.integrations.oauth2.openid_profile",
    "/api/method/frappe.integrations.oauth2_logins.login_via_frappe",
    "/api/method/frappe.website.doctype.web_page_view.web_page_view.make_view_log",
    "/api/method/ping",
    "/api/method/login",
    "/api/method/logout",
    "/api/method/upload_file",
    "/api/method/frappe.search.web_search",
    "/api/method/frappe.email.queue.unsubscribe",
    "/api/method/frappe.website.doctype.web_form.web_form.accept",
    "/api/method/frappe.core.doctype.user.user.test_password_strength",
    "/api/method/frappe.core.doctype.user.user.update_password",
]

ALLOWED_WILDCARD_PATHS = [
    "/api/method/lifegence_drive.api.",
    # Old paths from the drive app, mapped by override_whitelisted_methods below
    "/api/method/drive.api.",
]

DENIED_PATHS = []

DENIED_WILDCARD_PATHS = [
    "/api/",
]
require_type_annotated_api_methods = True
