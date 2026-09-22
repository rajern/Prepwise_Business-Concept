# Neon production database boundary

Neon is the managed production PostgreSQL platform, but it is not an Azure resource and is not
provisioned by this Bicep deployment. No Terraform or second infrastructure-as-code tool is added
only for Neon.

T3.2 will document and configure the following manual Neon prerequisites:

1. Create a production Neon project, database and least-privileged application role.
2. Obtain the pooled PostgreSQL connection string and require TLS with `sslmode=require`.
3. Store that connection string as a secret in Azure Key Vault.
4. Grant the Container App managed identity permission to read the secret.
5. Keep local development and CI connected to their own PostgreSQL instances.

Never commit a Neon connection string, password or generated `.env` file. Bicep may reference the
name of a Key Vault secret after T3.2, but the secret value remains outside source control and
deployment outputs.
