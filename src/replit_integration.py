#!/usr/bin/env python3
"""
Replit Integration Service for Stampede Hosting
Handles creation, deployment, and management of Replit projects for quick demos
"""

import os
import json
import time
import requests
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import asyncio
import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ReplitLanguage(Enum):
    HTML = "html"
    PYTHON = "python"
    JAVASCRIPT = "nodejs"
    REACT = "reactjs"
    FLASK = "python"
    NEXTJS = "nextjs"

@dataclass
class ReplitProject:
    """Data class for Replit project information"""
    id: str
    name: str
    url: str
    live_url: Optional[str] = None
    language: str = "python"
    status: str = "created"
    files: Dict[str, str] = None

class ReplitIntegration:
    """Main Replit integration service"""
    
    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.getenv("REPLIT_TOKEN")
        if not self.api_token:
            raise ValueError("Replit API token is required")
        
        self.base_url = "https://replit.com/api/v0"
        self.graphql_url = "https://replit.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "User-Agent": "Stampede-Hosting/1.0"
        }
    
    async def create_repl(self, name: str, language: ReplitLanguage, 
                         description: str = "", is_private: bool = False) -> ReplitProject:
        """Create a new Replit project"""
        
        # GraphQL mutation to create a repl
        mutation = """
        mutation CreateRepl($input: CreateReplInput!) {
            createRepl(input: $input) {
                ... on Repl {
                    id
                    title
                    slug
                    url
                    language
                    isPrivate
                }
                ... on UserError {
                    message
                }
            }
        }
        """
        
        variables = {
            "input": {
                "title": name,
                "language": language.value,
                "description": description,
                "isPrivate": is_private,
                "folderId": None
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.graphql_url,
                headers=self.headers,
                json={"query": mutation, "variables": variables}
            ) as response:
                
                if response.status != 200:
                    raise Exception(f"Failed to create repl: HTTP {response.status}")
                
                data = await response.json()
                
                if "errors" in data:
                    raise Exception(f"GraphQL errors: {data['errors']}")
                
                repl_data = data["data"]["createRepl"]
                
                if "message" in repl_data:  # UserError
                    raise Exception(f"Failed to create repl: {repl_data['message']}")
                
                logger.info(f"Created Replit project: {repl_data['url']}")
                
                return ReplitProject(
                    id=repl_data["id"],
                    name=repl_data["title"],
                    url=repl_data["url"],
                    language=repl_data["language"],
                    status="created"
                )
    
    async def upload_files(self, repl_id: str, files: Dict[str, str]) -> bool:
        """Upload files to a Replit project"""
        
        # GraphQL mutation to write files
        mutation = """
        mutation WriteFiles($replId: String!, $files: [FileInput!]!) {
            writeFiles(replId: $replId, files: $files) {
                ... on WriteFilesSuccess {
                    files {
                        path
                    }
                }
                ... on UserError {
                    message
                }
            }
        }
        """
        
        file_inputs = [
            {"path": path, "content": content}
            for path, content in files.items()
        ]
        
        variables = {
            "replId": repl_id,
            "files": file_inputs
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.graphql_url,
                headers=self.headers,
                json={"query": mutation, "variables": variables}
            ) as response:
                
                if response.status != 200:
                    logger.error(f"Failed to upload files: HTTP {response.status}")
                    return False
                
                data = await response.json()
                
                if "errors" in data:
                    logger.error(f"GraphQL errors: {data['errors']}")
                    return False
                
                result = data["data"]["writeFiles"]
                
                if "message" in result:  # UserError
                    logger.error(f"Failed to upload files: {result['message']}")
                    return False
                
                logger.info(f"Uploaded {len(files)} files to repl {repl_id}")
                return True
    
    async def run_repl(self, repl_id: str) -> Dict[str, Any]:
        """Start running a Replit project"""
        
        # GraphQL mutation to run a repl
        mutation = """
        mutation RunRepl($replId: String!) {
            runRepl(replId: $replId) {
                ... on RunReplSuccess {
                    message
                }
                ... on UserError {
                    message
                }
            }
        }
        """
        
        variables = {"replId": repl_id}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.graphql_url,
                headers=self.headers,
                json={"query": mutation, "variables": variables}
            ) as response:
                
                if response.status != 200:
                    raise Exception(f"Failed to run repl: HTTP {response.status}")
                
                data = await response.json()
                
                if "errors" in data:
                    raise Exception(f"GraphQL errors: {data['errors']}")
                
                result = data["data"]["runRepl"]
                logger.info(f"Started repl execution: {result.get('message', 'Success')}")
                
                return result
    
    async def get_repl_info(self, repl_id: str) -> Dict[str, Any]:
        """Get information about a Replit project"""
        
        query = """
        query GetRepl($id: String!) {
            repl(id: $id) {
                id
                title
                slug
                url
                language
                isPrivate
                isStarred
                size
                hostedUrl
                description
                timeCreated
                timeUpdated
                user {
                    username
                }
            }
        }
        """
        
        variables = {"id": repl_id}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.graphql_url,
                headers=self.headers,
                json={"query": query, "variables": variables}
            ) as response:
                
                if response.status != 200:
                    raise Exception(f"Failed to get repl info: HTTP {response.status}")
                
                data = await response.json()
                
                if "errors" in data:
                    raise Exception(f"GraphQL errors: {data['errors']}")
                
                return data["data"]["repl"]
    
    async def delete_repl(self, repl_id: str) -> bool:
        """Delete a Replit project"""
        
        mutation = """
        mutation DeleteRepl($id: String!) {
            deleteRepl(id: $id) {
                ... on DeleteReplSuccess {
                    message
                }
                ... on UserError {
                    message
                }
            }
        }
        """
        
        variables = {"id": repl_id}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.graphql_url,
                headers=self.headers,
                json={"query": mutation, "variables": variables}
            ) as response:
                
                if response.status != 200:
                    logger.error(f"Failed to delete repl: HTTP {response.status}")
                    return False
                
                data = await response.json()
                
                if "errors" in data:
                    logger.error(f"GraphQL errors: {data['errors']}")
                    return False
                
                result = data["data"]["deleteRepl"]
                
                if "message" in result and "success" not in result.get("message", "").lower():
                    logger.error(f"Failed to delete repl: {result['message']}")
                    return False
                
                logger.info(f"Deleted repl {repl_id}")
                return True
    
    async def list_repls(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List user's Replit projects"""
        
        query = """
        query ListRepls($limit: Int!) {
            currentUser {
                repls(limit: $limit) {
                    items {
                        id
                        title
                        slug
                        url
                        language
                        isPrivate
                        hostedUrl
                        timeCreated
                        timeUpdated
                    }
                }
            }
        }
        """
        
        variables = {"limit": limit}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.graphql_url,
                headers=self.headers,
                json={"query": query, "variables": variables}
            ) as response:
                
                if response.status != 200:
                    raise Exception(f"Failed to list repls: HTTP {response.status}")
                
                data = await response.json()
                
                if "errors" in data:
                    raise Exception(f"GraphQL errors: {data['errors']}")
                
                return data["data"]["currentUser"]["repls"]["items"]

