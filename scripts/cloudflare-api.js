const axios = require('axios');
const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

class CloudflareAPI {
  constructor() {
    this.apiToken = process.env.CLOUDFLARE_API_TOKEN;
    this.baseURL = 'https://api.cloudflare.com/client/v4';
    this.domainsConfig = yaml.load(fs.readFileSync(path.join(__dirname, '../config/domains.yml'), 'utf8'));
    
    if (!this.apiToken) {
      throw new Error('CLOUDFLARE_API_TOKEN environment variable is required. Please set it in your environment or GitHub secrets.');
    }

    // Validate token format - allow longer tokens as well
    if (!this.apiToken.match(/^[A-Za-z0-9_-]{32,}$/)) {
      throw new Error('Invalid Cloudflare API token format. Token should be at least 32 characters long.');
    }
  }

  async createDNSRecord(domain, subdomain, record) {
    const domainConfig = this.domainsConfig.domains[domain];
    if (!domainConfig) {
      throw new Error(`Domain ${domain} not found in configuration`);
    }

    const zoneId = domainConfig.cloudflare_zone_id;
    const recordName = subdomain ? `${subdomain}.${domain}` : domain;

    const recordData = {
      type: record.type,
      name: recordName,
      content: record.value,
      ttl: record.ttl || 3600,
      proxied: record.proxied || false
    };

    if (record.type === 'MX' && record.priority) {
      recordData.priority = record.priority;
    }

    try {
      const response = await axios.post(
        `${this.baseURL}/zones/${zoneId}/dns_records`,
        recordData,
        {
          headers: {
            'Authorization': `Bearer ${this.apiToken}`,
            'Content-Type': 'application/json'
          },
          timeout: 15000 // 15 second timeout
        }
      );

      if (response.data.success) {
        return response.data.result;
      } else {
        throw new Error(`Cloudflare API error: ${JSON.stringify(response.data.errors)}`);
      }
    } catch (error) {
      if (error.response?.status === 401) {
        throw new Error(`Cloudflare API authentication failed. Please check if your API token is valid and not expired. Token preview: ${this.apiToken.substring(0, 8)}...${this.apiToken.substring(this.apiToken.length - 4)}`);
      }
      
      if (error.response?.status === 403) {
        throw new Error(`Cloudflare API permission denied. Your token lacks required permissions for zone ${zoneId}. Please ensure your token has Zone:Read and DNS:Edit permissions.`);
      }

      if (error.response?.status === 400 && error.response?.data?.errors) {
        const cfError = error.response.data.errors[0];
        
        // Handle proxied record with private IP error
        if (cfError.code === 9003 && recordData.proxied) {
          console.log(`⚠️  Private IP detected with proxy enabled, retrying without proxy...`);
          recordData.proxied = false;
          
          try {
            const retryResponse = await axios.post(
              `${this.baseURL}/zones/${zoneId}/dns_records`,
              recordData,
              {
                headers: {
                  'Authorization': `Bearer ${this.apiToken}`,
                  'Content-Type': 'application/json'
                },
                timeout: 15000
              }
            );

            if (retryResponse.data.success) {
              console.log(`✅ Record created successfully without proxy`);
              return retryResponse.data.result;
            }
          } catch (retryError) {
            console.error(`❌ Retry failed:`, retryError.response?.data || retryError.message);
          }
        }
        
        throw new Error(`Cloudflare API error (${cfError.code}): ${cfError.message}`);
      }
      
      if (error.code === 'ENOTFOUND' || error.code === 'ECONNREFUSED') {
        throw new Error(`Network connection error: Cannot reach Cloudflare API (${error.code}). Check internet connection.`);
      }
      
      if (error.code === 'ETIMEDOUT') {
        throw new Error(`Request timeout: Cloudflare API did not respond within 15 seconds. This might be a temporary issue.`);
      }
      
      if (error.response) {
        throw new Error(`Cloudflare API error: ${error.response.status} - ${JSON.stringify(error.response.data)}`);
      }
      throw error;
    }
  }

  async updateDNSRecord(domain, subdomain, record, recordId) {
    const domainConfig = this.domainsConfig.domains[domain];
    const zoneId = domainConfig.cloudflare_zone_id;
    const recordName = subdomain ? `${subdomain}.${domain}` : domain;

    const recordData = {
      type: record.type,
      name: recordName,
      content: record.value,
      ttl: record.ttl || 3600,
      proxied: record.proxied || false
    };

    if (record.type === 'MX' && record.priority) {
      recordData.priority = record.priority;
    }

    try {
      const response = await axios.put(
        `${this.baseURL}/zones/${zoneId}/dns_records/${recordId}`,
        recordData,
        {
          headers: {
            'Authorization': `Bearer ${this.apiToken}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.data.success) {
        return response.data.result;
      } else {
        throw new Error(`Cloudflare API error: ${JSON.stringify(response.data.errors)}`);
      }
    } catch (error) {
      if (error.response?.status === 400 && error.response?.data?.errors) {
        const cfError = error.response.data.errors[0];
        
        // Handle proxied record with private IP error
        if (cfError.code === 9003 && recordData.proxied) {
          console.log(`⚠️  Private IP detected with proxy enabled, retrying without proxy...`);
          recordData.proxied = false;
          
          try {
            const retryResponse = await axios.put(
              `${this.baseURL}/zones/${zoneId}/dns_records/${recordId}`,
              recordData,
              {
                headers: {
                  'Authorization': `Bearer ${this.apiToken}`,
                  'Content-Type': 'application/json'
                }
              }
            );

            if (retryResponse.data.success) {
              console.log(`✅ Record updated successfully without proxy`);
              return retryResponse.data.result;
            }
          } catch (retryError) {
            console.error(`❌ Retry failed:`, retryError.response?.data || retryError.message);
          }
        }
        
        throw new Error(`Cloudflare API error (${cfError.code}): ${cfError.message}`);
      }
      
      if (error.response) {
        throw new Error(`Cloudflare API error: ${error.response.status} - ${JSON.stringify(error.response.data)}`);
      }
      throw error;
    }
  }

  async deleteDNSRecord(domain, recordId) {
    const domainConfig = this.domainsConfig.domains[domain];
    const zoneId = domainConfig.cloudflare_zone_id;

    try {
      const response = await axios.delete(
        `${this.baseURL}/zones/${zoneId}/dns_records/${recordId}`,
        {
          headers: {
            'Authorization': `Bearer ${this.apiToken}`,
            'Content-Type': 'application/json'
          }
        }
      );

      return response.data.success;
    } catch (error) {
      if (error.response) {
        throw new Error(`Cloudflare API error: ${error.response.status} - ${JSON.stringify(error.response.data)}`);
      }
      throw error;
    }
  }

  async getDNSRecords(domain, subdomain = null) {
    const domainConfig = this.domainsConfig.domains[domain];
    const zoneId = domainConfig.cloudflare_zone_id;
    const recordName = subdomain ? `${subdomain}.${domain}` : domain;

    try {
      const response = await axios.get(
        `${this.baseURL}/zones/${zoneId}/dns_records?name=${recordName}`,
        {
          headers: {
            'Authorization': `Bearer ${this.apiToken}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.data.success) {
        return response.data.result;
      } else {
        throw new Error(`Cloudflare API error: ${JSON.stringify(response.data.errors)}`);
      }
    } catch (error) {
      if (error.response) {
        throw new Error(`Cloudflare API error: ${error.response.status} - ${JSON.stringify(error.response.data)}`);
      }
      throw error;
    }
  }
}

module.exports = CloudflareAPI;
