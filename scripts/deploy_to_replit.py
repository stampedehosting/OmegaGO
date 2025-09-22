#!/usr/bin/env python3
"""
Script to deploy projects to Replit for quick demos
Integrates with Replit API to create and configure repls
"""

import os
import json
import requests
import argparse
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ReplitDeployer:
    """Handles deployment to Replit"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://replit.com/api/v0"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    def create_repl(self, name: str, language: str, description: str = "") -> Dict[str, Any]:
        """Create a new repl"""
        payload = {
            "name": name,
            "language": language,
            "description": description,
            "isPrivate": False
        }
        
        response = requests.post(
            f"{self.base_url}/repls",
            headers=self.headers,
            json=payload
        )
        
        if response.status_code == 201:
            repl_data = response.json()
            logger.info(f"Created repl: {repl_data['url']}")
            return repl_data
        else:
            logger.error(f"Failed to create repl: {response.text}")
            raise Exception(f"Repl creation failed: {response.status_code}")
    
    def upload_files(self, repl_id: str, files: Dict[str, str]) -> bool:
        """Upload files to a repl"""
        for file_path, content in files.items():
            payload = {
                "path": file_path,
                "content": content
            }
            
            response = requests.post(
                f"{self.base_url}/repls/{repl_id}/files",
                headers=self.headers,
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to upload {file_path}: {response.text}")
                return False
        
        logger.info(f"Uploaded {len(files)} files to repl")
        return True
    
    def run_repl(self, repl_id: str) -> Dict[str, Any]:
        """Start running a repl"""
        response = requests.post(
            f"{self.base_url}/repls/{repl_id}/run",
            headers=self.headers
        )
        
        if response.status_code == 200:
            run_data = response.json()
            logger.info(f"Started repl execution")
            return run_data
        else:
            logger.error(f"Failed to run repl: {response.text}")
            raise Exception(f"Repl execution failed: {response.status_code}")

def get_kit_template_files(kit_type: str, customer_id: str, domain_name: str) -> Dict[str, str]:
    """Get template files for different kit types"""
    
    if kit_type == "starter_site":
        return {
            "index.html": f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{customer_id} - Starter Site</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            text-align: center;
            max-width: 800px;
            padding: 2rem;
        }}
        h1 {{
            font-size: 3rem;
            margin-bottom: 1rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        p {{
            font-size: 1.2rem;
            margin-bottom: 2rem;
            opacity: 0.9;
        }}
        .cta-button {{
            background: rgba(255,255,255,0.2);
            border: 2px solid white;
            color: white;
            padding: 1rem 2rem;
            font-size: 1.1rem;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }}
        .cta-button:hover {{
            background: white;
            color: #667eea;
        }}
        .features {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 2rem;
            margin-top: 3rem;
        }}
        .feature {{
            background: rgba(255,255,255,0.1);
            padding: 1.5rem;
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Welcome to {customer_id}</h1>
        <p>Your professional website is now live and ready to impress your visitors!</p>
        <a href="#{domain_name}" class="cta-button">Get Started</a>
        
        <div class="features">
            <div class="feature">
                <h3>⚡ Lightning Fast</h3>
                <p>Optimized for speed and performance</p>
            </div>
            <div class="feature">
                <h3>📱 Mobile Ready</h3>
                <p>Looks great on all devices</p>
            </div>
            <div class="feature">
                <h3>🔒 Secure</h3>
                <p>SSL certificate included</p>
            </div>
        </div>
    </div>
</body>
</html>""",
            "style.css": """/* Additional styles can be added here */
body {
    transition: all 0.3s ease;
}

@media (max-width: 768px) {
    .container h1 {
        font-size: 2rem;
    }
    .container p {
        font-size: 1rem;
    }
}""",
            "script.js": """// Interactive features
document.addEventListener('DOMContentLoaded', function() {
    console.log('Starter site loaded successfully!');
    
    // Add smooth scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
});""",
            "README.md": f"""# {customer_id} - Starter Site

This is your starter site deployed through Stampede Hosting!

## Features
- ⚡ Lightning fast loading
- 📱 Mobile responsive design
- 🔒 SSL certificate included
- 🚀 Easy to customize

## Domain
Your site will be available at: {domain_name}

## Customization
You can customize this site by editing the HTML, CSS, and JavaScript files.

Deployed with ❤️ by Stampede Hosting
"""
        }
    
    elif kit_type == "course_launch":
        return {
            "index.html": f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{customer_id} - Course Platform</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .header {{
            background: #2c3e50;
            color: white;
            padding: 1rem 0;
            position: fixed;
            width: 100%;
            top: 0;
            z-index: 1000;
        }}
        .nav {{
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 2rem;
        }}
        .logo {{ font-size: 1.5rem; font-weight: bold; }}
        .nav-links {{ display: flex; list-style: none; gap: 2rem; }}
        .nav-links a {{ color: white; text-decoration: none; }}
        .hero {{
            background: linear-gradient(135deg, #3498db, #2c3e50);
            color: white;
            padding: 8rem 2rem 4rem;
            text-align: center;
        }}
        .hero h1 {{ font-size: 3rem; margin-bottom: 1rem; }}
        .hero p {{ font-size: 1.2rem; margin-bottom: 2rem; }}
        .cta-button {{
            background: #e74c3c;
            color: white;
            padding: 1rem 2rem;
            border: none;
            border-radius: 5px;
            font-size: 1.1rem;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
        }}
        .courses {{
            padding: 4rem 2rem;
            max-width: 1200px;
            margin: 0 auto;
        }}
        .course-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2rem;
            margin-top: 2rem;
        }}
        .course-card {{
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 1.5rem;
            text-align: center;
            transition: transform 0.3s ease;
        }}
        .course-card:hover {{ transform: translateY(-5px); }}
    </style>