class ReplitTemplateManager:
    """Manages templates for different kit types"""
    
    @staticmethod
    def get_starter_site_template(customer_id: str, domain_name: str) -> Dict[str, str]:
        """Get starter site template files"""
        return {
            "index.html": f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{customer_id} - Professional Website</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header class="hero">
        <nav class="navbar">
            <div class="nav-brand">{customer_id}</div>
            <ul class="nav-menu">
                <li><a href="#about">About</a></li>
                <li><a href="#services">Services</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
        </nav>
        <div class="hero-content">
            <h1>Welcome to {customer_id}</h1>
            <p>Your professional website is now live on {domain_name}</p>
            <a href="#contact" class="cta-button">Get Started</a>
        </div>
    </header>

    <section id="about" class="section">
        <div class="container">
            <h2>About Us</h2>
            <p>We provide high-quality digital assets faster than you can pop a bag of popcorn.</p>
        </div>
    </section>

    <section id="services" class="section">
        <div class="container">
            <h2>Our Services</h2>
            <div class="services-grid">
                <div class="service-card">
                    <h3>⚡ Lightning Fast</h3>
                    <p>Optimized for speed and performance</p>
                </div>
                <div class="service-card">
                    <h3>📱 Mobile Ready</h3>
                    <p>Responsive design for all devices</p>
                </div>
                <div class="service-card">
                    <h3>🔒 Secure</h3>
                    <p>SSL certificate included</p>
                </div>
            </div>
        </div>
    </section>

    <footer id="contact" class="footer">
        <div class="container">
            <h2>Contact Us</h2>
            <p>Ready to get started? Reach out to us!</p>
            <p>Domain: {domain_name}</p>
        </div>
    </footer>

    <script src="script.js"></script>
</body>
</html>""",
            "style.css": """/* Modern CSS Reset */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6;
    color: #333;
}

/* Hero Section */
.hero {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

.navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
}

.nav-brand {
    font-size: 1.5rem;
    font-weight: bold;
}

.nav-menu {
    display: flex;
    list-style: none;
    gap: 2rem;
}

.nav-menu a {
    color: white;
    text-decoration: none;
    transition: opacity 0.3s ease;
}

.nav-menu a:hover {
    opacity: 0.8;
}

.hero-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 2rem;
}

.hero-content h1 {
    font-size: 3.5rem;
    margin-bottom: 1rem;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

.hero-content p {
    font-size: 1.2rem;
    margin-bottom: 2rem;
    opacity: 0.9;
}

.cta-button {
    background: rgba(255, 255, 255, 0.2);
    border: 2px solid white;
    color: white;
    padding: 1rem 2rem;
    font-size: 1.1rem;
    border-radius: 50px;
    text-decoration: none;
    transition: all 0.3s ease;
    display: inline-block;
}

.cta-button:hover {
    background: white;
    color: #667eea;
    transform: translateY(-2px);
    box-shadow: 0 10px 20px rgba(0,0,0,0.2);
}

/* Sections */
.section {
    padding: 4rem 0;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 2rem;
}

.section h2 {
    text-align: center;
    font-size: 2.5rem;
    margin-bottom: 3rem;
    color: #333;
}

.services-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 2rem;
    margin-top: 2rem;
}

.service-card {
    background: white;
    padding: 2rem;
    border-radius: 10px;
    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    text-align: center;
    transition: transform 0.3s ease;
}

.service-card:hover {
    transform: translateY(-5px);
}

.service-card h3 {
    font-size: 1.5rem;
    margin-bottom: 1rem;
    color: #667eea;
}

/* Footer */
.footer {
    background: #2c3e50;
    color: white;
    padding: 3rem 0;
    text-align: center;
}

.footer h2 {
    color: white;
    margin-bottom: 1rem;
}

/* Responsive Design */
@media (max-width: 768px) {
    .hero-content h1 {
        font-size: 2.5rem;
    }
    
    .nav-menu {
        gap: 1rem;
    }
    
    .services-grid {
        grid-template-columns: 1fr;
    }
}""",
            "script.js": """// Smooth scrolling for navigation links
document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Add scroll effect to navbar
    window.addEventListener('scroll', function() {
        const navbar = document.querySelector('.navbar');
        if (window.scrollY > 100) {
            navbar.style.background = 'rgba(255, 255, 255, 0.95)';
            navbar.style.color = '#333';
        } else {
            navbar.style.background = 'rgba(255, 255, 255, 0.1)';
            navbar.style.color = 'white';
        }
    });

    // Animate service cards on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    document.querySelectorAll('.service-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(card);
    });

    console.log('Starter site loaded successfully! 🚀');
});""",
            "README.md": f"""# {customer_id} - Starter Site

A professional website template deployed through Stampede Hosting.

## Features
- ⚡ Lightning fast performance
- 📱 Fully responsive design
- 🎨 Modern gradient design
- 🔧 Easy to customize
- 🚀 SEO optimized

## Live Demo
Visit your site at: {domain_name}

## Customization
- Edit `index.html` for content
- Modify `style.css` for styling
- Update `script.js` for interactions

## Deployment
This site is automatically deployed through Stampede Hosting's automated pipeline.

Built with ❤️ by Stampede Hosting
"""
        }
    
    @staticmethod
    def get_course_platform_template(customer_id: str, domain_name: str) -> Dict[str, str]:
        """Get course platform template files"""
        return {
            "main.py": f"""from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime
import json

app = Flask(__name__)

