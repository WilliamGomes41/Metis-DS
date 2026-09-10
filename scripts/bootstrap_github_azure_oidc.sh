#!/usr/bin/env bash
set -euo pipefail

# One-time bootstrap for the GitHub Actions production deploy identity.
# Run while signed in with Azure CLI as an account allowed to create app
# registrations/service principals and assign RBAC on the target web app.
#
# Required env:
#   AZURE_SUBSCRIPTION_ID
#   AZURE_RESOURCE_GROUP
# Optional env:
#   AZURE_PRODUCTION_WEBAPP_NAME (default: vvn-metis-console)
#   GITHUB_REPOSITORY (default: WilliamGomes41/Metis-DS)
#   DEPLOY_APP_NAME (default: metis-deploy-production)

: "${AZURE_SUBSCRIPTION_ID:?set AZURE_SUBSCRIPTION_ID}"
: "${AZURE_RESOURCE_GROUP:?set AZURE_RESOURCE_GROUP}"

AZURE_PRODUCTION_WEBAPP_NAME="${AZURE_PRODUCTION_WEBAPP_NAME:-vvn-metis-console}"
GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-WilliamGomes41/Metis-DS}"
DEPLOY_APP_NAME="${DEPLOY_APP_NAME:-metis-deploy-production}"
FEDERATED_NAME="github-production"
SUBJECT="repo:${GITHUB_REPOSITORY}:environment:production"

az account set --subscription "$AZURE_SUBSCRIPTION_ID"
TENANT_ID="$(az account show --query tenantId -o tsv)"

APP_ID="$(az ad app list --display-name "$DEPLOY_APP_NAME" --query '[0].appId' -o tsv)"
if [ -z "$APP_ID" ]; then
  APP_ID="$(az ad app create --display-name "$DEPLOY_APP_NAME" --query appId -o tsv)"
fi

OBJECT_ID="$(az ad app show --id "$APP_ID" --query id -o tsv)"
SP_OBJECT_ID="$(az ad sp list --filter "appId eq '$APP_ID'" --query '[0].id' -o tsv)"
if [ -z "$SP_OBJECT_ID" ]; then
  SP_OBJECT_ID="$(az ad sp create --id "$APP_ID" --query id -o tsv)"
fi

EXISTING_FIC="$(az ad app federated-credential list --id "$OBJECT_ID" --query "[?name=='$FEDERATED_NAME'].name | [0]" -o tsv)"
if [ -z "$EXISTING_FIC" ]; then
  TMP="$(mktemp)"
  trap 'rm -f "$TMP"' EXIT
  cat > "$TMP" <<JSON
{
  "name": "$FEDERATED_NAME",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "$SUBJECT",
  "description": "GitHub Actions production deployment for $GITHUB_REPOSITORY",
  "audiences": ["api://AzureADTokenExchange"]
}
JSON
  az ad app federated-credential create --id "$OBJECT_ID" --parameters "$TMP" >/dev/null
fi

WEBAPP_ID="$(az webapp show \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_PRODUCTION_WEBAPP_NAME" \
  --query id -o tsv)"

ROLE_COUNT="$(az role assignment list \
  --assignee-object-id "$SP_OBJECT_ID" \
  --scope "$WEBAPP_ID" \
  --query "[?roleDefinitionName=='Website Contributor'] | length(@)" -o tsv)"
if [ "$ROLE_COUNT" = "0" ]; then
  az role assignment create \
    --assignee-object-id "$SP_OBJECT_ID" \
    --assignee-principal-type ServicePrincipal \
    --role "Website Contributor" \
    --scope "$WEBAPP_ID" >/dev/null
fi

cat <<OUT
Azure production OIDC bootstrap complete.

Set these GitHub Actions variables:
AZURE_PRODUCTION_CLIENT_ID=$APP_ID
AZURE_TENANT_ID=$TENANT_ID
AZURE_SUBSCRIPTION_ID=$AZURE_SUBSCRIPTION_ID
AZURE_RESOURCE_GROUP=$AZURE_RESOURCE_GROUP
AZURE_PRODUCTION_WEBAPP_NAME=$AZURE_PRODUCTION_WEBAPP_NAME

Federated subject:
$SUBJECT

Then run GitHub Actions workflow: deploy-production
Leave commit_sha empty to deploy the current main tip, or supply a full main SHA for rollback/redeploy.
OUT
