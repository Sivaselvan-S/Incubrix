# ==============================================================================
# LongTail Passport - Local Real Instances Bootstrap Script (PowerShell)
# Boots Ghost, Lemmy, PostgreSQL, MinIO, and MockHub via Docker Compose.
# ==============================================================================

Write-Host "==> Starting LongTail Passport core services and real instances..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Warning "Docker is not installed or not in PATH."
    exit 1
}

docker compose --profile real-instances up -d

Write-Host "==> Waiting for Ghost Admin API (http://localhost:2368)..."
$maxRetries = 30
$retries = 0
$ghostReady = $false
while (-not $ghostReady -and $retries -lt $maxRetries) {
    $retries++
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:2368/ghost/api/admin/site/" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($resp.StatusCode -eq 200) { $ghostReady = $true }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if ($ghostReady) {
    Write-Host "==> Ghost is ready at http://localhost:2368."
} else {
    Write-Warning "Ghost did not become ready in time, continuing..."
}

Write-Host "==> Waiting for Lemmy (http://localhost:8536)..."
$retries = 0
$lemmyReady = $false
while (-not $lemmyReady -and $retries -lt $maxRetries) {
    $retries++
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8536/api/v3/site" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($resp.StatusCode -eq 200) { $lemmyReady = $true }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if ($lemmyReady) {
    Write-Host "==> Lemmy is ready at http://localhost:8536."
} else {
    Write-Warning "Lemmy did not become ready in time, continuing..."
}

Write-Host "==> All local instances initialized successfully."
