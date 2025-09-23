# Agency Engine - Insurance Agent Management Platform

A comprehensive platform for managing health insurance agents with training, CRM integration, and automated marketing. Built specifically for agencies like The Independent Life.

## 🎯 Project Overview

Agency Engine addresses the core challenge of helping insurance agents make money ASAP while teaching them to think like business owners. The platform provides:

- **Agent Management**: Comprehensive profiles with performance tracking
- **Training Platform**: Interactive courses with progress monitoring
- **CRM Integration**: Seamless connection with MedicarePro and other industry CRMs
- **Website Generation**: Automated agent websites with lead capture
- **Marketing Automation**: Social media posting and email campaigns
- **Analytics Dashboard**: Real-time performance metrics and forecasting

## 🏗️ Architecture

### Backend (Python/Flask)
- **Framework**: Flask with SQLAlchemy ORM
- **Authentication**: JWT-based with role-based access control
- **Database**: PostgreSQL (production) / SQLite (development)
- **APIs**: RESTful API with comprehensive endpoints
- **Integrations**: MedicarePro CRM, Agent Methods, Social Media APIs

### Frontend (React)
- **Framework**: React with Vite
- **Styling**: Tailwind CSS with shadcn/ui components
- **Icons**: Lucide React
- **Features**: Responsive design, interactive dashboards, real-time updates

## 🚀 Quick Start

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export FLASK_ENV=development
export SECRET_KEY=your-secret-key
export MEDICAREPRO_API_KEY=your-medicarepro-key
export AGENT_METHODS_API_KEY=your-agent-methods-key

# Initialize database
flask init-db
flask seed-db

# Run the application
python run.py
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
pnpm install

# Start development server
pnpm run dev --host
```

## 📊 Demo Features

The live demo showcases:

- **25 Active Agents** (matching client's team size)
- **$125,000 Monthly Revenue** tracking
- **89 Completed Courses** with progress monitoring
- **87% Average Performance** metrics
- **Real-time Integration Status** with MedicarePro and Agent Methods

## 🔌 API Integrations

### MedicarePro CRM
- Lead management and tracking
- Policy creation and updates
- Commission tracking
- Agent performance metrics
- Webhook support for real-time updates

### Agent Methods
- Automated website generation
- Social media posting (Facebook, LinkedIn, Instagram)
- Email marketing campaigns
- Lead capture forms
- Content template management

### Additional Integrations
- **Email Services**: SendGrid for transactional emails
- **File Storage**: AWS S3 for document management
- **Payment Processing**: Stripe for subscription management
- **Analytics**: Custom dashboard with forecasting

## 🎓 Training Platform

### Course Categories
- **Onboarding**: Medicare Basics, System Training
- **Sales**: Techniques, Customer Relations
- **Compliance**: Regulations, Certifications
- **Advanced**: Leadership, Business Development

### Features
- Interactive video content
- Progress tracking with completion certificates
- Quiz assessments with scoring
- Automated enrollment for required courses
- Performance analytics for administrators

## 👥 User Roles

### Admin
- Full system access
- Agent management and creation
- Course creation and management
- Analytics and reporting
- Integration configuration

### Manager
- Team oversight
- Performance monitoring
- Training assignment
- Limited administrative functions

### Agent
- Personal dashboard
- Course enrollment and completion
- Performance tracking
- Lead and policy management

## 📈 Analytics & Reporting

### Agent Performance
- Sales metrics and commission tracking
- Goal progress monitoring
- Training completion rates
- Customer satisfaction scores

### Agency Overview
- Revenue trends and forecasting
- Agent productivity comparisons
- Training effectiveness metrics
- Integration health monitoring

## 🔧 Configuration

### Environment Variables

```bash
# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret

# Database
DATABASE_URL=postgresql://user:password@localhost/agency_engine

# API Keys
MEDICAREPRO_API_KEY=your-medicarepro-key
AGENT_METHODS_API_KEY=your-agent-methods-key
SENDGRID_API_KEY=your-sendgrid-key

# Social Media
FACEBOOK_APP_ID=your-facebook-app-id
FACEBOOK_APP_SECRET=your-facebook-secret
LINKEDIN_CLIENT_ID=your-linkedin-id
LINKEDIN_CLIENT_SECRET=your-linkedin-secret

# File Storage
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_S3_BUCKET=agency-engine-files

# Payment Processing
STRIPE_PUBLISHABLE_KEY=your-stripe-public-key
STRIPE_SECRET_KEY=your-stripe-secret-key
```

## 🚀 Deployment

### Production Deployment

1. **Backend Deployment**
   ```bash
   # Using Gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 run:app
   ```

2. **Frontend Deployment**
   ```bash
   # Build for production
   pnpm run build
   
   # Deploy to static hosting (Netlify, Vercel, etc.)
   ```

3. **Database Migration**
   ```bash
   flask db upgrade
   ```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d
```

## 📝 API Documentation

### Authentication Endpoints
- `POST /api/auth/login` - User authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/refresh` - Token refresh
- `POST /api/auth/logout` - User logout

### Agent Management
- `GET /api/agents` - List all agents
- `POST /api/agents` - Create new agent
- `GET /api/agents/{id}` - Get agent details
- `PUT /api/agents/{id}` - Update agent
- `GET /api/agents/{id}/performance` - Agent performance metrics

### Course Management
- `GET /api/courses` - List available courses
- `POST /api/courses` - Create new course (admin)
- `POST /api/courses/{id}/enroll` - Enroll in course
- `POST /api/courses/{id}/complete` - Complete course

### CRM Integration
- `GET /api/crm/leads` - Get leads from CRM
- `POST /api/crm/leads` - Create new lead
- `GET /api/crm/policies` - Get policies
- `POST /api/crm/policies` - Create new policy

### Analytics
- `GET /api/analytics/dashboard` - Admin dashboard data
- `GET /api/analytics/agents/{id}` - Agent analytics
- `GET /api/analytics/revenue` - Revenue analytics

## 🤝 Client Integration

### The Independent Life Specific Features
- **25 Agent Support**: Designed for current team size with scalability
- **MedicarePro Integration**: Direct connection to existing CRM
- **Agent Methods Integration**: Seamless website and marketing automation
- **Custom Branding**: Tailored to agency's visual identity
- **Training Content**: Medicare-specific courses and compliance training

### Implementation Timeline
1. **Week 1-2**: Backend API development and testing
2. **Week 3**: Frontend dashboard implementation
3. **Week 4**: CRM and marketing integrations
4. **Week 5**: Training platform setup
5. **Week 6**: Testing, deployment, and agent onboarding

## 📞 Support & Contact

**Stampede Hosting**
- Phone: (330) 351-8697
- Email: hello@agencyengine.com
- Website: [Agency Engine Demo](http://localhost:5173)

## 📄 License

This project is proprietary software developed by Stampede Hosting for The Independent Life. All rights reserved.

## 🔄 Version History

- **v1.0.0** - Initial implementation with core features
- **v1.1.0** - Enhanced CRM integration and analytics
- **v1.2.0** - Advanced training platform with certifications
- **v2.0.0** - Full automation suite with AI-powered insights

---

*Built with ❤️ by Stampede Hosting for The Independent Life*
