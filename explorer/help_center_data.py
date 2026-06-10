ASSIGNMENT_QUESTIONS = {
    "change_password": {
        "label": "Reset a known password",
        "question": "How do I reset my password while I am signed in?",
        "intent": (
            "The customer knows the current password and wants to replace it from "
            "account settings."
        ),
    },
    "forgot_password": {
        "label": "Recover a forgotten password",
        "question": "I forgot my password. How do I get back into my account?",
        "intent": (
            "The customer cannot sign in and needs the email-based account recovery "
            "flow."
        ),
    },
}


HELP_CENTER_DOCUMENTS = {
    "HC-001": {
        "title": "Reset or change your password while signed in",
        "relevant_for": ("change_password",),
        "content": """
Use this procedure when you know your current password and can already access your
account. Select your profile picture, open Settings, and choose Security. In the
Password section, select Change password. Enter your current password once, then
enter the new password twice and select Save password. Your new password takes
effect immediately. The application signs out other browser sessions but keeps the
current session active. If you cannot supply the current password, do not use this
screen; return to the sign-in page and use the account recovery option instead.
Changing a password does not alter your email address, workspace memberships, or
two-factor authentication settings.
""".strip(),
    },
    "HC-002": {
        "title": "Recover access when you forgot your password",
        "relevant_for": ("forgot_password",),
        "content": """
Use account recovery when you cannot sign in because you no longer remember your
password. On the sign-in page, select Forgot password, enter the email address on
your account, and choose Send recovery email. Open the message titled Reset your
Acme Cloud password and follow its secure link. The link expires after 30 minutes
and can be used only once. Enter a new password twice, submit the form, and then
sign in with the new password. If no message arrives after several minutes, check
spam and confirm that you entered the account email correctly. Workspace
administrators cannot view or choose a password for another user.
""".strip(),
    },
    "HC-003": {
        "title": "Password strength and character requirements",
        "relevant_for": (),
        "content": """
Acme Cloud passwords must contain at least twelve characters. A password may
include spaces and should combine several unrelated words or use a password
manager-generated value. The service blocks passwords found in common breach
lists, repeated characters, and values containing the user's email address.
Uppercase letters, numbers, and symbols are allowed but are not individually
required. Password history prevents reuse of the five most recent values.
Organizations on the Enterprise plan can require a minimum of sixteen characters.
These rules apply whenever a user creates a credential, regardless of whether the
account was created by invitation or through the public signup page.
""".strip(),
    },
    "HC-004": {
        "title": "Unlock an account after failed sign-in attempts",
        "relevant_for": (),
        "content": """
An account is temporarily locked after ten unsuccessful sign-in attempts within
fifteen minutes. The lock protects the account from automated guessing and clears
automatically after thirty minutes. Wait for the lock period to end before trying
again, because additional attempts can extend the delay. Enterprise administrators
can view lock events in the security log but cannot manually bypass the waiting
period. Confirm that Caps Lock is off and that the browser is not filling an old
credential. If a security alert names a location you do not recognize, contact the
organization's security administrator before attempting another login.
""".strip(),
    },
    "HC-005": {
        "title": "Troubleshoot missing account emails",
        "relevant_for": (),
        "content": """
Automated account messages can be delayed by corporate mail filters. Search all
mail folders for messages from notifications@acmecloud.example and add that sender
to the approved list. Ask the mail administrator whether messages from the
acmecloud.example domain are quarantined. Delivery attempts are visible to support
for 72 hours, but message contents are not stored. Confirm that the email address
on the profile is current and does not contain a typing error. Repeatedly requesting
the same automated message can invalidate older links, so use only the newest
message. SMS notifications and product newsletters use separate delivery systems.
""".strip(),
    },
    "HC-006": {
        "title": "Set up two-factor authentication",
        "relevant_for": (),
        "content": """
Two-factor authentication adds a rotating verification code after the normal
sign-in credential. Open Settings, choose Security, and select Enable two-factor
authentication. Scan the QR code with an authenticator application, enter the
six-digit code, and store the recovery codes in a secure location. Codes refresh
every thirty seconds and cannot be delivered by email. Organization owners can
require two-factor authentication for all members. Enabling this feature does not
replace the primary credential and does not change existing single sign-on rules.
Users should register a second authenticator before replacing a phone.
""".strip(),
    },
    "HC-007": {
        "title": "Use a two-factor recovery code",
        "relevant_for": (),
        "content": """
Recovery codes are intended for users who know their normal sign-in credential but
cannot access the authenticator device. At the verification-code prompt, choose
Use a recovery code and enter one unused code from the set created during
enrollment. Each code works once. After signing in, remove the unavailable device
and register a replacement under Security settings. If every recovery code has
already been used, an organization owner must begin the identity verification
process with support. Support cannot read authenticator secrets or generate a code
over chat. Store new recovery codes outside the device used for daily access.
""".strip(),
    },
    "HC-008": {
        "title": "Sign in with company single sign-on",
        "relevant_for": (),
        "content": """
Organizations with SAML single sign-on direct members to the company's identity
provider. Enter the work email on the Acme Cloud sign-in page and select Continue
with company SSO. The browser then opens the employer's authentication page.
Credentials for that page are managed by the employer, not Acme Cloud. If the
identity provider rejects access, contact the internal IT team and provide the
displayed request identifier. Workspace owners can enforce SSO and prevent members
from using standalone credentials. Personal workspaces remain accessible through
their original sign-in method unless they were converted to managed accounts.
""".strip(),
    },
    "HC-009": {
        "title": "Update the email address on your account",
        "relevant_for": (),
        "content": """
To replace an account email, open Profile settings and select Edit beside the
current address. Enter the new address and confirm it from the verification message
sent to that inbox. The old address remains active until verification is complete.
An address already attached to another account cannot be reused. Managed accounts
may have email changes disabled because identity information is synchronized from
the employer. Updating the address changes future sign-in identification and
notification delivery, but it does not move data between accounts or merge
workspace histories. Organization billing contacts are maintained separately.
""".strip(),
    },
    "HC-010": {
        "title": "Find your workspace URL and username",
        "relevant_for": (),
        "content": """
Most users sign in with an email address rather than a separate username. A
workspace URL appears in invitation messages and has the format
team-name.acmecloud.example. Visit the workspace finder, enter a verified email,
and the service will send a list of matching workspaces. For privacy, the page does
not display memberships directly in the browser. Users belonging to several
organizations can switch workspaces from the profile menu after authentication.
A workspace URL can change when an owner renames the organization, but bookmarks
to the former address redirect for ninety days.
""".strip(),
    },
    "HC-011": {
        "title": "Review and end active sessions",
        "relevant_for": (),
        "content": """
The Sessions page lists browsers and mobile devices that recently accessed the
account. Each entry includes an approximate location, browser name, and last active
time. Select End session to revoke one device or End all other sessions to retain
only the current browser. Location estimates can be inaccurate on cellular or
corporate networks. Ending a session removes locally cached access tokens the next
time that device connects. It does not delete files, revoke API keys, or remove
members from workspaces. Unexpected activity should also be reported to the
organization's security contact.
""".strip(),
    },
    "HC-012": {
        "title": "Create and revoke API access tokens",
        "relevant_for": (),
        "content": """
API tokens allow scripts to call Acme Cloud without an interactive browser session.
Create a token from Developer settings, give it a descriptive name, choose the
minimum required scopes, and copy it immediately. The complete value is displayed
only once. Store tokens in a secrets manager rather than source code or shared
documents. Revoking a token immediately stops future API requests made with it.
Rotating an API token does not affect browser login, connected identity providers,
or other developers' tokens. Organization administrators can restrict token
creation and audit the date each token was last used.
""".strip(),
    },
    "HC-013": {
        "title": "Accept an invitation to a workspace",
        "relevant_for": (),
        "content": """
Workspace invitations are valid for seven days and are tied to the invited email
address. Open the invitation message and select Join workspace. Existing users
should authenticate with the same address; new users will be guided through account
creation. An expired invitation can be reissued by a workspace administrator.
Forwarding the invitation to another person does not transfer the seat. If the link
opens the wrong account, sign out before opening it again or use a private browser
window. Joining a workspace gives access according to the role chosen by the
administrator and does not expose personal workspaces.
""".strip(),
    },
    "HC-014": {
        "title": "Understand member roles and permissions",
        "relevant_for": (),
        "content": """
Workspace roles control access to projects and administrative features. Members can
create and edit content shared with them. Project administrators can manage project
membership and settings. Organization administrators can invite users, configure
security policies, and review audit events. Owners additionally control billing,
data retention, and organization deletion. A role change takes effect immediately
and is recorded in the audit log. Roles do not let administrators inspect private
credentials or authenticator secrets. For least-privilege access, assign the
narrowest role that supports a person's current responsibilities.
""".strip(),
    },
    "HC-015": {
        "title": "Clear browser data for sign-in problems",
        "relevant_for": (),
        "content": """
Stale cookies can cause redirect loops, blank authentication pages, or repeated
workspace selection. First reload the page without cached content. If the problem
continues, clear cookies for acmecloud.example, close every Acme Cloud tab, and
restart the browser. A private browsing window is a useful test because it starts
with a clean session. Ensure that browser extensions are not blocking cookies or
scripts required by the sign-in page. Clearing site data signs the browser out and
removes unsaved local preferences, but content already synchronized to the service
is not deleted.
""".strip(),
    },
    "HC-016": {
        "title": "Sign in to the mobile application",
        "relevant_for": (),
        "content": """
The iOS and Android applications use the same account identity as the web service.
Open the application, enter the account email, and follow the sign-in method shown
for the associated organization. Single sign-on users may be transferred to a
system browser before returning to the application. Device biometric unlock can be
enabled after the first successful authentication, but it only unlocks the locally
stored session. Removing the application also removes that session. Mobile releases
older than the supported minimum may show a generic authentication error and should
be updated through the official app store.
""".strip(),
    },
    "HC-017": {
        "title": "Recognize phishing and suspicious sign-in pages",
        "relevant_for": (),
        "content": """
Acme Cloud employees will never ask for a credential, authenticator code, recovery
code, or complete API token. Before entering account information, verify that the
browser address ends in acmecloud.example and uses HTTPS. Be cautious with urgent
messages claiming that an account will be deleted or billing will stop. Report
suspicious messages by forwarding them as an attachment to the security team.
If information was entered on an untrusted page, disconnect the device from unknown
browser extensions, notify the organization administrator, and review recent
sessions and audit activity.
""".strip(),
    },
    "HC-018": {
        "title": "Complete identity verification with support",
        "relevant_for": (),
        "content": """
Support uses identity verification only when normal automated access methods are
unavailable. The process may require confirmation from an organization owner,
recent billing details, workspace identifiers, and evidence of account ownership.
Agents cannot accept government identification through ordinary chat and will
provide a secure upload link when documentation is necessary. Verification does not
guarantee restoration because managed organizations retain control over their
members. Support will never reveal stored credential data, disable a company
identity provider, or transfer an account based solely on knowledge of project
content.
""".strip(),
    },
    "HC-019": {
        "title": "View account security history",
        "relevant_for": (),
        "content": """
Security history records successful sign-ins, rejected authentication attempts,
new device approvals, two-factor changes, and session revocations. Open Settings,
choose Security, and select View history. Entries include time, approximate
location, device information, and the authentication method used. Users can export
the most recent ninety days as a CSV file. Organization audit logs provide a
separate view of administrative activity. A familiar event can appear under a
different city when an internet provider routes traffic through another region.
Report events that cannot be explained by travel, VPN use, or shared corporate
networks.
""".strip(),
    },
    "HC-020": {
        "title": "Delete an account and export personal data",
        "relevant_for": (),
        "content": """
Account deletion permanently removes personal profile data after a fourteen-day
waiting period. Before requesting deletion, export personal data from Privacy
settings and transfer ownership of any organization resources. Owners must assign a
replacement owner or delete the organization first. During the waiting period, the
request can be canceled from the confirmation email. After deletion completes,
support cannot restore the account, files, comments, or activity history. Removing
a member from one workspace is different from deleting the entire account.
Enterprise retention policies may preserve organization records even after the
personal profile is removed.
""".strip(),
    },
}
