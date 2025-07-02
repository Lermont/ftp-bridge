# FTP Bridge v2.1.0 🌉

**A professional secure bridge for integrating FTP/SFTP servers with Power BI and analytics systems.**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![Security](https://img.shields.io/badge/Security-Production_Ready-red.svg)](#security)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 Table of Contents

- [Features](#features)
- [Security](#security)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Administrative Utilities](#administrative-utilities)
- [Monitoring](#monitoring)
- [Docker](#docker)
- [Power BI Integration](#power-bi-integration)
- [Troubleshooting](#troubleshooting)

## 🚀 Features

### ✨ New in v2.1.0

- **🔐 SFTP Host Key Verification**: Host key verification for maximum security
- **📡 HEAD Endpoint**: Retrieve file metadata without downloading (for Power BI preflight)
- **🛡️ Path Sanitizer**: Advanced protection against path traversal attacks
- **🔒 PII Masking**: Masking of personal data in logs (email, users)
- **⚡ Auto-Chunk Tuning**: Automatic chunk size optimization for large files
- **🔶 Degraded Mode**: Graceful startup without tokens with limited functionality
- **🏗️ Storage Backend Architecture**: Unified architecture for FTP/FTPS/SFTP
- **🔧 Default Rate Limits**: Built-in 100/minute limits for extra protection

### ✨ Features in v2.0.0

- **🔒 Enhanced Security**: Tokens only via environment variables
- **⚡ Rate Limiting**: Protection from DDoS and abuse with `slowapi`
- **🌐 Secure CORS**: Configurable domains instead of wildcard `*`
- **🔐 SFTP Support**: Encrypted file transfer via paramiko
- **📊 Log Rotation**: Automatic log size management
- **⚙️ Pydantic v2**: Modern configuration validation with BaseSettings
- **🛠️ Advanced Admin Utilities**: Monitoring, diagnostics, maintenance

### 🌟 Core Features

- **Streaming large files** without loading into memory
- **Protocol support**: FTP, FTPS, SFTP
- **RESTful API** with automatic documentation
- **File validation** by extension and size
- **Path Traversal Protection**
- **Detailed logging** with rotation
- **Health Check** endpoints for monitoring
- **Docker Ready** with prebuilt containers

## 🔒 Security

### Critical Security Improvements

**❌ Fixed in v2.0.0:**
- ✅ Hardcoded tokens removed from code
- ✅ Added rate limiting for attack protection
- ✅ CORS configured for specific domains (not `*`)
- ✅ Added SFTP support for encrypted transfer
- ✅ Implemented log rotation
- ✅ Modern secret management with Pydantic v2

### Security Architecture

1. **Token Management** 🔑
   - Tokens only via environment variables
   - Minimum length 32 characters
   - Automatic token strength validation

2. **Rate Limiting** ⚡
   - Configurable request limits
   - DDoS protection
   - IP-based blocking

3. **CORS Policy** 🌐
   - Domain restriction in production
   - Configurable methods and headers
   - Credentials support

4. **File Validation** 📁
   - File extension checks
   - Path traversal protection
   - File size limits

## 🛡️ Security Fixes and Compliance

### Summary of Security Fixes (v2.1.0)

- **Token Storage:** All hardcoded tokens removed; tokens only from environment variables; minimum length 32 characters; automatic validation.
- **Rate Limiting:** Added `slowapi` middleware; default 100/minute; configurable via environment.
- **CORS:** Wildcard `*` removed; customizable via env; separate dev/prod configs; validation in monitoring.
- **SFTP/FTPS:** Full SFTP support with host key verification; FTPS by default; warnings for insecure FTP.
- **Log Rotation:** RotatingFileHandler with configurable size/count; log size monitoring.
- **Secrets Management:** Full transition to Pydantic v2 BaseSettings; .env support; type-level validation.
- **Additional:** Path sanitizer, PII masking in logs, degraded mode, HEAD endpoint, auto-chunk tuning, unified backend architecture.

### Security Architecture (Multi-layered)

1. **Authentication:** Tokens only from environment, min 32 chars, auto validation.
2. **Authorization:** Bearer token, client identification, access logging.
3. **Rate Limiting:** DDoS protection, IP blocking, configurable limits.
4. **CORS Policy:** Domain restriction, secure headers, method control.
5. **Data Validation:** Pydantic v2, file checks, path traversal protection.
6. **Encryption:** SFTP/FTPS support, secure transfer.

### Security Testing

- **Automated:** Path traversal, token validation, rate limiting, CORS, SFTP, HEAD endpoint, degraded mode.
- **Manual:** Penetration testing, brute force protection, file system boundaries, protocol validation.

### Production Security Checklist

1. **Tokens**
   - [ ] Generate unique tokens 32+ characters
   - [ ] Set environment variables
   - [ ] Remove all example tokens
2. **CORS**
   - [ ] Specify exact domains (not "*")
   - [ ] Test access from Power BI
3. **Rate Limiting**
   - [ ] Set limits for your load
   - [ ] Test attack protection
4. **Protocols**
   - [ ] Enable FTPS or SFTP
   - [ ] Test encrypted connections
5. **Monitoring**
   - [ ] Set up health check
   - [ ] Check log rotation

**Additional Measures:**
- Regular token rotation (every 90 days)
- Monitoring rate limiting and security
- Use Docker Secrets in production
- Log auditing for suspicious activity

### Compliance Metrics

- **OWASP Top 10 2021:**
  - A01 Broken Access Control: Resolved by tokens/validation
  - A02 Cryptographic Failures: Resolved by FTPS/SFTP
  - A03 Injection: Resolved by path sanitizer
  - A05 Security Misconfiguration: Resolved by Pydantic v2
  - A07 Identification/Authentication Failures: Resolved by tokens
  - A09 Security Logging: Resolved by PII masking
- **Security Standards:**
  - ISO 27001: Secrets management
  - NIST Cybersecurity Framework: Multi-layered protection
  - PCI DSS: Encrypted data transfer

## 🚀 Quick Start

### 1. Clone and Install
```bash
git clone https://github.com/your-repo/ftp_bridge.git
cd ftp_bridge
pip install -r requirements.txt
```

### 2. Set Up Security Tokens
```bash
# Generate tokens
python -c "import secrets; print('FTP_BRIDGE_TOKEN_POWERBI=' + secrets.token_hex(16))"
python -c "import secrets; print('FTP_BRIDGE_TOKEN_EXCEL=' + secrets.token_hex(16))"

# Create .env file
echo "FTP_BRIDGE_TOKEN_POWERBI=your_generated_token_here" > .env
echo "FTP_BRIDGE_TOKEN_EXCEL=another_generated_token_here" >> .env
```

### 3. Start with Auto-Setup
```bash
python start.py
```

### 4. Test the Service
```bash
curl -H "Authorization: Bearer your_token" \
     "http://localhost:8000/download?host=ftp.example.com&user=demo&password=password&path=/&file=test.txt"
```

## 📦 Installation

### Requirements
- **Python 3.8+**
- **FastAPI 0.104+**
- **Pydantic v2**

### Automatic Installation
```bash
python start.py  # Will check and install dependencies automatically
```

### Manual Installation
```bash
pip install -r requirements.txt
```

### Optional Dependencies
```bash
# For SFTP support
pip install paramiko

# For production
pip install gunicorn
```

## ⚙️ Configuration

### Environment Variables

#### 🔑 Security Tokens (REQUIRED)
```bash
# Client tokens (minimum 32 characters)
FTP_BRIDGE_TOKEN_POWERBI=aabbccdd11223344556677889900aabbccddee
FTP_BRIDGE_TOKEN_EXCEL=1122334455667788990011223344556677889900
FTP_BRIDGE_TOKEN_ANALYTICS=9988776655443322110099887766554433221100
```

#### 🌐 CORS and Security
```bash
# Allowed domains (DO NOT use * in production!)
FTP_BRIDGE_CORS_ORIGINS=https://app.powerbi.com,https://your-domain.com

# Rate limiting
FTP_BRIDGE_RATE_LIMIT_ENABLED=true
FTP_BRIDGE_RATE_LIMIT_REQUESTS=100      # Requests per hour
FTP_BRIDGE_RATE_LIMIT_WINDOW=3600       # Window in seconds
```

#### 🔌 Protocols
```bash
# Default protocol (ftps recommended for security)
FTP_BRIDGE_DEFAULT_PROTOCOL=ftps        # ftp, ftps, sftp

# FTPS settings
FTP_BRIDGE_USE_FTPS=true

# Ports
FTP_BRIDGE_FTP_PORT=21                  # FTP port
FTP_BRIDGE_SFTP_PORT=22                 # SFTP port

# SFTP Host Key Verification (for maximum security)
FTP_BRIDGE_KNOWN_HOSTS_PATH=/home/user/.ssh/known_hosts

# Degraded mode (graceful fallback)
FTP_BRIDGE_DEGRADED_MODE=false
```

#### 📊 Log Rotation
```bash
FTP_BRIDGE_LOG_ROTATION=true
FTP_BRIDGE_LOG_MAX_SIZE=10485760        # 10MB
FTP_BRIDGE_LOG_BACKUP_COUNT=5
```

### Create .env File
```bash
# Copy from template
cp env_example.txt .env

# Edit tokens
nano .env
```

## 🔧 Usage

### API Endpoints

#### File Download
```http
GET /download?host=ftp.example.com&user=demo&password=password&path=/reports/data.xlsx&protocol=ftps
Authorization: Bearer your_token_here
```

#### File Metadata (HEAD) - **New in v2.1.0**
```http
HEAD /download?host=ftp.example.com&user=demo&password=password&path=/reports/data.xlsx&protocol=ftps
Authorization: Bearer your_token_here
```

**Returns headers:**
- `X-File-Size` - File size in bytes
- `X-Protocol` - Protocol used (ftp/ftps/sftp)
- `X-File-Name` - File name
- `Content-Length` - Download size

*Used by Power BI for preflight requests and optimized loading*

#### Parameters
- `host` - FTP/SFTP server
- `user` - Username
- `password` - Password
- `path` - Full file path on the server (including file name)
- `protocol` - `auto`, `ftp`, `ftps`, `sftp` (optional, default is ftps)

#### Health Check
```http
GET /health
```

**Advanced diagnostics v2.1.0:**
```json
{
  "status": "healthy",
  "degraded_mode": false,
  "default_protocol": "ftps",
  "sftp_host_key_verification": true,
  "protocols_available": ["ftp", "ftps", "sftp"]
}
```

#### Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Integration Examples

#### Python requests
```python
import requests

headers = {"Authorization": "Bearer your_token"}
params = {
    "host": "ftp.example.com",
    "user": "demo", 
    "password": "password",
    "path": "/data/report.xlsx",  # Full file path
    "protocol": "ftps"  # Secure FTPS by default
}

# First, get metadata (optional)
head_response = requests.head("http://localhost:8000/download", 
                             headers=headers, params=params)
file_size = head_response.headers.get('X-File-Size')
print(f"File size: {file_size} bytes")

# Download file
response = requests.get("http://localhost:8000/download", 
                       headers=headers, params=params, stream=True)

with open("downloaded_file.xlsx", "wb") as f:
    for chunk in response.iter_content(chunk_size=8192):
        f.write(chunk)
```

#### cURL examples
```bash
# HEAD request for metadata
curl -I -H "Authorization: Bearer your_token" \
     "http://localhost:8000/download?host=ftp.example.com&user=demo&password=password&path=/data/report.xlsx&protocol=ftps"

# Download file
curl -H "Authorization: Bearer your_token" \
     -o downloaded_file.xlsx \
     "http://localhost:8000/download?host=ftp.example.com&user=demo&password=password&path=/data/report.xlsx&protocol=ftps"
```

#### New in v2.1.0
```bash
# Check degraded mode
curl "http://localhost:8000/health" | jq '.degraded_mode'

# Auto-optimization for large files
curl -H "Authorization: Bearer your_token" \
     -I "http://localhost:8000/download?path=/large_file.zip" \
     | grep "X-Auto-Chunk-Tuned"
```

## 🛠️ Administrative Utilities

### Token Management
```bash
# List tokens with security analysis
python admin_utils.py tokens list

# Generate new token
python admin_utils.py tokens generate --length 32 --client "Power BI"

# Validate token
python admin_utils.py tokens validate your_token_here
```

### System Monitoring
```bash
# Full system diagnostics
python admin_utils.py monitor health

# JSON output for automation
python admin_utils.py monitor health --json
```

### Maintenance
```bash
# Clean up old temp files
python admin_utils.py maintenance cleanup --max-age-hours 24

# Validate configuration
python admin_utils.py maintenance validate

# Backup configuration
python admin_utils.py maintenance backup --dir backups
```

## 📊 Monitoring

### Health Check
```json
{
  "status": "healthy",
  "temp_dir": "./temp",
  "temp_dir_exists": true,
  "temp_dir_writable": true,
  "active_tokens": 3,
  "protocols_available": ["ftp", "ftps", "sftp"],
  "rate_limit_enabled": true
}
```

### System Checks
- ✅ Temp directory status
- ✅ Log rotation configuration
- ✅ Settings validation
- ✅ Token security analysis
- ✅ Performance settings

### Testing
```bash
# Comprehensive testing
python test_api.py

# Tests include:
# - Basic endpoints
# - Authentication and tokens
# - Parameter validation
# - Rate limiting
# - CORS headers
# - SFTP support
# - Real file downloads
```

## 🐳 Docker

### Quick Start
```bash
# Build and run
docker-compose up -d

# Set tokens via environment
docker-compose exec ftp-bridge python admin_utils.py tokens generate
```

### Production Setup
```yaml
# docker-compose.prod.yml
services:
  ftp-bridge:
    environment:
      - FTP_BRIDGE_TOKEN_POWERBI=${POWERBI_TOKEN}
      - FTP_BRIDGE_CORS_ORIGINS=https://app.powerbi.com
      - FTP_BRIDGE_RATE_LIMIT_REQUESTS=50
      - FTP_BRIDGE_USE_FTPS=true
```

## 📈 Power BI Integration

### Power Query Example
```m
let
    // Settings
    ApiUrl = "http://your-server:8000/download",
    ApiToken = "your_secure_token_here",
    
    // FTP Parameters
    FtpHost = "ftp.your-company.com",
    FtpUser = "your_user",
    FtpPassword = "your_password",
    FilePath = "/reports/monthly_data.xlsx",
    
    // Build URL
    Url = ApiUrl & "?" & 
          "host=" & FtpHost & 
          "&user=" & FtpUser & 
          "&password=" & FtpPassword & 
          "&path=" & FilePath & 
          "&file=data.xlsx" &
          "&protocol=sftp",
    
    // Authorization headers
    Headers = [
        #"Authorization" = "Bearer " & ApiToken,
        #"Content-Type" = "application/octet-stream"
    ],
    
    // Download file
    Response = Web.Contents(Url, [Headers=Headers]),
    
    // Process Excel file
    Excel = Excel.Workbook(Response),
    Sheet = Excel[Data]{[Item="Sheet1",Kind="Sheet"]}[Data]
in
    Sheet
```

### Power BI Service Setup
1. **Add domain to CORS:**
   ```bash
   FTP_BRIDGE_CORS_ORIGINS=https://app.powerbi.com,https://msit.powerbi.com
   ```

2. **Use HTTPS** in production
3. **Set up auto-refresh** with appropriate limits

## 🚨 Troubleshooting

### Security Issues

#### Tokens not set
```bash
❌ CRITICAL ERROR: No tokens found!

# Solution:
export FTP_BRIDGE_TOKEN_CLIENT1=$(python -c 'import secrets; print(secrets.token_hex(16))')
```

#### CORS errors in browser
```bash
⚠️ CORS allows any domains in production

# Solution:
FTP_BRIDGE_CORS_ORIGINS=https://app.powerbi.com,https://your-domain.com
```

#### Rate limiting triggered
```json
{"detail": "Rate limit exceeded: 100 per 3600 seconds"}
```
Solution: Increase limits or optimize request frequency

### Connection Issues

#### SFTP unavailable
```bash
⚠️ SFTP support unavailable. Install paramiko.

# Solution:
pip install paramiko
```

#### Port issues
```bash
❌ Port 8000 already in use

# Solution:
FTP_BRIDGE_PORT=8001
```

### Diagnostics
```bash
# Full diagnostics
python admin_utils.py monitor health

# Check configuration
python admin_utils.py maintenance validate

# API testing
python test_api.py
```

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

## 🤝 Support

- **Documentation**: [API Docs](http://localhost:8000/docs)
- **Issues**: [GitHub Issues](https://github.com/your-repo/ftp_bridge/issues)
- **Security**: Report vulnerabilities via private channels

## 🔄 Changelog

### v2.0.0 - Security and Performance
- ✨ Pydantic v2 BaseSettings for configuration
- 🔒 Hardcoded tokens removed
- ⚡ Rate limiting with slowapi
- 🌐 Secure CORS for production  
- 🔐 SFTP support via paramiko
- 📊 Log rotation with RotatingFileHandler
- 🛠️ Advanced admin utilities
- 🧪 Comprehensive security testing

### v1.0.0 - First Release
- 🌉 Basic FTP Bridge functionality
- 📡 File streaming via FastAPI
- 🔑 Simple token authentication
- 📖 Automatic API documentation

---

**FTP Bridge v2.0.0** - A professional solution for secure FTP/SFTP integration with analytics systems 🚀 