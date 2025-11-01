# SSL Setup Complete - Post Installation Steps

Your SSL certificates have been successfully obtained! However, certbot couldn't automatically configure nginx because nginx is running in Docker.

## ✅ Certificates Obtained

Your certificates are saved at:
- Certificate: `/etc/letsencrypt/live/peeq.co.in/fullchain.pem`
- Private Key: `/etc/letsencrypt/live/peeq.co.in/privkey.pem`
- Expires: 2026-01-30

## 🔧 Next Steps to Complete HTTPS Setup

### Step 1: Update Docker Compose Configuration

The `docker-compose.prod.yml` has been updated to mount the host's `/etc/letsencrypt` directory into the nginx container.

**Important**: Make sure the nginx service can read the certificates. You may need to ensure proper permissions.

### Step 2: Update Nginx Configuration

The `nginx/peeq.conf` file has been updated to include HTTPS configuration. The config now:
- Redirects HTTP to HTTPS
- Serves HTTPS on port 443
- Uses the SSL certificates from `/etc/letsencrypt`

### Step 3: Restart Nginx

After updating the configuration, restart nginx:

```bash
docker-compose -f docker-compose.prod.yml restart nginx
```

### Step 4: Test Nginx Configuration

Before restarting, test the configuration:

```bash
docker-compose -f docker-compose.prod.yml exec nginx nginx -t
```

If you see any errors about certificate files not found, check:
1. Certificates exist on host: `sudo ls -la /etc/letsencrypt/live/peeq.co.in/`
2. Nginx can access them (permissions)
3. Docker volume mount is working: `docker-compose -f docker-compose.prod.yml exec nginx ls -la /etc/letsencrypt/live/peeq.co.in/`

### Step 5: Verify HTTPS Works

After restarting nginx, test HTTPS:

```bash
# Test HTTP redirect (should redirect to HTTPS)
curl -I http://peeq.co.in/

# Test HTTPS directly
curl -I https://peeq.co.in/
curl -I https://www.peeq.co.in/
```

Both should return HTTP 200 (not 502 or connection refused).

## 🔄 Certificate Renewal

Since you used certbot on the host (not Docker), certbot has set up auto-renewal on the host. The renewal will work automatically, but you'll need to reload nginx after renewal.

### Option 1: Manual Renewal (Current Setup)

When certificates renew, reload nginx:

```bash
# Test renewal (dry run)
sudo certbot renew --dry-run

# When certificates renew, reload nginx
sudo certbot renew
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

### Option 2: Automated Renewal Hook

Create a renewal hook to automatically reload nginx:

```bash
# Create renewal hook
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh << 'EOF'
#!/bin/bash
docker-compose -f /path/to/shopify_public_app/docker-compose.prod.yml exec nginx nginx -s reload
EOF

sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

**Note**: Update `/path/to/shopify_public_app` with your actual project path.

## 🐛 Troubleshooting

### Issue: "nginx: [emerg] SSL_CTX_use_PrivateKey_file" error

**Cause**: Nginx cannot read certificate files.

**Solution**:
```bash
# Check if certificates exist on host
sudo ls -la /etc/letsencrypt/live/peeq.co.in/

# Check if nginx container can see them
docker-compose -f docker-compose.prod.yml exec nginx ls -la /etc/letsencrypt/live/peeq.co.in/

# If not visible, check Docker volume mount
docker-compose -f docker-compose.prod.yml exec nginx mount | grep letsencrypt
```

### Issue: "403 Forbidden" or permission errors

**Cause**: Nginx user doesn't have permission to read certificates.

**Solution**: Ensure certificates are readable:
```bash
# Check permissions on host
sudo ls -la /etc/letsencrypt/live/peeq.co.in/

# Certificates should be readable (not world-readable for security, but readable by root)
# If needed, fix permissions:
sudo chmod 644 /etc/letsencrypt/live/peeq.co.in/fullchain.pem
sudo chmod 600 /etc/letsencrypt/live/peeq.co.in/privkey.pem
```

### Issue: HTTP redirects but HTTPS returns 502

**Cause**: App service is not running or not accessible.

**Solution**:
```bash
# Check app service
docker-compose -f docker-compose.prod.yml ps app

# Check app logs
docker-compose -f docker-compose.prod.yml logs app

# Restart app if needed
docker-compose -f docker-compose.prod.yml restart app
```

## ✅ Verification Checklist

After completing setup, verify:

- [ ] HTTP redirects to HTTPS: `curl -I http://peeq.co.in/`
- [ ] HTTPS works: `curl -I https://peeq.co.in/`
- [ ] www subdomain works: `curl -I https://www.peeq.co.in/`
- [ ] Browser shows valid certificate (green lock icon)
- [ ] App loads correctly via HTTPS
- [ ] No SSL/TLS errors in browser console

## 📝 Update Environment Variables

After HTTPS is working, update your `.env` file:

```bash
# Edit .env
nano .env

# Update this line:
SHOPIFY_REDIRECT_URI=https://peeq.co.in/auth/callback

# Restart app service
docker-compose -f docker-compose.prod.yml restart app
```

## 🎉 Success!

Once HTTPS is working, your Shopify app is ready for production!

