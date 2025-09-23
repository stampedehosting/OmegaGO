"""
MedicarePro CRM Integration Service
Handles all interactions with the MedicarePro API
"""

import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import current_app

logger = logging.getLogger(__name__)

class MedicareProAPI:
    """MedicarePro CRM API integration class"""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        """Initialize MedicarePro API client"""
        self.api_key = api_key or current_app.config.get('MEDICAREPRO_API_KEY')
        self.base_url = base_url or current_app.config.get('MEDICAREPRO_BASE_URL')
        self.session = requests.Session()
        
        if not self.api_key:
            raise ValueError("MedicarePro API key is required")
        
        # Set default headers
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'AgencyEngine/1.0'
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make HTTP request to MedicarePro API"""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"MedicarePro API request failed: {e}")
            raise Exception(f"MedicarePro API error: {str(e)}")
    
    def get_agent_profile(self, agent_id: str) -> Dict:
        """Get agent profile from MedicarePro"""
        return self._make_request('GET', f'/agents/{agent_id}')
    
    def get_leads(self, agent_id: str = None, status: str = None, 
                  start_date: datetime = None, end_date: datetime = None) -> List[Dict]:
        """Get leads from MedicarePro CRM"""
        params = {}
        
        if agent_id:
            params['agent_id'] = agent_id
        if status:
            params['status'] = status
        if start_date:
            params['start_date'] = start_date.isoformat()
        if end_date:
            params['end_date'] = end_date.isoformat()
        
        response = self._make_request('GET', '/leads', params=params)
        return response.get('leads', [])
    
    def create_lead(self, lead_data: Dict) -> Dict:
        """Create a new lead in MedicarePro"""
        required_fields = ['first_name', 'last_name', 'phone', 'email']
        
        for field in required_fields:
            if field not in lead_data:
                raise ValueError(f"Required field '{field}' is missing")
        
        return self._make_request('POST', '/leads', json=lead_data)
    
    def update_lead(self, lead_id: str, lead_data: Dict) -> Dict:
        """Update an existing lead in MedicarePro"""
        return self._make_request('PUT', f'/leads/{lead_id}', json=lead_data)
    
    def get_contacts(self, agent_id: str = None, limit: int = 100) -> List[Dict]:
        """Get contacts from MedicarePro"""
        params = {'limit': limit}
        if agent_id:
            params['agent_id'] = agent_id
        
        response = self._make_request('GET', '/contacts', params=params)
        return response.get('contacts', [])
    
    def create_contact(self, contact_data: Dict) -> Dict:
        """Create a new contact in MedicarePro"""
        return self._make_request('POST', '/contacts', json=contact_data)
    
    def get_policies(self, agent_id: str = None, customer_id: str = None) -> List[Dict]:
        """Get policies from MedicarePro"""
        params = {}
        if agent_id:
            params['agent_id'] = agent_id
        if customer_id:
            params['customer_id'] = customer_id
        
        response = self._make_request('GET', '/policies', params=params)
        return response.get('policies', [])
    
    def create_policy(self, policy_data: Dict) -> Dict:
        """Create a new policy in MedicarePro"""
        required_fields = ['customer_id', 'agent_id', 'plan_id', 'premium_amount']
        
        for field in required_fields:
            if field not in policy_data:
                raise ValueError(f"Required field '{field}' is missing")
        
        return self._make_request('POST', '/policies', json=policy_data)
    
    def get_commissions(self, agent_id: str, start_date: datetime = None, 
                       end_date: datetime = None) -> List[Dict]:
        """Get commission data for an agent"""
        params = {'agent_id': agent_id}
        
        if start_date:
            params['start_date'] = start_date.isoformat()
        if end_date:
            params['end_date'] = end_date.isoformat()
        
        response = self._make_request('GET', '/commissions', params=params)
        return response.get('commissions', [])
    
    def get_agent_performance(self, agent_id: str, period: str = 'month') -> Dict:
        """Get agent performance metrics"""
        params = {'period': period}  # month, quarter, year
        
        response = self._make_request('GET', f'/agents/{agent_id}/performance', params=params)
        return response
    
    def sync_agent_data(self, agent_id: str) -> Dict:
        """Sync all agent data from MedicarePro"""
        try:
            # Get agent profile
            profile = self.get_agent_profile(agent_id)
            
            # Get recent leads (last 30 days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            leads = self.get_leads(agent_id, start_date=start_date, end_date=end_date)
            
            # Get contacts
            contacts = self.get_contacts(agent_id, limit=500)
            
            # Get policies
            policies = self.get_policies(agent_id)
            
            # Get commissions (last 90 days)
            commission_start = end_date - timedelta(days=90)
            commissions = self.get_commissions(agent_id, start_date=commission_start, end_date=end_date)
            
            # Get performance metrics
            performance = self.get_agent_performance(agent_id)
            
            return {
                'profile': profile,
                'leads': leads,
                'contacts': contacts,
                'policies': policies,
                'commissions': commissions,
                'performance': performance,
                'sync_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to sync agent data for {agent_id}: {e}")
            raise
    
    def webhook_handler(self, webhook_data: Dict) -> Dict:
        """Handle incoming webhooks from MedicarePro"""
        event_type = webhook_data.get('event_type')
        data = webhook_data.get('data', {})
        
        logger.info(f"Received MedicarePro webhook: {event_type}")
        
        # Process different webhook events
        if event_type == 'lead.created':
            return self._handle_lead_created(data)
        elif event_type == 'lead.updated':
            return self._handle_lead_updated(data)
        elif event_type == 'policy.created':
            return self._handle_policy_created(data)
        elif event_type == 'commission.paid':
            return self._handle_commission_paid(data)
        else:
            logger.warning(f"Unknown webhook event type: {event_type}")
            return {'status': 'ignored', 'reason': 'unknown_event_type'}
    
    def _handle_lead_created(self, data: Dict) -> Dict:
        """Handle new lead creation webhook"""
        # Process new lead data and update local database
        logger.info(f"Processing new lead: {data.get('id')}")
        return {'status': 'processed', 'action': 'lead_created'}
    
    def _handle_lead_updated(self, data: Dict) -> Dict:
        """Handle lead update webhook"""
        logger.info(f"Processing lead update: {data.get('id')}")
        return {'status': 'processed', 'action': 'lead_updated'}
    
    def _handle_policy_created(self, data: Dict) -> Dict:
        """Handle new policy creation webhook"""
        logger.info(f"Processing new policy: {data.get('id')}")
        return {'status': 'processed', 'action': 'policy_created'}
    
    def _handle_commission_paid(self, data: Dict) -> Dict:
        """Handle commission payment webhook"""
        logger.info(f"Processing commission payment: {data.get('id')}")
        return {'status': 'processed', 'action': 'commission_paid'}

# Utility functions for data transformation
def transform_medicarepro_lead(mp_lead: Dict) -> Dict:
    """Transform MedicarePro lead data to internal format"""
    return {
        'external_id': mp_lead.get('id'),
        'first_name': mp_lead.get('first_name'),
        'last_name': mp_lead.get('last_name'),
        'email': mp_lead.get('email'),
        'phone': mp_lead.get('phone'),
        'status': mp_lead.get('status'),
        'source': mp_lead.get('source', 'medicarepro'),
        'created_at': mp_lead.get('created_at'),
        'updated_at': mp_lead.get('updated_at')
    }

def transform_medicarepro_policy(mp_policy: Dict) -> Dict:
    """Transform MedicarePro policy data to internal format"""
    return {
        'external_id': mp_policy.get('id'),
        'policy_number': mp_policy.get('policy_number'),
        'customer_name': f"{mp_policy.get('customer_first_name', '')} {mp_policy.get('customer_last_name', '')}".strip(),
        'premium_amount': mp_policy.get('premium_amount'),
        'commission_amount': mp_policy.get('commission_amount'),
        'effective_date': mp_policy.get('effective_date'),
        'status': mp_policy.get('status')
    }
