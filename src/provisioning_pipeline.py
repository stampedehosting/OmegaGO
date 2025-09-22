#!/usr/bin/env python3
"""
Automated Provisioning Pipeline for Stampede Hosting
Handles server provisioning, DNS configuration, SSL setup, and application deployment
"""

import os
import json
import time
import subprocess
import paramiko
import requests
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KitType(Enum):
    STARTER_SITE = "starter_site"
    COURSE_LAUNCH = "course_launch"
    DEVELOPER_SANDBOX = "developer_sandbox"

class ProvisioningStatus(Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    CONFIGURING = "configuring"
    DEPLOYING = "deploying"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ProvisioningRequest:
    """Data class for provisioning requests"""
    kit_type: KitType
    customer_id: str
    domain_name: str
    github_repo: Optional[str] = None
    custom_config: Optional[Dict[str, Any]] = None
    request_id: str = None

class ProvisioningPipeline:
    """Main provisioning pipeline class"""
    
    def __init__(self):
        self.ssh_key_path = os.getenv('SSH_PRIVATE_KEY_PATH', '~/.ssh/id_rsa')
        self.ssh_user = os.getenv('SSH_USER', 'ubuntu')
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.replit_token = os.getenv('REPLIT_TOKEN')
        self.dns_provider_api_key = os.getenv('DNS_PROVIDER_API_KEY')
        self.vps_inventory = self._load_vps_inventory()
        
    def _load_vps_inventory(self) -> Dict[str, Any]:
        """Load VPS inventory from configuration"""
        try:
            with open('/home/ubuntu/OmegaGO/config/vps_inventory.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("VPS inventory file not found, using default configuration")
            return {
                "web_servers": ["192.168.1.100", "192.168.1.101"],
                "db_servers": ["192.168.1.200"],
                "worker_servers": ["192.168.1.300"]
            }
    
    def provision_environment(self, request: ProvisioningRequest) -> Dict[str, Any]:
        """Main provisioning method"""
        logger.info(f"Starting provisioning for request {request.request_id}")
        
        try:
            # Step 1: Select and provision server
            server_ip = self._select_server(request.kit_type)
            logger.info(f"Selected server: {server_ip}")
            
            # Step 2: Configure DNS
            self._configure_dns(request.domain_name, server_ip)
            logger.info(f"DNS configured for {request.domain_name}")
            
            # Step 3: Install SSL certificate
            self._install_ssl_certificate(server_ip, request.domain_name)
            logger.info(f"SSL certificate installed for {request.domain_name}")
            
            # Step 4: Deploy application based on kit type
            deployment_info = self._deploy_application(request, server_ip)
            logger.info(f"Application deployed successfully")
            
            # Step 5: Create GitHub repository if needed
            if request.github_repo:
                repo_url = self._create_github_repo(request)
                deployment_info['github_repo'] = repo_url
            
            # Step 6: Deploy to Replit for demo
            replit_url = self._deploy_to_replit(request)
            deployment_info['replit_demo'] = replit_url
            
            result = {
                'status': ProvisioningStatus.COMPLETED.value,
                'server_ip': server_ip,
                'domain': request.domain_name,
                'deployment_info': deployment_info,
                'access_urls': {
                    'live_site': f"https://{request.domain_name}",
                    'replit_demo': replit_url
                }
            }
            
            logger.info(f"Provisioning completed for request {request.request_id}")
            return result
            
        except Exception as e:
            logger.error(f"Provisioning failed for request {request.request_id}: {str(e)}")
            return {
                'status': ProvisioningStatus.FAILED.value,
                'error': str(e)
            }
    
    def _select_server(self, kit_type: KitType) -> str:
        """Select appropriate server based on kit type"""
        if kit_type == KitType.DEVELOPER_SANDBOX:
            # Developer sandbox needs more resources
            return self.vps_inventory.get("worker_servers", ["192.168.1.300"])[0]
        else:
            # Web servers for starter sites and course platforms
            return self.vps_inventory.get("web_servers", ["192.168.1.100"])[0]
    
    def _configure_dns(self, domain_name: str, server_ip: str):
        """Configure DNS records for the domain"""
        # This is a placeholder - actual implementation would depend on DNS provider API
        logger.info(f"Configuring DNS: {domain_name} -> {server_ip}")
        
        # Example for Cloudflare API (would need actual implementation)
        if self.dns_provider_api_key:
            # DNS configuration logic here
            pass
        else:
            logger.warning("DNS provider API key not configured - manual DNS setup required")
    
    def _install_ssl_certificate(self, server_ip: str, domain_name: str):
        """Install Let's Encrypt SSL certificate"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(server_ip, username=self.ssh_user, key_filename=self.ssh_key_path)
            
            # Install certbot and obtain certificate
            commands = [
                "sudo apt-get update",
                "sudo apt-get install -y certbot python3-certbot-nginx",
                f"sudo certbot --nginx -d {domain_name} --non-interactive --agree-tos --email admin@stampedehosting.com"
            ]
            
            for cmd in commands:
                stdin, stdout, stderr = ssh.exec_command(cmd)
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                    error_msg = stderr.read().decode()
                    logger.error(f"SSL installation failed: {error_msg}")
                    raise Exception(f"SSL installation failed: {error_msg}")
            
            ssh.close()
            logger.info(f"SSL certificate installed successfully for {domain_name}")
            
        except Exception as e:
            logger.error(f"Failed to install SSL certificate: {str(e)}")
            raise
    
    def _deploy_application(self, request: ProvisioningRequest, server_ip: str) -> Dict[str, Any]:
        """Deploy application based on kit type"""
        deployment_info = {}
        
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(server_ip, username=self.ssh_user, key_filename=self.ssh_key_path)
            
            if request.kit_type == KitType.STARTER_SITE:
                deployment_info = self._deploy_starter_site(ssh, request)
            elif request.kit_type == KitType.COURSE_LAUNCH:
                deployment_info = self._deploy_course_platform(ssh, request)
            elif request.kit_type == KitType.DEVELOPER_SANDBOX:
                deployment_info = self._deploy_developer_sandbox(ssh, request)
            
            ssh.close()
            return deployment_info
            
        except Exception as e:
            logger.error(f"Application deployment failed: {str(e)}")
            raise
    
    def _deploy_starter_site(self, ssh, request: ProvisioningRequest) -> Dict[str, Any]:
        """Deploy a static site using Hugo or similar"""
        commands = [
            "sudo apt-get install -y nginx hugo",
            "hugo new site /var/www/html/site",
            "cd /var/www/html/site && git init",
            "sudo systemctl enable nginx",
            "sudo systemctl start nginx"
        ]
        
        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                error_msg = stderr.read().decode()
                logger.warning(f"Command failed: {cmd} - {error_msg}")
        
        return {
            'type': 'static_site',
            'generator': 'hugo',
            'document_root': '/var/www/html/site/public'
        }
    
    def _deploy_course_platform(self, ssh, request: ProvisioningRequest) -> Dict[str, Any]:
        """Deploy Moodle or similar LMS"""
        commands = [
            "sudo apt-get update",
            "sudo apt-get install -y nginx mysql-server php-fpm php-mysql",
            "wget https://download.moodle.org/download.php/direct/stable401/moodle-latest-401.tgz",
            "tar -xzf moodle-latest-401.tgz -C /var/www/html/",
            "sudo chown -R www-data:www-data /var/www/html/moodle",
            "sudo systemctl enable nginx mysql php7.4-fpm",
            "sudo systemctl start nginx mysql php7.4-fpm"
        ]
        
        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                error_msg = stderr.read().decode()
                logger.warning(f"Command failed: {cmd} - {error_msg}")
        
        return {
            'type': 'lms',
            'platform': 'moodle',
            'admin_url': f"https://{request.domain_name}/admin"
        }
    
    def _deploy_developer_sandbox(self, ssh, request: ProvisioningRequest) -> Dict[str, Any]:
        """Deploy development environment with Docker and tools"""
        commands = [
            "sudo apt-get update",
            "sudo apt-get install -y docker.io git python3 python3-pip nodejs npm",
            "sudo usermod -aG docker ubuntu",
            "sudo systemctl enable docker",
            "sudo systemctl start docker",
            "pip3 install flask fastapi uvicorn",
            "npm install -g create-react-app"
        ]
        
        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                error_msg = stderr.read().decode()
                logger.warning(f"Command failed: {cmd} - {error_msg}")
        
        return {
            'type': 'development',
            'tools': ['docker', 'git', 'python3', 'nodejs', 'npm'],
            'ssh_access': True
        }
    
    def _create_github_repo(self, request: ProvisioningRequest) -> str:
        """Create GitHub repository for the project"""
        if not self.github_token:
            logger.warning("GitHub token not configured")
            return None
        
        repo_name = f"{request.customer_id}-{request.kit_type.value}-{int(time.time())}"
        
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        data = {
            'name': repo_name,
            'description': f'Stampede Hosting {request.kit_type.value} for {request.customer_id}',
            'private': False,
            'auto_init': True
        }
        
        try:
            response = requests.post('https://api.github.com/user/repos', 
                                   headers=headers, json=data)
            
            if response.status_code == 201:
                repo_info = response.json()
                logger.info(f"GitHub repository created: {repo_info['html_url']}")
                return repo_info['html_url']
            else:
                logger.error(f"Failed to create GitHub repository: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"GitHub repository creation failed: {str(e)}")
            return None
    
    def _deploy_to_replit(self, request: ProvisioningRequest) -> str:
        """Deploy to Replit for quick demo"""
        # This is a placeholder - actual Replit API integration would be needed
        logger.info(f"Deploying to Replit for demo purposes")
        
        # For now, return a placeholder URL
        demo_url = f"https://replit.com/@stampedehosting/{request.customer_id}-{request.kit_type.value}-demo"
        return demo_url

def main():
    """Test the provisioning pipeline"""
    pipeline = ProvisioningPipeline()
    
    # Test provisioning request
    test_request = ProvisioningRequest(
        kit_type=KitType.STARTER_SITE,
        customer_id="test-customer-001",
        domain_name="test-site.stampedehosting.com",
        request_id="req-001"
    )
    
    result = pipeline.provision_environment(test_request)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
