"""
Agent Methods Integration Service
Handles website hosting, design, and social media automation
"""

import requests
import logging
from datetime import datetime
from typing import Dict, List, Optional
from flask import current_app

logger = logging.getLogger(__name__)

class AgentMethodsAPI:
    """Agent Methods API integration class"""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        """Initialize Agent Methods API client"""
        self.api_key = api_key or current_app.config.get('AGENT_METHODS_API_KEY')
        self.base_url = base_url or current_app.config.get('AGENT_METHODS_BASE_URL')
        self.session = requests.Session()
        
        if not self.api_key:
            raise ValueError("Agent Methods API key is required")
        
        # Set default headers
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'AgencyEngine/1.0'
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make HTTP request to Agent Methods API"""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Agent Methods API request failed: {e}")
            raise Exception(f"Agent Methods API error: {str(e)}")
    
    # Website Management
    def create_agent_website(self, agent_data: Dict) -> Dict:
        """Create a new agent website"""
        website_data = {
            'agent_name': f"{agent_data.get('first_name')} {agent_data.get('last_name')}",
            'agent_email': agent_data.get('email'),
            'agent_phone': agent_data.get('phone'),
            'license_number': agent_data.get('license_number'),
            'license_state': agent_data.get('license_state'),
            'territory': agent_data.get('territory'),
            'template': agent_data.get('template', 'medicare_pro'),
            'custom_domain': agent_data.get('custom_domain'),
            'branding': {
                'primary_color': agent_data.get('primary_color', '#0066cc'),
                'secondary_color': agent_data.get('secondary_color', '#ffffff'),
                'logo_url': agent_data.get('logo_url')
            }
        }
        
        return self._make_request('POST', '/websites', json=website_data)
    
    def update_agent_website(self, website_id: str, update_data: Dict) -> Dict:
        """Update an existing agent website"""
        return self._make_request('PUT', f'/websites/{website_id}', json=update_data)
    
    def get_website_info(self, website_id: str) -> Dict:
        """Get website information and statistics"""
        return self._make_request('GET', f'/websites/{website_id}')
    
    def get_website_analytics(self, website_id: str, start_date: str = None, end_date: str = None) -> Dict:
        """Get website analytics data"""
        params = {}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        
        return self._make_request('GET', f'/websites/{website_id}/analytics', params=params)
    
    # Social Media Management
    def connect_social_accounts(self, agent_id: str, social_accounts: Dict) -> Dict:
        """Connect social media accounts for an agent"""
        connection_data = {
            'agent_id': agent_id,
            'accounts': social_accounts  # {'facebook': {...}, 'linkedin': {...}, 'instagram': {...}}
        }
        
        return self._make_request('POST', '/social/connect', json=connection_data)
    
    def schedule_social_post(self, agent_id: str, post_data: Dict) -> Dict:
        """Schedule a social media post"""
        post_payload = {
            'agent_id': agent_id,
            'content': post_data.get('content'),
            'image_url': post_data.get('image_url'),
            'platforms': post_data.get('platforms', ['facebook', 'linkedin', 'instagram']),
            'scheduled_time': post_data.get('scheduled_time'),
            'tags': post_data.get('tags', []),
            'call_to_action': post_data.get('call_to_action')
        }
        
        return self._make_request('POST', '/social/posts', json=post_payload)
    
    def get_social_posts(self, agent_id: str, status: str = None) -> List[Dict]:
        """Get scheduled and published social media posts"""
        params = {'agent_id': agent_id}
        if status:
            params['status'] = status  # scheduled, published, failed
        
        response = self._make_request('GET', '/social/posts', params=params)
        return response.get('posts', [])
    
    def get_social_analytics(self, agent_id: str, platform: str = None, 
                           start_date: str = None, end_date: str = None) -> Dict:
        """Get social media analytics"""
        params = {'agent_id': agent_id}
        if platform:
            params['platform'] = platform
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        
        return self._make_request('GET', '/social/analytics', params=params)
    
    # Email Marketing
    def create_email_campaign(self, agent_id: str, campaign_data: Dict) -> Dict:
        """Create an email marketing campaign"""
        email_payload = {
            'agent_id': agent_id,
            'campaign_name': campaign_data.get('name'),
            'subject': campaign_data.get('subject'),
            'template': campaign_data.get('template', 'medicare_newsletter'),
            'content': campaign_data.get('content'),
            'recipient_list': campaign_data.get('recipients', []),
            'send_time': campaign_data.get('send_time'),
            'personalization': campaign_data.get('personalization', {})
        }
        
        return self._make_request('POST', '/email/campaigns', json=email_payload)
    
    def get_email_campaigns(self, agent_id: str) -> List[Dict]:
        """Get email campaigns for an agent"""
        params = {'agent_id': agent_id}
        response = self._make_request('GET', '/email/campaigns', params=params)
        return response.get('campaigns', [])
    
    def get_email_analytics(self, campaign_id: str) -> Dict:
        """Get email campaign analytics"""
        return self._make_request('GET', f'/email/campaigns/{campaign_id}/analytics')
    
    # Content Management
    def get_content_templates(self, category: str = None) -> List[Dict]:
        """Get available content templates"""
        params = {}
        if category:
            params['category'] = category  # social, email, blog, etc.
        
        response = self._make_request('GET', '/content/templates', params=params)
        return response.get('templates', [])
    
    def generate_content(self, template_id: str, agent_data: Dict, custom_params: Dict = None) -> Dict:
        """Generate personalized content using a template"""
        content_data = {
            'template_id': template_id,
            'agent_data': agent_data,
            'custom_params': custom_params or {}
        }
        
        return self._make_request('POST', '/content/generate', json=content_data)
    
    # Lead Capture Integration
    def setup_lead_capture(self, website_id: str, capture_config: Dict) -> Dict:
        """Setup lead capture forms on agent website"""
        config_data = {
            'website_id': website_id,
            'forms': capture_config.get('forms', []),
            'integrations': capture_config.get('integrations', {}),
            'notifications': capture_config.get('notifications', {})
        }
        
        return self._make_request('POST', '/lead-capture/setup', json=config_data)
    
    def get_captured_leads(self, website_id: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Get leads captured from agent website"""
        params = {'website_id': website_id}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        
        response = self._make_request('GET', '/lead-capture/leads', params=params)
        return response.get('leads', [])
    
    # Automation Workflows
    def create_automation_workflow(self, agent_id: str, workflow_data: Dict) -> Dict:
        """Create an automation workflow"""
        workflow_payload = {
            'agent_id': agent_id,
            'name': workflow_data.get('name'),
            'trigger': workflow_data.get('trigger'),  # new_lead, policy_sold, etc.
            'actions': workflow_data.get('actions', []),  # email, social_post, crm_update
            'conditions': workflow_data.get('conditions', {}),
            'is_active': workflow_data.get('is_active', True)
        }
        
        return self._make_request('POST', '/automation/workflows', json=workflow_payload)
    
    def get_automation_workflows(self, agent_id: str) -> List[Dict]:
        """Get automation workflows for an agent"""
        params = {'agent_id': agent_id}
        response = self._make_request('GET', '/automation/workflows', params=params)
        return response.get('workflows', [])
    
    def trigger_workflow(self, workflow_id: str, trigger_data: Dict) -> Dict:
        """Manually trigger an automation workflow"""
        return self._make_request('POST', f'/automation/workflows/{workflow_id}/trigger', json=trigger_data)

