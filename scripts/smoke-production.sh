#!/usr/bin/env bash
set -euo pipefail

frontend_url="${1:?Usage: smoke-production.sh FRONTEND_URL BACKEND_URL}"
backend_url="${2:?Usage: smoke-production.sh FRONTEND_URL BACKEND_URL}"
[[ "$frontend_url" == https://* ]] || { echo "Frontend URL must use HTTPS" >&2; exit 1; }
[[ "$backend_url" == https://* ]] || { echo "Backend URL must use HTTPS" >&2; exit 1; }
temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT

curl_retry=(
  --fail
  --silent
  --show-error
  --retry 12
  --retry-delay 5
  --retry-all-errors
  --proto '=https'
  --tlsv1.2
)

echo "Checking frontend availability"
curl "${curl_retry[@]}" \
  --dump-header "$temporary_directory/frontend-headers" \
  "$frontend_url" \
  --output "$temporary_directory/frontend.html"
grep --fixed-strings '<title>Prepwise</title>' "$temporary_directory/frontend.html" >/dev/null

echo "Checking frontend security headers"
grep --fixed-strings --ignore-case \
  "content-security-policy: default-src 'self'" \
  "$temporary_directory/frontend-headers" >/dev/null
grep --fixed-strings --ignore-case \
  'strict-transport-security: max-age=31536000; includeSubDomains' \
  "$temporary_directory/frontend-headers" >/dev/null
grep --fixed-strings --ignore-case \
  'x-content-type-options: nosniff' \
  "$temporary_directory/frontend-headers" >/dev/null
grep --fixed-strings --ignore-case \
  'x-frame-options: DENY' \
  "$temporary_directory/frontend-headers" >/dev/null
grep --fixed-strings --ignore-case \
  'referrer-policy: strict-origin-when-cross-origin' \
  "$temporary_directory/frontend-headers" >/dev/null

echo "Checking backend liveness"
curl "${curl_retry[@]}" "$backend_url/health/live" |
  jq --exit-status '.status == "ok"' >/dev/null

echo "Checking backend readiness and database connectivity"
curl "${curl_retry[@]}" "$backend_url/health/ready" |
  jq --exit-status '.status == "ok"' >/dev/null

echo "Checking public meal catalogue"
curl "${curl_retry[@]}" "$backend_url/api/meals" --output "$temporary_directory/meals.json"
jq --exit-status 'length > 0 and all(.[]; .id and .name and .price_nok)' \
  "$temporary_directory/meals.json" >/dev/null
meal_id="$(jq --raw-output '.[0].id' "$temporary_directory/meals.json")"
curl "${curl_retry[@]}" "$backend_url/api/meals/$meal_id" |
  jq --exit-status --arg meal_id "$meal_id" '.id == $meal_id and .available == true' >/dev/null

echo "Checking versioned meal illustrations on the frontend origin"
jq --raw-output '.[].image_url | select(type == "string") | select(test("^/images/meals/[a-z-]+-v1[.]webp$"))' \
  "$temporary_directory/meals.json" | sort --unique > "$temporary_directory/image-paths"
while IFS= read -r image_path; do
  curl "${curl_retry[@]}" \
    --dump-header "$temporary_directory/image-headers" \
    --output "$temporary_directory/image.webp" "$frontend_url$image_path"
  grep --extended-regexp --ignore-case '^content-type: image/webp' \
    "$temporary_directory/image-headers" >/dev/null
  python - "$temporary_directory/image.webp" <<'PY'
import pathlib
import sys
image = pathlib.Path(sys.argv[1]).read_bytes()
assert image[:4] == b"RIFF" and image[8:12] == b"WEBP", "Invalid WebP response"
assert 10_000 < len(image) < 300_000, "Invalid illustration size"
PY
done < "$temporary_directory/image-paths"
missing_status="$(curl --silent --show-error --proto '=https' --tlsv1.2 \
  --output /dev/null --write-out '%{http_code}' "$frontend_url/images/meals/nonexistent.webp")"
[[ "$missing_status" == 404 ]] || { echo "Missing illustration did not return 404" >&2; exit 1; }

echo "Checking production browser CORS policy"
curl "${curl_retry[@]}" \
  --dump-header "$temporary_directory/cors-headers" \
  --output /dev/null \
  --header "Origin: $frontend_url" \
  "$backend_url/api/meals"
grep --fixed-strings --ignore-case \
  "access-control-allow-origin: $frontend_url" \
  "$temporary_directory/cors-headers" >/dev/null

echo "Production smoke tests passed"