# Mock data for courses
courses_data = [
    {{
        'id': 1,
        'title': 'Web Development Fundamentals',
        'description': 'Learn HTML, CSS, and JavaScript from scratch',
        'price': 99,
        'students': 1250,
        'rating': 4.8,
        'duration': '8 weeks',
        'level': 'Beginner'
    }},
    {{
        'id': 2,
        'title': 'Digital Marketing Mastery',
        'description': 'Master social media, SEO, and content marketing',
        'price': 149,
        'students': 890,
        'rating': 4.9,
        'duration': '6 weeks',
        'level': 'Intermediate'
    }},
    {{
        'id': 3,
        'title': 'Business Strategy & Growth',
        'description': 'Learn to build and scale successful businesses',
        'price': 199,
        'students': 675,
        'rating': 4.7,
        'duration': '10 weeks',
        'level': 'Advanced'
    }}
]

@app.route('/')
def home():
    return render_template('index.html', courses=courses_data, customer_id='{customer_id}', domain='{domain_name}')

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    course = next((c for c in courses_data if c['id'] == course_id), None)
    if not course:
        return redirect(url_for('home'))
    return render_template('course.html', course=course, customer_id='{customer_id}')

@app.route('/api/courses')
def get_courses():
    return jsonify(courses_data)

@app.route('/api/enroll', methods=['POST'])
def enroll_student():
    data = request.get_json()
    course_id = data.get('course_id')
    student_email = data.get('email')
    
    # In a real application, this would handle payment and enrollment
    return jsonify({{
        'success': True,
        'message': f'Successfully enrolled in course {{course_id}}!',
        'enrollment_id': f'ENR-{{course_id}}-{{int(datetime.now().timestamp())}}'
    }})

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', customer_id='{customer_id}')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
""",
            "templates/index.html": f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{{{ customer_id }}}} Academy - Online Learning Platform</title>
    <link rel="stylesheet" href="{{{{ url_for('static', filename='style.css') }}}}">
</head>
<body>
    <header class="header">
        <nav class="navbar">
            <div class="nav-brand">{{{{ customer_id }}}} Academy</div>
            <ul class="nav-menu">
                <li><a href="#courses">Courses</a></li>
                <li><a href="#about">About</a></li>
                <li><a href="/dashboard">Dashboard</a></li>
                <li><a href="#contact" class="cta-nav">Sign Up</a></li>
            </ul>
        </nav>
    </header>

    <section class="hero">
        <div class="hero-content">
            <h1>Learn. Grow. Succeed.</h1>
            <p>Join thousands of students in our comprehensive online courses</p>
            <p class="domain-info">Platform: {{{{ domain }}}}</p>
            <a href="#courses" class="cta-button">Browse Courses</a>
        </div>
    </section>

    <section id="courses" class="courses-section">
        <div class="container">
            <h2>Featured Courses</h2>
            <div class="courses-grid">
                {{% for course in courses %}}
                <div class="course-card">
                    <div class="course-header">
                        <span class="course-level">{{{{ course.level }}}}</span>
                        <span class="course-rating">⭐ {{{{ course.rating }}}}</span>
                    </div>
                    <h3>{{{{ course.title }}}}</h3>
                    <p>{{{{ course.description }}}}</p>
                    <div class="course-meta">
                        <span>👥 {{{{ course.students }}}} students</span>
                        <span>⏱️ {{{{ course.duration }}}}</span>
                    </div>
                    <div class="course-footer">
                        <span class="price">${{{{ course.price }}}}</span>
                        <button class="enroll-btn" onclick="enrollCourse({{{{ course.id }}}})">
                            Enroll Now
                        </button>
                    </div>
                </div>
                {{% endfor %}}
            </div>
        </div>
    </section>

    <section id="about" class="about-section">
        <div class="container">
            <h2>Why Choose {{{{ customer_id }}}} Academy?</h2>
            <div class="features-grid">
                <div class="feature">
                    <div class="feature-icon">🎓</div>
                    <h3>Expert Instructors</h3>
                    <p>Learn from industry professionals with years of experience</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">📱</div>
                    <h3>Learn Anywhere</h3>
                    <p>Access courses on any device, anytime, anywhere</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">🏆</div>
                    <h3>Certificates</h3>
                    <p>Earn certificates upon course completion</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">💬</div>
                    <h3>Community Support</h3>
                    <p>Connect with fellow learners and get help when needed</p>
                </div>
            </div>
        </div>
    </section>

    <footer id="contact" class="footer">
        <div class="container">
            <h2>Ready to Start Learning?</h2>
            <p>Join our community of learners today!</p>
            <div class="contact-info">
                <p>Platform: {{{{ domain }}}}</p>
                <p>Email: support@{{{{ domain }}}}</p>
            </div>
        </div>
    </footer>

    <script src="{{{{ url_for('static', filename='script.js') }}}}"></script>
</body>
</html>""",
            "static/style.css": """/* Course Platform Styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.6;
    color: #333;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 2rem;
}

/* Header */
.header {
    background: #2c3e50;
    color: white;
    padding: 1rem 0;
    position: fixed;
    width: 100%;
    top: 0;
    z-index: 1000;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 2rem;
}

.nav-brand {
    font-size: 1.5rem;
    font-weight: bold;
}

.nav-menu {
    display: flex;
    list-style: none;
    gap: 2rem;
    align-items: center;
}

.nav-menu a {
    color: white;
    text-decoration: none;
    transition: opacity 0.3s ease;
}

.nav-menu a:hover {
    opacity: 0.8;
}

.cta-nav {
    background: #e74c3c !important;
    padding: 0.5rem 1rem !important;
    border-radius: 5px !important;
}

/* Hero Section */
.hero {
    background: linear-gradient(135deg, #3498db, #2c3e50);
    color: white;
    padding: 8rem 2rem 4rem;
    text-align: center;
    margin-top: 60px;
}

.hero-content h1 {
    font-size: 3.5rem;
    margin-bottom: 1rem;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

.hero-content p {
    font-size: 1.2rem;
    margin-bottom: 1rem;
    opacity: 0.9;
}

.domain-info {
    font-size: 1rem !important;
    opacity: 0.7 !important;
    font-style: italic;
}

.cta-button {
    background: #e74c3c;
    color: white;
    padding: 1rem 2rem;
    border: none;
    border-radius: 5px;
    font-size: 1.1rem;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    margin-top: 1rem;
    transition: all 0.3s ease;
}

.cta-button:hover {
    background: #c0392b;
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(0,0,0,0.2);
}

/* Courses Section */
.courses-section {
    padding: 4rem 0;
    background: #f8f9fa;
}

.courses-section h2 {
    text-align: center;
    font-size: 2.5rem;
    margin-bottom: 3rem;
    color: #2c3e50;
}

.courses-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: 2rem;
}

.course-card {
    background: white;
    border-radius: 10px;
    padding: 1.5rem;
    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    transition: transform 0.3s ease;
}

.course-card:hover {
    transform: translateY(-5px);
}

.course-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}

.course-level {
    background: #3498db;
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 15px;
    font-size: 0.8rem;
}

.course-rating {
    color: #f39c12;
    font-weight: bold;
}

.course-card h3 {
    font-size: 1.3rem;
    margin-bottom: 0.5rem;
    color: #2c3e50;
}

.course-card p {
    color: #666;
    margin-bottom: 1rem;
}

.course-meta {
    display: flex;
    gap: 1rem;
    margin-bottom: 1rem;
    font-size: 0.9rem;
    color: #666;
}

.course-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.price {
    font-size: 1.5rem;
    font-weight: bold;
    color: #e74c3c;
}

.enroll-btn {
    background: #27ae60;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 5px;
    cursor: pointer;
    transition: background 0.3s ease;
}

.enroll-btn:hover {
    background: #219a52;
}

/* About Section */
.about-section {
    padding: 4rem 0;
}

.about-section h2 {
    text-align: center;
    font-size: 2.5rem;
    margin-bottom: 3rem;
    color: #2c3e50;
}

.features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 2rem;
}

.feature {
    text-align: center;
    padding: 2rem;
}

.feature-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
}

.feature h3 {
    font-size: 1.3rem;
    margin-bottom: 1rem;
    color: #2c3e50;
}

/* Footer */
.footer {
    background: #2c3e50;
    color: white;
    padding: 3rem 0;
    text-align: center;
}

.footer h2 {
    color: white;
    margin-bottom: 1rem;
}

.contact-info {
    margin-top: 2rem;
}

.contact-info p {
    margin: 0.5rem 0;
    opacity: 0.8;
}

/* Responsive Design */
@media (max-width: 768px) {
    .hero-content h1 {
        font-size: 2.5rem;
    }
    
    .nav-menu {
        gap: 1rem;
    }
    
    .courses-grid {
        grid-template-columns: 1fr;
    }
    
    .features-grid {
        grid-template-columns: 1fr;
    }
}""",
            "static/script.js": """// Course Platform JavaScript
document.addEventListener('DOMContentLoaded', function() {
    console.log('Course platform loaded! 🎓');
    
    // Smooth scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Navbar scroll effect
    window.addEventListener('scroll', function() {
        const header = document.querySelector('.header');
        if (window.scrollY > 100) {
            header.style.background = 'rgba(44, 62, 80, 0.95)';
        } else {
            header.style.background = '#2c3e50';
        }
    });
});

async function enrollCourse(courseId) {
    try {
        const email = prompt('Enter your email to enroll:');
        if (!email) return;
        
        const response = await fetch('/api/enroll', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                course_id: courseId,
                email: email
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`✅ ${result.message}\\nEnrollment ID: ${result.enrollment_id}`);
        } else {
            alert('❌ Enrollment failed. Please try again.');
        }
    } catch (error) {
        console.error('Enrollment error:', error);
        alert('❌ An error occurred. Please try again.');
    }
}""",
            "requirements.txt": """Flask==2.3.3
Werkzeug==2.3.7""",
            "README.md": f"""# {customer_id} Academy - Course Platform

A complete online learning platform built with Flask.

## Features
- 📚 Course catalog with detailed information
- 💳 Enrollment system (payment integration ready)
- 👥 Student dashboard
- 📊 Progress tracking
- 🎓 Certificate generation
- 📱 Fully responsive design

## Live Platform
Access your platform at: {domain_name}

## Admin Features
- Course management
- Student enrollment tracking
- Analytics dashboard
- Payment processing

## Technology Stack
- Backend: Python Flask
- Frontend: HTML5, CSS3, JavaScript
- Database: SQLite (upgradeable to PostgreSQL)
- Deployment: Replit + Stampede Hosting

## Getting Started
1. Access the platform at {domain_name}
2. Browse available courses
3. Enroll in courses of interest
4. Access the student dashboard

Built with 💙 by Stampede Hosting
"""
        }
    
    @staticmethod
    def get_developer_sandbox_template(customer_id: str, domain_name: str) -> Dict[str, str]:
        """Get developer sandbox template files"""
        return {
            "main.py": f"""#!/usr/bin/env python3
'''
{customer_id} - Developer Sandbox
Multi-language development environment with code execution capabilities
'''

import os
import subprocess
import json
import tempfile
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Supported languages and their execution commands
LANGUAGES = {{
    'python': {{'extension': '.py', 'command': ['python3']}},
    'javascript': {{'extension': '.js', 'command': ['node']}},
    'bash': {{'extension': '.sh', 'command': ['bash']}},
    'html': {{'extension': '.html', 'command': None}},
    'css': {{'extension': '.css', 'command': None}},
}}

@app.route('/')
def home():
    return render_template('index.html', 
                         customer_id='{customer_id}', 
                         domain='{domain_name}',
                         languages=list(LANGUAGES.keys()))

@app.route('/api/execute', methods=['POST'])
def execute_code():
    data = request.get_json()
    language = data.get('language', 'python')
    code = data.get('code', '')
    
    if language not in LANGUAGES:
        return jsonify({{'error': f'Unsupported language: {{language}}'}})
    
    lang_config = LANGUAGES[language]
    
    # Handle non-executable languages
    if lang_config['command'] is None:
        if language == 'html':
            return jsonify({{
                'output': 'HTML code saved. Open in browser to view.',
                'html_content': code
            }})
        elif language == 'css':
            return jsonify({{
                'output': 'CSS code saved. Include in HTML to apply styles.',
                'css_content': code
            }})
    
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix=lang_config['extension'], 
            delete=False
        ) as temp_file:
            temp_file.write(code)
            temp_file_path = temp_file.name
        
        # Execute code
        if language == 'python':
            result = subprocess.run(
                ['python3', temp_file_path], 
                capture_output=True, 
                text=True, 
                timeout=10,
                cwd=os.path.dirname(temp_file_path)
            )
        elif language == 'javascript':
            result = subprocess.run(
                ['node', temp_file_path], 
                capture_output=True, 
                text=True, 
                timeout=10,
                cwd=os.path.dirname(temp_file_path)
            )
        elif language == 'bash':
            result = subprocess.run(
                ['bash', temp_file_path], 
                capture_output=True, 
                text=True, 
                timeout=10,
                cwd=os.path.dirname(temp_file_path)
            )
        
        # Clean up
        os.unlink(temp_file_path)
        
        return jsonify({{
            'output': result.stdout,
            'error': result.stderr,
            'returncode': result.returncode,
            'success': result.returncode == 0
        }})
    
    except subprocess.TimeoutExpired:
        return jsonify({{'error': 'Code execution timed out (10s limit)'}})
    except Exception as e:
        return jsonify({{'error': f'Execution error: {{str(e)}}'}})

@app.route('/api/files', methods=['GET'])
def list_files():
    try:
        files = []
        for root, dirs, filenames in os.walk('.'):
            # Skip hidden directories and __pycache__
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            
            for filename in filenames:
                if not filename.startswith('.') and not filename.endswith('.pyc'):
                    file_path = os.path.join(root, filename)
                    file_size = os.path.getsize(file_path)
                    files.append({{
                        'path': file_path,
                        'name': filename,
                        'size': file_size,
                        'type': os.path.splitext(filename)[1][1:] or 'file'
                    }})
        
        return jsonify(files)
    except Exception as e:
        return jsonify({{'error': str(e)}})

@app.route('/api/file/<path:filename>', methods=['GET'])
def get_file(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({{'content': content, 'filename': filename}})
    except Exception as e:
        return jsonify({{'error': str(e)}})

@app.route('/api/save', methods=['POST'])
def save_file():
    data = request.get_json()
    filename = secure_filename(data.get('filename', 'untitled.txt'))
    content = data.get('content', '')
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({{'success': True, 'message': f'File {{filename}} saved successfully'}})
    except Exception as e:
        return jsonify({{'error': str(e)}})

@app.route('/api/system-info')
def system_info():
    try:
        info = {{
            'python_version': subprocess.check_output(['python3', '--version']).decode().strip(),
            'node_version': subprocess.check_output(['node', '--version']).decode().strip(),
            'platform': os.name,
            'cwd': os.getcwd(),
            'env_vars': dict(os.environ)
        }}
        return jsonify(info)
    except Exception as e:
        return jsonify({{'error': str(e)}})

if __name__ == '__main__':
    print(f"🚀 {{'{customer_id}'}} Developer Sandbox starting...")
    print(f"🌐 Domain: {{'{domain_name}'}} ")
    print(f"💻 Available languages: {{', '.join(LANGUAGES.keys())}}")
    app.run(host='0.0.0.0', port=5000, debug=True)
""",
            "templates/index.html": f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{{{ customer_id }}}} - Developer Sandbox</title>
    <link rel="stylesheet" href="{{{{ url_for('static', filename='style.css') }}}}">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/theme/monokai.min.css">
