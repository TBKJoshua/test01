
import os
import sys
import threading
import queue
import subprocess
import ast
import configparser
import time
import re
import base64
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, scrolledtext
from pathlib import Path
from PIL import Image, ImageTk

# pip install google-genai Pillow
try:
    from google import genai
    from google.genai import types
    GENAI_IMPORTED = True
except ImportError:
    GENAI_IMPORTED = False

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
CONFIG_PATH = Path('config.ini')
VM_DIR = Path('vm')
APP_TITLE = "Enhanced Multi-Agent IDE"
TEXT_MODEL_NAME = "gemini-2.5-flash-preview-05-20"
IMAGE_MODEL_NAME = "gemini-2.0-flash-preview-image-generation"

# Enhanced Agent System Prompts with Grading System
MAIN_AGENT_PROMPT = """You are the PRIMARY CODER AGENT in an advanced multi-agent IDE system. Your role is to implement code, execute commands, and coordinate with other agents.

**ENVIRONMENT:**
You operate in a headless environment with full vision capabilities. You can analyze images, understand visual content, and make informed coding decisions based on visual context.

**COMMANDS:**
- `create_file(path, content)`: Creates a new text file with specified content.
- `write_to_file(path, content)`: Overwrites an existing text file.
- `delete_file(path)`: Deletes a file or directory.
- `run_command(command)`: Executes a shell command in the project directory.
- `generate_image(path, prompt)`: Generates an image using AI based on a text prompt.

**ENHANCED CAPABILITIES:**
- **Vision Analysis**: Can analyze existing images to inform coding decisions
- **Image Generation**: Can create images when requested by users
- **Code Integration**: Seamlessly integrates visual assets into code projects
- **Multi-format Support**: Handles text, images, and mixed-media projects
- **Quality Focus**: Strive for excellence as your work will be graded by critique agents

**RULES:**
1. **COMMAND ONLY OUTPUT**: Your response must ONLY contain commands wrapped in backticks.
2. **PROPER QUOTING**: All string arguments must be in single quotes.
3. **MULTILINE CONTENT**: Use triple quotes for file content spanning multiple lines.
4. **NO COMMENTARY**: Never output explanatory text outside backticked commands.
5. **VISUAL AWARENESS**: Consider existing images when making implementation decisions.
6. **COLLABORATION**: Work with Code Critic and Art Critic for optimal results.
7. **QUALITY EXCELLENCE**: Aim for high-quality implementation as critique agents will grade your work.

**INTERACTION FLOW:**
1. Implement user requests through commands with highest quality standards
2. Generate images when visual content is needed
3. Create comprehensive solutions that may include both code and visual assets
4. Accept feedback gracefully and improve upon critiques
"""

CRITIC_AGENT_PROMPT = """You are the CODE CRITIQUE AGENT in an advanced multi-agent IDE system. Your enhanced role includes code review, security analysis, performance optimization, and GRADING the Main Coder's work.

**GRADING RESPONSIBILITIES:**
You must provide a numerical grade (0-100) for the Main Coder's implementation based on:
- **Code Quality (25%)**: Structure, readability, maintainability
- **Security (25%)**: Vulnerability assessment, safe practices
- **Performance (25%)**: Efficiency, optimization, scalability
- **Best Practices (25%)**: Standards compliance, documentation, error handling

**GRADING SCALE:**
- 90-100: Excellent - Outstanding implementation with minimal issues
- 80-89: Good - Solid work with minor improvements needed
- 70-79: Satisfactory - Adequate but needs some improvements
- 60-69: Needs Improvement - Significant issues that should be addressed
- Below 60: Poor - Major problems requiring complete rework

**ENHANCED RESPONSIBILITIES:**
- **Code Quality Analysis**: Review code structure, readability, and maintainability
- **Security Assessment**: Identify potential security vulnerabilities and suggest fixes
- **Performance Optimization**: Recommend performance improvements and efficient algorithms
- **Best Practices Enforcement**: Ensure adherence to coding standards and conventions
- **Architecture Review**: Suggest better design patterns and system architecture
- **Testing Strategy**: Recommend testing approaches and identify untested code paths
- **Documentation Review**: Ensure code is properly documented and self-explanatory

**MANDATORY RESPONSE FORMAT:**
Start your response with: **GRADE: [score]/100**
Then provide structured feedback with:
- **Priority Level**: Critical, High, Medium, Low
- **Category**: Security, Performance, Maintainability, etc.
- **Specific Issue**: Clear description of the problem
- **Recommended Solution**: Actionable steps to resolve the issue
- **Code Examples**: When helpful, provide improved code snippets

**GRADING CRITERIA:**
Be thorough but fair in your assessment. Consider the complexity of the task and provide constructive feedback that helps the Main Coder improve.
"""

ART_AGENT_PROMPT = """You are the ART CRITIQUE AGENT in an advanced multi-agent IDE system with SUPERIOR VISION CAPABILITIES. You specialize in visual analysis, artistic guidance, and GRADING visual/design work.

**GRADING RESPONSIBILITIES:**
You must provide a numerical grade (0-100) for visual and design work based on:
- **Visual Composition (25%)**: Balance, hierarchy, rule of thirds, contrast
- **Color Theory (25%)**: Harmony, psychology, accessibility, consistency
- **User Experience (25%)**: Usability, accessibility, user flow
- **Technical Quality (25%)**: Resolution, file formats, optimization

**GRADING SCALE:**
- 90-100: Excellent - Outstanding visual design with professional quality
- 80-89: Good - Strong design with minor aesthetic improvements needed
- 70-79: Satisfactory - Adequate design but needs visual enhancements
- 60-69: Needs Improvement - Significant design issues affecting usability
- Below 60: Poor - Major visual problems requiring complete redesign

**ENHANCED VISION CAPABILITIES:**
- **Image Analysis**: Deep understanding of visual composition, color theory, and design principles
- **Style Recognition**: Identify artistic styles, design patterns, and visual trends
- **UI/UX Evaluation**: Assess user interface design and user experience elements
- **Visual Consistency**: Ensure consistent visual branding across project assets
- **Accessibility Review**: Check visual accessibility and inclusive design practices

**MANDATORY RESPONSE FORMAT:**
Start your response with: **GRADE: [score]/100**
Then provide comprehensive artistic guidance including:
- **Visual Assessment**: Analysis of current visual elements
- **Design Recommendations**: Specific suggestions for improvement
- **Technical Specifications**: Color codes, dimensions, file formats
- **Image Generation Prompts**: Detailed, optimized prompts for AI image creation
- **Implementation Notes**: Technical considerations for developers

**GRADING CRITERIA:**
Assess both aesthetic quality and functional usability. Consider accessibility, user experience, and technical implementation quality.
"""

PROMPT_ENHANCER_AGENT_PROMPT = """You are a PROMPT ENHANCER AGENT. Your role is to take a user's raw prompt and transform it into a more detailed, specific, and well-structured prompt that is optimized for large language models (LLMs) and image generation models. Your *sole* responsibility is to refine and rephrase the user's input to be a better prompt for a different AI. You do not answer or execute any part of the user's request.

**TASK:**
Rewrite the given user prompt to maximize its effectiveness. Consider the following:
1.  **Clarity and Specificity:** Add details that make the request unambiguous. For example, if the user asks for "a cat image," you might enhance it to "a photorealistic image of a fluffy ginger tabby cat lounging in a sunbeam."
2.  **Context:** If the user's prompt is for coding, ensure the enhanced prompt specifies language, libraries, and desired functionality. For example, "python script for web server" could become "Create a Python script using the Flask framework to implement a simple web server with a single endpoint '/' that returns 'Hello, World!'."
3.  **Structure:** Organize the prompt logically. Use bullet points or numbered lists for complex requests.
4.  **Keywords:** Include relevant keywords that the LLM can use to generate a better response.
5.  **Tone and Style:** Maintain the user's original intent but refine the language to be more effective for AI. For image generation, suggest artistic styles (e.g., "impressionistic style", "cyberpunk aesthetic", "shot on 35mm film").
6.  **Completeness:** Ensure the prompt contains all necessary information for the AI to perform the task well.

**RULES:**
1.  **CRITICALLY IMPORTANT: OUTPUT ONLY THE ENHANCED PROMPT:** Your response *must exclusively* contain the refined prompt text and nothing else. Do not include any explanations, apologies, conversational filler, or any attempt to answer or execute the user's underlying request. Your job is *only* to improve the prompt for another AI.
2.  **MAINTAIN INTENT:** Do not change the core meaning or goal of the user's original request.
3.  **BE CONCISE BUT THOROUGH:** The enhanced prompt should be detailed but not overly verbose.
4.  **DO NOT ANSWER:** Under no circumstances should you attempt to answer or fulfill the request described in the user's prompt. Your only task is to make the prompt itself better for a subsequent AI agent.

**EXAMPLE (Image Generation):**
User Prompt: "dog playing"
Enhanced Prompt: "A high-resolution digital painting of a golden retriever puppy playfully chasing a red ball across a sunlit grassy field, with a shallow depth of field effect. Art style: Disney Pixar."

**EXAMPLE (Code Generation):**
User Prompt: "make a button in html"
Enhanced Prompt: "Create an HTML snippet for a button with the text 'Click Me'. The button should have a blue background, white text, rounded corners (border-radius: 5px), and a subtle box-shadow. When clicked, it should execute a JavaScript function called 'handleButtonClick()'."

Now, enhance the following user prompt:
"""

def load_api_key():
    """Load API key from environment or config file"""
    if "GEMINI_API_KEY" in os.environ:
        return os.environ["GEMINI_API_KEY"]

    config = configparser.ConfigParser()
    if CONFIG_PATH.exists():
        config.read(CONFIG_PATH)
        return config.get('API', 'key', fallback=None)
    return None

