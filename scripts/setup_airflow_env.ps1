param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$securePassword = Read-Host 'MySQL password for spend_app@host.docker.internal' -AsSecureString
$passwordPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $mysqlPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPtr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPtr)
}

function New-HexSecret([int]$bytes = 48) {
    $buffer = New-Object byte[] $bytes
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($buffer)
    } finally {
        $generator.Dispose()
    }
    return -join ($buffer | ForEach-Object { $_.ToString('x2') })
}

$fernetBytes = New-Object byte[] 32
$fernetGenerator = [Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $fernetGenerator.GetBytes($fernetBytes)
} finally {
    $fernetGenerator.Dispose()
}
$fernetKey = [Convert]::ToBase64String($fernetBytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
$adminPassword = New-HexSecret 24
$jwtSecret = New-HexSecret 48
$metadataPassword = New-HexSecret 32

function ConvertTo-DotEnvValue([string]$value) {
    $escaped = $value.Replace('\', '\\').Replace('"', '\"').Replace('$', '$$')
    return '"' + $escaped + '"'
}

$content = @"
AIRFLOW_UID=50000
AIRFLOW_ADMIN_USER="admin"
AIRFLOW_ADMIN_PASSWORD=$(ConvertTo-DotEnvValue $adminPassword)
AIRFLOW_FERNET_KEY=$(ConvertTo-DotEnvValue $fernetKey)
AIRFLOW_JWT_SECRET=$(ConvertTo-DotEnvValue $jwtSecret)
AIRFLOW_METADATA_PASSWORD=$(ConvertTo-DotEnvValue $metadataPassword)
MYSQL_HOST="host.docker.internal"
MYSQL_PORT=3306
MYSQL_DATABASE="enterprise_spend"
MYSQL_USER="spend_app"
MYSQL_PASSWORD=$(ConvertTo-DotEnvValue $mysqlPassword)
"@

$envPath = Join-Path $ProjectRoot 'airflow\.env'
[IO.File]::WriteAllText($envPath, $content, [Text.UTF8Encoding]::new($false))
$mysqlPassword = $null
$securePassword.Dispose()
Write-Host "Created $envPath (ignored by Git)."
Write-Host 'Generated secrets and the MySQL password were not printed.'