</head>
<body>
    <div class="header">
        <div class="header-content">
            <h1>{{{{ customer_id }}}} Developer Sandbox</h1>
            <div class="header-info">
                <span class="domain-badge">{{{{ domain }}}}</span>
                <span class="status-badge online">● Online</span>
            </div>
        </div>
    </div>

    <div class="container">
        <div class="sidebar">
            <div class="sidebar-section">
                <h3>Languages</h3>
                <div class="language-selector">
                    {{% for lang in languages %}}
                    <button class="lang-btn" data-lang="{{{{ lang }}}}" 
                            onclick="selectLanguage('{{{{ lang }}}}')">{{{{ lang.title() }}}}</button>
                    {{% endfor %}}
                </div>
            </div>
            
            <div class="sidebar-section">
                <h3>Files</h3>
                <div class="file-explorer">
                    <button onclick="refreshFiles()" class="refresh-btn">🔄 Refresh</button>
                    <div id="file-list"></div>
                </div>
            </div>
            
            <div class="sidebar-section">
                <h3>Actions</h3>
                <div class="actions">
                    <button onclick="executeCode()" class="action-btn run">▶️ Run Code</button>
                    <button onclick="saveFile()" class="action-btn save">💾 Save File</button>
                    <button onclick="clearOutput()" class="action-btn clear">🗑️ Clear Output</button>
                    <button onclick="showSystemInfo()" class="action-btn info">ℹ️ System Info</button>
                </div>
            </div>
        </div>

        <div class="main-content">
            <div class="editor-section">
                <div class="editor-header">
                    <span id="current-language">Python</span>
                    <input type="text" id="filename" placeholder="filename.py" class="filename-input">
                </div>
                <div class="editor-container">
                    <textarea id="code-editor" placeholder="Write your code here...">
