# PowerShell script to set up environment variables in Vercel from .env file
# Usage: .\setup-vercel-env.ps1

Write-Host "Setting up Vercel environment variables from .env file..." -ForegroundColor Green

# Check if .env file exists
if (-not (Test-Path .env)) {
    Write-Host "Error: .env file not found!" -ForegroundColor Red
    exit 1
}

# Read .env file and set each variable
Get-Content .env | ForEach-Object {
    # Skip comments and empty lines
    if ($_ -match '^#.*$' -or [string]::IsNullOrWhiteSpace($_)) {
        return
    }
    
    # Parse key=value
    if ($_ -match '^([^=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        
        # Skip empty values
        if ([string]::IsNullOrWhiteSpace($value)) {
            Write-Host "Skipping $key (empty value)" -ForegroundColor Yellow
            return
        }
        
        Write-Host "Setting $key..." -ForegroundColor Cyan
        vercel env add $key $value
    }
}

Write-Host "Environment variables setup complete!" -ForegroundColor Green
Write-Host "Run 'vercel --prod' to deploy with the new environment variables." -ForegroundColor Yellow
