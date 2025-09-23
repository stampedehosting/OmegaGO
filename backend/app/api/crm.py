"""
CRM Integration API Blueprint
Handles MedicarePro CRM integration and lead management
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from datetime import datetime, timedelta
import logging

from app import db
from app.models import Agent, Sale
from app.integrations.medicarepro import MedicareProAPI, transform_medicarepro_lead, transform_medicarepro_policy
from app.utils.decorators import admin_required, agent_or_admin_required

logger = logging.getLogger(__name__)

crm_bp = Blueprint('crm', __name__)

@crm_bp.route('/leads', methods=['GET'])
@jwt_required()
@agent_or_admin_required
def get_leads():
    """Get leads from MedicarePro CRM"""
    try:
        current_user_claims = get_jwt()
        current_user_id = get_jwt_identity()
        
        # Get query parameters
        agent_id = request.args.get('agent_id', type=int)
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 50, type=int)
        
        # Permission check
        if current_user_claims.get('role') != 'admin':
            # Non-admin users can only see their own leads
            user_agent = Agent.query.filter_by(user_id=current_user_id).first()
            if not user_agent:
                return jsonify({'error': 'Agent profile not found'}), 404
            agent_id = user_agent.id
        
        # Get agent for MedicarePro ID
        if agent_id:
            agent = Agent.query.get(agent_id)
            if not agent or not agent.medicarepro_id:
                return jsonify({'error': 'Agent not found or not connected to MedicarePro'}), 404
            medicarepro_agent_id = agent.medicarepro_id
        else:
            medicarepro_agent_id = None
        
        # Parse dates
        start_dt = None
        end_dt = None
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Get leads from MedicarePro
        medicarepro = MedicareProAPI()
        leads = medicarepro.get_leads(
            agent_id=medicarepro_agent_id,
            status=status,
            start_date=start_dt,
            end_date=end_dt
        )
        
        # Transform leads to internal format
        transformed_leads = [transform_medicarepro_lead(lead) for lead in leads[:limit]]
        
        return jsonify({
            'leads': transformed_leads,
            'count': len(transformed_leads),
            'filters': {
                'agent_id': agent_id,
                'status': status,
                'start_date': start_date,
                'end_date': end_date
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Get leads error: {e}")
        return jsonify({'error': 'Failed to get leads'}), 500

@crm_bp.route('/leads', methods=['POST'])
@jwt_required()
@agent_or_admin_required
def create_lead():
    """Create a new lead in MedicarePro CRM"""
    try:
        current_user_claims = get_jwt()
        current_user_id = get_jwt_identity()
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'phone', 'email']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Get agent
        agent_id = data.get('agent_id')
        if current_user_claims.get('role') != 'admin':
            # Non-admin users can only create leads for themselves
            user_agent = Agent.query.filter_by(user_id=current_user_id).first()
            if not user_agent:
                return jsonify({'error': 'Agent profile not found'}), 404
            agent_id = user_agent.id
        
        if not agent_id:
            return jsonify({'error': 'Agent ID is required'}), 400
        
        agent = Agent.query.get(agent_id)
        if not agent or not agent.medicarepro_id:
            return jsonify({'error': 'Agent not found or not connected to MedicarePro'}), 404
        
        # Prepare lead data for MedicarePro
        lead_data = {
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'phone': data['phone'],
            'email': data['email'],
            'agent_id': agent.medicarepro_id,
            'source': data.get('source', 'agency_engine'),
            'notes': data.get('notes', ''),
            'preferred_contact_method': data.get('preferred_contact_method', 'phone'),
            'best_time_to_call': data.get('best_time_to_call', ''),
            'date_of_birth': data.get('date_of_birth'),
            'zip_code': data.get('zip_code'),
            'current_coverage': data.get('current_coverage', ''),
            'interested_products': data.get('interested_products', [])
        }
        
        # Create lead in MedicarePro
        medicarepro = MedicareProAPI()
        created_lead = medicarepro.create_lead(lead_data)
        
        logger.info(f"Lead created in MedicarePro: {created_lead.get('id')}")
        
        return jsonify({
            'message': 'Lead created successfully',
            'lead': transform_medicarepro_lead(created_lead)
        }), 201
        
    except Exception as e:
        logger.error(f"Create lead error: {e}")
        return jsonify({'error': 'Failed to create lead'}), 500

@crm_bp.route('/leads/<lead_id>', methods=['PUT'])
@jwt_required()
@agent_or_admin_required
def update_lead(lead_id):
    """Update a lead in MedicarePro CRM"""
    try:
        current_user_claims = get_jwt()
        current_user_id = get_jwt_identity()
        
        data = request.get_json()
        
        # Permission check - ensure user can update this lead
        if current_user_claims.get('role') != 'admin':
            # For non-admin users, we should verify they own this lead
            # This would require additional logic to check lead ownership
            pass
        
        # Update lead in MedicarePro
        medicarepro = MedicareProAPI()
        updated_lead = medicarepro.update_lead(lead_id, data)
        
        logger.info(f"Lead updated in MedicarePro: {lead_id}")
        
        return jsonify({
            'message': 'Lead updated successfully',
            'lead': transform_medicarepro_lead(updated_lead)
        }), 200
        
    except Exception as e:
        logger.error(f"Update lead error: {e}")
        return jsonify({'error': 'Failed to update lead'}), 500

@crm_bp.route('/contacts', methods=['GET'])
@jwt_required()
@agent_or_admin_required
def get_contacts():
    """Get contacts from MedicarePro CRM"""
    try:
        current_user_claims = get_jwt()
        current_user_id = get_jwt_identity()
        
        # Get query parameters
        agent_id = request.args.get('agent_id', type=int)
        limit = request.args.get('limit', 100, type=int)
        
        # Permission check
        if current_user_claims.get('role') != 'admin':
            user_agent = Agent.query.filter_by(user_id=current_user_id).first()
            if not user_agent:
                return jsonify({'error': 'Agent profile not found'}), 404
            agent_id = user_agent.id
        
        # Get agent for MedicarePro ID
        if agent_id:
            agent = Agent.query.get(agent_id)
            if not agent or not agent.medicarepro_id:
                return jsonify({'error': 'Agent not found or not connected to MedicarePro'}), 404
            medicarepro_agent_id = agent.medicarepro_id
        else:
            medicarepro_agent_id = None
        
        # Get contacts from MedicarePro
        medicarepro = MedicareProAPI()
        contacts = medicarepro.get_contacts(
            agent_id=medicarepro_agent_id,
            limit=limit
        )
        
        return jsonify({
            'contacts': contacts,
            'count': len(contacts)
        }), 200
        
    except Exception as e:
        logger.error(f"Get contacts error: {e}")
        return jsonify({'error': 'Failed to get contacts'}), 500

@crm_bp.route('/policies', methods=['GET'])
@jwt_required()
@agent_or_admin_required
def get_policies():
    """Get policies from MedicarePro CRM"""
    try:
        current_user_claims = get_jwt()
        current_user_id = get_jwt_identity()
        
        # Get query parameters
        agent_id = request.args.get('agent_id', type=int)
        customer_id = request.args.get('customer_id')
        
        # Permission check
        if current_user_claims.get('role') != 'admin':
            user_agent = Agent.query.filter_by(user_id=current_user_id).first()
            if not user_agent:
                return jsonify({'error': 'Agent profile not found'}), 404
            agent_id = user_agent.id
        
        # Get agent for MedicarePro ID
        if agent_id:
            agent = Agent.query.get(agent_id)
            if not agent or not agent.medicarepro_id:
                return jsonify({'error': 'Agent not found or not connected to MedicarePro'}), 404
            medicarepro_agent_id = agent.medicarepro_id
        else:
            medicarepro_agent_id = None
        
        # Get policies from MedicarePro
        medicarepro = MedicareProAPI()
        policies = medicarepro.get_policies(
            agent_id=medicarepro_agent_id,
            customer_id=customer_id
        )
        
        # Transform policies to internal format
        transformed_policies = [transform_medicarepro_policy(policy) for policy in policies]
        
        return jsonify({
            'policies': transformed_policies,
            'count': len(transformed_policies)
        }), 200
        
    except Exception as e:
        logger.error(f"Get policies error: {e}")
        return jsonify({'error': 'Failed to get policies'}), 500

@crm_bp.route('/policies', methods=['POST'])
@jwt_required()
@agent_or_admin_required
def create_policy():
    """Create a new policy in MedicarePro CRM"""
    try:
        current_user_claims = get_jwt()
        current_user_id = get_jwt_identity()
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['customer_id', 'plan_id', 'premium_amount']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Get agent
        agent_id = data.get('agent_id')
        if current_user_claims.get('role') != 'admin':
            user_agent = Agent.query.filter_by(user_id=current_user_id).first()
            if not user_agent:
                return jsonify({'error': 'Agent profile not found'}), 404
            agent_id = user_agent.id
        
        if not agent_id:
            return jsonify({'error': 'Agent ID is required'}), 400
        
        agent = Agent.query.get(agent_id)
        if not agent or not agent.medicarepro_id:
            return jsonify({'error': 'Agent not found or not connected to MedicarePro'}), 404
        
        # Prepare policy data for MedicarePro
        policy_data = {
            'customer_id': data['customer_id'],
            'agent_id': agent.medicarepro_id,
            'plan_id': data['plan_id'],
            'premium_amount': data['premium_amount'],
            'commission_rate': data.get('commission_rate', agent.commission_rate),
            'effective_date': data.get('effective_date'),
            'application_date': data.get('application_date', datetime.now().isoformat()),
            'notes': data.get('notes', '')
        }
        
        # Calculate commission amount
        commission_amount = policy_data['premium_amount'] * (policy_data['commission_rate'] / 100)
        policy_data['commission_amount'] = commission_amount
        
        # Create policy in MedicarePro
        medicarepro = MedicareProAPI()
        created_policy = medicarepro.create_policy(policy_data)
        
        # Also create a local sale record
        sale = Sale(
            agent_id=agent.id,
            policy_number=created_policy.get('policy_number'),
            customer_name=f"{created_policy.get('customer_first_name', '')} {created_policy.get('customer_last_name', '')}".strip(),
            customer_email=created_policy.get('customer_email'),
            customer_phone=created_policy.get('customer_phone'),
            premium_amount=policy_data['premium_amount'],
            commission_amount=commission_amount,
            commission_rate=policy_data['commission_rate'],
            sale_date=datetime.strptime(policy_data['application_date'][:10], '%Y-%m-%d').date(),
            effective_date=datetime.strptime(policy_data['effective_date'], '%Y-%m-%d').date() if policy_data.get('effective_date') else None,
            medicarepro_lead_id=created_policy.get('id')
        )
        
        db.session.add(sale)
        
        # Update agent YTD metrics
        agent.ytd_sales += policy_data['premium_amount']
        agent.ytd_commissions += commission_amount
        
        db.session.commit()
        
        logger.info(f"Policy created in MedicarePro: {created_policy.get('id')}")
        
        return jsonify({
            'message': 'Policy created successfully',
            'policy': transform_medicarepro_policy(created_policy),
            'local_sale': sale.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Create policy error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to create policy'}), 500

@crm_bp.route('/commissions', methods=['GET'])
@jwt_required()
@agent_or_admin_required
def get_commissions():
    """Get commission data from MedicarePro CRM"""
    try:
        current_user_claims = get_jwt()
        current_user_id = get_jwt_identity()
        
        # Get query parameters
        agent_id = request.args.get('agent_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Permission check
        if current_user_claims.get('role') != 'admin':
            user_agent = Agent.query.filter_by(user_id=current_user_id).first()
            if not user_agent:
                return jsonify({'error': 'Agent profile not found'}), 404
            agent_id = user_agent.id
        
        if not agent_id:
            return jsonify({'error': 'Agent ID is required'}), 400
        
        agent = Agent.query.get(agent_id)
        if not agent or not agent.medicarepro_id:
            return jsonify({'error': 'Agent not found or not connected to MedicarePro'}), 404
        
        # Parse dates
        start_dt = None
        end_dt = None
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Get commissions from MedicarePro
        medicarepro = MedicareProAPI()
        commissions = medicarepro.get_commissions(
            agent.medicarepro_id,
            start_date=start_dt,
            end_date=end_dt
        )
        
        # Calculate summary
        total_commissions = sum(c.get('amount', 0) for c in commissions)
        paid_commissions = sum(c.get('amount', 0) for c in commissions if c.get('status') == 'paid')
        pending_commissions = sum(c.get('amount', 0) for c in commissions if c.get('status') == 'pending')
        
        return jsonify({
            'commissions': commissions,
            'summary': {
                'total_commissions': total_commissions,
                'paid_commissions': paid_commissions,
                'pending_commissions': pending_commissions,
                'count': len(commissions)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Get commissions error: {e}")
        return jsonify({'error': 'Failed to get commissions'}), 500

@crm_bp.route('/sync/<int:agent_id>', methods=['POST'])
@jwt_required()
@admin_required
def sync_crm_data(agent_id):
    """Sync CRM data for a specific agent"""
    try:
        agent = Agent.query.get(agent_id)
        
        if not agent or not agent.medicarepro_id:
            return jsonify({'error': 'Agent not found or not connected to MedicarePro'}), 404
        
        # Sync data from MedicarePro
        medicarepro = MedicareProAPI()
        sync_data = medicarepro.sync_agent_data(agent.medicarepro_id)
        
        # Process and store synced data
        sync_results = {
            'leads_synced': 0,
            'policies_synced': 0,
            'commissions_synced': 0,
            'errors': []
        }
        
        try:
            # Sync policies and create local sales records
            policies = sync_data.get('policies', [])
            for policy in policies:
                # Check if we already have this policy
                existing_sale = Sale.query.filter_by(
                    agent_id=agent.id,
                    policy_number=policy.get('policy_number')
                ).first()
                
                if not existing_sale:
                    sale = Sale(
                        agent_id=agent.id,
                        policy_number=policy.get('policy_number'),
                        customer_name=f"{policy.get('customer_first_name', '')} {policy.get('customer_last_name', '')}".strip(),
                        premium_amount=policy.get('premium_amount', 0),
                        commission_amount=policy.get('commission_amount', 0),
                        sale_date=datetime.strptime(policy.get('application_date', datetime.now().isoformat())[:10], '%Y-%m-%d').date(),
                        medicarepro_lead_id=policy.get('id')
                    )
                    db.session.add(sale)
                    sync_results['policies_synced'] += 1
            
            # Update agent performance metrics
            performance = sync_data.get('performance', {})
            if performance:
                agent.ytd_sales = performance.get('ytd_sales', agent.ytd_sales)
                agent.ytd_commissions = performance.get('ytd_commissions', agent.ytd_commissions)
            
            db.session.commit()
            
        except Exception as sync_error:
            logger.error(f"Data sync processing error: {sync_error}")
            sync_results['errors'].append(str(sync_error))
            db.session.rollback()
        
        return jsonify({
            'message': 'CRM data sync completed',
            'sync_results': sync_results,
            'sync_timestamp': sync_data.get('sync_timestamp')
        }), 200
        
    except Exception as e:
        logger.error(f"Sync CRM data error: {e}")
        return jsonify({'error': 'Failed to sync CRM data'}), 500

@crm_bp.route('/webhook', methods=['POST'])
def medicarepro_webhook():
    """Handle webhooks from MedicarePro CRM"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Verify webhook signature (implement based on MedicarePro's webhook security)
        # signature = request.headers.get('X-MedicarePro-Signature')
        # if not verify_webhook_signature(data, signature):
        #     return jsonify({'error': 'Invalid signature'}), 401
        
        # Process webhook
        medicarepro = MedicareProAPI()
        result = medicarepro.webhook_handler(data)
        
        logger.info(f"MedicarePro webhook processed: {result}")
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"MedicarePro webhook error: {e}")
        return jsonify({'error': 'Webhook processing failed'}), 500