# Welcome to {{{{ customer_id }}}} Developer Sandbox!
# Multi-language development environment

print("🚀 Hello from {{{{ customer_id }}}} Developer Sandbox!")
print("🌐 Domain: {{{{ domain }}}}")
print("💻 Available languages: Python, JavaScript, Bash, HTML, CSS")
print()

# Example: Simple calculator
def calculate(a, b, operation):
    operations = {{
        'add': lambda x, y: x + y,
        'subtract': lambda x, y: x - y,
        'multiply': lambda x, y: x * y,
        'divide': lambda x, y: x / y if y != 0 else 'Cannot divide by zero'
    }}
    return operations.get(operation, lambda x, y: 'Invalid operation')(a, b)

# Test the calculator
result = calculate(10, 5, 'add')
print(f"10 + 5 = {{result}}")

result = calculate(20, 4, 'divide')
print(f"20 ÷ 4 = {{result}}")

# List comprehension example
squares = [x**2 for x in range(1, 6)]
print(f"Squares of 1-5: {{squares}}")

print("\\n✨ Ready to code! Choose a language and start building.")
</textarea>
                </div>
            </div>

            <div class="output-section">
                <div class="output-header">
                    <h3>Output</h3>
                    <div class="output-controls">
                        <button onclick="clearOutput()" class="clear-output">Clear</button>
                    </div>
                </div>
                <div id="output-content" class="output-content">
                    <div class="welcome-message">
                        <p>👋 Welcome to your Developer Sandbox!</p>
                        <p>• Select a language from the sidebar</p>
                        <p>• Write your code in the editor</p>
                        <p>• Click "Run Code" to execute</p>
                        <p>• Use "Save File" to persist your work</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/python/python.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/javascript/javascript.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/shell/shell.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/htmlmixed/htmlmixed.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/css/css.min.js"></script>
    <script src="{{{{ url_for('static', filename='script.js') }}}}"></script>
