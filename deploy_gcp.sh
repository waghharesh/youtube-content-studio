#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   export GCP_PROJECT_ID="your-gcp-project-id"
#   export GCP_REGION="us-central1"
#   ./deploy_gcp.sh

PROJECT_ID="${GCP_PROJECT_ID:-project-524e25ba-13c7-42b8-848}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="youtube-content-studio"

echo "Enabling required Google Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  youtube.googleapis.com \
  --project="${PROJECT_ID}"

echo "Building and deploying ${SERVICE_NAME} to Cloud Run in ${REGION}..."
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900
