# Vercel Deployment Guide

## Quick Deployment Steps

### 1. Install Vercel CLI
```bash
npm install -g vercel
```

### 2. Login to Vercel
```bash
vercel login
```

### 3. Deploy
```bash
vercel
```

Follow the prompts:
- **Set up and deploy?** `Yes`
- **Which scope?** Select your account
- **Link to existing project?** `No`
- **What's your project's name?** `hifi-api` (or your preferred name)
- **In which directory is your code located?** `./` (current directory)
- **Want to modify these settings?** `No`

### 4. Set Environment Variables
After initial deployment, set your Tidal credentials:

```bash
vercel env add CLIENT_ID
vercel env add CLIENT_SECRET
vercel env add USER_ID
vercel env add REFRESH_TOKEN
vercel env add COUNTRY_CODE
```

For optional catalog credentials:
```bash
vercel env add CATALOG_CLIENT_ID
vercel env add CATALOG_CLIENT_SECRET
vercel env add CATALOG_REFRESH_TOKEN
vercel env add CATALOG_USER_ID
```

For proxy configuration (optional):
```bash
vercel env add USE_PROXIES
vercel env add PROXIES_FILE
```

### 5. Redeploy with Environment Variables
```bash
vercel --prod
```

## Alternative: Using Vercel Dashboard

1. Push your code to GitHub
2. Import project in Vercel Dashboard
3. Configure environment variables in project settings
4. Deploy

## Important Notes

### Serverless Considerations
- **Cold Starts**: First request may be slower (Vercel spins up function)
- **Stateless**: Each request is independent, no persistent state
- **Time Limits**: Vercel functions have execution time limits (10s for Hobby, 60s for Pro)
- **Memory**: Limited memory allocation (1024MB for Hobby, 3072MB for Pro)

### Tidal Account Safety
- **WARNING**: Tidal may block accounts using this API
- **IP Exposure**: Using Vercel may expose your Vercel IP to Tidal
- **Proxy Support**: Configure proxies in environment variables if needed
- **Rate Limiting**: Vercel has built-in rate limiting, but Tidal's limits still apply

### Environment Variables Reference
```
CLIENT_ID=your_tidal_client_id
CLIENT_SECRET=your_tidal_client_secret
USER_ID=your_tidal_user_id
REFRESH_TOKEN=your_tidal_refresh_token
COUNTRY_CODE=US
CATALOG_CLIENT_ID=optional_catalog_client_id
CATALOG_CLIENT_SECRET=optional_catalog_client_secret
CATALOG_REFRESH_TOKEN=optional_catalog_refresh_token
CATALOG_USER_ID=optional_catalog_user_id
USE_PROXIES=False
PROXIES_FILE=proxies.txt
DEV_MODE=False
USER_AGENT=okhttp/5.3.2
```

### Testing Your Deployment
```bash
# Test root endpoint
curl https://your-project.vercel.app/

# Test track info
curl https://your-project.vercel.app/info/?id=194567102

# Test search
curl https://your-project.vercel.app/search/?s=daft+punk
```

## Troubleshooting

### Build Failures
- Ensure `requirements-vercel.txt` contains all dependencies
- Check Python version compatibility (Vercel uses Python 3.9+)

### Runtime Errors
- Verify all environment variables are set
- Check Vercel function logs for specific errors
- Ensure Tidal credentials are valid

### Performance Issues
- Consider upgrading to Vercel Pro for longer timeouts
- Optimize your API calls to reduce response time
- Use Vercel Edge Network caching where possible

## File Structure for Vercel
```
hifi-api/
├── api/
│   └── index.py          # Vercel entry point
├── main.py               # Main FastAPI application
├── requirements-vercel.txt # Dependencies for Vercel
├── vercel.json           # Vercel configuration
├── .vercelignore         # Files to exclude
└── .env.example          # Environment variable template
```

## Cost Considerations
- **Vercel Hobby**: Free tier with limitations
- **Vercel Pro**: $20/month for better performance
- **Bandwidth**: Included in both tiers, overages charged
- **Function Execution**: Free tier has limits, Pro offers more

## Security Recommendations
- Use Vercel Environment Variables for sensitive data
- Never commit `.env` or `token.json` to git
- Consider adding authentication to your API
- Use Vercel's built-in security features
