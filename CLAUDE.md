# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

HanyangAuto is an automated lecture attendance system for Hanyang University's Learning Management System. The system consists of three microservices that work together to automate course completion:

- **back**: Core API service handling user authentication, admin operations, and database management
- **automation**: Selenium-based automation service that executes lecture attendance using headless Chrome
- **front**: FastAPI proxy server serving a React SPA (Single Page Application) with admin dashboard

## Architecture

### Service Communication Flow
1. Users authenticate through the frontend (React SPA)
2. Frontend proxies API requests to the `back` service
3. `back` service triggers automation by calling the `automation` service via HTTP
4. `automation` service uses Selenium to navigate the university LMS and complete lectures
5. Automation results are stored in the SQLite database shared via mounted volumes

### Key Components

**Database Layer** (`utils/database.py`)
- SQLite database with AES-GCM encryption for user passwords
- Tables: `User`, `Admin`, `Learned_Lecture`
- Encryption key must be set via `DB_ENCRYPTION_KEY_B64` environment variable
- Shared across services via Docker volume mount at `/app/data`

**Logging System** (`utils/logger.py`)
- Structured logging with daily rotation
- Log types: 'system', 'user', 'server', 'automation'
- Logs stored in `/app/logs/{date}/{type}/{user_id}/log{n}.log`

**Automation Engine** (`automation/automation.py`)
- Core functions: `login()`, `get_courses()`, `learn_lecture()`
- Uses Selenium WebDriver with Chrome in headless mode
- Handles PDF lectures, video lectures, and file-based content
- Automatic progress tracking and completion verification

**Scheduler** (`automation/main.py`)
- APScheduler with AsyncIO for daily automation at 7:00 AM KST
- Thread pool executor (max 5 concurrent jobs) for parallel user processing
- 15-second stagger delay between user automations to prevent resource spikes

## Development Commands

### Docker Deployment
```bash
# Build and start all services
docker-compose up -d --build

# View logs for specific service
docker-compose logs -f front
docker-compose logs -f back
docker-compose logs -f automation

# Restart a specific service
docker-compose restart automation

# Stop all services
docker-compose down
```

### Frontend Development
```bash
cd front/web

# Install dependencies
npm install

# Run development server (Vite)
npm run dev

# Build client only (React SPA)
npm run build:client

# Build server only
npm run build:server

# Build everything
npm run build

# Type checking
npm run typecheck
```

### Backend Development
```bash
# Run back service locally
cd back
uvicorn main:app --host 0.0.0.0 --port 9000 --reload

# Run automation service locally
cd automation
uvicorn main:app --host 0.0.0.0 --port 7000 --reload

# Run frontend proxy locally
cd front
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Database Encryption Key Setup
```bash
# Generate a new encryption key (must be 32 bytes base64-encoded)
openssl rand -base64 32

