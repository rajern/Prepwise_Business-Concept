# Microsoft Entra External ID

Prepwise customer authentication uses browser-delegated Microsoft Entra External ID. Microsoft
hosts the combined sign-up/sign-in and password-recovery experience. The React SPA uses MSAL with
the OAuth 2.0 authorization code flow with PKCE; Prepwise never receives a password or uses a
client secret.

## External tenant configuration

The manually managed External ID resources are:

* external tenant: `Prepwise Customers`
* external tenant ID: `1a782388-bf90-4ea8-af8f-bcc755f5cd7e`
* primary domain: `prepwisecustomers.onmicrosoft.com`
* tenant subdomain: `prepwisecustomers`
* SPA application: `prepwise-spa`
* SPA application ID: `c8b5d058-4de9-4adf-ae70-616920a20515`
* API application: `prepwise-api`
* delegated API scope: `api://82773ea0-fcf3-4874-81c3-3cd0da7d00c7/access_as_user`
* user flow: `prepwise-sign-up-sign-in`

The SPA registration uses these redirect bridge URIs for sign-up and sign-in:

* `http://localhost:3000/redirect.html`
* `https://nice-island-080f30a0f.6.azurestaticapps.net/redirect.html`

MSAL v5 completes authentication on this dedicated redirect bridge page. The bridge broadcasts the
authorization response to the main application frame and does not render the React application.
The existing application-root URIs remain registered because logout returns directly to those
locations:

* `http://localhost:3000/`
* `https://nice-island-080f30a0f.6.azurestaticapps.net/`

The SPA is pre-authorised for the delegated `access_as_user` scope. Access tokens use version 2.
Implicit grant is disabled, and neither application has a client secret. Customer/admin roles are
application data in PostgreSQL rather than Entra app roles.

## Local frontend configuration

Copy `frontend/.env.example` to `frontend/.env.local`. The four `VITE_ENTRA_*` values are public
application identifiers embedded in the SPA bundle; they are not credentials.

Run the frontend at `http://localhost:3000/`, because redirect URI matching is exact.

## Production build configuration

The GitHub `production` environment must define these non-secret variables:

* `ENTRA_EXTERNAL_TENANT_ID=1a782388-bf90-4ea8-af8f-bcc755f5cd7e`
* `ENTRA_EXTERNAL_TENANT_SUBDOMAIN=prepwisecustomers`
* `ENTRA_SPA_CLIENT_ID=c8b5d058-4de9-4adf-ae70-616920a20515`
* `ENTRA_API_SCOPE=api://82773ea0-fcf3-4874-81c3-3cd0da7d00c7/access_as_user`

The deployment workflow maps them to Vite build variables. No Entra credential belongs in GitHub,
Key Vault or source control for the SPA flow.

Both the tenant-name authority host and the tenant-ID issuer host are configured as known MSAL
authorities. External ID discovery uses the name host, while its OpenID metadata identifies the
issuer with the tenant-ID host.

## Backend token validation

FastAPI validates only delegated access tokens intended for the API application. Validation checks
the RS256 signature against the tenant-specific rotating JWKS, the exact issuer published by the
tenant metadata, the API application ID as audience, expiry, token version, tenant ID and the
`access_as_user` scope.

The protected `GET /api/me` endpoint maps the immutable `tid` and `oid` claims to the local user.
Email and display name claims are stored only as profile data and are never identity keys or
authorization inputs. New local users receive the database default `customer` role. The existing
`GET /api/meals` catalogue remains public.

The backend configuration is public metadata rather than credentials:

* `ENTRA_TENANT_ID=1a782388-bf90-4ea8-af8f-bcc755f5cd7e`
* `ENTRA_TENANT_SUBDOMAIN=prepwisecustomers`
* `ENTRA_API_CLIENT_ID=82773ea0-fcf3-4874-81c3-3cd0da7d00c7`
* `ENTRA_API_SCOPE=access_as_user`

Docker Compose supplies these values locally. Bicep and the production deployment workflow supply
them to the Container App. No client secret is required by the API for access-token validation.
