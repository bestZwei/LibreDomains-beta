const axios = require('axios');

class CloudflareTokenValidator {
  constructor(token) {
    this.token = token;
    this.baseURL = 'https://api.cloudflare.com/client/v4';
  }

  async validateToken() {
    if (!this.token) {
      return {
        valid: false,
        error: 'Cloudflare API token is not provided',
        suggestion: 'Please set CLOUDFLARE_API_TOKEN environment variable or provide token as argument'
      };
    }

    // Check token format
    if (!this.token.match(/^[A-Za-z0-9_-]{40}$/)) {
      return {
        valid: false,
        error: 'Invalid token format',
        suggestion: 'Cloudflare API tokens should be 40 characters long containing only letters, numbers, underscores and hyphens'
      };
    }

    try {
      // Test token by getting user details - use correct endpoint
      const response = await axios.get(`${this.baseURL}/user/tokens/verify`, {
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        },
        timeout: 10000 // 10 second timeout
      });

      if (response.data.success) {
        const result = response.data.result;
        
        // Check required permissions
        const requiredPermissions = [
          'zone:read',
          'dns_records:edit'
        ];
        
        const tokenPermissions = result.policies?.map(p => 
          p.permission_groups?.map(pg => pg.id || pg.name)
        ).flat().filter(Boolean) || [];
        
        const missingPermissions = requiredPermissions.filter(perm => 
          !tokenPermissions.some(tp => tp.toLowerCase().includes(perm.split(':')[0]) && 
                                       tp.toLowerCase().includes(perm.split(':')[1]))
        );
        
        if (missingPermissions.length > 0) {
          return {
            valid: false,
            error: 'Token lacks required permissions',
            missingPermissions,
            currentPermissions: tokenPermissions,
            suggestion: `Token is missing required permissions: ${missingPermissions.join(', ')}. Please ensure your token has:\n  • Zone:Zone:Read (to access zone information)\n  • Zone:DNS:Edit (to create, update, and delete DNS records)\n  • Include all zones you want to manage in the token scope`
          };
        }
        
        return {
          valid: true,
          tokenInfo: {
            id: result.id,
            status: result.status,
            permissions: tokenPermissions,
            expires_on: result.expires_on || 'Never',
            requiredPermissions: requiredPermissions,
            hasAllPermissions: missingPermissions.length === 0
          }
        };
      } else {
        return {
          valid: false,
          error: 'Token verification failed',
          details: response.data.errors,
          suggestion: 'Token exists but failed verification. Check if token has been revoked.'
        };
      }
    } catch (error) {
      if (error.response) {
        const status = error.response.status;
        const data = error.response.data;
        
        if (status === 401) {
          return {
            valid: false,
            error: 'Invalid Cloudflare API token (401 Unauthorized)',
            suggestion: 'Token is invalid, expired, or revoked. Please:\n  1. Generate a new token at https://dash.cloudflare.com/profile/api-tokens\n  2. Create "Custom token" with required permissions:\n     • Zone:Zone:Read (to access zone information)\n     • Zone:DNS:Edit (to manage DNS records)\n  3. Include all zones you want to manage in "Zone Resources"\n  4. Update the CLOUDFLARE_API_TOKEN secret in GitHub'
          };
        } else if (status === 403) {
          return {
            valid: false,
            error: 'Insufficient permissions for Cloudflare API token (403 Forbidden)',
            suggestion: 'Token lacks required permissions. Please:\n  1. Edit token at https://dash.cloudflare.com/profile/api-tokens\n  2. Ensure these permissions are granted:\n     • Zone:Zone:Read (to access zone information)\n     • Zone:DNS:Edit (to create, update, delete DNS records)\n  3. Verify "Zone Resources" includes all zones you want to manage:\n     • Include:All zones (recommended)\n     • Or Include:Specific zone for each domain\n  4. Save token changes'
          };
        } else if (status === 429) {
          return {
            valid: false,
            error: 'Rate limit exceeded (429 Too Many Requests)',
            suggestion: 'Too many API requests. Wait a few minutes and try again.'
          };
        } else {
          return {
            valid: false,
            error: `Cloudflare API error (${status})`,
            details: data?.errors || [error.message],
            suggestion: 'Unexpected API error. Check Cloudflare status page.'
          };
        }
      } else if (error.code === 'ENOTFOUND' || error.code === 'ECONNREFUSED') {
        return {
          valid: false,
          error: `Network connection error: ${error.code}`,
          suggestion: 'Cannot reach Cloudflare API. Check internet connection and DNS settings.'
        };
      } else if (error.code === 'ECONNRESET' || error.code === 'ETIMEDOUT') {
        return {
          valid: false,
          error: `Connection timeout: ${error.code}`,
          suggestion: 'Request timed out. This might be a temporary network issue, try again.'
        };
      } else {
        return {
          valid: false,
          error: `Network error: ${error.message}`,
          suggestion: 'Unexpected network error. Check your connection and try again.'
        };
      }
    }
  }

  async checkZonePermissions(zoneName) {
    if (!this.token) {
      return { hasPermission: false, error: 'No token provided' };
    }

    try {
      // Get zones to check if token has access
      const response = await axios.get(`${this.baseURL}/zones?name=${zoneName}`, {
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.data.success && response.data.result.length > 0) {
        return {
          hasPermission: true,
          zone: response.data.result[0]
        };
      } else {
        return {
          hasPermission: false,
          error: `Zone ${zoneName} not found or no access permission`
        };
      }
    } catch (error) {
      return {
        hasPermission: false,
        error: `Failed to check zone permissions: ${error.message}`
      };
    }
  }
}