def save_api_key(key):
    """Save API key to config file"""
    config = configparser.ConfigParser()
    config['API'] = {'key': key}
    with open(CONFIG_PATH, 'w') as f:
        config.write(f)

# -----------------------------------------------------------------------------
# Enhanced Multi-Agent System
# -----------------------------------------------------------------------------
class EnhancedMultiAgentSystem:
    def __init__(self, api_key):
        if not GENAI_IMPORTED:
            raise ImportError("google-genai not installed")

        self.client = genai.Client(api_key=api_key)
        self.conversation_history = []
        self.error_context = []
        self.project_context = {"files": [], "images": [], "recent_changes": []}
        self.grading_enabled = True
        self.prompt_enhancer_enabled = True
        self.max_retry_attempts = 3
        self.current_attempt = 0
        
        self.command_handlers = {
            "create_file": self._create_file,
            "write_to_file": self._write_to_file,
            "delete_file": self._delete_file,
            "run_command": self._run_command,
            "generate_image": self.generate_image,
        }

    def _get_enhanced_prompt(self, user_prompt):
        """Calls the PROMPT_ENHANCER_AGENT to refine the user's prompt."""
        try:
            prompt_parts = [{"text": f"{PROMPT_ENHANCER_AGENT_PROMPT}\n\n{user_prompt}"}]
            enhanced_response = self.client.models.generate_content(
                model=TEXT_MODEL_NAME,
                contents=prompt_parts
            )
            self._log_interaction("prompt_enhancer", enhanced_response.text)
            return enhanced_response.text
        except Exception as e:
            self.error_context.append(f"Prompt Enhancer Error: {e}")
            # Fallback to original prompt if enhancer fails
            return user_prompt

    def run_enhanced_interaction(self, original_user_prompt):
        """Enhanced multi-agent interaction with grading and retry system"""
        if not self.client:
            yield {"type": "error", "content": "AI system not configured. Please set API key."}
            return

        if self.prompt_enhancer_enabled:
            # Initial prompt enhancement (occurs only once before retries)
            yield {"type": "system", "content": "✨ Enhancing prompt..."}
            enhanced_user_prompt = self._get_enhanced_prompt(original_user_prompt)
            yield {"type": "agent", "agent": "✨ Prompt Enhancer", "content": enhanced_user_prompt}
        else:
            enhanced_user_prompt = original_user_prompt
            yield {"type": "system", "content": "✨ Prompt enhancer disabled. Using original prompt."}

        current_main_coder_prompt = enhanced_user_prompt

        # Reset attempt counter for new interactions
        self.current_attempt = 0
        
        while self.current_attempt < self.max_retry_attempts:
            self.current_attempt += 1
            attempt_suffix = f" (Attempt {self.current_attempt}/{self.max_retry_attempts})" if self.current_attempt > 1 else ""
            
            # Update project context
            self._update_project_context()
            
            # Phase 1: Main Coder Agent Analysis and Implementation
            yield {"type": "system", "content": f"🚀 Main Coder Agent analyzing and implementing...{attempt_suffix}"}
            
            main_prompt_parts = self._build_enhanced_prompt(current_main_coder_prompt, MAIN_AGENT_PROMPT)
            
            try:
                main_response = self.client.models.generate_content(
                    model=TEXT_MODEL_NAME,
                    contents=main_prompt_parts
                )
                
                self._log_interaction("user", current_main_coder_prompt) # Log the prompt sent to main coder
                self._log_interaction("main_coder", main_response.text)
                
                yield {"type": "agent", "agent": "🤖 Main Coder", "content": main_response.text}
                
                # Execute commands and track changes
                implementation_results = []
                for result in self._process_enhanced_commands(main_response.text):
                    implementation_results.append(result)
                    yield result

                # Phase 2: Smart Agent Selection with Grading
                # Critics should see the original prompt to understand the user's raw request
                should_use_critic = self._should_invoke_code_critic(original_user_prompt, main_response.text, implementation_results)
                should_use_art_critic = self._should_invoke_art_critic(original_user_prompt, main_response.text, implementation_results)
                
                critic_grade = None
                art_grade = None
                
                if should_use_critic and self.grading_enabled:
                    yield {"type": "system", "content": "🔍 Code Critic Agent performing deep analysis and grading..."}
                    
                    critic_analysis = self._get_code_critique(original_user_prompt, main_response.text, implementation_results)
                    if critic_analysis:
                        yield {"type": "agent", "agent": "📊 Code Critic", "content": critic_analysis}
                        critic_grade = self._extract_grade(critic_analysis)

                if should_use_art_critic and self.grading_enabled:
                    yield {"type": "system", "content": "🎨 Art Critic Agent analyzing visual elements and grading..."}
                    
                    art_analysis = self._get_art_critique(original_user_prompt, main_response.text, implementation_results)
                    if art_analysis:
                        yield {"type": "agent", "agent": "🎭 Art Critic", "content": art_analysis}
                        art_grade = self._extract_grade(art_analysis)

                # Phase 3: Grade Evaluation and Retry Decision
                if self.grading_enabled and (critic_grade is not None or art_grade is not None):
                    overall_grade = self._calculate_overall_grade(critic_grade, art_grade)
                    yield {"type": "system", "content": f"📊 Overall Grade: {overall_grade}/100"}
                    
                    if overall_grade < 70 and self.current_attempt < self.max_retry_attempts:
                        yield {"type": "system", "content": f"⚠️ Grade below 70. Requesting Main Coder to improve... (Attempt {self.current_attempt + 1}/{self.max_retry_attempts})"}
                        retry_intro = f"RETRY (Original User Prompt: '{original_user_prompt}'):\n\nPREVIOUS ATTEMPT FEEDBACK:\nCode Critic Grade: {critic_grade or 'N/A'}\nArt Critic Grade: {art_grade or 'N/A'}\nOverall Grade: {overall_grade}/100\n\nPlease improve the implementation based on the critique feedback above."
                        current_main_coder_prompt = f"{retry_intro}\n\n{enhanced_user_prompt}"
                        continue  # Retry with improved prompt
                    elif overall_grade >= 70:
                        yield {"type": "system", "content": f"✅ Grade acceptable ({overall_grade}/100). Implementation approved!"}
                    else:
                        yield {"type": "system", "content": f"⚠️ Maximum attempts reached. Final grade: {overall_grade}/100"}

                # Phase 4: Collaborative Refinement (only if agents were involved and refinement needed)
                if (should_use_critic or should_use_art_critic) and self._needs_refinement(implementation_results):
                    yield {"type": "system", "content": "🔄 Agents collaborating on final refinements..."}
                    refinement_suggestions = self._get_collaborative_refinement()
                    if refinement_suggestions:
                        yield {"type": "agent", "agent": "🤝 Collaborative", "content": refinement_suggestions}

                yield {"type": "system", "content": "✅ Multi-agent analysis complete!"}
                break  # Exit retry loop on successful completion

            except Exception as e:
                error_msg = f"Enhanced Agent System Error: {e}"
                self.error_context.append(error_msg)
                yield {"type": "error", "content": error_msg}
                break  # Exit on system errors

    def _get_code_critique(self, user_prompt, main_response, implementation_results):
        """Get enhanced code critique"""
        critique_context = f"""
ORIGINAL REQUEST: {user_prompt}

MAIN CODER IMPLEMENTATION: {main_response}

IMPLEMENTATION RESULTS: {self._format_results(implementation_results)}

PROJECT CONTEXT: {self._get_project_summary()}

Please provide a comprehensive code review focusing on quality, security, performance, and best practices.
"""
        
        try:
            response = self.client.models.generate_content(
                model=TEXT_MODEL_NAME,
                contents=[{"text": f"{CRITIC_AGENT_PROMPT}\n\n{critique_context}"}]
            )
            self._log_interaction("code_critic", response.text)
            return response.text
        except Exception as e:
            self.error_context.append(f"Code Critic Error: {e}")
            return None

    def _get_art_critique(self, user_prompt, main_response, implementation_results):
        """Get enhanced art critique with vision capabilities"""
        art_context_parts = self._build_visual_context(f"""
ORIGINAL REQUEST: {user_prompt}

MAIN CODER IMPLEMENTATION: {main_response}

IMPLEMENTATION RESULTS: {self._format_results(implementation_results)}

Please analyze visual elements, provide design guidance, and suggest improvements for better aesthetics and user experience.
""", ART_AGENT_PROMPT)
        
        try:
            response = self.client.models.generate_content(
                model=TEXT_MODEL_NAME,
                contents=art_context_parts
            )
            self._log_interaction("art_critic", response.text)
            return response.text
        except Exception as e:
            self.error_context.append(f"Art Critic Error: {e}")
            return None

    def _get_collaborative_refinement(self):
        """Get collaborative refinement suggestions"""
        if len(self.conversation_history) < 3:
            return None
            
        refinement_context = f"""
Based on the recent multi-agent analysis, provide collaborative refinement suggestions that combine:
1. Technical implementation improvements
2. Code quality enhancements  
3. Visual and UX improvements

Recent conversation:
{self._get_recent_conversation_summary()}

Focus on actionable improvements that leverage all three agent perspectives.
"""
        
        try:
            response = self.client.models.generate_content(
                model=TEXT_MODEL_NAME,
                contents=[{"text": refinement_context}]
            )
            return response.text
        except Exception as e:
            return None

    def _update_project_context(self):
        """Update project context for better agent awareness"""
        self.project_context = {
            "files": self._get_project_files(),
            "images": self._get_project_images(),
            "recent_changes": self._get_recent_changes()
        }

    def _build_enhanced_prompt(self, user_prompt, system_prompt):
        """Build enhanced prompt with comprehensive context"""
        prompt_parts = [{"text": f"{system_prompt}\n\n**PROJECT STATUS:**\n"}]

        # Add current files with content
        if VM_DIR.exists():
            for root, _, files in os.walk(VM_DIR):
                for name in sorted(files):
                    rel_path = os.path.relpath(os.path.join(root, name), VM_DIR)
                    file_path = os.path.join(root, name)
                    
                    try:
                        if name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                            try:
                                img = Image.open(file_path)
                                prompt_parts.append({"text": f"\n--- IMAGE: {rel_path} ---\n"})
                                prompt_parts.append(img)
                            except Exception:
                                prompt_parts.append({"text": f"\n--- IMAGE ERROR: {rel_path} ---\n"})
                        else:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read(3000)  # Increased content limit
                            prompt_parts.append({"text": f"\n--- FILE: {rel_path} ---\n{content}\n"})
                    except IOError:
                        continue

        # Add conversation history for context
        if self.conversation_history:
            prompt_parts.append({"text": "\n**CONVERSATION HISTORY:**\n"})
            for entry in self.conversation_history[-8:]:  # More history
                role = entry["role"].replace("_", " ").title()
                content = entry["content"][:300] + "..." if len(entry["content"]) > 300 else entry["content"]
                prompt_parts.append({"text": f"{role}: {content}\n\n"})

        # Add error context if any
        if self.error_context:
            prompt_parts.append({"text": f"\n**RECENT ERRORS:**\n{chr(10).join(self.error_context[-3:])}\n"})

        prompt_parts.append({"text": f"\n**USER REQUEST:**\n{user_prompt}"})
        return prompt_parts

    def _build_visual_context(self, context_text, system_prompt):
        """Build visual context for art critic with all images"""
        context_parts = [{"text": f"{system_prompt}\n\n{context_text}\n\n**VISUAL CONTEXT:**\n"}]
        
        if VM_DIR.exists():
            image_count = 0
            for root, _, files in os.walk(VM_DIR):
                for name in files:
                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        file_path = os.path.join(root, name)
                        rel_path = os.path.relpath(file_path, VM_DIR)
                        try:
                            img = Image.open(file_path)
                            context_parts.append({"text": f"\n--- ANALYZING IMAGE: {rel_path} ---\n"})
                            context_parts.append(img)
                            image_count += 1
                        except Exception:
                            continue
            
            if image_count == 0:
                context_parts.append({"text": "No images found in project.\n"})
        
        return context_parts

    def _should_invoke_code_critic(self, user_prompt, main_response, implementation_results):
        """Smart detection for when Code Critic is actually needed"""
        # Skip for simple operational commands
        simple_commands = [
            'run', 'start', 'execute', 'launch', 'install', 'update', 'pip install',
            'npm install', 'serve', 'host', 'deploy', 'build', 'compile'
        ]
        prompt_lower = user_prompt.lower()
        if any(cmd in prompt_lower and len(prompt_lower.split()) <= 4 for cmd in simple_commands):
            return False
        
        # Only invoke if there's substantial code creation/modification
        code_creation_indicators = [
            'create_file', 'write_to_file', 'function', 'class', 'algorithm',
            'implement', 'refactor', 'optimize', 'fix bug', 'debug', 'security',
            'performance', 'review code', 'analyze code'
        ]
        
        text_to_check = f"{user_prompt} {main_response}".lower()
        has_code_work = any(indicator in text_to_check for indicator in code_creation_indicators)
        
        # Also check if significant code was actually created/modified
        has_file_changes = any(result.get("type") == "system" and 
                              any(op in result.get("content", "") for op in ["Created file", "Updated file"])
                              for result in implementation_results)
        
        return has_code_work and has_file_changes

    def _should_invoke_art_critic(self, user_prompt, main_response, implementation_results):
        """Smart detection for when Art Critic is actually needed"""
        # Skip for simple operational commands
        simple_commands = [
            'run', 'start', 'execute', 'launch', 'install', 'update', 'serve'
        ]
        prompt_lower = user_prompt.lower()
        if any(cmd in prompt_lower and len(prompt_lower.split()) <= 4 for cmd in simple_commands):
            return False
        
        # Only invoke for visual/design work
        visual_work_indicators = [
            'generate_image', 'create image', 'design', 'visual', 'ui', 'interface',
            'color', 'layout', 'style', 'aesthetic', 'art', 'graphic', 'icon',
            'logo', 'banner', 'picture', 'photo'
        ]
        
        text_to_check = f"{user_prompt} {main_response}".lower()
        has_visual_work = any(indicator in text_to_check for indicator in visual_work_indicators)
        
        # Check if images were actually generated/modified
        has_image_changes = any(result.get("type") == "file_changed" and 
                               result.get("content", "").lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))
                               for result in implementation_results)
        
        # Check if this is specifically about visual analysis
        explicit_visual_analysis = any(phrase in prompt_lower for phrase in [
            'analyze image', 'review design', 'visual feedback', 'art critique',
            'design review', 'improve visuals'
        ])
        
        return has_visual_work or has_image_changes or explicit_visual_analysis

    def _needs_refinement(self, implementation_results):
        """Determine if refinement is needed based on results"""
        error_count = sum(1 for result in implementation_results if result.get("type") == "error")
        # Only suggest refinement if there are actual errors or complex operations
        complex_operations = sum(1 for result in implementation_results 
                               if result.get("type") == "system" and 
                               any(op in result.get("content", "") for op in ["Created file", "Updated file", "Generated"]))
        
        return error_count > 0 or complex_operations > 2

    def _has_project_images(self):
        """Check if project contains images"""
        if not VM_DIR.exists():
            return False
        
        for root, _, files in os.walk(VM_DIR):
            for name in files:
                if name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    return True
        return False

    def _process_enhanced_commands(self, response_text):
        """Enhanced command processing with better error handling"""
        command_pattern = re.compile(r'`(.*?)`', re.DOTALL)
        matches = command_pattern.finditer(response_text)

        for match in matches:
            command_str = match.group(1).strip()
            if not command_str:
                continue

            try:
                parsed_expr = ast.parse(command_str, mode="eval")
                call_node = parsed_expr.body
                
                if not isinstance(call_node, ast.Call):
                    continue

                func_name = call_node.func.id
                if func_name not in self.command_handlers:
                    yield {"type": "error", "content": f"Unknown command: {func_name}"}
                    continue

                args = [ast.literal_eval(arg) for arg in call_node.args]
                result = self.command_handlers[func_name](*args)

                if func_name == "generate_image":
                    for update in result:
                        yield update
                else:
                    yield {"type": "system", "content": result}
                    
                # Track successful changes
                if func_name in ["create_file", "write_to_file", "generate_image"]:
                    self.project_context["recent_changes"].append({
                        "command": func_name,
                        "args": args,
                        "timestamp": time.time()
                    })

            except Exception as e:
                error_msg = f"Command execution error: '{command_str}' - {e}"
                self.error_context.append(error_msg)
                yield {"type": "error", "content": error_msg}

    def _log_interaction(self, role, content):
        """Log interaction for conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        
        # Keep history manageable
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-15:]

    def _format_results(self, results):
        """Format implementation results for agent review"""
        if not results:
            return "No implementation results"
        
        formatted = []
        for result in results[-5:]:  # Last 5 results
            formatted.append(f"- {result.get('type', 'unknown')}: {result.get('content', '')}")
        return "\n".join(formatted)

    def _get_project_summary(self):
        """Get concise project summary"""
        file_count = len(self.project_context.get("files", []))
        image_count = len(self.project_context.get("images", []))
        recent_changes = len(self.project_context.get("recent_changes", []))
        
        return f"Files: {file_count}, Images: {image_count}, Recent changes: {recent_changes}"

    def _get_recent_conversation_summary(self):
        """Get summary of recent conversation"""
        if not self.conversation_history:
            return "No recent conversation"
        
        recent = self.conversation_history[-6:]
        summary = []
        for entry in recent:
            role = entry["role"].replace("_", " ").title()
            content = entry["content"][:150] + "..." if len(entry["content"]) > 150 else entry["content"]
            summary.append(f"{role}: {content}")
        
        return "\n".join(summary)

    def _get_project_files(self):
        """Get list of project files"""
        files = []
        if VM_DIR.exists():
            for root, _, filenames in os.walk(VM_DIR):
                for name in filenames:
                    if not name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        rel_path = os.path.relpath(os.path.join(root, name), VM_DIR)
                        files.append(rel_path)
        return files

    def _get_project_images(self):
        """Get list of project images"""
        images = []
        if VM_DIR.exists():
            for root, _, filenames in os.walk(VM_DIR):
                for name in filenames:
                    if name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        rel_path = os.path.relpath(os.path.join(root, name), VM_DIR)
                        images.append(rel_path)
        return images

    def _get_recent_changes(self):
        """Get recent project changes"""
        return self.project_context.get("recent_changes", [])[-10:]  # Last 10 changes

    def _extract_grade(self, agent_response):
        """Extract numerical grade from agent response"""
        if not agent_response:
            return None
            
        # Look for "GRADE: XX/100" pattern
        import re
        grade_match = re.search(r'GRADE:\s*(\d+)/100', agent_response, re.IGNORECASE)
        if grade_match:
            return int(grade_match.group(1))
        
        # Fallback: look for standalone numbers near "grade"
        grade_match = re.search(r'grade[:\s]*(\d+)', agent_response, re.IGNORECASE)
        if grade_match:
            return int(grade_match.group(1))
            
        return None

    def _calculate_overall_grade(self, critic_grade, art_grade):
        """Calculate overall grade from individual agent grades"""
        grades = [g for g in [critic_grade, art_grade] if g is not None]
        if not grades:
            return 85  # Default grade if no grading available
        return sum(grades) // len(grades)  # Average of available grades

    def _safe_path(self, filename):
        """Sanitize file paths"""
        if not filename or ".." in filename.split(os.path.sep):
            return None
        return VM_DIR / filename

    def _create_file(self, path, content=""):
        """Create new file with enhanced error handling"""
        filepath = self._safe_path(path)
        if not filepath:
            return f"❌ Invalid path: {path}"

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding='utf-8')
            return f"✅ Created file: {path} ({len(content)} characters)"
        except Exception as e:
            error_msg = f"❌ Error creating file {path}: {e}"
            self.error_context.append(error_msg)
            return error_msg

    def _write_to_file(self, path, content):
        """Write to file with enhanced feedback"""
        filepath = self._safe_path(path)
        if not filepath:
            return f"❌ Invalid path: {path}"
        
        if not filepath.exists():
            return f"❌ File not found: {path}"

        try:
            old_size = filepath.stat().st_size if filepath.exists() else 0
            filepath.write_text(content, encoding='utf-8')
            new_size = len(content.encode('utf-8'))
            return f"✅ Updated file: {path} ({old_size} → {new_size} bytes)"
        except Exception as e:
            error_msg = f"❌ Error writing to file {path}: {e}"
            self.error_context.append(error_msg)
            return error_msg

    def _delete_file(self, path):
        """Delete file with enhanced feedback"""
        filepath = self._safe_path(path)
        if not filepath or not filepath.exists():
            return f"❌ File not found: {path}"

        try:
            if filepath.is_dir():
                # Enhanced directory deletion
                file_count = sum(1 for _ in filepath.rglob('*') if _.is_file())
                for p in reversed(list(filepath.rglob('*'))):
                    if p.is_file():
                        p.unlink()
                    elif p.is_dir():
                        try:
                            p.rmdir()
                        except OSError:
                            pass
                filepath.rmdir()
                return f"✅ Deleted directory: {path} ({file_count} files)"
            else:
                file_size = filepath.stat().st_size
                filepath.unlink()
                return f"✅ Deleted file: {path} ({file_size} bytes)"
        except Exception as e:
            error_msg = f"❌ Error deleting {path}: {e}"
            self.error_context.append(error_msg)
            return error_msg

    def _run_command(self, command):
        """Execute shell command with enhanced output"""
        if not command:
            return "❌ No command provided"

        try:
            start_time = time.time()
            proc = subprocess.run(
                command,
                cwd=VM_DIR,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120  # Increased timeout
            )
            execution_time = time.time() - start_time
            
            output = f"🔧 Command: {command}\n⏱️ Execution time: {execution_time:.2f}s\n"
            
            if proc.stdout:
                output += f"📤 STDOUT:\n{proc.stdout}\n"
            if proc.stderr:
                output += f"⚠️ STDERR:\n{proc.stderr}\n"
                self.error_context.append(f"Command stderr: {proc.stderr}")
            
            if proc.returncode == 0:
                output += "✅ Command completed successfully"
            else:
                output += f"❌ Command failed with exit code: {proc.returncode}"
                
            return output
            
        except subprocess.TimeoutExpired:
            error_msg = "⏰ Command timed out after 120 seconds"
            self.error_context.append(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"❌ Command execution error: {e}"
            self.error_context.append(error_msg)
            return error_msg

    def generate_image(self, path, prompt):
        """Enhanced image generation with better feedback"""
        if not self.client:
            yield {"type": "error", "content": "❌ Image generation not configured"}
            return

        filepath = self._safe_path(path)
        if not filepath:
            yield {"type": "error", "content": f"❌ Invalid path: {path}"}
            return

        yield {"type": "system", "content": f"🎨 Generating image: {path}"}
        yield {"type": "system", "content": f"📝 Prompt: {prompt}"}

        try:
            config = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
            response = self.client.models.generate_content(
                model=IMAGE_MODEL_NAME,
                contents=prompt,
                config=config
            )

            image_bytes = None
            candidates = getattr(response, "candidates", [])
            if candidates:
                parts = candidates[0].content.parts
                for part in parts:
                    if hasattr(part, "inline_data") and part.inline_data is not None:
                        image_bytes = part.inline_data.data
                        break

            if not image_bytes:
                yield {"type": "error", "content": "❌ No image data received from AI"}
                return

            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(image_bytes)
            
            # Get image info
            try:
                img = Image.open(filepath)
                width, height = img.size
                file_size = filepath.stat().st_size
                yield {"type": "system", "content": f"✅ Image generated: {width}x{height}px, {file_size} bytes"}
            except Exception:
                yield {"type": "system", "content": f"✅ Image generated: {path}"}
            
            yield {"type": "file_changed", "content": str(filepath)}

        except Exception as e:
            error_msg = f"❌ Image generation failed: {e}"
            self.error_context.append(error_msg)
            yield {"type": "error", "content": error_msg}

# -----------------------------------------------------------------------------
# Enhanced IDE Application
# -----------------------------------------------------------------------------
class EnhancedGeminiIDE(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1600x1000")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        VM_DIR.mkdir(exist_ok=True)
        self.msg_queue = queue.Queue()
        self.current_image = None
        self.current_open_file_path = None

        self._create_enhanced_menu()
        self._create_enhanced_layout()
        self._create_enhanced_status_bar()

        api_key = load_api_key()
        if not api_key and GENAI_IMPORTED:
            self.prompt_api_key()
        elif GENAI_IMPORTED:
            self.configure_enhanced_agents(api_key)
        else:
            messagebox.showerror("Missing Dependency", "Install google-genai: pip install google-genai")
            self.status_var.set("❌ google-genai not installed")

        self.after(100, self._process_messages)

    def _create_enhanced_menu(self):
        """Create enhanced application menu"""
        menubar = tk.Menu(self)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="📄 New File", command=self.new_file)
        file_menu.add_command(label="💾 Save File", command=self.save_current_file)
        file_menu.add_command(label="🔄 Refresh Files", command=self.refresh_files)
        file_menu.add_separator()
        file_menu.add_command(label="🧹 Clear Chat", command=self.clear_chat)
        file_menu.add_command(label="📊 Project Stats", command=self.show_project_stats)
        menubar.add_cascade(label="File", menu=file_menu)

        # Agents menu
        agents_menu = tk.Menu(menubar, tearoff=0)
        agents_menu.add_command(label="🤖 Test Main Coder", command=lambda: self.test_agent("main"))
        agents_menu.add_command(label="📊 Test Code Critic", command=lambda: self.test_agent("critic"))
        agents_menu.add_command(label="🎨 Test Art Critic", command=lambda: self.test_agent("art"))
        agents_menu.add_separator()
        agents_menu.add_command(label="🔄 Reset Agent Memory", command=self.reset_agent_memory)
        # Prompt Enhancer toggle is now a Canvas switch in the main UI, not a menu item.
        menubar.add_cascade(label="Agents", menu=agents_menu)

        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="🔑 Set API Key", command=self.prompt_api_key)
        settings_menu.add_command(label="⚙️ Agent Settings", command=self.show_agent_settings)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        self.config(menu=menubar)

    def _create_enhanced_layout(self):
        """Create enhanced UI layout"""
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel with enhanced features
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=1)

        # Enhanced image preview
        img_frame = ttk.LabelFrame(left_frame, text="🖼️ Visual Preview", padding=5)
        img_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.canvas = tk.Canvas(img_frame, bg='#f0f0f0', height=320)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_text(160, 160, text="🖼️ No image selected\nImages will be analyzed by Art Critic", 
                               fill="gray", font=("Arial", 11), justify=tk.CENTER)

        # Enhanced file tree
        tree_frame = ttk.LabelFrame(left_frame, text="📁 Project Explorer", padding=5)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=("fullpath", "size"), show="tree")
        self.tree.heading("#0", text="Name")
        self.tree.heading("size", text="Size")
        self.tree.column("fullpath", width=0, stretch=False)
        self.tree.column("size", width=80)

        # Scrollbars for tree
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self._attach_enhanced_tree_context_menu()

        # Right panel with enhanced notebook
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=3)

        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Enhanced editor tab
        editor_frame = ttk.Frame(self.notebook)
        self.editor = scrolledtext.ScrolledText(
            editor_frame, 
            wrap=tk.WORD, 
            font=("Consolas", 12),
            padx=15,
            pady=15,
            bg="#1e1e1e",
            fg="#dcdcdc",
            insertbackground="#dcdcdc"
        )
        self.editor.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(editor_frame, text="📝 Code Editor")

        # Enhanced multi-agent chat tab
        chat_frame = ttk.Frame(self.notebook)
        self.chat = scrolledtext.ScrolledText(
            chat_frame, 
            wrap=tk.WORD, 
            font=("Segoe UI", 11),
            padx=15,
            pady=15,
            state="disabled",
            bg="#f8f9fa"
        )
        self.chat.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(chat_frame, text="🤖 Multi-Agent Chat")

        # Project insights tab
        insights_frame = ttk.Frame(self.notebook)
        self.insights = scrolledtext.ScrolledText(
            insights_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            padx=15,
            pady=15,
            state="disabled",
            bg="#f0f8ff"
        )
        self.insights.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(insights_frame, text="📊 Project Insights")

        # Enhanced input area
        input_frame = ttk.Frame(right_frame)
        input_frame.pack(fill=tk.X, pady=(0, 5))

        # Input text with placeholder
        self.input_txt = tk.Text(
            input_frame, 
            height=4, 
            wrap=tk.WORD,
            font=("Segoe UI", 11),
            padx=10,
            pady=10,
            bg="#ffffff",
            relief=tk.RAISED
        )
        self.input_txt.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_txt.bind("<Control-Return>", lambda e: self.send_enhanced_prompt())
        self.input_txt.insert("1.0", "💬 Ask the multi-agent system anything... (Ctrl+Enter to send)")
        self.input_txt.bind("<FocusIn>", self._clear_placeholder)
        self.input_txt.bind("<FocusOut>", self._restore_placeholder)

        # Frame for control buttons (toggle, screenshot, send)
        control_button_frame = ttk.Frame(input_frame)
        control_button_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0)) # Use fill=tk.Y and anchor

        # Label for the toggle switch
        self.enhancer_toggle_label = ttk.Label(control_button_frame, text="Enhancer:")
        self.enhancer_toggle_label.pack(side=tk.LEFT, padx=(0, 2), anchor='center')

        # Custom Toggle Switch Canvas
        self.enhancer_toggle_switch = tk.Canvas(
            control_button_frame,
            width=50,
            height=22,
            borderwidth=0, # Using 0 and drawing own border if needed
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.enhancer_toggle_switch.pack(side=tk.LEFT, padx=(0, 8), anchor='center') # Added more padding

        # Screenshot upload button (now icon-only for compactness)
        self.screenshot_btn = ttk.Button(
            control_button_frame,
            text="📸",
            command=self.upload_screenshot,
            width=3
        )
        self.screenshot_btn.pack(side=tk.LEFT, padx=(0, 3), anchor='center') # Adjusted padding
        
        # Enhanced send button
        self.send_btn = ttk.Button(
            control_button_frame,
            text="🚀 Send",
            command=self.send_enhanced_prompt
        )
        self.send_btn.pack(side=tk.LEFT, anchor='center')
        self.enhancer_toggle_switch.bind("<Button-1>", self._toggle_prompt_enhancer)

        self.editor.bind("<Control-s>", lambda e: self.save_current_file())
        self._setup_enhanced_syntax_highlighting()
        self.editor.bind("<KeyRelease>", self._on_editor_key_release)
        self.refresh_files()

    def _setup_enhanced_syntax_highlighting(self):
        """Enhanced syntax highlighting"""
        # Dark theme syntax colors
        self.editor.tag_configure("keyword", foreground="#569cd6")
        self.editor.tag_configure("string", foreground="#ce9178")
        self.editor.tag_configure("comment", foreground="#6a9955")
        self.editor.tag_configure("number", foreground="#b5cea8")
        self.editor.tag_configure("function", foreground="#dcdcaa")
        self.editor.tag_configure("class", foreground="#4ec9b0")
        self.editor.tag_configure("operator", foreground="#d4d4d4")

        self.syntax_patterns = {
            "keyword": r"\b(def|class|import|from|for|while|if|elif|else|return|in|and|or|not|is|with|as|try|except|finally|raise|yield|pass|continue|break|global|nonlocal|lambda|assert|async|await)\b",
            "string": r"(\".*?\"|\'.*?\'|\"\"\".*?\"\"\"|\'\'\'.*?\'\'\')",
            "comment": r"#.*",
            "number": r"\b\d+(\.\d*)?\b",
            "function": r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()",
            "class": r"\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            "operator": r"[+\-*/=<>!&|^~%]"
        }

    def _apply_enhanced_syntax_highlighting(self):
        """Apply enhanced syntax highlighting"""
        content = self.editor.get("1.0", tk.END)

        for tag in self.syntax_patterns.keys():
            self.editor.tag_remove(tag, "1.0", tk.END)

        for tag, pattern in self.syntax_patterns.items():
            for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                start, end = match.span()
                self.editor.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")

    def _on_editor_key_release(self, event=None):
        """Enhanced editor key release handler"""
        self._apply_enhanced_syntax_highlighting()
        # Auto-save after 2 seconds of inactivity
        if hasattr(self, '_save_timer'):
            self.after_cancel(self._save_timer)
        self._save_timer = self.after(2000, self._auto_save)

    def _auto_save(self):
        """Auto-save current file"""
        if self.current_open_file_path:
            self.save_current_file()

    def _clear_placeholder(self, event):
        """Clear placeholder text"""
        if self.input_txt.get("1.0", tk.END).strip().startswith("💬 Ask the multi-agent"):
            self.input_txt.delete("1.0", tk.END)

    def _restore_placeholder(self, event):
        """Restore placeholder if empty"""
        if not self.input_txt.get("1.0", tk.END).strip():
            self.input_txt.insert("1.0", "💬 Ask the multi-agent system anything... (Ctrl+Enter to send)")

    def _attach_enhanced_tree_context_menu(self):
        """Enhanced context menu for file tree"""
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="📝 Rename", command=self.rename_file)
        self.context_menu.add_command(label="🗑️ Delete", command=self.delete_file)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🔍 Analyze with Agents", command=self.analyze_selected_file)
        self.context_menu.add_command(label="🎨 Review Design", command=self.review_visual_design)
        self.tree.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event):
        """Show enhanced context menu"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _create_enhanced_status_bar(self):
        """Create enhanced status bar"""
        status_frame = ttk.Frame(self)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_var = tk.StringVar(value="🚀 Enhanced Multi-Agent System Ready")
        status_bar = ttk.Label(
            status_frame, 
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=5
        )
        status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Agent status indicators
        self.agent_status_frame = ttk.Frame(status_frame)
        self.agent_status_frame.pack(side=tk.RIGHT, padx=5)

        self.main_status = ttk.Label(self.agent_status_frame, text="🤖", foreground="green")
        self.main_status.pack(side=tk.LEFT, padx=2)
        
        self.critic_status = ttk.Label(self.agent_status_frame, text="📊", foreground="green")
        self.critic_status.pack(side=tk.LEFT, padx=2)
        
        self.art_status = ttk.Label(self.agent_status_frame, text="🎨", foreground="green")
        self.art_status.pack(side=tk.LEFT, padx=2)

    def configure_enhanced_agents(self, api_key):
        """Configure enhanced multi-agent system"""
        try:
            self.agent_system = EnhancedMultiAgentSystem(api_key)
            self.status_var.set("✅ Enhanced Multi-Agent System configured")
            self.add_chat_message("System", "🚀 Enhanced Multi-Agent System ready!\n\n🤖 Main Coder Agent - Vision-enabled implementation\n📊 Code Critic Agent - Deep analysis & security\n🎨 Art Critic Agent - Visual analysis & design")
            self._draw_enhancer_toggle_switch() # Initial draw of the custom toggle switch
            self.update_agent_insights()
        except Exception as e:
            self.status_var.set(f"❌ Agent error: {str(e)}")
            self.add_chat_message("System", f"Agent configuration failed: {str(e)}", "#ff0000")

    def update_agent_insights(self):
        """Update project insights"""
        if not hasattr(self, 'agent_system'):
            return
            
        insights = []
        insights.append("📊 PROJECT ANALYSIS")
        insights.append("=" * 50)
        
        # File analysis
        file_count = len(self.agent_system._get_project_files())
        image_count = len(self.agent_system._get_project_images())
        insights.append(f"📁 Files: {file_count}")
        insights.append(f"🖼️ Images: {image_count}")
        
        # Recent changes
        recent_changes = len(self.agent_system._get_recent_changes())
        insights.append(f"🔄 Recent changes: {recent_changes}")
        
        # Agent capabilities
        insights.append("\n🤖 AGENT CAPABILITIES")
        insights.append("=" * 50)
        insights.append("🤖 Main Coder: Implementation + Vision")
        insights.append("📊 Code Critic: Quality + Security + Performance")
        insights.append("🎨 Art Critic: Visual Analysis + Design + UX")
        
        self.insights.config(state="normal")
        self.insights.delete("1.0", tk.END)
        self.insights.insert("1.0", "\n".join(insights))
        self.insights.config(state="disabled")

    def send_enhanced_prompt(self):
        """Send enhanced prompt to multi-agent system"""
        text = self.input_txt.get("1.0", tk.END).strip()
        if not text or text.startswith("💬 Ask the multi-agent"):
            return

        self.add_chat_message("👤 You", text)
        self.input_txt.delete("1.0", tk.END)

        self.input_txt.config(state="disabled")
        self.send_btn.config(state="disabled")
        self.status_var.set("🔄 Enhanced Multi-Agent System Processing...")

        # Update agent status to processing
        self.main_status.config(foreground="orange")
        self.critic_status.config(foreground="orange")  
        self.art_status.config(foreground="orange")

        threading.Thread(
            target=self._process_enhanced_prompt, 
            args=(text,),
            daemon=True
        ).start()

    def _process_enhanced_prompt(self, text):
        """Process enhanced prompt with multi-agent system"""
        if not hasattr(self, 'agent_system') or self.agent_system is None:
            self.msg_queue.put({"type": "error", "content": "Enhanced Multi-Agent System not configured. Set API key."})
            self.msg_queue.put({"type": "done"})
            return

        for response in self.agent_system.run_enhanced_interaction(text):
            self.msg_queue.put(response)
        self.msg_queue.put({"type": "done"})

    def _process_messages(self):
        """Enhanced message processing"""
        try:
            while not self.msg_queue.empty():
                msg = self.msg_queue.get_nowait()

                if msg["type"] == "agent":
                    agent_name = msg["agent"]
                    agent_colors = {
                        "🤖 Main Coder": "#2E8B57",
                        "📊 Code Critic": "#FF6347",
                        "🎭 Art Critic": "#9370DB",
                        "✨ Prompt Enhancer": "#FFD700", # Gold color for enhancer
                        "🤝 Collaborative": "#4169E1"
                    }
                    color = agent_colors.get(agent_name, "#000000")
                    self.add_chat_message(agent_name, msg["content"], color)
                elif msg["type"] == "system":
                    self.add_chat_message("🔧 System", msg["content"], "#2E8B57")
                elif msg["type"] == "error":
                    self.add_chat_message("❌ Error", msg["content"], "#ff0000")
                elif msg["type"] == "file_changed":
                    self.refresh_files()
                    self.update_agent_insights()
                    changed_file_path = Path(msg["content"])
                    if changed_file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                        self.display_enhanced_image(changed_file_path)
                    elif self.current_open_file_path and self.current_open_file_path.samefile(changed_file_path):
                        self.display_file(self.current_open_file_path)
                elif msg["type"] == "done":
                    self.input_txt.config(state="normal")
                    self.send_btn.config(state="normal")
                    self.status_var.set("✅ Enhanced Multi-Agent System Ready")
                    # Reset agent status
                    self.main_status.config(foreground="green")
                    self.critic_status.config(foreground="green")
                    self.art_status.config(foreground="green")

        except queue.Empty:
            pass

        self.after(100, self._process_messages)

    def display_enhanced_image(self, path):
        """Enhanced image display with metadata"""
        try:
            img = Image.open(path)
            original_size = img.size
            img.thumbnail((400, 300))

            self.canvas.delete("all")
            tk_img = ImageTk.PhotoImage(img)
            self.canvas.create_image(200, 150, image=tk_img, anchor=tk.CENTER)
            self.canvas.image = tk_img

            # Add image metadata
            file_size = path.stat().st_size
            self.canvas.create_text(
                200, 280, 
                text=f"{path.name}\n{original_size[0]}x{original_size[1]}px\n{file_size:,} bytes", 
                fill="darkblue", 
                justify=tk.CENTER,
                font=("Arial", 9)
            )

            self.status_var.set(f"🖼️ Displaying: {path.name} ({original_size[0]}x{original_size[1]})")
        except Exception as e:
            self.canvas.delete("all")
            self.canvas.create_text(200, 150, text=f"❌ Error loading image:\n{str(e)}", 
                                   fill="red", justify=tk.CENTER)
            self.status_var.set(f"❌ Image error: {str(e)}")

    def refresh_files(self):
        """Enhanced file tree refresh with metadata"""
        self.tree.delete(*self.tree.get_children())
        self._populate_enhanced_tree(VM_DIR, "")

    def _populate_enhanced_tree(self, path, parent):
        """Enhanced tree population with file sizes"""
        for item in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            if item.is_dir():
                node = self.tree.insert(
                    parent, 
                    'end', 
                    text=f"📁 {item.name}", 
                    values=(str(item.relative_to(VM_DIR)), ""), 
                    open=False
                )
                self._populate_enhanced_tree(item, node)
            else:
                try:
                    file_size = item.stat().st_size
                    size_str = self._format_file_size(file_size)
                    
                    if item.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                        icon = "🖼️"
                    elif item.suffix.lower() in ['.py', '.js', '.html', '.css']:
                        icon = "📝"
                    else:
                        icon = "📄"
                        
                    node = self.tree.insert(
                        parent, 
                        'end', 
                        text=f"{icon} {item.name}", 
                        values=(str(item.relative_to(VM_DIR)), size_str)
                    )
                except OSError:
                    continue

    def _format_file_size(self, size):
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def add_chat_message(self, sender, message, color="#000000"):
        """Enhanced chat message with better formatting"""
        self.chat.config(state="normal")
        
        # Create timestamp
        timestamp = time.strftime("[%H:%M:%S] ")
        
        # Configure tags
        # Use regex to create a safe tag name from the sender string
        safe_sender_name = re.sub(r'\W+', '', sender) # Remove non-alphanumeric
        sender_tag = f"sender_{safe_sender_name.strip()}"
        self.chat.tag_configure(sender_tag, foreground=color, font=("Segoe UI", 11, "bold"))
        self.chat.tag_configure("timestamp", foreground="gray", font=("Segoe UI", 9))
        self.chat.tag_configure("message", font=("Segoe UI", 11))
        
        # Insert message
        self.chat.insert(tk.END, timestamp, "timestamp")
        self.chat.insert(tk.END, f"{sender}:\n", sender_tag)
        self.chat.insert(tk.END, f"{message}\n\n", "message")
        
        self.chat.see(tk.END)
        self.chat.config(state="disabled")
        self.notebook.select(1)  # Switch to chat tab

    # Additional enhanced methods
    def test_agent(self, agent_type):
        """Test individual agent functionality"""
        test_prompts = {
            "main": "Create a simple hello.py file with a greeting function",
            "critic": "Review the code quality of any Python files in the project",
            "art": "Analyze any images in the project and suggest visual improvements"
        }
        
        if agent_type in test_prompts:
            self.input_txt.delete("1.0", tk.END)
            self.input_txt.insert("1.0", test_prompts[agent_type])
            self.send_enhanced_prompt()

    def reset_agent_memory(self):
        """Reset agent conversation history"""
        if hasattr(self, 'agent_system'):
            self.agent_system.conversation_history = []
            self.agent_system.error_context = []
            self.add_chat_message("🔄 System", "Agent memory reset successfully")

    def show_project_stats(self):
        """Show detailed project statistics"""
        if not hasattr(self, 'agent_system'):
            return
            
        stats = []
        stats.append("📊 PROJECT STATISTICS")
        stats.append("=" * 40)
        
        files = self.agent_system._get_project_files()
        images = self.agent_system._get_project_images()
        
        stats.append(f"📁 Total Files: {len(files)}")
        stats.append(f"🖼️ Images: {len(images)}")
        
        if files:
            stats.append("\n📝 CODE FILES:")
            for f in files[:10]:  # Show first 10
                stats.append(f"  • {f}")
        
        if images:
            stats.append("\n🖼️ IMAGE FILES:")
            for img in images:
                stats.append(f"  • {img}")
        
        messagebox.showinfo("Project Statistics", "\n".join(stats))

    def show_agent_settings(self):
        """Show agent system settings with grading controls"""
        if not hasattr(self, 'agent_system'):
            messagebox.showwarning("⚠️ Warning", "Agent system not configured. Please set API key first.")
            return
            
        # Create settings dialog
        settings_window = tk.Toplevel(self)
        settings_window.title("🤖 Agent System Settings")
        settings_window.geometry("500x600")
        settings_window.transient(self)
        settings_window.grab_set()
        
        # Main content frame
        main_frame = ttk.Frame(settings_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="🤖 ENHANCED MULTI-AGENT SYSTEM", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Configuration section
        config_frame = ttk.LabelFrame(main_frame, text="📋 Configuration", padding=10)
        config_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(config_frame, text=f"• Text Model: {TEXT_MODEL_NAME}").pack(anchor=tk.W)
        ttk.Label(config_frame, text=f"• Image Model: {IMAGE_MODEL_NAME}").pack(anchor=tk.W)
        ttk.Label(config_frame, text="• Vision Capabilities: ✅ Enabled").pack(anchor=tk.W)
        ttk.Label(config_frame, text="• Image Generation: ✅ Enabled").pack(anchor=tk.W)
        
        # Grading system section
        grading_frame = ttk.LabelFrame(main_frame, text="📊 Grading System", padding=10)
        grading_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.grading_var = tk.BooleanVar(value=getattr(self.agent_system, 'grading_enabled', True))
        grading_check = ttk.Checkbutton(
            grading_frame, 
            text="Enable Agent Grading & Retry System",
            variable=self.grading_var,
            command=self._toggle_grading
        )
        grading_check.pack(anchor=tk.W)
        
        # self.prompt_enhancer_var = tk.BooleanVar(value=getattr(self.agent_system, 'prompt_enhancer_enabled', True))
        # prompt_enhancer_check = ttk.Checkbutton(
        #     grading_frame,
        #     text="Enable Prompt Enhancer Agent ✨",
        #     variable=self.prompt_enhancer_var,
        #     command=self._toggle_prompt_enhancer
        # )
        # prompt_enhancer_check.pack(anchor=tk.W)

        ttk.Label(grading_frame, text=f"• Max Retry Attempts: {getattr(self.agent_system, 'max_retry_attempts', 3)}").pack(anchor=tk.W)
        ttk.Label(grading_frame, text="• Minimum Passing Grade: 70/100").pack(anchor=tk.W)
        
        # Agent capabilities section
        agents_frame = ttk.LabelFrame(main_frame, text="🎯 Agent Capabilities", padding=10)
        agents_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(agents_frame, text="• Main Coder: Implementation + Vision Analysis").pack(anchor=tk.W)
        ttk.Label(agents_frame, text="• Code Critic: Quality + Security + Performance + Grading").pack(anchor=tk.W)
        ttk.Label(agents_frame, text="• Art Critic: Visual Design + UX + Accessibility + Grading").pack(anchor=tk.W)
        
        # Memory section
        memory_frame = ttk.LabelFrame(main_frame, text="💾 Memory Status", padding=10)
        memory_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(memory_frame, text=f"• Conversation History: {len(getattr(self.agent_system, 'conversation_history', []))} entries").pack(anchor=tk.W)
        ttk.Label(memory_frame, text=f"• Error Context: {len(getattr(self.agent_system, 'error_context', []))} entries").pack(anchor=tk.W)
        
        # Features section
        features_frame = ttk.LabelFrame(main_frame, text="🔧 Features", padding=10)
        features_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(features_frame, text="• Enhanced syntax highlighting").pack(anchor=tk.W)
        ttk.Label(features_frame, text="• Auto-save functionality").pack(anchor=tk.W)
        ttk.Label(features_frame, text="• Visual file tree with metadata").pack(anchor=tk.W)
        ttk.Label(features_frame, text="• Real-time project insights").pack(anchor=tk.W)
        ttk.Label(features_frame, text="• Screenshot upload & analysis").pack(anchor=tk.W)
        
        # Close button
        close_btn = ttk.Button(main_frame, text="✅ Close", command=settings_window.destroy)
        close_btn.pack(pady=(20, 0))
        
    def _toggle_grading(self):
        """Toggle grading system on/off"""
        if hasattr(self, 'agent_system'):
            self.agent_system.grading_enabled = self.grading_var.get()
            status = "enabled" if self.grading_var.get() else "disabled"
            self.status_var.set(f"📊 Grading system {status}")
            self.add_chat_message("⚙️ Settings", f"Grading system {status}")

    def _toggle_prompt_enhancer(self, event=None):
        """Toggle prompt enhancer system on/off - called by the UI switch."""
        if hasattr(self, 'agent_system'):
            self.agent_system.prompt_enhancer_enabled = not self.agent_system.prompt_enhancer_enabled
            status = "enabled" if self.agent_system.prompt_enhancer_enabled else "disabled"
            self.status_var.set(f"✨ Prompt Enhancer {status}")
            self.add_chat_message("⚙️ Settings", f"Prompt Enhancer agent {status}")
            self._draw_enhancer_toggle_switch() # Update visual state of the switch

    # def _toggle_prompt_enhancer_menu(self): # Removed as toggle is no longer in menu
    #     """Toggle prompt enhancer system on/off - called by menu."""
    #     pass

    def _draw_enhancer_toggle_switch(self):
        """Draws the custom toggle switch based on the current state."""
        if not hasattr(self, 'enhancer_toggle_switch') or not hasattr(self, 'agent_system'):
            return # Not ready to draw

        self.enhancer_toggle_switch.delete("all") # Clear previous drawing

        # Get actual canvas dimensions as it's laid out
        self.enhancer_toggle_switch.update_idletasks() # Ensure dimensions are up-to-date
        width = self.enhancer_toggle_switch.winfo_width()
        height = self.enhancer_toggle_switch.winfo_height()

        if width <= 1 or height <= 1: # Canvas not yet sized by Tkinter
             # Fallback dimensions if still not available (should not happen often with update_idletasks)
            width = 50
            height = 22
            # self.enhancer_toggle_switch.after(50, self._draw_enhancer_toggle_switch)
            # return

        padding = 2
        oval_diameter = height - 2 * padding

        text_y_offset = height // 2

        if self.agent_system.prompt_enhancer_enabled:
            # Green background for "ON"
            self.enhancer_toggle_switch.create_rectangle(
                0, 0, width, height,
                fill="#4CAF50", outline="#388E3C", width=1 # Darker green for border
            )
            # White "ON" text
            self.enhancer_toggle_switch.create_text(
                (width - oval_diameter - padding) / 2, text_y_offset, text="ON", fill="white",
                font=("Segoe UI", 7, "bold"), anchor="center"
            )
            # Switch handle (oval) on the right
            self.enhancer_toggle_switch.create_oval(
                width - oval_diameter - padding, padding,
                width - padding, height - padding,
                fill="white", outline="#BDBDBD" # Light gray outline for handle
            )
        else:
            # Red background for "OFF"
            self.enhancer_toggle_switch.create_rectangle(
                0, 0, width, height,
                fill="#F44336", outline="#D32F2F", width=1 # Darker red for border
            )
            # White "OFF" text
            self.enhancer_toggle_switch.create_text(
                (width + oval_diameter + padding) / 2, text_y_offset, text="OFF", fill="white",
                font=("Segoe UI", 7, "bold"), anchor="center"
            )
            # Switch handle (oval) on the left
            self.enhancer_toggle_switch.create_oval(
                padding, padding,
                oval_diameter + padding, height - padding,
                fill="white", outline="#BDBDBD" # Light gray outline for handle
            )

    def analyze_selected_file(self):
        """Analyze selected file with agents"""
        selected = self.tree.selection()
        if not selected:
            return

        rel_path = Path(self.tree.item(selected[0], "values")[0])
        prompt = f"Please analyze the file '{rel_path}' and provide comprehensive feedback on code quality, design, and potential improvements."
        
        self.input_txt.delete("1.0", tk.END)
        self.input_txt.insert("1.0", prompt)
        self.send_enhanced_prompt()

    def review_visual_design(self):
        """Review visual design of selected file"""
        selected = self.tree.selection()
        if not selected:
            return

        rel_path = Path(self.tree.item(selected[0], "values")[0])
        if rel_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
            prompt = f"Please analyze the visual design of '{rel_path}' image and provide detailed artistic feedback including composition, color theory, and suggestions for improvement."
        else:
            prompt = f"Please review '{rel_path}' for UI/UX design principles if it contains interface code, or suggest ways to make it more visually appealing."
        
        self.input_txt.delete("1.0", tk.END)
        self.input_txt.insert("1.0", prompt)
        self.send_enhanced_prompt()

    def prompt_api_key(self):
        """Enhanced API key prompt"""
        api_key = simpledialog.askstring(
            "🔑 API Key Configuration", 
            "Enter your Gemini API Key:\n(Required for multi-agent functionality)", 
            parent=self
        )
        if api_key:
            save_api_key(api_key)
            self.configure_enhanced_agents(api_key)
            messagebox.showinfo("✅ Success", "API Key saved and agents configured!")

    def on_tree_select(self, event):
        """Enhanced tree selection handler"""
        selected = self.tree.selection()
        if not selected:
            return

        rel_path = Path(self.tree.item(selected[0], "values")[0])
        file_path = VM_DIR / rel_path

        if file_path.is_file():
            if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                self.display_enhanced_image(file_path)
                self.current_open_file_path = None
                self.editor.delete("1.0", tk.END)
            else:
                self.display_file(file_path)

    def display_file(self, path):
        """Enhanced file display"""
        try:
            self.current_open_file_path = path
            content = path.read_text(encoding='utf-8')

            self.editor.config(state="normal")
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", content)
            self.editor.config(state="normal")

            self._apply_enhanced_syntax_highlighting()
            self.notebook.select(0)  # Switch to editor tab
            
            line_count = len(content.splitlines())
            char_count = len(content)
            self.status_var.set(f"📝 Loaded: {path.name} ({line_count} lines, {char_count} chars)")
        except Exception as e:
            self.editor.delete("1.0", tk.END)
            self.editor.insert("1.0", f"❌ Error reading file: {str(e)}")
            self.status_var.set(f"❌ File error: {str(e)}")
            self.current_open_file_path = None

    def save_current_file(self):
        """Enhanced file saving"""
        if self.current_open_file_path and self.current_open_file_path.is_file():
            try:
                content = self.editor.get("1.0", tk.END)
                self.current_open_file_path.write_text(content, encoding='utf-8')
                
                line_count = len(content.splitlines())
                char_count = len(content)
                self.status_var.set(f"💾 Saved: {self.current_open_file_path.name} ({line_count} lines, {char_count} chars)")
                
                # Update insights
                self.update_agent_insights()
            except Exception as e:
                self.status_var.set(f"❌ Save error: {str(e)}")
        else:
            self.status_var.set("❌ No file open to save")

    def new_file(self):
        """Enhanced new file creation"""
        file_name = simpledialog.askstring(
            "📄 New File", 
            "Enter file name (relative to project):\nTip: Include extension (.py, .js, .html, etc.)"
        )
        if file_name:
            file_path = self.agent_system._safe_path(file_name) if hasattr(self, 'agent_system') else VM_DIR / file_name
            if file_path:
                try:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.touch()
                    self.refresh_files()
                    self.display_file(file_path)
                    self.status_var.set(f"✅ Created: {file_name}")
                    self.update_agent_insights()
                except Exception as e:
                    self.status_var.set(f"❌ Error: {str(e)}")

    def rename_file(self):
        """Enhanced file renaming"""
        selected = self.tree.selection()
        if not selected:
            return

        old_rel_path = Path(self.tree.item(selected[0], "values")[0])
        old_full_path = VM_DIR / old_rel_path

        new_name = simpledialog.askstring(
            "📝 Rename File", 
            f"Renaming: {old_rel_path.name}\nEnter new name:", 
            initialvalue=old_rel_path.name
        )

        if new_name:
            new_full_path = old_full_path.parent / new_name
            try:
                old_full_path.rename(new_full_path)
                if self.current_open_file_path and self.current_open_file_path == old_full_path:
                    self.current_open_file_path = new_full_path
                self.refresh_files()
                self.status_var.set(f"✅ Renamed: {old_rel_path.name} → {new_name}")
                self.update_agent_insights()
            except Exception as e:
                self.status_var.set(f"❌ Rename error: {str(e)}")

    def delete_file(self):
        """Enhanced file deletion"""
        selected = self.tree.selection()
        if not selected:
            return

        path_value = self.tree.item(selected[0], "values")[0]
        path_to_delete = Path(path_value)
        full_path_to_delete = VM_DIR / path_to_delete

        if messagebox.askyesno("🗑️ Confirm Deletion", f"Delete '{path_to_delete}'?\n\nThis action cannot be undone."):
            try:
                if full_path_to_delete.is_dir():
                    file_count = sum(1 for _ in full_path_to_delete.rglob('*') if _.is_file())
                    for p in reversed(list(full_path_to_delete.rglob('*'))):
                        if p.is_file():
                            p.unlink()
                        elif p.is_dir():
                            try:
                                p.rmdir()
                            except OSError:
                                pass
                    full_path_to_delete.rmdir()
                    self.status_var.set(f"✅ Deleted directory: {path_to_delete} ({file_count} files)")
                else:
                    file_size = full_path_to_delete.stat().st_size
                    full_path_to_delete.unlink()
                    self.status_var.set(f"✅ Deleted file: {path_to_delete} ({self._format_file_size(file_size)})")

                if self.current_open_file_path and self.current_open_file_path == full_path_to_delete:
                    self.editor.delete("1.0", tk.END)
                    self.current_open_file_path = None

                self.refresh_files()
                self.update_agent_insights()
            except Exception as e:
                self.status_var.set(f"❌ Delete error: {str(e)}")

    def clear_chat(self):
        """Enhanced chat clearing"""
        if messagebox.askyesno("🧹 Clear Chat", "Clear all chat history?\n\nThis will also reset agent conversation memory."):
            self.chat.config(state="normal")
            self.chat.delete("1.0", tk.END)
            self.chat.config(state="disabled")
            
            if hasattr(self, 'agent_system'):
                self.agent_system.conversation_history = []
                self.agent_system.error_context = []
            
            self.add_chat_message("🔄 System", "Chat history and agent memory cleared")

    def upload_screenshot(self):
        """Automatic screenshot capture and insertion"""
        try:
            import tempfile
            import subprocess
            import time
            import threading
            from tkinter import filedialog
            
            # Option 1: Auto-capture screenshot with Snipping Tool
            if messagebox.askyesno("📸 Screenshot Method", 
                                 "Choose screenshot method:\n\n" +
                                 "YES: Auto-capture with Snipping Tool\n" +
                                 "NO: Browse for existing image file"):
                
                self.status_var.set("📸 Starting screenshot capture...")
                self.screenshot_btn.config(state="disabled", text="📸 Capturing...")
                
                # Start screenshot capture in background thread
                threading.Thread(target=self._auto_capture_screenshot, daemon=True).start()
                
            else:
                # Option 2: Browse for existing file
                file_path = filedialog.askopenfilename(
                    title="Select Screenshot or Image",
                    filetypes=[
                        ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                        ("PNG files", "*.png"),
                        ("JPEG files", "*.jpg *.jpeg"),
                        ("All files", "*.*")
                    ]
                )
                
                if file_path:
                    self._process_uploaded_image(file_path)
                        
        except Exception as e:
            messagebox.showerror("❌ Screenshot Error", f"Screenshot functionality error: {str(e)}")
            self.screenshot_btn.config(state="normal", text="📸 Upload Screenshot")

    def _auto_capture_screenshot(self):
        """Automatically capture screenshot and save to project"""
        try:
            import tempfile
            import subprocess
            import time
            import io
            from PIL import ImageGrab
            
            # Method 1: Try using PIL ImageGrab with clipboard after snipping tool
            try:
                # Launch Windows 10 Snipping Tool with clipboard copy
                subprocess.run(["snippingtool", "/clip"], shell=True, timeout=2)
                
                # Give user time to take screenshot
                time.sleep(0.5)
                
                # Monitor clipboard for screenshot
                self._monitor_clipboard_for_screenshot()
                
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                # Fallback: Try alternative snipping tool launch
                try:
                    subprocess.run(["snippingtool"], shell=True, timeout=2)
                    time.sleep(0.5)
                    self._monitor_clipboard_for_screenshot()
                    
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    # Final fallback: Manual file selection
                    self.msg_queue.put({
                        "type": "screenshot_error", 
                        "content": "Could not launch screenshot tool. Please use file browser option."
                    })
                    
        except Exception as e:
            self.msg_queue.put({
                "type": "screenshot_error", 
                "content": f"Screenshot capture error: {str(e)}"
            })

    def _monitor_clipboard_for_screenshot(self):
        """Monitor clipboard for screenshot and auto-save"""
        import time
        from PIL import ImageGrab
        
        max_wait_time = 30  # Wait up to 30 seconds for screenshot
        check_interval = 0.5  # Check every 0.5 seconds
        checks = 0
        max_checks = int(max_wait_time / check_interval)
        
        # Show user instruction
        self.msg_queue.put({
            "type": "screenshot_info", 
            "content": "Take your screenshot now - it will auto-save when ready..."
        })
        
        while checks < max_checks:
            try:
                # Try to get image from clipboard
                clipboard_image = ImageGrab.grabclipboard()
                
                if clipboard_image is not None:
                    # Successfully captured screenshot from clipboard
                    timestamp = int(time.time())
                    filename = f"screenshot_{timestamp}.png"
                    filepath = VM_DIR / filename
                    
                    # Save the image
                    clipboard_image.save(filepath, "PNG")
                    
                    # Queue success message and processing
                    self.msg_queue.put({
                        "type": "screenshot_success", 
                        "content": filename
                    })
                    return
                    
                time.sleep(check_interval)
                checks += 1
                
            except Exception as e:
                self.msg_queue.put({
                    "type": "screenshot_error", 
                    "content": f"Clipboard monitoring error: {str(e)}"
                })
                return
        
        # Timeout reached
        self.msg_queue.put({
            "type": "screenshot_timeout", 
            "content": "Screenshot capture timed out. Please try again or use file browser."
        })

    def _process_uploaded_image(self, file_path):
        """Process uploaded image file"""
        try:
            import shutil
            
            # Generate filename with timestamp
            timestamp = int(time.time())
            original_name = os.path.basename(file_path)
            name_parts = os.path.splitext(original_name)
            filename = f"screenshot_{timestamp}{name_parts[1]}"
            destination = VM_DIR / filename
            
            # Copy file to project directory
            shutil.copy2(file_path, destination)
            
            # Process the image
            self._finalize_screenshot_processing(filename)
            
        except Exception as e:
            messagebox.showerror("❌ Upload Error", f"Failed to process image: {str(e)}")

    def _finalize_screenshot_processing(self, filename):
        """Finalize screenshot processing and add to chat"""
        try:
            # Refresh files and display image
            self.refresh_files()
            filepath = VM_DIR / filename
            self.display_enhanced_image(filepath)
            
            # Auto-insert analysis prompt into text box
            analysis_prompt = f"Please analyze this screenshot '{filename}' and describe what you see, including any UI elements, code, text, or design patterns. Provide detailed feedback and suggestions for improvement."
            
            # Clear and set input text
            self._clear_placeholder(None)
            self.input_txt.delete("1.0", tk.END)
            self.input_txt.insert("1.0", analysis_prompt)
            
            # Add to chat history
            self.add_chat_message("📸 Auto-Screenshot", f"Screenshot captured and saved as '{filename}' - analysis prompt ready!")
            
            # Update status
            self.status_var.set(f"✅ Screenshot ready: {filename}")
            
            # Focus on input box for user to send
            self.input_txt.focus()
            
        except Exception as e:
            self.status_var.set(f"❌ Screenshot processing error: {str(e)}")

    def _process_messages(self):
        """Enhanced message processing with screenshot handling"""
        try:
            while not self.msg_queue.empty():
                msg = self.msg_queue.get_nowait()

                if msg["type"] == "agent":
                    agent_name = msg["agent"]
                    agent_colors = {
                        "🤖 Main Coder": "#2E8B57",
                        "📊 Code Critic": "#FF6347",
                        "🎭 Art Critic": "#9370DB",
                        "✨ Prompt Enhancer": "#FFD700", # Gold color for enhancer
                        "🤝 Collaborative": "#4169E1"
                    }
                    color = agent_colors.get(agent_name, "#000000")
                    self.add_chat_message(agent_name, msg["content"], color)
                elif msg["type"] == "system":
                    self.add_chat_message("🔧 System", msg["content"], "#2E8B57")
                elif msg["type"] == "error":
                    self.add_chat_message("❌ Error", msg["content"], "#ff0000")
                elif msg["type"] == "screenshot_success":
                    filename = msg["content"]
                    self._finalize_screenshot_processing(filename)
                    self.screenshot_btn.config(state="normal", text="📸 Upload Screenshot")
                elif msg["type"] == "screenshot_error":
                    self.add_chat_message("❌ Screenshot Error", msg["content"], "#ff0000")
                    self.screenshot_btn.config(state="normal", text="📸 Upload Screenshot")
                elif msg["type"] == "screenshot_timeout":
                    self.add_chat_message("⏰ Screenshot Timeout", msg["content"], "#ff6600")
                    self.screenshot_btn.config(state="normal", text="📸 Upload Screenshot")
                elif msg["type"] == "screenshot_info":
                    self.status_var.set(msg["content"])
                elif msg["type"] == "file_changed":
                    self.refresh_files()
                    self.update_agent_insights()
                    changed_file_path = Path(msg["content"])
                    if changed_file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                        self.display_enhanced_image(changed_file_path)
                    elif self.current_open_file_path and self.current_open_file_path.samefile(changed_file_path):
                        self.display_file(self.current_open_file_path)
                elif msg["type"] == "done":
                    self.input_txt.config(state="normal")
                    self.send_btn.config(state="normal")
                    self.status_var.set("✅ Enhanced Multi-Agent System Ready")
                    # Reset agent status
                    self.main_status.config(foreground="green")
                    self.critic_status.config(foreground="green")
                    self.art_status.config(foreground="green")

        except queue.Empty:
            pass

        self.after(100, self._process_messages)

    def on_close(self):
        """Enhanced close handler"""
        if messagebox.askokcancel("🚪 Exit", "Exit Enhanced Multi-Agent IDE?\n\nUnsaved changes will be lost."):
            self.destroy()

# -----------------------------------------------------------------------------
# Application Entry Point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    VM_DIR.mkdir(exist_ok=True)
    app = EnhancedGeminiIDE()
    app.mainloop()
