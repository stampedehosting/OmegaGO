#!/usr/bin/env python3
"""
Automation Orchestrator for Stampede Hosting
Manages and coordinates multiple automation tasks and workflows
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from playwright_automation import PlaywrightAutomation, AutomationTask, AutomationType

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class WorkflowStep:
    """Individual step in an automation workflow"""
    step_id: str
    automation_task: AutomationTask
    depends_on: Optional[List[str]] = None
    retry_count: int = 0
    max_retries: int = 3
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@dataclass
class AutomationWorkflow:
    """Complete automation workflow"""
    workflow_id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: float = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

class AutomationOrchestrator:
    """Orchestrates complex automation workflows"""
    
    def __init__(self):
        self.workflows: Dict[str, AutomationWorkflow] = {}
        self.automation_engine = None
        
    async def initialize(self):
        """Initialize the automation engine"""
        self.automation_engine = PlaywrightAutomation(headless=True)
        await self.automation_engine.initialize()
        
    async def cleanup(self):
        """Clean up resources"""
        if self.automation_engine:
            await self.automation_engine.cleanup()
    
    def create_workflow(self, workflow: AutomationWorkflow) -> str:
        """Create a new automation workflow"""
        if workflow.created_at is None:
            workflow.created_at = time.time()
            
        self.workflows[workflow.workflow_id] = workflow
        logger.info(f"Created workflow: {workflow.workflow_id} - {workflow.name}")
        return workflow.workflow_id
    
    async def execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Execute an automation workflow"""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.workflows[workflow_id]
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = time.time()
        
        logger.info(f"Starting workflow execution: {workflow_id}")
        
        try:
            # Execute steps in dependency order
            executed_steps = set()
            
            while len(executed_steps) < len(workflow.steps):
                # Find steps that can be executed (dependencies met)
                ready_steps = []
                
                for step in workflow.steps:
                    if step.step_id in executed_steps:
                        continue
                        
                    if step.status == WorkflowStatus.COMPLETED:
                        executed_steps.add(step.step_id)
                        continue
                        
                    # Check if dependencies are met
                    if step.depends_on:
                        deps_met = all(
                            dep_id in executed_steps or 
                            any(s.step_id == dep_id and s.status == WorkflowStatus.COMPLETED 
                                for s in workflow.steps)
                            for dep_id in step.depends_on
                        )
                        if not deps_met:
                            continue
                    
                    ready_steps.append(step)
                
                if not ready_steps:
                    # Check if we're stuck due to failed dependencies
                    remaining_steps = [s for s in workflow.steps if s.step_id not in executed_steps]
                    if remaining_steps:
                        failed_deps = []
                        for step in remaining_steps:
                            if step.depends_on:
                                for dep_id in step.depends_on:
                                    dep_step = next((s for s in workflow.steps if s.step_id == dep_id), None)
                                    if dep_step and dep_step.status == WorkflowStatus.FAILED:
                                        failed_deps.append(dep_id)
                        
                        if failed_deps:
                            raise Exception(f"Workflow blocked by failed dependencies: {failed_deps}")
                    break
                
                # Execute ready steps (can be done in parallel if no dependencies between them)
                tasks = []
                for step in ready_steps:
                    tasks.append(self._execute_step(step))
                
                # Wait for all ready steps to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results):
                    step = ready_steps[i]
                    if isinstance(result, Exception):
                        step.status = WorkflowStatus.FAILED
                        step.error = str(result)
                        logger.error(f"Step {step.step_id} failed: {result}")
                    else:
                        step.status = WorkflowStatus.COMPLETED
                        step.result = result
                        executed_steps.add(step.step_id)
                        logger.info(f"Step {step.step_id} completed successfully")
            
            # Check overall workflow status
            failed_steps = [s for s in workflow.steps if s.status == WorkflowStatus.FAILED]
            if failed_steps:
                workflow.status = WorkflowStatus.FAILED
                logger.error(f"Workflow {workflow_id} failed due to {len(failed_steps)} failed steps")
            else:
                workflow.status = WorkflowStatus.COMPLETED
                logger.info(f"Workflow {workflow_id} completed successfully")
            
            workflow.completed_at = time.time()
            
            return {
                'workflow_id': workflow_id,
                'status': workflow.status.value,
                'steps_completed': len(executed_steps),
                'total_steps': len(workflow.steps),
                'execution_time': workflow.completed_at - workflow.started_at,
                'results': {step.step_id: step.result for step in workflow.steps if step.result}
            }
            
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            workflow.completed_at = time.time()
            logger.error(f"Workflow {workflow_id} failed: {str(e)}")
            
            return {
                'workflow_id': workflow_id,
                'status': WorkflowStatus.FAILED.value,
                'error': str(e),
                'execution_time': workflow.completed_at - workflow.started_at if workflow.started_at else 0
            }
    
    async def _execute_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute a single workflow step with retry logic"""
        step.status = WorkflowStatus.RUNNING
        
        for attempt in range(step.max_retries + 1):
            try:
                logger.info(f"Executing step {step.step_id} (attempt {attempt + 1})")
                result = await self.automation_engine.execute_automation(step.automation_task)
                
                if result.get('success', False):
                    return result
                else:
                    raise Exception(result.get('error', 'Unknown error'))
                    
            except Exception as e:
                step.retry_count = attempt + 1
                logger.warning(f"Step {step.step_id} attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < step.max_retries:
                    # Wait before retry (exponential backoff)
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying step {step.step_id} in {wait_time} seconds")
                    await asyncio.sleep(wait_time)
                else:
                    # Max retries reached
                    step.error = str(e)
                    raise e
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get the current status of a workflow"""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.workflows[workflow_id]
        
        return {
            'workflow_id': workflow_id,
            'name': workflow.name,
            'status': workflow.status.value,
            'created_at': workflow.created_at,
            'started_at': workflow.started_at,
            'completed_at': workflow.completed_at,
            'steps': [
                {
                    'step_id': step.step_id,
                    'status': step.status.value,
                    'retry_count': step.retry_count,
                    'error': step.error
                }
                for step in workflow.steps
            ]
        }
    
    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow"""
        if workflow_id not in self.workflows:
            return False
        
        workflow = self.workflows[workflow_id]
        if workflow.status == WorkflowStatus.RUNNING:
            workflow.status = WorkflowStatus.CANCELLED
            workflow.completed_at = time.time()
            logger.info(f"Workflow {workflow_id} cancelled")
            return True
        
        return False
    
    def create_standard_workflows(self) -> Dict[str, str]:
        """Create standard workflows for common deployment scenarios"""
        workflows = {}
        
        # Starter Site Workflow
        starter_site_workflow = self._create_starter_site_workflow()
        workflows['starter_site'] = self.create_workflow(starter_site_workflow)
        
        # Course Launch Workflow
        course_launch_workflow = self._create_course_launch_workflow()
        workflows['course_launch'] = self.create_workflow(course_launch_workflow)
        
        # Developer Sandbox Workflow
        dev_sandbox_workflow = self._create_developer_sandbox_workflow()
        workflows['developer_sandbox'] = self.create_workflow(dev_sandbox_workflow)
        
        return workflows
    
    def _create_starter_site_workflow(self) -> AutomationWorkflow:
        """Create workflow for starter site deployment"""
        steps = [
            WorkflowStep(
                step_id="github_setup",
                automation_task=AutomationTask(
                    task_type=AutomationType.GITHUB_REPO_SETUP,
                    target_url="https://github.com",
                    credentials={"username": "github_user", "password": "github_pass"},
                    parameters={
                        "repo_name": "starter-site-template",
                        "description": "Starter site template repository",
                        "private": False,
                        "init_readme": True
                    }
                )
            ),
            WorkflowStep(
                step_id="replit_deploy",
                automation_task=AutomationTask(
                    task_type=AutomationType.REPLIT_DEPLOYMENT,
                    target_url="https://replit.com",
                    credentials={"username": "replit_user", "password": "replit_pass"},
                    parameters={
                        "repl_name": "starter-site-demo",
                        "template": "HTML/CSS/JS"
                    }
                ),
                depends_on=["github_setup"]
            )
        ]
        
        return AutomationWorkflow(
            workflow_id="starter_site_workflow",
            name="Starter Site Deployment",
            description="Complete workflow for deploying a starter site",
            steps=steps
        )
    
    def _create_course_launch_workflow(self) -> AutomationWorkflow:
        """Create workflow for course platform deployment"""
        steps = [
            WorkflowStep(
                step_id="github_setup",
                automation_task=AutomationTask(
                    task_type=AutomationType.GITHUB_REPO_SETUP,
                    target_url="https://github.com",
                    credentials={"username": "github_user", "password": "github_pass"},
                    parameters={
                        "repo_name": "course-platform-template",
                        "description": "Course platform template repository",
                        "private": False
                    }
                )
            ),
            WorkflowStep(
                step_id="moodle_setup",
                automation_task=AutomationTask(
                    task_type=AutomationType.MOODLE_SETUP,
                    target_url="https://course-platform.example.com",
                    credentials={"username": "admin", "password": "admin_pass"},
                    parameters={
                        "site_name": "Course Platform",
                        "site_shortname": "CP",
                        "admin_username": "admin",
                        "admin_password": "secure_pass",
                        "admin_email": "admin@example.com",
                        "db_host": "localhost",
                        "db_name": "moodle_db",
                        "db_user": "moodle_user",
                        "db_password": "db_pass"
                    }
                ),
                depends_on=["github_setup"]
            )
        ]
        
        return AutomationWorkflow(
            workflow_id="course_launch_workflow",
            name="Course Platform Deployment",
            description="Complete workflow for deploying a course platform",
            steps=steps
        )
    
    def _create_developer_sandbox_workflow(self) -> AutomationWorkflow:
        """Create workflow for developer sandbox deployment"""
        steps = [
            WorkflowStep(
                step_id="github_setup",
                automation_task=AutomationTask(
                    task_type=AutomationType.GITHUB_REPO_SETUP,
                    target_url="https://github.com",
                    credentials={"username": "github_user", "password": "github_pass"},
                    parameters={
                        "repo_name": "developer-sandbox",
                        "description": "Developer sandbox environment",
                        "private": True
                    }
                )
            ),
            WorkflowStep(
                step_id="replit_deploy",
                automation_task=AutomationTask(
                    task_type=AutomationType.REPLIT_DEPLOYMENT,
                    target_url="https://replit.com",
                    credentials={"username": "replit_user", "password": "replit_pass"},
                    parameters={
                        "repl_name": "developer-sandbox",
                        "template": "Python"
                    }
                ),
                depends_on=["github_setup"]
            )
        ]
        
        return AutomationWorkflow(
            workflow_id="developer_sandbox_workflow",
            name="Developer Sandbox Deployment",
            description="Complete workflow for deploying a developer sandbox",
            steps=steps
        )

async def main():
    """Test the automation orchestrator"""
    orchestrator = AutomationOrchestrator()
    
    try:
        await orchestrator.initialize()
        
        # Create standard workflows
        workflows = orchestrator.create_standard_workflows()
        print(f"Created workflows: {list(workflows.keys())}")
        
        # Execute starter site workflow
        result = await orchestrator.execute_workflow(workflows['starter_site'])
        print(json.dumps(result, indent=2))
        
    finally:
        await orchestrator.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
