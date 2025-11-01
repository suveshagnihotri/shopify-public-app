# SSL Certificate Installation - Quick Guide

This guide provides step-by-step instructions to install SSL certificates for `peeq.co.in`.

## Quick Start (Automated)

```bash
# On your EC2 server, run:
cd /path/to/shopify_public_app
./scripts/install_ssl.sh
```

The script will handle everything automatically. If it succeeds, you're done! ✅

## Manual Installation (Step-by-Step)

If you prefer to install manually or the script fails, follow these steps:

### Step 1: Verify Services Are Running

```bash
# Check all services
docker-compose -f docker-compose.prod.yml ps

# Should show nginx, app, redis, db all "Up"
```

### Step 2: Test ACME Challenge Path

```bash
# Create test file
docker-compose -f docker-compose.prod.yml exec nginx sh -c 'mkdir -p /var/www/certbot/.well-known/acme-challenge/ && echo "test-123" > /var/www/certbot/.well-known/acme-challenge/test'

# Test if accessible
curl http://peeq.co.in/.well-known/acme-challenge/test
curl http://www.peeq.co.in/.well-known/acme-challenge/test

# Both should return: test-123

# Clean up
docker-compose -f docker-compose.prod.yml exec nginx rm -f /var/www/certbot/.well-known/acme-challenge/test
```

### Step 3: Install SSL Certificate

```bash
docker-compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email suveshagnihotri145@gmail.com \
  --agree-tos \
  --no-eff-email \
  -d peeq.co.in \
  -d www.peeq.co.in
```

**Expected Output:**
```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/peeq.co.in/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/peeq.co.in/privkey.pem
```

### Step 4: Update Nginx Configuration

```bash
# Copy HTTPS configuration
cp nginx/peeq.conf.https nginx/peeq.conf

# Test nginx config
docker-compose -f docker-compose.prod.yml exec nginx nginx -t

# Restart nginx
docker-compose -f docker-compose.prod.yml restart nginx
```

### Step 5: Verify HTTPS Works

```bash
# Test HTTP (should redirect to HTTPS)
curl -I http://peeq.co.in/
# Should see: HTTP/1.1 301 Moved Permanently

# Test HTTPS
curl -I https://peeq.co.in/
curl -I https://www.peeq.co.in/
# Should see: HTTP/1.1 200 OK
```

### Step 6: Update Environment Variables

After HTTPS is working, update your `.env` file:

```bash
# Edit .env
nano .env

# Update these values:
SHOPIFY_REDIRECT_URI=https://peeq.co.in/auth/callback

# Restart app service
docker-compose -f docker-compose.prod.yml restart app
```

### Step 7: Set Up Auto-Renewal

Add to crontab for automatic certificate renewal:

```bash
# Edit crontab
crontab -e

# Add this line (adjust path to your project directory)
0 2 * * * cd /path/to/shopify_public_app && ./scripts/renew_ssl.sh >> /var/log/ssl-renewal.log 2>&1
```

## Troubleshooting

### Issue: "Connection refused" during certbot challenge

**Solution:**
- Check AWS Security Group allows inbound traffic on port 80
- Verify DNS A record points to your EC2 server IP
- Test: `curl -I http://peeq.co.in/` should work

### Issue: "Failed to authenticate some domains"

**Solution:**
- Verify Step 2 works (test file is accessible)
- Check nginx config has correct ACME challenge location block
- Ensure `certbot_www` volume is shared between nginx and certbot

### Issue: HTTPS doesn't work after installing certificates

**Solution:**
- Verify Step 4 completed (nginx config updated)
- Check nginx logs: `docker-compose -f docker-compose.prod.yml logs nginx`
- Ensure certificate paths in nginx config are correct

### Issue: "nginx: [emerg] SSL_CTX_use_PrivateKey_file"

**Solution:**
```bash
# Verify certificates exist
docker-compose -f docker-compose.prod.yml run --rm certbot certificates

# Check paths in nginx/peeq.conf match certbot output
```

## Verification Checklist

After installation, verify:

- [ ] HTTP redirects to HTTPS: `curl -I http://peeq.co.in/`
- [ ] HTTPS works: `curl -I https://peeq.co.in/`
- [ ] www subdomain works: `curl -I https://www.peeq.co.in/`
- [ ] Browser shows valid certificate (green lock icon)
- [ ] App loads correctly via HTTPS
- [ ] OAuth flow works (Shopify redirects use HTTPS)

## Certificate Information

**Certificate Location:**
- Full chain: `/etc/letsencrypt/live/peeq.co.in/fullchain.pem`
- Private key: `/etc/letsencrypt/live/peeq.co.in/privkey.pem`

**Validity:**
- Certificates expire every 90 days
- Auto-renewal runs daily (if cron job is set up)
- Renewal happens automatically when within 30 days of expiration

**Check Expiration:**
```bash
docker-compose -f docker-compose.prod.yml run --rm certbot certificates
```