# Utility functions for Agent Methods integration
def create_default_agent_website(agent_data: Dict) -> Dict:
    """Create a default website configuration for a new agent"""
    return {
        'template': 'medicare_professional',
        'pages': [
            {'type': 'home', 'title': 'Welcome', 'content': 'default_home_content'},
            {'type': 'about', 'title': 'About Me', 'content': 'default_about_content'},
            {'type': 'services', 'title': 'My Services', 'content': 'default_services_content'},
            {'type': 'contact', 'title': 'Contact Me', 'content': 'default_contact_content'}
        ],
        'features': [
            'lead_capture_forms',
            'appointment_booking',
            'social_media_integration',
            'blog_section',
            'testimonials'
        ],
        'seo_settings': {
            'meta_title': f"{agent_data.get('first_name')} {agent_data.get('last_name')} - Medicare Insurance Agent",
            'meta_description': f"Professional Medicare insurance services in {agent_data.get('territory', 'your area')}",
            'keywords': ['medicare', 'insurance', 'health coverage', agent_data.get('territory', '')]
        }
    }

def create_social_media_content_calendar(agent_data: Dict, weeks: int = 4) -> List[Dict]:
    """Create a social media content calendar for an agent"""
    content_types = [
        'educational_tip',
        'client_testimonial',
        'industry_news',
        'personal_story',
        'service_highlight'
    ]
    
    calendar = []
    for week in range(weeks):
        for day in range(7):  # 7 days a week
            if day in [1, 3, 5]:  # Post on Monday, Wednesday, Friday
                content_type = content_types[len(calendar) % len(content_types)]
                calendar.append({
                    'week': week + 1,
                    'day': day + 1,
                    'content_type': content_type,
                    'platforms': ['facebook', 'linkedin'],
                    'scheduled': True
                })
    
    return calendar