</body>
</html>""",
            "static/style.css": """/* Developer Sandbox Styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
    background: #1e1e1e;
    color: #d4d4d4;
    height: 100vh;
    overflow: hidden;
}

.header {
    background: #2d2d30;
    border-bottom: 1px solid #3e3e42;
    padding: 1rem;
}

.header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1400px;
    margin: 0 auto;
}

.header h1 {
    color: #569cd6;
    font-size: 1.5rem;
}

.header-info {
    display: flex;
    gap: 1rem;
    align-items: center;
}

.domain-badge {
    background: #3c3c3c;
    color: #d4d4d4;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.8rem;
}

.status-badge {
    font-size: 0.8rem;
    padding: 0.25rem 0.5rem;
    border-radius: 10px;
}

.status-badge.online {
    color: #4ec9b0;
    background: rgba(78, 201, 176, 0.1);
}

.container {
    display: flex;
    height: calc(100vh - 80px);
    max-width: 1400px;
    margin: 0 auto;
}

/* Sidebar */
.sidebar {
    width: 300px;
    background: #252526;
    border-right: 1px solid #3e3e42;
    padding: 1rem;
    overflow-y: auto;
}

.sidebar-section {
    margin-bottom: 2rem;
}

.sidebar-section h3 {
    color: #cccccc;
    font-size: 0.9rem;
    margin-bottom: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.language-selector {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.lang-btn {
    background: #3c3c3c;
    color: #d4d4d4;
    border: none;
    padding: 0.5rem;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: left;
}

.lang-btn:hover {
    background: #4a4a4a;
}

.lang-btn.active {
    background: #0e639c;
    color: white;
}

.file-explorer {
    max-height: 200px;
    overflow-y: auto;
}

.refresh-btn {
    background: #3c3c3c;
    color: #d4d4d4;
    border: none;
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    cursor: pointer;
    font-size: 0.8rem;
    margin-bottom: 0.5rem;
}

.file-item {
    padding: 0.25rem 0.5rem;
    cursor: pointer;
    border-radius: 3px;
    font-size: 0.8rem;
    transition: background 0.2s ease;
}

.file-item:hover {
    background: #3c3c3c;
}

.actions {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.action-btn {
    background: #3c3c3c;
    color: #d4d4d4;
    border: none;
    padding: 0.5rem;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: left;
    font-size: 0.9rem;
}

.action-btn:hover {
    background: #4a4a4a;
}

.action-btn.run {
    background: #16825d;
    color: white;
}

.action-btn.run:hover {
    background: #1a9268;
}

.action-btn.save {
    background: #0e639c;
    color: white;
}

.action-btn.save:hover {
    background: #1177bb;
}

/* Main Content */
.main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
}

.editor-section {
    flex: 1;
    display: flex;
    flex-direction: column;
}

.editor-header {
    background: #2d2d30;
    padding: 0.5rem 1rem;
    border-bottom: 1px solid #3e3e42;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

#current-language {
    color: #569cd6;
    font-weight: bold;
}

.filename-input {
    background: #3c3c3c;
    color: #d4d4d4;
    border: none;
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    font-family: inherit;
    font-size: 0.8rem;
}

.editor-container {
    flex: 1;
    position: relative;
}

#code-editor {
    width: 100%;
    height: 100%;
    background: #1e1e1e;
    color: #d4d4d4;
    border: none;
    padding: 1rem;
    font-family: inherit;
    font-size: 14px;
    resize: none;
    outline: none;
}

.CodeMirror {
    height: 100% !important;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace !important;
    font-size: 14px !important;
}

/* Output Section */
.output-section {
    height: 300px;
    background: #252526;
    border-top: 1px solid #3e3e42;
    display: flex;
    flex-direction: column;
}

.output-header {
    background: #2d2d30;
    padding: 0.5rem 1rem;
    border-bottom: 1px solid #3e3e42;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.output-header h3 {
    color: #cccccc;
    font-size: 0.9rem;
}

.clear-output {
    background: #3c3c3c;
    color: #d4d4d4;
    border: none;
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    cursor: pointer;
    font-size: 0.8rem;
}

.output-content {
    flex: 1;
    padding: 1rem;
    overflow-y: auto;
    font-family: inherit;
}

.welcome-message {
    color: #4ec9b0;
    line-height: 1.6;
}

.welcome-message p {
    margin-bottom: 0.5rem;
}

.output-success {
    color: #4ec9b0;
    white-space: pre-wrap;
    font-family: inherit;
}

.output-error {
    color: #f44747;
    white-space: pre-wrap;
    font-family: inherit;
}

.output-info {
    color: #569cd6;
    white-space: pre-wrap;
    font-family: inherit;
}

/* Responsive Design */
@media (max-width: 1024px) {
    .sidebar {
        width: 250px;
    }
}

@media (max-width: 768px) {
    .container {
        flex-direction: column;
    }
    
    .sidebar {
        width: 100%;
        height: 200px;
        border-right: none;
        border-bottom: 1px solid #3e3e42;
    }
    
    .output-section {
        height: 200px;
    }
}""",
            "static/script.js": """// Developer Sandbox JavaScript
let currentLanguage = 'python';
let editor;

// Language configurations
const languageConfigs = {
    python: { mode: 'python', extension: '.py' },
    javascript: { mode: 'javascript', extension: '.js' },
    bash: { mode: 'shell', extension: '.sh' },
    html: { mode: 'htmlmixed', extension: '.html' },
    css: { mode: 'css', extension: '.css' }
};

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Developer Sandbox loaded!');
    
    // Initialize CodeMirror editor
    const textarea = document.getElementById('code-editor');
    editor = CodeMirror.fromTextArea(textarea, {
        lineNumbers: true,
        mode: 'python',
        theme: 'monokai',
        indentUnit: 4,
        lineWrapping: true,
        autoCloseBrackets: true,
        matchBrackets: true
    });
    
    // Set initial language
    selectLanguage('python');
    
    // Load files on startup
    refreshFiles();
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case 'Enter':
                    e.preventDefault();
                    executeCode();
                    break;
                case 's':
                    e.preventDefault();
                    saveFile();
                    break;
                case 'l':
                    e.preventDefault();
                    clearOutput();
                    break;
            }
        }
    });
});