</head>
<body>
    <header class="header">
        <nav class="nav">
            <div class="logo">{customer_id} Academy</div>
            <ul class="nav-links">
                <li><a href="#courses">Courses</a></li>
                <li><a href="#about">About</a></li>
                <li><a href="#contact">Contact</a></li>
                <li><a href="#login">Login</a></li>
            </ul>
        </nav>
    </header>

    <section class="hero">
        <h1>Learn. Grow. Succeed.</h1>
        <p>Join thousands of students in our comprehensive online courses</p>
        <a href="#courses" class="cta-button">Browse Courses</a>
    </section>

    <section class="courses" id="courses">
        <h2 style="text-align: center; margin-bottom: 2rem;">Featured Courses</h2>
        <div class="course-grid">
            <div class="course-card">
                <h3>Web Development Fundamentals</h3>
                <p>Learn HTML, CSS, and JavaScript from scratch</p>
                <div style="margin-top: 1rem;">
                    <span style="background: #3498db; color: white; padding: 0.5rem 1rem; border-radius: 20px;">$99</span>
                </div>
            </div>
            <div class="course-card">
                <h3>Digital Marketing Mastery</h3>
                <p>Master social media, SEO, and content marketing</p>
                <div style="margin-top: 1rem;">
                    <span style="background: #3498db; color: white; padding: 0.5rem 1rem; border-radius: 20px;">$149</span>
                </div>
            </div>
            <div class="course-card">
                <h3>Business Strategy</h3>
                <p>Learn to build and scale successful businesses</p>
                <div style="margin-top: 1rem;">
                    <span style="background: #3498db; color: white; padding: 0.5rem 1rem; border-radius: 20px;">$199</span>
                </div>
            </div>
        </div>
    </section>
</body>
</html>""",
            "app.py": f"""# Course Platform Backend (Flask)
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/courses')
def get_courses():
    courses = [
        {{
            'id': 1,
            'title': 'Web Development Fundamentals',
            'description': 'Learn HTML, CSS, and JavaScript from scratch',
            'price': 99,
            'students': 1250
        }},
        {{
            'id': 2,
            'title': 'Digital Marketing Mastery',
            'description': 'Master social media, SEO, and content marketing',
            'price': 149,
            'students': 890
        }},
        {{
            'id': 3,
            'title': 'Business Strategy',
            'description': 'Learn to build and scale successful businesses',
            'price': 199,
            'students': 675
        }}
    ]
    return jsonify(courses)

@app.route('/api/enroll', methods=['POST'])
def enroll_student():
    data = request.get_json()
    # In a real application, this would handle payment and enrollment
    return jsonify({{'success': True, 'message': 'Enrollment successful!'}})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
""",
            "requirements.txt": """Flask==2.3.3
Werkzeug==2.3.7""",
            "README.md": f"""# {customer_id} - Course Platform

A complete online course platform built with Flask and modern web technologies.

## Features
- 📚 Course catalog
- 💳 Payment integration ready
- 👥 Student management
- 📊 Progress tracking
- 🎓 Certificate generation

