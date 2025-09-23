"""
Agency Engine - Flask Application Runner
Main entry point for the Flask application
"""

import os
from app import create_app, db
from app.models import User, Agent, Course, CourseEnrollment, Sale, Integration
from flask.cli import with_appcontext
import click

# Create Flask application
app = create_app()

@app.shell_context_processor
def make_shell_context():
    """Make database models available in Flask shell"""
    return {
        'db': db,
        'User': User,
        'Agent': Agent,
        'Course': Course,
        'CourseEnrollment': CourseEnrollment,
        'Sale': Sale,
        'Integration': Integration
    }

@app.cli.command()
@with_appcontext
def init_db():
    """Initialize the database with tables"""
    db.create_all()
    click.echo('Database tables created successfully!')

@app.cli.command()
@with_appcontext
def seed_db():
    """Seed the database with initial data"""
    
    # Create admin user
    admin_user = User(
        email='admin@agencyengine.com',
        first_name='Admin',
        last_name='User',
        role='admin'
    )
    admin_user.set_password('AdminPassword123!')
    
    # Create sample courses
    courses = [
        Course(
            title='Medicare Basics',
            description='Introduction to Medicare insurance fundamentals',
            category='onboarding',
            difficulty_level='beginner',
            duration_minutes=45,
            is_required=True,
            quiz_questions=[
                {
                    'id': 1,
                    'question': 'What are the four parts of Medicare?',
                    'options': ['A, B, C, D', 'Part 1, 2, 3, 4', 'Basic, Premium, Plus, Pro'],
                    'correct_answer': 'A, B, C, D'
                },
                {
                    'id': 2,
                    'question': 'When can someone first enroll in Medicare?',
                    'options': ['Age 60', 'Age 65', 'Age 70'],
                    'correct_answer': 'Age 65'
                }
            ]
        ),
        Course(
            title='Sales Techniques for Insurance',
            description='Effective sales strategies for insurance agents',
            category='sales',
            difficulty_level='intermediate',
            duration_minutes=60,
            is_required=False,
            quiz_questions=[
                {
                    'id': 1,
                    'question': 'What is the most important part of a sales conversation?',
                    'options': ['Listening', 'Talking', 'Presenting'],
                    'correct_answer': 'Listening'
                }
            ]
        ),
        Course(
            title='Compliance and Regulations',
            description='Understanding insurance compliance requirements',
            category='compliance',
            difficulty_level='advanced',
            duration_minutes=90,
            is_required=True,
            quiz_questions=[
                {
                    'id': 1,
                    'question': 'How often must agents complete compliance training?',
                    'options': ['Annually', 'Bi-annually', 'Monthly'],
                    'correct_answer': 'Annually'
                }
            ]
        )
    ]
    
    # Add to database
    db.session.add(admin_user)
    for course in courses:
        db.session.add(course)
    
    try:
        db.session.commit()
        click.echo('Database seeded successfully!')
        click.echo(f'Admin user created: admin@agencyengine.com / AdminPassword123!')
        click.echo(f'Created {len(courses)} sample courses')
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error seeding database: {e}')

@app.cli.command()
@with_appcontext
def create_sample_agent():
    """Create a sample agent for testing"""
    
    # Create agent user
    agent_user = User(
        email='agent@example.com',
        first_name='John',
        last_name='Smith',
        role='agent'
    )
    agent_user.set_password('AgentPassword123!')
    
    db.session.add(agent_user)
    db.session.flush()  # Get the user ID
    
    # Create agent profile
    agent = Agent(
        user_id=agent_user.id,
        agent_id='JS001',
        phone='330-555-0123',
        license_number='OH12345',
        license_state='OH',
        territory='Northeast Ohio',
        commission_rate=15.0,
        monthly_goal=5000.0
    )
    
    db.session.add(agent)
    
    try:
        db.session.commit()
        click.echo('Sample agent created successfully!')
        click.echo(f'Agent login: agent@example.com / AgentPassword123!')
        click.echo(f'Agent ID: JS001')
    except Exception as e:
        db.session.rollback()
        click.echo(f'Error creating sample agent: {e}')

@app.cli.command()
@with_appcontext
def reset_db():
    """Reset the database (drop and recreate all tables)"""
    if click.confirm('This will delete all data. Are you sure?'):
        db.drop_all()
        db.create_all()
        click.echo('Database reset successfully!')

@app.cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=5000, help='Port to bind to')
@click.option('--debug', is_flag=True, help='Enable debug mode')
def runserver(host, port, debug):
    """Run the development server"""
    app.run(host=host, port=port, debug=debug)

@app.cli.command()
@with_appcontext
def test_integrations():
    """Test external API integrations"""
    from app.integrations.medicarepro import MedicareProAPI
    from app.integrations.agent_methods import AgentMethodsAPI
    
    click.echo('Testing integrations...')
    
    # Test MedicarePro (if configured)
    try:
        if app.config.get('MEDICAREPRO_API_KEY'):
            medicarepro = MedicareProAPI()
            click.echo('✓ MedicarePro API client initialized')
        else:
            click.echo('⚠ MedicarePro API key not configured')
    except Exception as e:
        click.echo(f'✗ MedicarePro API error: {e}')
    
    # Test Agent Methods (if configured)
    try:
        if app.config.get('AGENT_METHODS_API_KEY'):
            agent_methods = AgentMethodsAPI()
            click.echo('✓ Agent Methods API client initialized')
        else:
            click.echo('⚠ Agent Methods API key not configured')
    except Exception as e:
        click.echo(f'✗ Agent Methods API error: {e}')

if __name__ == '__main__':
    # Set environment variables for development
    os.environ.setdefault('FLASK_ENV', 'development')
    os.environ.setdefault('FLASK_APP', 'run.py')
    
    # Run the application
    app.run(
        host=os.environ.get('HOST', '0.0.0.0'),
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('FLASK_ENV') == 'development'
    )