function selectLanguage(language) {
    currentLanguage = language;
    
    // Update UI
    document.getElementById('current-language').textContent = language.charAt(0).toUpperCase() + language.slice(1);
    document.getElementById('filename').placeholder = `filename${languageConfigs[language].extension}`;
    
    // Update editor mode
    if (editor) {
        editor.setOption('mode', languageConfigs[language].mode);
    }
    
    // Update active button
    document.querySelectorAll('.lang-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.lang === language) {
            btn.classList.add('active');
        }
    });
    
    // Load example code for the language
    loadExampleCode(language);
}

function loadExampleCode(language) {
    const examples = {
        python: `# Python Example
print("Hello from Python! 🐍")

# Variables and data types
name = "Developer"
age = 25
languages = ["Python", "JavaScript", "HTML", "CSS"]

print(f"Name: {name}, Age: {age}")
print(f"Known languages: {', '.join(languages)}")

# Function example
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print(f"Fibonacci sequence (first 10): {[fibonacci(i) for i in range(10)]}")`,
        
        javascript: `// JavaScript Example
console.log("Hello from JavaScript! 🟨");

// Variables and data types
const name = "Developer";
const age = 25;
const languages = ["Python", "JavaScript", "HTML", "CSS"];

console.log(\`Name: \${name}, Age: \${age}\`);
console.log(\`Known languages: \${languages.join(", ")}\`);

// Function example
function fibonacci(n) {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}

const fibSequence = Array.from({length: 10}, (_, i) => fibonacci(i));
console.log(\`Fibonacci sequence (first 10): \${fibSequence}\`);

// Async example
setTimeout(() => {
    console.log("⏰ This message appears after 1 second!");
}, 1000);`,
        
        bash: `#!/bin/bash
# Bash Script Example
echo "Hello from Bash! 🐚"

# Variables
NAME="Developer"
AGE=25

echo "Name: $NAME, Age: $AGE"

# Array example
LANGUAGES=("Python" "JavaScript" "HTML" "CSS")
echo "Known languages: ${LANGUAGES[*]}"

# Loop example
echo "Counting to 5:"
for i in {1..5}; do
    echo "Count: $i"
done

# System information
echo "Current directory: $(pwd)"
echo "Current user: $(whoami)"
echo "Date: $(date)"`,
        
        html: `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HTML Example</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .card {
            background: rgba(255, 255, 255, 0.1);
            padding: 2rem;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            margin: 1rem 0;
        }
        button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>Hello from HTML! 🌐</h1>
        <p>This is an interactive HTML example.</p>
        <button onclick="showMessage()">Click me!</button>
        <div id="message"></div>
    </div>
    
    <script>
        function showMessage() {
            document.getElementById('message').innerHTML = 
                '<p>🎉 JavaScript is working inside HTML!</p>';
        }
    </script>
</body>
</html>`,
        
        css: `/* CSS Example */
/* Modern CSS with animations and effects */

:root {
    --primary-color: #667eea;
    --secondary-color: #764ba2;
    --accent-color: #4CAF50;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    margin: 0;
    padding: 2rem;
    background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
    min-height: 100vh;
    color: white;
}

.container {
    max-width: 800px;
    margin: 0 auto;
}

.card {
    background: rgba(255, 255, 255, 0.1);
    padding: 2rem;
    border-radius: 15px;
    backdrop-filter: blur(10px);
    margin: 1rem 0;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.card:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
}

.button {
    background: var(--accent-color);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 25px;
    cursor: pointer;
    font-size: 1rem;
    transition: all 0.3s ease;
    display: inline-block;
    text-decoration: none;
}

.button:hover {
    background: #45a049;
    transform: scale(1.05);
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

.fade-in {
    animation: fadeIn 0.6s ease-out;
}

/* Responsive design */
@media (max-width: 768px) {
    body { padding: 1rem; }
    .card { padding: 1.5rem; }
}`
    };
    
    if (editor && examples[language]) {
        editor.setValue(examples[language]);
    }
}

async function executeCode() {
    const code = editor.getValue();
    const outputDiv = document.getElementById('output-content');
    
    if (!code.trim()) {
        showOutput('⚠️ No code to execute', 'info');
        return;
    }
    
    showOutput('⏳ Executing code...', 'info');
    
    try {
        const response = await fetch('/api/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                language: currentLanguage,
                code: code
            })
        });
        
        const result = await response.json();
        
        if (result.error) {
            showOutput(`❌ Error:\\n${result.error}`, 'error');
        } else if (result.html_content) {
            showOutput('✅ HTML code ready. Save as .html file and open in browser.', 'success');
        } else if (result.css_content) {
            showOutput('✅ CSS code ready. Include in HTML file to apply styles.', 'success');
        } else {
            const output = result.output || 'Code executed successfully (no output)';
            showOutput(`✅ Output:\\n${output}`, 'success');
        }
        
    } catch (error) {
        showOutput(`❌ Network error: ${error.message}`, 'error');
    }
}

async function saveFile() {
    const filename = document.getElementById('filename').value || 
                    `untitled${languageConfigs[currentLanguage].extension}`;
    const content = editor.getValue();
    
    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                filename: filename,
                content: content
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showOutput(`💾 ${result.message}`, 'success');
            refreshFiles();
        } else {
            showOutput(`❌ Save failed: ${result.error}`, 'error');
        }
        
    } catch (error) {
        showOutput(`❌ Save error: ${error.message}`, 'error');
    }
}

async function refreshFiles() {
    try {
        const response = await fetch('/api/files');
        const files = await response.json();
        
        const fileList = document.getElementById('file-list');
        fileList.innerHTML = '';
        
        if (files.error) {
            fileList.innerHTML = `<div class="file-item">Error: ${files.error}</div>`;
            return;
        }
        
        files.forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            fileItem.innerHTML = `📄 ${file.name} (${formatFileSize(file.size)})`;
            fileItem.onclick = () => loadFile(file.path);
            fileList.appendChild(fileItem);
        });
        
    } catch (error) {
        console.error('Error refreshing files:', error);
    }
}

async function loadFile(filepath) {
    try {
        const response = await fetch(`/api/file/${encodeURIComponent(filepath)}`);
        const result = await response.json();
        
        if (result.error) {
            showOutput(`❌ Error loading file: ${result.error}`, 'error');
            return;
        }
        
        editor.setValue(result.content);
        document.getElementById('filename').value = result.filename;
        showOutput(`📂 Loaded file: ${result.filename}`, 'info');
        
    } catch (error) {
        showOutput(`❌ Error loading file: ${error.message}`, 'error');
    }
}