## Domain
Your platform will be available at: {domain_name}

## Admin Access
- Admin URL: {domain_name}/admin
- Default credentials will be provided separately

Powered by Stampede Hosting 🚀
"""
        }
    
    elif kit_type == "developer_sandbox":
        return {
            "main.py": f"""#!/usr/bin/env python3
'''
{customer_id} - Developer Sandbox
A flexible development environment with multiple language support
'''

import os
import subprocess
import json
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/execute', methods=['POST'])
def execute_code():
    data = request.get_json()
    language = data.get('language', 'python')
    code = data.get('code', '')
    
    try:
        if language == 'python':
            result = subprocess.run(['python3', '-c', code], 
                                  capture_output=True, text=True, timeout=10)
        elif language == 'javascript':
            result = subprocess.run(['node', '-e', code], 
                                  capture_output=True, text=True, timeout=10)
        elif language == 'bash':
            result = subprocess.run(['bash', '-c', code], 
                                  capture_output=True, text=True, timeout=10)
        else:
            return jsonify({{'error': 'Unsupported language'}})
        
        return jsonify({{
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }})
    
    except subprocess.TimeoutExpired:
        return jsonify({{'error': 'Code execution timed out'}})
    except Exception as e:
        return jsonify({{'error': str(e)}})

@app.route('/api/files')
def list_files():
    files = []
    for root, dirs, filenames in os.walk('.'):
        for filename in filenames:
            if not filename.startswith('.'):
                files.append(os.path.join(root, filename))
    return jsonify(files)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
""",
            "templates/index.html": f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{customer_id} - Developer Sandbox</title>
    <style>
        body {{
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            margin: 0;
            padding: 0;
            background: #1e1e1e;
            color: #d4d4d4;
        }}
        .header {{
            background: #2d2d30;
            padding: 1rem;
            border-bottom: 1px solid #3e3e42;
        }}
        .container {{
            display: flex;
            height: calc(100vh - 60px);
        }}
        .editor {{
            flex: 1;
            display: flex;
            flex-direction: column;
        }}
        .toolbar {{
            background: #2d2d30;
            padding: 0.5rem;
            border-bottom: 1px solid #3e3e42;
        }}
        select, button {{
            background: #3c3c3c;
            color: #d4d4d4;
            border: 1px solid #5a5a5a;
            padding: 0.5rem;
            margin-right: 0.5rem;
        }}
        textarea {{
            flex: 1;
            background: #1e1e1e;
            color: #d4d4d4;
            border: none;
            padding: 1rem;
            font-family: inherit;
            font-size: 14px;
            resize: none;
        }}
        .output {{
            width: 400px;
            background: #252526;
            border-left: 1px solid #3e3e42;
            padding: 1rem;
            overflow-y: auto;
        }}
        .output pre {{
            background: #1e1e1e;
            padding: 1rem;
            border-radius: 4px;
            overflow-x: auto;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{customer_id} Developer Sandbox</h1>
        <p>Multi-language development environment - Domain: {domain_name}</p>
    </div>
    
    <div class="container">
        <div class="editor">
            <div class="toolbar">
                <select id="language">
                    <option value="python">Python</option>
                    <option value="javascript">JavaScript</option>
                    <option value="bash">Bash</option>
                </select>
                <button onclick="executeCode()">Run Code</button>
                <button onclick="clearOutput()">Clear Output</button>
            </div>
            <textarea id="code" placeholder="Write your code here...">print("Hello from {customer_id} Developer Sandbox!")
print("Available languages: Python, JavaScript, Bash")
print("Domain:", "{domain_name}")

# Example: Simple calculator
def calculate(a, b, operation):
    if operation == 'add':
        return a + b
    elif operation == 'subtract':
        return a - b
    elif operation == 'multiply':
        return a * b
    elif operation == 'divide':
        return a / b if b != 0 else 'Cannot divide by zero'

result = calculate(10, 5, 'add')
print(f"10 + 5 = {{result}}")
</textarea>
        </div>
        
        <div class="output">
            <h3>Output</h3>
            <div id="output-content">
                <p>Click "Run Code" to execute your code...</p>
            </div>
        </div>
    </div>

    <script>
        async function executeCode() {{
            const language = document.getElementById('language').value;
            const code = document.getElementById('code').value;
            const outputDiv = document.getElementById('output-content');
            
            outputDiv.innerHTML = '<p>Executing...</p>';
            
            try {{
                const response = await fetch('/api/execute', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify({{ language, code }})
                }});
                
                const result = await response.json();
                
                let output = '';
                if (result.stdout) {{
                    output += `<h4>Output:</h4><pre>${{result.stdout}}</pre>`;
                }}
                if (result.stderr) {{
                    output += `<h4>Errors:</h4><pre style="color: #f44747;">${{result.stderr}}</pre>`;
                }}
                if (result.error) {{
                    output += `<h4>Error:</h4><pre style="color: #f44747;">${{result.error}}</pre>`;
                }}
                
                outputDiv.innerHTML = output || '<p>No output</p>';
            }} catch (error) {{
                outputDiv.innerHTML = `<p style="color: #f44747;">Error: ${{error.message}}</p>`;
            }}
        }}
        
        function clearOutput() {{
            document.getElementById('output-content').innerHTML = '<p>Output cleared</p>';
        }}
    </script>
</body>
</html>""",
            "requirements.txt": """Flask==2.3.3
Werkzeug==2.3.7""",
            "package.json": """{
  "name": "developer-sandbox",
  "version": "1.0.0",
  "description": "Developer sandbox environment",
  "main": "server.js",
  "scripts": {
    "start": "node server.js",
    "dev": "nodemon server.js"
  },
  "dependencies": {
    "express": "^4.18.2",
    "cors": "^2.8.5"
  }
}""",
            "README.md": f"""# {customer_id} - Developer Sandbox

A complete development environment with multi-language support.

## Features
- 🐍 Python 3.11
- 🟨 Node.js 18
- 🐚 Bash scripting
- 🐳 Docker support
- 📁 File management
- 🔧 Package management

## Access
- Web IDE: {domain_name}
- SSH Access: ssh user@{domain_name}
- FTP Access: Available on request

## Languages & Tools
- Python with pip
- Node.js with npm
- Git version control
- Docker containers
- Various development tools

## Getting Started
1. Open the web IDE at {domain_name}
2. Choose your programming language
3. Write and execute code instantly
4. Use SSH for advanced development

Powered by Stampede Hosting 🚀
"""
        }
    
    else:
        raise ValueError(f"Unknown kit type: {kit_type}")