# Set in environment or .env file
export DB_ENCRYPTION_KEY_B64="<generated_key>"
```

## Important Technical Details

### Password Encryption
- Uses AES-GCM mode (v2 format: `v2:nonce:ciphertext:tag`)
- Legacy CBC format (`iv:ct`) supported for decryption only
- All new passwords are encrypted with GCM
- Key loaded from `DB_ENCRYPTION_KEY_B64` environment variable

### Selenium Driver Configuration (`utils/selenium_utils.py`)
- Runs in headless mode with Xvfb virtual display (DISPLAY=:99)
- Chrome binary path: `/opt/chrome/chrome`
- ChromeDriver path: `/opt/chromedriver/chromedriver`
- User agent randomization to avoid detection
- Automatic retry logic with configurable wait times

### API Endpoints

**User Endpoints** (`back/main.py`)
- `POST /api/user/login` - User registration/login (triggers automation)
- Authentication triggers immediate automation run via `/on-user-registered`

**Admin Endpoints** (requires session authentication)
- `POST /api/admin/login` - Admin authentication
- `GET /api/admin/check-auth` - Session validation
- `GET /api/admin/users` - List all users with course status
- `DELETE /api/admin/user/{user_id}` - Delete user and learned lectures
- `GET /api/admin/user/{user_id}/logs` - Fetch today's logs for a user
- `POST /api/admin/change-password` - Change admin password
- `POST /api/admin/trigger-all` - Manually trigger automation for all users
- `POST /api/admin/logout` - Clear admin session

**Automation Endpoints** (`automation/main.py`)
- `POST /start-automation` - Queue automation job for a user
- `POST /on-user-registered` - Trigger automation for newly registered user
- `POST /trigger-daily` - Manually trigger daily automation for all users

### Status Values
User status is tracked in the `Status` column of the `User` table:
- `active` - Automation is currently running
- `completed` - Last automation run completed successfully
- `error` - Last automation run encountered an error

### Frontend Routes
- `/` - User login page
- `/success` - Post-login success page
- `/admin/login` - Admin login
- `/admin/dashboard` - Admin dashboard (user management, logs, manual triggers)
- `/admin/change-password` - Admin password change page

## Common Development Workflows

### Adding a New API Endpoint
1. Define the endpoint in `back/main.py`
2. Add authentication dependency if needed: `dependencies=[Depends(get_current_admin)]`
3. Update database functions in `utils/database.py` if database access is required
4. Test with the frontend by adding the API call in the appropriate React component

### Modifying Automation Logic
1. Edit functions in `automation/automation.py`
2. Test changes by triggering automation via admin dashboard
3. Check logs in `/app/logs` for debugging
4. Ensure status updates are called appropriately (`update_user_status()`)

### Debugging Selenium Issues
1. Check automation service logs: `docker-compose logs -f automation`
2. Verify Chrome/ChromeDriver versions are compatible
3. Test selectors in browser DevTools against the university LMS
4. Adjust wait times if elements are slow to load
5. Ensure Xvfb is running (check DISPLAY environment variable)

### Database Schema Changes
1. Modify table definitions in `utils/database.py`
2. Update `init_db()` function to handle migrations if needed
3. Consider backward compatibility with existing encrypted data
4. Test encryption/decryption functions after schema changes

## Environment Variables

Required:
- `DB_ENCRYPTION_KEY_B64` - Base64-encoded 32-byte AES key for password encryption

Optional:
- `RECEIVE_SERVER_URL` - Automation service URL (default: `http://automation:7000`)
- `CORS_ALLOW_ORIGINS` - Comma-separated list of allowed CORS origins
- `SESSION_SECRET_B64` - Base64-encoded session key for admin authentication
- `DOMAIN` - Domain for Traefik routing
- `PORT` - Frontend service port (default: 8000)
- `CONTAINER_NAME` - Docker container prefix
- `DOCKER_IMAGE` - Docker image name prefix

## File Structure

```
.
├── back/               # Core API service
│   ├── main.py        # FastAPI app with user/admin endpoints
│   └── requirements.txt
├── automation/        # Selenium automation service
│   ├── main.py       # Scheduler and HTTP trigger endpoints
│   ├── automation.py # Core automation logic (login, learn_lecture, etc.)
│   └── requirements.txt
├── front/            # Frontend proxy and React SPA
│   ├── main.py       # FastAPI proxy server
│   ├── requirements.txt
│   └── web/          # React application
│       ├── client/   # React source code
│       │   ├── pages/    # Page components
│       │   └── components/
│       ├── dist/spa/ # Built React app (served by proxy)
│       └── package.json
├── utils/            # Shared utilities
│   ├── database.py   # SQLite operations with AES-GCM encryption
│   ├── logger.py     # Structured logging system
│   └── selenium_utils.py # WebDriver initialization and helpers
├── data/             # SQLite database and encryption keys (mounted volume)
├── logs/             # Application logs (mounted volume)
├── docker-compose.yml
├── *.Dockerfile      # Service-specific Dockerfiles
└── genkey.sh         # Encryption key generation script
```

## Network Architecture

- `hanyang-net`: Internal bridge network for service-to-service communication
- `traefik-net`: External network for reverse proxy (production)
- Services expose internal ports: front (8000), back (9000), automation (7000)
- Frontend proxies `/api/*` requests to back service at `back:9000`
- Back service triggers automation via `automation:7000`

## Security Considerations

- User passwords are encrypted with AES-GCM before database storage
- Admin sessions use secure session middleware with HMAC signatures
- Security headers middleware adds HSTS, X-Frame-Options, CSP-equivalent headers
- Default admin credentials (admin/admin) require immediate password change
- Non-root users in all Docker containers (UID 1000)
- CORS configured to restrict cross-origin requests

## Testing Notes

- Frontend uses Vitest for testing: `npm run test`
- Manual testing of automation requires valid university credentials
- Test automation endpoint: `POST /api/admin/trigger-all` from dashboard
- Monitor logs in real-time during testing: `docker-compose logs -f automation`
