# Microsoft Entra External ID

Prepwise customer authentication uses browser-delegated Microsoft Entra External ID. Microsoft
hosts the combined sign-up/sign-in and password-recovery experience. The React SPA uses MSAL with
the OAuth 2.0 authorization code flow with PKCE; Prepwise never receives a password or uses a
client secret.

## External tenant configuration

The manually managed External ID resources are:

* external tenant: `Prepwise Customers`
* primary domain: `prepwisecustomers.onmicrosoft.com`
* tenant subdomain: `prepwisecustomers`
* SPA application: `prepwise-spa`
* SPA application ID: `c8b5d058-4de9-4adf-ae70-616920a20515`
* API application: `prepwise-api`
* delegated API scope: `api://82773ea0-fcf3-4874-81c3-3cd0da7d00c7/access_as_user`
* user flow: `prepwise-sign-up-sign-in`

The SPA registration uses these redirect URIs:

* `http://localhost:3000/`
* `https://nice-island-080f30a0f.6.azurestaticapps.net/`

The SPA is pre-authorised for the delegated `access_as_user` scope. Access tokens use version 2.
Implicit grant is disabled, and neither application has a client secret. Customer/admin roles are
application data in PostgreSQL rather than Entra app roles.

## Local frontend configuration

Copy `frontend/.env.example` to `frontend/.env.local`. The three `VITE_ENTRA_*` values are public
application identifiers embedded in the SPA bundle; they are not credentials.

Run the frontend at `http://localhost:3000/`, because redirect URI matching is exact.

## Production build configuration

The GitHub `production` environment must define these non-secret variables:

* `ENTRA_EXTERNAL_TENANT_SUBDOMAIN=prepwisecustomers`
* `ENTRA_SPA_CLIENT_ID=c8b5d058-4de9-4adf-ae70-616920a20515`
* `ENTRA_API_SCOPE=api://82773ea0-fcf3-4874-81c3-3cd0da7d00c7/access_as_user`

The deployment workflow maps them to Vite build variables. No Entra credential belongs in GitHub,
Key Vault or source control for the SPA flow.

## Task boundary

T4.1 signs users in and obtains the delegated Prepwise API access token in the browser. T4.2 adds
FastAPI JWT validation, protected endpoints and local-user resolution. Until T4.2 is implemented,
the existing meal catalogue remains public and the access token is not treated as trusted by the
backend.
