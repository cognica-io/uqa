#!/usr/bin/env bash
#
# Download NYC Taxi & Limousine Commission trip data (Parquet format).
#
# Source: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page
# CDN:    https://d37ci6vzurychx.cloudfront.net/trip-data/
#
# Usage:
#   ./download_nyc_taxi.sh                  # default: yellow, 2024-01 to 2024-06
#   ./download_nyc_taxi.sh green 2023 1 12  # green taxi, 2023 full year
#
# Taxi types: yellow, green, fhv, fhvhv

set -euo pipefail

BASE_URL="https://d37ci6vzurychx.cloudfront.net/trip-data"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

TAXI_TYPE="${1:-yellow}"
YEAR="${2:-2024}"
START_MONTH="${3:-1}"
END_MONTH="${4:-6}"

# Validate taxi type
case "$TAXI_TYPE" in
    yellow|green|fhv|fhvhv) ;;
    *)
        echo "Error: unknown taxi type '$TAXI_TYPE'. Use: yellow, green, fhv, fhvhv"
        exit 1
        ;;
esac

# Validate year
if [[ "$YEAR" -lt 2009 || "$YEAR" -gt 2026 ]]; then
    echo "Error: year must be between 2009 and 2026"
    exit 1
fi

# Validate months
if [[ "$START_MONTH" -lt 1 || "$START_MONTH" -gt 12 ]]; then
    echo "Error: start month must be between 1 and 12"
    exit 1
fi
if [[ "$END_MONTH" -lt 1 || "$END_MONTH" -gt 12 ]]; then
    echo "Error: end month must be between 1 and 12"
    exit 1
fi
if [[ "$START_MONTH" -gt "$END_MONTH" ]]; then
    echo "Error: start month ($START_MONTH) must be <= end month ($END_MONTH)"
    exit 1
fi

DEST_DIR="$SCRIPT_DIR/${TAXI_TYPE}_tripdata"
mkdir -p "$DEST_DIR"

echo "Downloading $TAXI_TYPE taxi data for $YEAR ($START_MONTH - $END_MONTH)"
echo "Destination: $DEST_DIR"
echo ""

DOWNLOADED=0
FAILED=0

for MONTH in $(seq "$START_MONTH" "$END_MONTH"); do
    MONTH_PAD=$(printf "%02d" "$MONTH")
    FILENAME="${TAXI_TYPE}_tripdata_${YEAR}-${MONTH_PAD}.parquet"
    URL="${BASE_URL}/${FILENAME}"
    DEST_FILE="${DEST_DIR}/${FILENAME}"

    if [[ -f "$DEST_FILE" ]]; then
        SIZE=$(wc -c < "$DEST_FILE" | tr -d ' ')
        echo "[skip] $FILENAME already exists ($(numfmt --to=iec "$SIZE" 2>/dev/null || echo "${SIZE} bytes"))"
        DOWNLOADED=$((DOWNLOADED + 1))
        continue
    fi

    echo -n "[download] $FILENAME ... "
    HTTP_CODE=$(curl -sS -w "%{http_code}" -o "$DEST_FILE" "$URL" 2>/dev/null || echo "000")

    if [[ "$HTTP_CODE" == "200" ]]; then
        SIZE=$(wc -c < "$DEST_FILE" | tr -d ' ')
        echo "OK ($(numfmt --to=iec "$SIZE" 2>/dev/null || echo "${SIZE} bytes"))"
        DOWNLOADED=$((DOWNLOADED + 1))
    else
        echo "FAILED (HTTP $HTTP_CODE)"
        rm -f "$DEST_FILE"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "Done: $DOWNLOADED downloaded, $FAILED failed"
echo "Files: $DEST_DIR/"
