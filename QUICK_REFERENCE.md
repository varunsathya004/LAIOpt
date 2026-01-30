# LAIOpt Quick Reference Card

## Quick Start Commands

### Local Deployment
```bash
# Linux/Mac
./deploy.sh

# Windows
deploy.bat
```

### Docker Deployment
```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Restart
docker-compose restart
```

## Access URLs

- **Local:** http://localhost:8501
- **Network:** http://your-ip:8501

## Common Tasks

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Manually
```bash
streamlit run laiopt/frontend/app.py
```

### Run on Custom Port
```bash
streamlit run laiopt/frontend/app.py --server.port=8080
```

### Check Health
```bash
curl http://localhost:8501/_stcore/health
```

## File Locations

- **Application:** `laiopt/frontend/app.py`
- **Data:** `laiopt/data/`
- **Config:** `.streamlit/config.toml`
- **Backend:** `laiopt/backend/`

## Troubleshooting

### Port in Use
```bash
# Find process
lsof -i :8501  # Linux/Mac
netstat -ano | findstr :8501  # Windows

# Use different port
streamlit run laiopt/frontend/app.py --server.port=8502
```

### Module Not Found
```bash
source venv/bin/activate  # Activate venv
pip install -r requirements.txt  # Reinstall
```

### Docker Issues
```bash
docker system prune -a  # Clean up
docker-compose build --no-cache  # Rebuild
```

## Production Setup (Linux)

### Install as System Service
```bash
sudo cp laiopt.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable laiopt
sudo systemctl start laiopt
sudo systemctl status laiopt
```

### Service Commands
```bash
sudo systemctl start laiopt    # Start
sudo systemctl stop laiopt     # Stop
sudo systemctl restart laiopt  # Restart
sudo systemctl status laiopt   # Check status
journalctl -u laiopt -f        # View logs
```

## Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## Performance Tips

1. **Increase Memory:**
   - Docker: Settings > Resources > Memory (8GB+)
   - EC2: Use t2.large or larger

2. **Optimize Configuration:**
   ```toml
   # .streamlit/config.toml
   [server]
   maxUploadSize = 200
   maxMessageSize = 200
   
   [runner]
   magicEnabled = false
   ```

3. **Monitor Resources:**
   ```bash
   # CPU/Memory usage
   docker stats laiopt-app
   ```

## Security Checklist

- [ ] Use HTTPS in production
- [ ] Set up firewall rules
- [ ] Regular updates: `pip install -r requirements.txt --upgrade`
- [ ] Backup data directory
- [ ] Monitor logs
- [ ] Use authentication (add reverse proxy with auth)

## Data Backup

```bash
# Backup data directory
tar -czf laiopt-data-backup-$(date +%Y%m%d).tar.gz laiopt/data/

# Restore
tar -xzf laiopt-data-backup-YYYYMMDD.tar.gz
```

## Environment Variables

```bash
# Set in .env file
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
```

## Logs

### View Application Logs
```bash
# Local deployment
tail -f nohup.out

# Docker
docker logs -f laiopt-app

# Systemd service
journalctl -u laiopt -f
```

## Update Application

```bash
git pull origin main
pip install -r requirements.txt --upgrade
# Restart application
```

## Network Configuration

### Allow Port Through Firewall
```bash
# UFW (Ubuntu)
sudo ufw allow 8501

# Firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=8501/tcp
sudo firewall-cmd --reload
```

## Resources

- Documentation: DEPLOYMENT_GUIDE.md
- Project Context: MASTER_PROJECT_CONTEXT.md
- Streamlit Docs: https://docs.streamlit.io
- Docker Docs: https://docs.docker.com

---
**Version:** 1.0 | **Last Updated:** January 2026