def main():
    parser = argparse.ArgumentParser(description="Deploy to Replit")
    parser.add_argument("--kit-type", required=True, choices=["starter_site", "course_launch", "developer_sandbox"])
    parser.add_argument("--customer-id", required=True, help="Customer ID")
    parser.add_argument("--domain-name", required=True, help="Domain name")
    parser.add_argument("--replit-token", help="Replit API token (or use REPLIT_TOKEN env var)")
    
    args = parser.parse_args()
    
    # Get Replit token
    replit_token = args.replit_token or os.getenv("REPLIT_TOKEN")
    if not replit_token:
        logger.error("Replit token is required. Provide --replit-token or set REPLIT_TOKEN environment variable")
        return 1
    
    try:
        deployer = ReplitDeployer(replit_token)
        
        # Determine language based on kit type
        language_map = {
            "starter_site": "html",
            "course_launch": "python",
            "developer_sandbox": "python"
        }
        
        language = language_map[args.kit_type]
        repl_name = f"{args.customer_id}-{args.kit_type}-demo"
        description = f"Demo deployment for {args.customer_id} using {args.kit_type} kit"
        
        # Create repl
        logger.info(f"Creating Replit project: {repl_name}")
        repl_data = deployer.create_repl(repl_name, language, description)
        
        # Get template files
        logger.info(f"Preparing template files for {args.kit_type}")
        files = get_kit_template_files(args.kit_type, args.customer_id, args.domain_name)
        
        # Upload files
        logger.info("Uploading files to Replit")
        success = deployer.upload_files(repl_data['id'], files)
        
        if success:
            # Start the repl
            logger.info("Starting Replit execution")
            run_data = deployer.run_repl(repl_data['id'])
            
            logger.info(f"✅ Deployment successful!")
            logger.info(f"🔗 Repl URL: {repl_data['url']}")
            logger.info(f"🌐 Live URL: {repl_data.get('liveUrl', 'Will be available once running')}")
            
            # Output JSON for GitHub Actions
            output = {
                "success": True,
                "repl_url": repl_data['url'],
                "live_url": repl_data.get('liveUrl'),
                "repl_id": repl_data['id']
            }
            print(json.dumps(output))
            
        else:
            logger.error("Failed to upload files")
            return 1
            
    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        output = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(output))
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