module.exports = CloudflareTokenValidator;

// CLI usage
if (require.main === module) {
  const token = process.env.CLOUDFLARE_API_TOKEN || process.argv[2];
  const zoneName = process.argv[3];
  
  if (!token) {
    console.error('❌ Usage: node validate-cloudflare-token.js [token] [zone_name]');
    console.error('   Or set CLOUDFLARE_API_TOKEN environment variable');
    console.error('');
    console.error('🔧 Required Cloudflare API Token Permissions:');
    console.error('   • Zone:Zone:Read - Access zone information');
    console.error('   • Zone:DNS:Edit - Create, update, delete DNS records');
    console.error('');
    console.error('📝 To create the token:');
    console.error('   1. Go to https://dash.cloudflare.com/profile/api-tokens');
    console.error('   2. Click "Create Token"');
    console.error('   3. Use "Custom token" template');
    console.error('   4. Add permissions:');
    console.error('      - Zone:Zone:Read');
    console.error('      - Zone:DNS:Edit');
    console.error('   5. Zone Resources: Include All zones (or specific zones)');
    console.error('   6. IP Address Filtering: Optional (for security)');
    console.error('   7. TTL: Optional (token expiration)');
    process.exit(1);
  }

  (async () => {
    try {
      const validator = new CloudflareTokenValidator(token);
      
      console.log('🔍 Validating Cloudflare API token...');
      console.log(`📋 Token preview: ${token.substring(0, 8)}...${token.substring(token.length - 4)}`);
      
      const tokenResult = await validator.validateToken();
      
      if (!tokenResult.valid) {
        console.error('❌ Token validation failed:', tokenResult.error);
        if (tokenResult.details) {
          console.error('📝 Details:', tokenResult.details);
        }
        if (tokenResult.suggestion) {
          console.error('💡 Suggestion:', tokenResult.suggestion);
        }
        process.exit(1);
      }
      
      console.log('✅ Token is valid');
      console.log('📊 Token info:', tokenResult.tokenInfo);
      
      if (zoneName) {
        console.log(`\n🔍 Checking permissions for zone: ${zoneName}`);
        const zoneResult = await validator.checkZonePermissions(zoneName);
        
        if (!zoneResult.hasPermission) {
          console.error('❌ Zone permission check failed:', zoneResult.error);
          process.exit(1);
        }
        
        console.log('✅ Zone access confirmed');
        console.log('🆔 Zone ID:', zoneResult.zone.id);
      }
      
      process.exit(0);
    } catch (error) {
      console.error('💥 Unexpected error:', error.message);
      process.exit(1);
    }
  })();
}