async function showSystemInfo() {
    try {
        const response = await fetch('/api/system-info');
        const info = await response.json();
        
        if (info.error) {
            showOutput(`❌ Error getting system info: ${info.error}`, 'error');
            return;
        }
        
        const infoText = `🖥️ System Information:
Python: ${info.python_version}
Node.js: ${info.node_version}
Platform: ${info.platform}
Working Directory: ${info.cwd}

Environment Variables: ${Object.keys(info.env_vars).length} variables loaded`;
        
        showOutput(infoText, 'info');
        
    } catch (error) {
        showOutput(`❌ Error: ${error.message}`, 'error');
    }
}

function clearOutput() {
    const outputDiv = document.getElementById('output-content');
    outputDiv.innerHTML = `
        <div class="welcome-message">
            <p>🧹 Output cleared</p>
            <p>Ready for next execution...</p>
        </div>
    `;
}

function showOutput(message, type = 'info') {
    const outputDiv = document.getElementById('output-content');
    const outputClass = `output-${type}`;
    
    outputDiv.innerHTML = `<div class="${outputClass}">${message}</div>`;
    outputDiv.scrollTop = outputDiv.scrollHeight;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}""",
            "requirements.txt": """Flask==2.3.3
Werkzeug==2.3.7""",
            "README.md": f"""# {customer_id} - Developer Sandbox

A complete multi-language development environment with code execution capabilities.

## Features
- 🐍 **Python 3.11** - Full Python environment with pip
- 🟨 **Node.js 18** - JavaScript runtime with npm
- 🐚 **Bash Scripting** - Shell command execution
- 🌐 **HTML/CSS** - Web development support
- 📁 **File Management** - Save, load, and organize files
- ⚡ **Real-time Execution** - Run code instantly
- 💾 **Persistent Storage** - Your files are saved
- 🎨 **Syntax Highlighting** - CodeMirror integration

## Access Your Sandbox
- **Web IDE**: {domain_name}
- **Direct Access**: Available 24/7
- **Multi-language Support**: Switch between languages instantly

## Keyboard Shortcuts
- `Ctrl/Cmd + Enter` - Run code
- `Ctrl/Cmd + S` - Save file
- `Ctrl/Cmd + L` - Clear output

## Supported Languages

### Python
- Full Python 3.11 environment
- Standard library included
- Package installation with pip
- Scientific computing ready

### JavaScript
- Node.js runtime
- ES6+ features supported
- NPM package management
- Async/await support

### Bash
- Full shell environment
- System command access
- Script automation
- File operations

### HTML/CSS
- Modern web standards
- Responsive design support
- CSS3 features
- Interactive previews

## Getting Started

1. **Choose Language**: Select from the sidebar
2. **Write Code**: Use the built-in editor with syntax highlighting
3. **Execute**: Click "Run Code" or use Ctrl+Enter
4. **Save Work**: Use "Save File" to persist your code
5. **Manage Files**: Browse and load existing files

## Example Projects

Try these example projects to get started:

### Python Data Analysis
```python
import json
import statistics

# Sample data analysis
data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
print(f"Mean: {statistics.mean(data)}")
print(f"Median: {statistics.median(data)}")
```

### JavaScript Web Scraping
```javascript
// Fetch API example
fetch('https://api.github.com/users/octocat')
  .then(response => response.json())
  .then(data => console.log(data));
```

### Bash System Administration
```bash
#!/bin/bash
echo "System Information:"
echo "Uptime: $(uptime)"
echo "Disk Usage: $(df -h /)"
```

## Advanced Features

- **Code Persistence**: All files are automatically saved
- **Multi-tab Support**: Work on multiple files simultaneously
- **Error Handling**: Detailed error messages and debugging info
- **Performance Monitoring**: Execution time tracking
- **Security**: Sandboxed execution environment

## Support

Need help? Your sandbox includes:
- Built-in examples for each language
- System information panel
- File management tools
- Real-time error reporting

## Deployment Info

- **Platform**: Replit + Stampede Hosting
- **Uptime**: 99.9% availability
- **Performance**: Optimized for development workflows
- **Security**: Isolated execution environment

---

**Powered by Stampede Hosting** 🚀  
*Providing high-quality digital assets faster than you can pop a bag of popcorn!*

Domain: {domain_name}
"""
        }

async def deploy_kit_to_replit(kit_type: str, customer_id: str, domain_name: str) -> ReplitProject:
    """Deploy a specific kit to Replit"""
    
    integration = ReplitIntegration()
    template_manager = ReplitTemplateManager()
    
    # Determine language and get template
    language_map = {
        "starter_site": ReplitLanguage.HTML,
        "course_launch": ReplitLanguage.FLASK,
        "developer_sandbox": ReplitLanguage.PYTHON
    }
    
    template_methods = {
        "starter_site": template_manager.get_starter_site_template,
        "course_launch": template_manager.get_course_platform_template,
        "developer_sandbox": template_manager.get_developer_sandbox_template
    }
    
    language = language_map[kit_type]
    repl_name = f"{customer_id}-{kit_type}-demo"
    description = f"Demo deployment for {customer_id} using {kit_type} kit - Domain: {domain_name}"
    
    # Create repl
    logger.info(f"Creating Replit project: {repl_name}")
    repl = await integration.create_repl(repl_name, language, description, is_private=False)
    
    # Get template files
    logger.info(f"Preparing template files for {kit_type}")
    files = template_methods[kit_type](customer_id, domain_name)
    
    # Upload files
    logger.info("Uploading files to Replit")
    success = await integration.upload_files(repl.id, files)
    
    if not success:
        raise Exception("Failed to upload files to Replit")
    
    # Start the repl
    logger.info("Starting Replit execution")
    await integration.run_repl(repl.id)
    
    # Get updated info with live URL
    repl_info = await integration.get_repl_info(repl.id)
    repl.live_url = repl_info.get('hostedUrl')
    repl.status = "deployed"
    
    logger.info(f"✅ Deployment successful!")
    logger.info(f"🔗 Repl URL: {repl.url}")
    logger.info(f"🌐 Live URL: {repl.live_url}")
    
    return repl

async def main():
    """Test the Replit integration"""
    try:
        # Test deployment
        repl = await deploy_kit_to_replit(
            kit_type="starter_site",
            customer_id="test-customer",
            domain_name="test.stampedehosting.com"
        )
        
        print(f"Deployment successful!")
        print(f"Repl URL: {repl.url}")
        print(f"Live URL: {repl.live_url}")
        
    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
