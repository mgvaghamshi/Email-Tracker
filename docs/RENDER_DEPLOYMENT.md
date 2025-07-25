# 🚀 Render Deployment Guide for EmailTracker API

## Quick Start for Render Free Tier

### 📋 Pre-Deployment Setup

1. **Prepare Repository**
   ```bash
   # Make sure all files are committed
   git add .
   git commit -m "Prepare for Render deployment"
   git push origin main
   ```

2. **Environment Variables** (Set in Render Dashboard)
   ```
   ENVIRONMENT=production
   DEBUG=false
   SECRET_KEY=your-very-secure-secret-key-here
   SMTP_USERNAME=mgtechno0001@gmail.com
   SMTP_PASSWORD=vjft ucbi erbf jnkl
   DEFAULT_FROM_EMAIL=noreply@coldegeai.com
   SENDER_NAME=ColdEdge AI
   ```

### 🌐 Step-by-Step Render Deployment

#### Step 1: Create Render Account
1. Go to [render.com](https://render.com)
2. Sign up with GitHub
3. Connect your repository

#### Step 2: Create PostgreSQL Database (Optional but Recommended)
1. Click "New PostgreSQL"
2. Name: `emailtracker-db`
3. Database Name: `email_tracker`
4. User: `emailtracker_user`
5. Region: Choose closest to your users
6. Plan: Free tier
7. Click "Create Database"
8. **Copy the Internal Database URL** (starts with `postgresql://`)

#### Step 3: Create Web Service
1. Click "New Web Service"
2. Connect your GitHub repository
3. Choose your EmailTracker repository
4. Configure:
   - **Name**: `emailtracker-api`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py` (Render will auto-detect this)
   - **Plan**: Free

#### Step 4: Environment Variables
Add these in Render dashboard under "Environment":

**Required Variables:**
```
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=YOUR_SUPER_SECURE_SECRET_KEY_HERE_64_CHARS_MIN
DATABASE_URL=postgresql://... (from Step 2)
```

**Email Configuration:**
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=mgtechno0001@gmail.com
SMTP_PASSWORD=vjft ucbi erbf jnkl
SMTP_USE_TLS=true
DEFAULT_FROM_EMAIL=noreply@coldegeai.com
DEFAULT_FROM_NAME=ColdEdge AI
SENDER_NAME=ColdEdge AI
```

**Security & Features:**
```
CORS_ORIGINS=["https://your-frontend-domain.com"]
RATE_LIMIT_ENABLED=true
TRACKING_PIXEL_ENABLED=true
ENABLE_DOCS=true
```

#### Step 5: Deploy
1. Click "Create Web Service"
2. Render will automatically build and deploy
3. Monitor logs for any issues
4. Your API will be available at: `https://your-app-name.onrender.com`

### 🔗 Important URLs After Deployment

- **API Base**: `https://your-app-name.onrender.com`
- **Health Check**: `https://your-app-name.onrender.com/health`
- **API Docs**: `https://your-app-name.onrender.com/docs`
- **ReDoc**: `https://your-app-name.onrender.com/redoc`

### 🧪 Testing Your Deployment

#### 1. Health Check
```bash
curl https://your-app-name.onrender.com/health
```

#### 2. Create API Key
```bash
curl -X POST "https://your-app-name.onrender.com/api/v1/auth/api-keys" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Key", "rate_limit": 1000}'
```

#### 3. Send Test Email
```bash
curl -X POST "https://your-app-name.onrender.com/api/v1/emails/send" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "to_email": "test@example.com",
    "from_email": "noreply@coldegeai.com",
    "subject": "Test from Render",
    "html_content": "<h1>Hello from Render!</h1>"
  }'
```

### 📁 Files Created for Render

```
emailtracker/
├── app.py                    # ✅ Auto-detected entry point
├── start.sh                  # ✅ Alternative startup script
├── render.yaml              # ✅ Infrastructure as code
├── .env.render              # ✅ Render environment template
└── requirements.txt         # ✅ Dependencies
```

### 🚨 Render Free Tier Limitations

1. **Sleep Mode**: Service sleeps after 15 min of inactivity
2. **Build Time**: 500 hours/month build time limit
3. **Memory**: 512MB RAM limit
4. **Database**: 1GB PostgreSQL storage
5. **Custom Domain**: Not available on free tier

### 🔧 Common Issues & Solutions

#### Issue 1: Build Fails
```bash
# Check requirements.txt is valid
pip install -r requirements.txt

# Make sure all imports work
python -c "from app.main import app; print('OK')"
```

#### Issue 2: Database Connection Error
- Verify DATABASE_URL is set correctly
- Check PostgreSQL database is created
- Ensure database user has permissions

#### Issue 3: Application Won't Start
- Check Render logs in dashboard
- Verify PORT environment variable usage
- Test locally first: `python app.py`

#### Issue 4: SMTP Errors
- Use Gmail App Password instead of regular password
- Enable 2FA and create App Password
- Test SMTP settings locally first

### 📈 Scaling Beyond Free Tier

When ready to upgrade:

1. **Paid Plan Benefits**:
   - No sleep mode
   - More resources
   - Custom domains
   - Multiple environments

2. **Database Scaling**:
   - Larger PostgreSQL instances
   - Redis add-on for caching
   - Database replicas

3. **Advanced Features**:
   - CDN integration
   - Load balancers
   - Auto-scaling

### 🛡️ Security Checklist for Production

- [ ] Strong SECRET_KEY (64+ characters)
- [ ] Restrict CORS origins to your domains
- [ ] Use environment variables for all secrets
- [ ] Enable rate limiting
- [ ] Monitor logs for suspicious activity
- [ ] Use HTTPS only (Render provides this free)

### 📞 Support Resources

- **Render Docs**: https://render.com/docs
- **Render Status**: https://status.render.com
- **Community**: https://community.render.com

### 🎯 Success Checklist

After deployment, verify:
- [ ] Health endpoint returns 200
- [ ] Can create API keys
- [ ] Can send emails
- [ ] Documentation accessible
- [ ] Database operations work
- [ ] Logs show no errors

Your EmailTracker API is now live on Render! 🎉
